import re
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_

from app.database import get_db
from app.models.scan_result import ScanResult
from app.schemas.scan import ScanResultOut
from app.api.deps import get_current_user

router = APIRouter(prefix="/search", tags=["搜索"])

_IP_RE = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")


@router.get("", response_model=list[ScanResultOut])
def search(
    q: str = Query(..., min_length=2, max_length=64),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # 智能搜索：完整 IP → 精确匹配
    if _IP_RE.match(q):
        results = (
            db.query(ScanResult)
            .options(joinedload(ScanResult.switch))
            .filter(ScanResult.ip_address == q)
            .order_by(ScanResult.id.desc())
            .limit(limit)
            .all()
        )
    else:
        results = (
            db.query(ScanResult)
            .options(joinedload(ScanResult.switch))
            .filter(
                or_(
                    ScanResult.ip_address.contains(q),
                    ScanResult.mac_address.contains(q),
                )
            )
            .order_by(ScanResult.id.desc())
            .limit(limit)
            .all()
        )
    out = []
    for r in results:
        d = ScanResultOut.model_validate(r).model_dump()
        if r.switch:
            d["switch_name"] = r.switch.name
            d["switch_ip"] = r.switch.ip_address
        out.append(d)
    return out
