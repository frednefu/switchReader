"""自动关联 — 解析 vm_folder 匹配部门。"""
import logging
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db
from app.api.deps import require_admin
from app.schemas.asset import AutoMatchPreview, AutoMatchResult, MatchPreviewItem

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/assets/auto-match", tags=["自动关联"])


def _seq_match(abbr: str, full: str) -> bool:
    """检查 abbr 的每个字符是否按序出现在 full 中。"""
    idx = 0
    for ch in abbr:
        idx = full.find(ch, idx)
        if idx == -1:
            return False
        idx += 1
    return True


def _extract_candidates(folder: str) -> list[tuple[str, str]]:
    """从文件夹路径中提取候选匹配项。
    返回 [(candidate, type), ...] 其中 type 为 'name' 或 'code'。
    格式如：'东北林业大学-OTHER_DEPT-123-宣传部' → [('123','code'), ('宣传部','name')]
    """
    candidates = []
    for seg in folder.split("/"):
        seg = seg.strip()
        if not seg:
            continue
        # 去掉 "东北林业大学-" 前缀
        for prefix in ["东北林业大学-", "东北林业大学－"]:
            if seg.startswith(prefix):
                seg = seg[len(prefix):]
                break
        # 按 '-' 分割
        for sub in seg.split("-"):
            sub = sub.strip()
            if not sub or len(sub) < 2:
                continue
            # 跳过泛化词
            skip = {"other_dept", "department", "dashboard", "datagovernance",
                    "datamiddleplatform", "vm", "server", "admin", "test", "dev"}
            if sub.lower() in skip:
                continue
            # 判断类型
            if sub.isdigit() and 3 <= len(sub) <= 6:
                candidates.append((sub, "code"))
            elif any('一' <= c <= '鿿' for c in sub):
                candidates.append((sub, "name"))
            elif len(sub) >= 3:
                candidates.append((sub, "code"))

    return candidates


def _match_folder_to_dept(db: Session, folder: str) -> tuple:
    """匹配文件夹到部门。优先按编码匹配，其次按名称匹配。"""
    if not folder:
        return None, None, None

    candidates = _extract_candidates(folder)
    if not candidates:
        return None, None, None

    depts = db.execute(text("SELECT id, dwmc, dwjc, dwbm FROM departments")).fetchall()
    # 构建编码查找表
    code_map = {}  # dwbm_suffix → [(full_dwbm, dept)]
    for d in depts:
        if d.dwbm:
            for suffix_len in [2, 3, 4, 5, 6]:
                if len(d.dwbm) >= suffix_len:
                    code_map.setdefault(d.dwbm[-suffix_len:], []).append(d)

    # 第一阶段：尝试编码匹配
    for val, typ in reversed(candidates):
        if typ == "code" and val in code_map:
            matches = code_map[val]
            if len(matches) == 1:
                return matches[0].id, matches[0].dwmc, val
            # 多个匹配时，用后续名称候选来验证
            for d in matches:
                # 找后面的 name 型候选来验证
                for v2, t2 in candidates:
                    if t2 == "name" and _seq_match(v2.lower(), (d.dwmc or "").lower()):
                        return d.id, d.dwmc, f"{val}+{v2}"
            # 没有名称验证，返回第一个
            return matches[0].id, matches[0].dwmc, val

    # 第二阶段：名称顺序匹配
    for val, typ in reversed(candidates):
        if typ == "name" and len(val) >= 2:
            # 精确匹配 dwjc
            for d in depts:
                if d.dwjc and d.dwjc.lower() == val.lower():
                    return d.id, d.dwmc, val
            # 顺序匹配 dwmc
            for d in depts:
                if _seq_match(val.lower(), (d.dwmc or "").lower()):
                    return d.id, d.dwmc, val
            # 精确匹配 dwbm
            for d in depts:
                if d.dwbm and d.dwbm.lower() == val.lower():
                    return d.id, d.dwmc, val

    return None, None, None


@router.get("/preview", response_model=AutoMatchPreview)
def preview_match(db: Session = Depends(get_db), _=Depends(require_admin)):
    vms = db.execute(text(
        "SELECT id, vm_name, vm_folder FROM vm_inventory "
        "WHERE (department_id IS NULL OR claim_status = 'unlinked') AND vm_folder IS NOT NULL AND vm_folder != ''"
    )).fetchall()

    items = []
    for v in vms:
        dept_id, dept_name, seg = _match_folder_to_dept(db, v.vm_folder)
        if dept_id:
            items.append(MatchPreviewItem(
                vm_id=v.id, vm_name=v.vm_name, vm_folder=v.vm_folder,
                matched_segment=seg, matched_dept_id=dept_id, matched_dept_name=dept_name,
            ))

    return AutoMatchPreview(items=items, total_vms=len(vms), matched_count=len(items))


@router.post("", response_model=AutoMatchResult)
def execute_match(db: Session = Depends(get_db), _=Depends(require_admin)):
    vms = db.execute(text(
        "SELECT id, vm_name, vm_folder FROM vm_inventory "
        "WHERE (department_id IS NULL OR claim_status = 'unlinked') AND vm_folder IS NOT NULL AND vm_folder != ''"
    )).fetchall()

    details = []
    matched = 0
    failed = 0
    for v in vms:
        dept_id, dept_name, seg = _match_folder_to_dept(db, v.vm_folder)
        if dept_id:
            try:
                db.execute(text(
                    "UPDATE vm_inventory SET department_id = :did, claim_status = 'auto', "
                    "claimed_at = NOW() WHERE id = :vid"
                ), {"did": dept_id, "vid": v.id})
                db.commit()
                matched += 1
                details.append({"vm_name": v.vm_name, "folder": v.vm_folder, "dept": dept_name, "status": "success"})
            except Exception as e:
                failed += 1
                details.append({"vm_name": v.vm_name, "folder": v.vm_folder, "dept": dept_name, "status": f"error: {e}"})
                db.rollback()

    logger.info(f"自动匹配完成：共 {len(vms)} VM，匹配 {matched}，失败 {failed}")
    return AutoMatchResult(total_vms=len(vms), matched=matched, failed=failed, details=details)
