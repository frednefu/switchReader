from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
import re
from math import ceil

from app.database import get_db
from app.models.scan_result import ScanResult
from app.models.route_table import RouteTable
from app.models.switch import Switch
from app.schemas.scan import ScanResultOut, RouteTableOut, PaginatedResponse
from app.api.deps import get_current_user
from app.utils.export import export_to_excel

_IP_RE = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")

router = APIRouter(prefix="/results", tags=["扫描结果"])


def _latest_ids_subquery(db):
    """获取每个 (IP, MAC, switch_id) 组合中最新的 scan_result id。"""
    return (
        db.query(func.max(ScanResult.id).label("max_id"))
        .group_by(ScanResult.ip_address, ScanResult.mac_address, ScanResult.switch_id)
        .subquery()
    )


def _enrich_result(row: ScanResult) -> dict:
    d = ScanResultOut.model_validate(row).model_dump()
    if row.switch:
        d["switch_name"] = row.switch.name
        d["switch_ip"] = row.switch.ip_address
    return d


def _enrich_route(row: RouteTable) -> dict:
    d = RouteTableOut.model_validate(row).model_dump()
    if row.switch:
        d["switch_name"] = row.switch.name
        d["switch_ip"] = row.switch.ip_address
    return d


@router.get("", response_model=PaginatedResponse)
def list_results(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    switch_id: int = Query(None),
    mac: str = Query("", max_length=17),
    ip: str = Query("", max_length=45),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # 只查询每个 (IP, MAC, switch) 组合中最新的记录
    latest = _latest_ids_subquery(db)
    base = db.query(ScanResult).filter(
        ScanResult.id.in_(db.query(latest.c.max_id))
    )
    if switch_id:
        base = base.filter(ScanResult.switch_id == switch_id)
    if mac:
        base = base.filter(ScanResult.mac_address.contains(mac))
    if ip:
        if _IP_RE.match(ip):
            base = base.filter(ScanResult.ip_address == ip)
        else:
            base = base.filter(ScanResult.ip_address.contains(ip))
    total = base.count()
    pages = ceil(total / size) if total > 0 else 0
    items = (
        base.options(joinedload(ScanResult.switch))
        .order_by(ScanResult.id.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    return PaginatedResponse(
        items=[_enrich_result(r) for r in items],
        total=total, page=page, size=size, pages=pages,
    )


@router.get("/routes", response_model=PaginatedResponse)
def list_routes(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    switch_id: int = Query(None),
    cidr: str = Query("", max_length=49),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    base = db.query(RouteTable)
    if switch_id:
        base = base.filter(RouteTable.switch_id == switch_id)
    if cidr:
        base = base.filter(RouteTable.cidr.contains(cidr))
    total = base.count()
    pages = ceil(total / size) if total > 0 else 0
    items = (
        base.options(joinedload(RouteTable.switch))
        .order_by(RouteTable.id.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    return PaginatedResponse(
        items=[_enrich_route(r) for r in items],
        total=total, page=page, size=size, pages=pages,
    )


@router.get("/export")
def export_results(
    switch_id: int = Query(None),
    mac: str = Query("", max_length=17),
    ip: str = Query("", max_length=45),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    latest = _latest_ids_subquery(db)
    base = db.query(ScanResult).filter(
        ScanResult.id.in_(db.query(latest.c.max_id))
    )
    if switch_id:
        base = base.filter(ScanResult.switch_id == switch_id)
    if mac:
        base = base.filter(ScanResult.mac_address.contains(mac))
    if ip:
        if _IP_RE.match(ip):
            base = base.filter(ScanResult.ip_address == ip)
        else:
            base = base.filter(ScanResult.ip_address.contains(ip))
    items = base.options(joinedload(ScanResult.switch)).order_by(ScanResult.id.desc()).all()
    enriched = [_enrich_result(r) for r in items]
    headers = ["交换机名称", "交换机IP", "IP地址", "MAC地址", "VLAN/BD", "VLAN类型", "物理端口", "虚拟端口", "交换机类型", "采集时间"]
    xls_rows = [[
        r.get("switch_name", ""), r.get("switch_ip", ""),
        r.get("ip_address", ""), r.get("mac_address", ""),
        r.get("vlan_bd", ""), r.get("vlan_type", ""),
        r.get("physical_port", ""), r.get("virtual_port", ""),
        r.get("switch_type", ""),
        r.get("created_at", "").strftime("%Y-%m-%d %H:%M:%S") if r.get("created_at") else "",
    ] for r in enriched]
    return export_to_excel(headers, xls_rows, "scan_results.xlsx", sheet_title="扫描结果")
