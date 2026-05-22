"""ZDNS 域名服务器管理 API — CRUD + 扫描 + 数据查询。"""
from math import ceil
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.zdns import ZDNSDevice, ZDNSRecord, ZDNSDomainMap
from app.schemas.zdns import (
    ZDNSDeviceCreate, ZDNSDeviceUpdate, ZDNSDeviceOut,
    ZDNSTestRequest, ZDNSTestResponse,
    ZDNSRecordOut, ZDNSDomainMapOut,
)
from app.schemas.scan import PaginatedResponse
from app.api.deps import get_current_user, require_admin
from app.services.zdns_scanner_service import trigger_zdns_scan, test_zdns_connection
from app.services.scheduler_service import refresh_zdns_job

router = APIRouter(prefix="/zdns", tags=["ZDNS"])


# ─── 静态路由（必须在 /{device_id} 之前） ───

@router.post("/test", response_model=ZDNSTestResponse)
async def test_connection(
    body: ZDNSTestRequest,
    current_user=Depends(get_current_user),
):
    result = await test_zdns_connection(body.host, body.username, body.password, body.port)
    return result


@router.post("/scan-all")
async def scan_all(
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    devices = db.query(ZDNSDevice).filter(ZDNSDevice.is_active == True).all()
    if not devices:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="没有可扫描的 ZDNS 设备")
    started = 0
    skipped = 0
    for dev in devices:
        if dev.last_scan_status == "running":
            skipped += 1
            continue
        await trigger_zdns_scan(dev)
        started += 1
    return {"message": f"已触发 {started} 个 ZDNS 扫描" + (f"，{skipped} 个正在扫描中跳过" if skipped else ""),
            "started": started, "skipped": skipped}


@router.delete("/all")
def delete_all(
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    count = db.query(ZDNSDevice).count()
    if count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="没有可删除的 ZDNS 设备")
    for dev in db.query(ZDNSDevice).all():
        refresh_zdns_job(dev.id, 0)
    db.query(ZDNSDevice).delete()
    db.commit()
    return {"message": f"已删除 {count} 个 ZDNS 设备及关联数据", "deleted": count}


# ─── 列表 ───

@router.get("")
def list_devices(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=500),
    search: str = Query("", max_length=128),
    is_active: bool = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    q = db.query(ZDNSDevice)
    if search:
        q = q.filter(
            (ZDNSDevice.name.contains(search)) | (ZDNSDevice.host.contains(search))
        )
    if is_active is not None:
        q = q.filter(ZDNSDevice.is_active == is_active)
    total = q.count()
    pages = ceil(total / size) if total > 0 else 0
    items = q.order_by(ZDNSDevice.id).offset((page - 1) * size).limit(size).all()
    return PaginatedResponse(
        items=[ZDNSDeviceOut.model_validate(dev) for dev in items],
        total=total, page=page, size=size, pages=pages,
    )


# ─── 创建 ───

@router.post("", response_model=ZDNSDeviceOut)
def create_device(
    body: ZDNSDeviceCreate,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    existing = db.query(ZDNSDevice).filter(ZDNSDevice.host == body.host).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="ZDNS 主机地址已存在")
    dev = ZDNSDevice(**body.model_dump(), created_by=admin.id)
    db.add(dev)
    db.commit()
    db.refresh(dev)
    if dev.is_active and dev.scan_interval > 0:
        refresh_zdns_job(dev.id, dev.scan_interval)
    return ZDNSDeviceOut.model_validate(dev)


# ─── 获取详情 ───

@router.get("/{device_id}", response_model=ZDNSDeviceOut)
def get_device(
    device_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    dev = db.query(ZDNSDevice).get(device_id)
    if not dev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ZDNS 设备不存在")
    return ZDNSDeviceOut.model_validate(dev)


# ─── 更新 ───

@router.put("/{device_id}", response_model=ZDNSDeviceOut)
def update_device(
    device_id: int,
    body: ZDNSDeviceUpdate,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    dev = db.query(ZDNSDevice).get(device_id)
    if not dev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ZDNS 设备不存在")
    for key, val in body.model_dump(exclude_unset=True).items():
        setattr(dev, key, val)
    db.commit()
    db.refresh(dev)
    refresh_zdns_job(dev.id, dev.scan_interval if dev.is_active else 0)
    return ZDNSDeviceOut.model_validate(dev)


# ─── 删除 ───

@router.delete("/{device_id}")
def delete_device(
    device_id: int,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    dev = db.query(ZDNSDevice).get(device_id)
    if not dev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ZDNS 设备不存在")
    refresh_zdns_job(device_id, 0)
    db.delete(dev)
    db.commit()
    return {"message": "ZDNS 设备已删除"}


# ─── 触发扫描 ───

@router.post("/{device_id}/scan")
async def trigger_scan(
    device_id: int,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    dev = db.query(ZDNSDevice).get(device_id)
    if not dev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ZDNS 设备不存在")
    if dev.last_scan_status == "running":
        dev.last_scan_status = None
        dev.last_scan_error = None
        db.commit()
    scan_log_id = await trigger_zdns_scan(dev)
    return {"message": "扫描已触发", "scan_log_id": scan_log_id}


# ─── DNS 记录清单 ───

@router.get("/{device_id}/records")
def list_records(
    device_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=500),
    search: str = Query("", max_length=256),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    dev = db.query(ZDNSDevice).get(device_id)
    if not dev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ZDNS 设备不存在")
    q = db.query(ZDNSRecord).filter(ZDNSRecord.zdns_device_id == device_id)
    if search:
        q = q.filter(
            (ZDNSRecord.name.contains(search)) |
            (ZDNSRecord.full_domain.contains(search)) |
            (ZDNSRecord.record_type.contains(search)) |
            (ZDNSRecord.rdata.contains(search))
        )
    total = q.count()
    pages = ceil(total / size) if total > 0 else 0
    items = q.order_by(ZDNSRecord.id).offset((page - 1) * size).limit(size).all()
    return PaginatedResponse(
        items=[ZDNSRecordOut.model_validate(r) for r in items],
        total=total, page=page, size=size, pages=pages,
    )


# ─── 域名映射清单（核心交付物） ───

@router.get("/{device_id}/domain-map")
def list_domain_map(
    device_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=500),
    search: str = Query("", max_length=256),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    dev = db.query(ZDNSDevice).get(device_id)
    if not dev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ZDNS 设备不存在")
    q = db.query(ZDNSDomainMap).filter(ZDNSDomainMap.zdns_device_id == device_id)
    if search:
        q = q.filter(
            (ZDNSDomainMap.domain_name.contains(search)) |
            (ZDNSDomainMap.ip_address.contains(search)) |
            (ZDNSDomainMap.view_name.contains(search)) |
            (ZDNSDomainMap.zone_name.contains(search))
        )
    total = q.count()
    pages = ceil(total / size) if total > 0 else 0
    items = q.order_by(ZDNSDomainMap.id).offset((page - 1) * size).limit(size).all()
    return PaginatedResponse(
        items=[ZDNSDomainMapOut.model_validate(r) for r in items],
        total=total, page=page, size=size, pages=pages,
    )
