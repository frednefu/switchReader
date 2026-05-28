"""教职工信息查询 — 对接外部 API 查询教职工基本信息。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.staff_info import StaffInfo
from app.models.department import Department
from app.schemas.department import StaffLookupRequest, StaffLookupResponse, StaffInfoOut
from app.api.deps import require_admin
from app.services import external_api_service

router = APIRouter(prefix="/sys/staff", tags=["教职工"])


def _resolve_department(db: Session, szdwbm: str) -> tuple:
    """根据单位编码查找部门名称和 ID。"""
    if not szdwbm:
        return None, None
    dept = db.query(Department).filter(Department.dwbm == szdwbm).first()
    if dept:
        return dept.dwmc, dept.id
    return None, None


def _staff_to_out(db: Session, staff: StaffInfo) -> StaffInfoOut:
    """将 StaffInfo 转为 StaffInfoOut，附加部门名称和 ID。"""
    dept_name, dept_id = _resolve_department(db, staff.szdwbm)
    out = StaffInfoOut.model_validate(staff)
    out.department_name = dept_name
    out.department_id = dept_id
    return out


def _sync_staff(db: Session, raw: dict) -> StaffInfo:
    """将外部 API 返回的教职工数据同步到本地。"""
    gh = raw.get("GH", "").strip()
    if not gh:
        raise ValueError("工号为空，无法同步")
    staff = db.query(StaffInfo).filter(StaffInfo.gh == gh).first()
    if not staff:
        staff = StaffInfo(gh=gh)
        db.add(staff)

    staff.xm = raw.get("XM", "")
    staff.szdwbm = raw.get("SZDWBM")
    staff.szks = raw.get("SZKS")
    staff.xbm = raw.get("XBM")
    staff.bgdh = raw.get("BGDH")
    staff.yddh = raw.get("YDDH")
    staff.dzyx = raw.get("DZYX")
    db.commit()
    db.refresh(staff)

    # 同步关联的部门（如果本地还没有）
    szdwbm = raw.get("SZDWBM", "").strip()
    if szdwbm:
        dept = db.query(Department).filter(Department.dwbm == szdwbm).first()
        if not dept:
            dept = Department(dwbm=szdwbm, dwmc=szdwbm)
            db.add(dept)
            db.commit()
            db.refresh(dept)

    return staff


@router.post("/lookup", response_model=StaffLookupResponse)
def lookup_staff(body: StaffLookupRequest, db: Session = Depends(get_db), _=Depends(require_admin)):
    """按工号和/或姓名查询教职工（OR 模糊匹配）。返回匹配列表。"""
    if not body.gh and not body.xm:
        return StaffLookupResponse(found=False, message="请至少输入工号或姓名")

    # 先查本地缓存 — 模糊匹配
    local_query = db.query(StaffInfo)
    if body.gh:
        local_query = local_query.filter(StaffInfo.gh.contains(body.gh))
    if body.xm:
        local_query = local_query.filter(StaffInfo.xm.contains(body.xm))
    local_results = local_query.limit(50).all()
    if local_results:
        return StaffLookupResponse(
            found=True,
            staff_list=[_staff_to_out(db, s) for s in local_results],
            message=f"本地缓存匹配到 {len(local_results)} 人",
        )

    # 调用外部 API
    try:
        items = external_api_service.fetch_staff(db, gh=body.gh or "", xm=body.xm or "")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询外部 API 失败：{e}")

    if not items:
        return StaffLookupResponse(found=False, message="未找到匹配的教职工")

    # 批量同步到本地
    synced = []
    for item in items:
        try:
            staff = _sync_staff(db, item)
            synced.append(_staff_to_out(db, staff))
        except ValueError:
            continue

    return StaffLookupResponse(
        found=True,
        staff_list=synced,
        message=f"查询成功，匹配到 {len(synced)} 人",
    )
