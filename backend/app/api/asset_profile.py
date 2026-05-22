"""资产画像 API — 跨系统数据关联统一视图。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.asset_profile import AssetProfileResponse, AssetProfileStats, AssetProfileRow
from app.services.asset_profile_service import build_asset_profile, compute_stats, filter_sort_paginate
from app.api.deps import get_current_user

router = APIRouter(prefix="/asset-profile", tags=["资产画像"])

# 缓存数据（在请求间重用，需要手动刷新）
_profile_cache: list[dict] | None = None


def _get_cached_profile(db: Session) -> list[dict]:
    """获取缓存的资产画像数据。每次请求重新构建以保证数据最新。"""
    global _profile_cache
    # 每次请求都重建，保证数据实时性
    _profile_cache = build_asset_profile(db)
    return _profile_cache


@router.get("", response_model=AssetProfileResponse)
def get_asset_profile(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    search: str = Query("", description="全局搜索（匹配所有字段）"),
    sort_by: str = Query("", description="排序字段名（如：公网IP、虚拟机名称 等）"),
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    rows = _get_cached_profile(db)
    stats = compute_stats(rows)
    result = filter_sort_paginate(rows, search=search, sort_by=sort_by, sort_dir=sort_dir, page=page, size=size)

    return AssetProfileResponse(
        rows=[AssetProfileRow(**r) for r in result["rows"]],
        total=result["total"],
        page=result["page"],
        size=result["size"],
        stats=AssetProfileStats(**stats),
    )
