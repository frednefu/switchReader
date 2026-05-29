"""资产认领 + 管理员指派。"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db
from app.models.user import User
from app.api.deps import get_current_user, require_admin
from app.schemas.asset import ClaimRequest, AssignRequest

router = APIRouter(prefix="/assets", tags=["资产认领"])


@router.post("/claim")
def claim_assets(
    body: ClaimRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """认领资产到本部门。管理员可选择目标部门。"""
    is_admin = current_user.role.value == "admin" if hasattr(current_user.role, "value") else current_user.role == "admin"

    dept_id = body.department_id if is_admin and body.department_id else current_user.department_id
    if not dept_id:
        raise HTTPException(status_code=400, detail="您没有所属部门，无法认领资产。请联系管理员指派。")

    if not body.vm_ids:
        raise HTTPException(status_code=400, detail="请选择要认领的资产")

    claimed = 0
    for vid in body.vm_ids:
        db.execute(text(
            "UPDATE vm_inventory SET department_id = COALESCE(department_id, :did), "
            "owner_user_id = :uid, claimed_by = :uid, claimed_at = NOW() "
            "WHERE id = :vid"
        ), {"did": dept_id, "uid": current_user.id, "vid": vid})
        claimed += 1
    db.commit()
    return {"message": f"成功认领 {claimed} 个资产", "claimed": claimed}


@router.post("/assign")
def assign_assets(
    body: AssignRequest,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    """管理员指派资产到部门或具体用户。"""
    if not body.vm_ids:
        raise HTTPException(status_code=400, detail="请选择要指派的资产")
    if not body.department_id and not body.user_id:
        raise HTTPException(status_code=400, detail="请指定目标部门或用户")

    assigned = 0
    for vid in body.vm_ids:
        params = {"vid": vid, "did": body.department_id, "uid": body.user_id}
        if body.department_id and body.user_id:
            db.execute(text(
                "UPDATE vm_inventory SET department_id = :did, owner_user_id = :uid, "
                "claim_status = 'manual', claimed_by = :uid, claimed_at = NOW() WHERE id = :vid"
            ), params)
        elif body.department_id:
            db.execute(text(
                "UPDATE vm_inventory SET department_id = :did, claim_status = 'manual', "
                "claimed_at = NOW() WHERE id = :vid"
            ), params)
        elif body.user_id:
            db.execute(text(
                "UPDATE vm_inventory SET owner_user_id = :uid, claim_status = 'manual', "
                "claimed_by = :uid, claimed_at = NOW() WHERE id = :vid"
            ), params)
        assigned += 1
    db.commit()
    return {"message": f"成功指派 {assigned} 个资产", "assigned": assigned}


@router.post("/revoke")
def revoke_assets(
    body: ClaimRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """撤销认领：清空选中资产的负责人和部门归属。"""
    if not body.vm_ids:
        raise HTTPException(status_code=400, detail="请选择要撤销的资产")

    revoked = 0
    for vid in body.vm_ids:
        db.execute(text(
            "UPDATE vm_inventory SET owner_user_id = NULL, claimed_by = NULL, claimed_at = NULL WHERE id = :vid"
        ), {"vid": vid})
        revoked += 1
    db.commit()
    return {"message": f"成功撤销 {revoked} 个资产认领", "revoked": revoked}


@router.post("/reset-all")
def reset_all_assets(
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    """重置所有关联数据：清空所有 VM 的部门、负责人、认领状态。"""
    result = db.execute(text(
        "UPDATE vm_inventory SET department_id = NULL, owner_user_id = NULL, "
        "claim_status = 'unlinked', claimed_by = NULL, claimed_at = NULL"
    ))
    db.commit()
    return {"message": f"已重置 {result.rowcount} 条资产关联数据", "count": result.rowcount}
