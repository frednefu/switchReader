"""信息资产管理 — 部门资产查询、未关联资产、搜索。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/assets", tags=["信息资产管理"])


def _should_skip_domain(name: str) -> bool:
    """排除 in-addr.arpa 等反向解析域名。"""
    if not name:
        return True
    return ".in-addr.arpa" in name.lower()


def _collect_domains(db: Session, linked_ips: set = None) -> list[dict]:
    """收集 ZDNS + F5 域名，去重合并，排除反向解析。"""
    seen = {}
    zdns_rows = db.execute(text(
        "SELECT domain_name, record_type, ip_address FROM zdns_domain_map"
    )).fetchall()
    for r in zdns_rows:
        name = (r.domain_name or "").strip()
        if _should_skip_domain(name):
            continue
        if linked_ips is not None and (r.ip_address or "").strip() in linked_ips:
            continue
        key = name.lower()
        if key not in seen:
            seen[key] = {"domain_name": name, "record_type": r.record_type,
                         "ip_address": r.ip_address, "source": "ZDNS", "vm_name": None, "vm_id": None}
    f5_rows = db.execute(text(
        "SELECT domain_name, vs_ip FROM f5_application_map WHERE domain_name IS NOT NULL AND domain_name != ''"
    )).fetchall()
    for r in f5_rows:
        name = (r.domain_name or "").strip()
        if _should_skip_domain(name):
            continue
        if linked_ips is not None and (r.vs_ip or "").strip() in linked_ips:
            continue
        key = name.lower()
        if key not in seen:
            seen[key] = {"domain_name": name, "record_type": None,
                         "ip_address": r.vs_ip, "source": "F5", "vm_name": None, "vm_id": None}
    return list(seen.values())


@router.get("/vm-filters")
def get_vm_filters(db: Session = Depends(get_db), _=Depends(get_current_user)):
    """获取 VM 筛选选项。"""
    power_states = db.execute(text(
        "SELECT DISTINCT power_state FROM vm_inventory WHERE power_state IS NOT NULL AND power_state != ''"
    )).fetchall()
    os_names = db.execute(text(
        "SELECT DISTINCT os_name FROM vm_inventory WHERE os_name IS NOT NULL AND os_name != ''"
    )).fetchall()
    networks = db.execute(text(
        "SELECT DISTINCT network_name FROM vm_inventory WHERE network_name IS NOT NULL AND network_name != ''"
    )).fetchall()
    folders = db.execute(text(
        "SELECT DISTINCT vm_folder FROM vm_inventory WHERE vm_folder IS NOT NULL AND vm_folder != ''"
    )).fetchall()
    return {
        "power_states": [r.power_state for r in power_states],
        "os_names": [r.os_name for r in os_names],
        "networks": [r.network_name for r in networks],
        "folders": [r.vm_folder for r in folders],
    }


@router.get("/tree")
def get_asset_tree(db: Session = Depends(get_db), _=Depends(get_current_user)):
    """获取组织树，统计每个部门的资产数量（VM+关联域名）。"""
    # VM 按部门统计
    vm_counts = {}
    dept_ips = {}  # department_id → set of IPs
    vm_rows = db.execute(text(
        "SELECT department_id, ip_address FROM vm_inventory "
        "WHERE department_id IS NOT NULL AND claim_status != 'unlinked'"
    )).fetchall()
    for r in vm_rows:
        vm_counts[r.department_id] = vm_counts.get(r.department_id, 0) + 1
        if r.department_id not in dept_ips:
            dept_ips[r.department_id] = set()
        for ip in (r.ip_address or "").split(","):
            ip = ip.strip()
            if ip:
                dept_ips[r.department_id].add(ip)

    # 按部门统计域名（去重，排除 in-addr.arpa）
    domain_counts = {}
    zdns_seen = {}
    f5_seen = {}
    zdns_rows = db.execute(text("SELECT DISTINCT domain_name, ip_address FROM zdns_domain_map")).fetchall()
    f5_rows = db.execute(text(
        "SELECT DISTINCT domain_name, vs_ip FROM f5_application_map WHERE domain_name IS NOT NULL AND domain_name != ''"
    )).fetchall()
    for r in zdns_rows:
        name = (r.domain_name or "").strip()
        if _should_skip_domain(name):
            continue
        ip = (r.ip_address or "").strip()
        if ip and name not in zdns_seen:
            zdns_seen[name] = ip
            for did, ips in dept_ips.items():
                if ip in ips:
                    domain_counts[did] = domain_counts.get(did, 0) + 1
                    break
    for r in f5_rows:
        name = (r.domain_name or "").strip()
        if _should_skip_domain(name):
            continue
        ip = (r.vs_ip or "").strip()
        if ip and name not in f5_seen:
            f5_seen[name] = ip
            for did, ips in dept_ips.items():
                if ip in ips:
                    domain_counts[did] = domain_counts.get(did, 0) + 1
                    break

    # 部门列表
    depts = db.execute(text("SELECT id, dwmc, dwjc, dwbm, lsdwh, pxh FROM departments")).fetchall()

    # 未关联统计（按域名+来源去重）
    unlinked_vms = db.execute(text(
        "SELECT COUNT(*) FROM vm_inventory WHERE department_id IS NULL OR claim_status = 'unlinked'"
    )).scalar() or 0
    linked_ips = set()
    for ips in dept_ips.values():
        linked_ips.update(ips)
    unlinked_zdns = sum(1 for d, ip in zdns_seen.items() if not _should_skip_domain(d) and ip not in linked_ips)
    unlinked_f5 = sum(1 for d, ip in f5_seen.items() if not _should_skip_domain(d) and ip not in linked_ips)
    unlinked_domains = unlinked_zdns + unlinked_f5

    # 构建树
    children_by_parent = {}
    for d in depts:
        key = d.lsdwh if d.lsdwh else "__root__"
        if key not in children_by_parent:
            children_by_parent[key] = []
        children_by_parent[key].append(d)

    def make_node(d):
        vc = vm_counts.get(d.id, 0)
        dc = domain_counts.get(d.id, 0)
        kids = [make_node(c) for c in children_by_parent.get(d.dwbm, [])]
        tv = vc + sum(k["vm_count"] for k in kids)
        td = dc + sum(k["domain_count"] for k in kids)
        return {"id": d.id, "label": d.dwmc or d.dwjc or d.dwbm,
                "vm_count": tv, "domain_count": td, "system_count": 0,
                "count": tv + td, "children": kids}

    roots = [make_node(d) for d in children_by_parent.get("__root__", [])]
    roots.sort(key=lambda n: n["label"])
    roots.append({"id": -1, "label": "未关联资产",
                  "vm_count": unlinked_vms, "domain_count": unlinked_domains, "system_count": 0,
                  "count": unlinked_vms + unlinked_domains, "children": []})
    return {"nodes": roots}


def _enrich_vms(db: Session, vm_rows: list) -> list[dict]:
    """增强 VM 数据：椒图 OS、F5 公网IP/域名、交换机 MAC→IP。"""
    if not vm_rows:
        return []

    # 收集 IPv4
    vm_ips = set()
    for r in vm_rows:
        for ip in (r.ip_address or "").split(","):
            ip = ip.strip()
            if ip and ":" not in ip:
                vm_ips.add(ip)

    # 椒图 OS
    qax_os = {}
    ip_list = list(vm_ips)
    for i in range(0, len(ip_list), 30):
        batch = ip_list[i:i + 30]
        quoted = ",".join([f"'{ip}'" for ip in batch])
        try:
            rows = db.execute(text(f"SELECT ipv4, os_name FROM qax_servers WHERE ipv4 IN ({quoted})")).fetchall()
            for qr in rows:
                if qr.os_name and qr.ipv4:
                    qax_os[qr.ipv4.strip()] = qr.os_name
        except Exception:
            pass

    # F5 映射
    f5_data = {}
    try:
        rows = db.execute(text(
            "SELECT member_ip, vs_ip, domain_name FROM f5_application_map WHERE member_ip IS NOT NULL AND member_ip != ''"
        )).fetchall()
        for r in rows:
            key = r.member_ip.strip() if r.member_ip else ""
            if key and key not in f5_data:
                f5_data[key] = []
            if key:
                f5_data[key].append({"public_ip": r.vs_ip, "domain": r.domain_name})
    except Exception:
        pass

    # 交换机 MAC→IP
    switch_mac_ip = {}
    try:
        rows = db.execute(text(
            "SELECT mac_address, ip_address FROM scan_results WHERE mac_address IS NOT NULL AND mac_address != ''"
        )).fetchall()
        for r in rows:
            for mac in (r.mac_address or "").split(","):
                mac = mac.strip().lower()
                if mac and mac not in switch_mac_ip:
                    switch_mac_ip[mac] = r.ip_address
    except Exception:
        pass

    # 组装
    items = []
    for r in vm_rows:
        vm_ips_r = [ip.strip() for ip in (r.ip_address or "").split(",") if ip.strip()]
        vm_macs = [mac.strip().lower() for mac in (r.mac_address or "").split(",") if mac.strip()]

        os_name = r.os_name or ""
        for ip in vm_ips_r:
            if ip in qax_os:
                os_name = qax_os[ip]
                break

        f5_ips, f5_doms = set(), set()
        for ip in vm_ips_r:
            if ip in f5_data:
                for e in f5_data[ip]:
                    if e["public_ip"]: f5_ips.add(e["public_ip"])
                    if e["domain"]: f5_doms.add(e["domain"])

        sw_ips = set()
        for mac in vm_macs:
            if mac in switch_mac_ip:
                sw_ips.add(switch_mac_ip[mac])

        items.append({
            "id": r.id, "vm_name": r.vm_name,
            "ip_address": r.ip_address, "mac_address": r.mac_address,
            "vm_folder": r.vm_folder, "os_name": os_name,
            "power_state": r.power_state,
            "cpu_count": r.cpu_count, "memory_gb": r.memory_gb,
            "network_name": r.network_name,
            "department_id": r.department_id,
            "department_name": r.dept_name if hasattr(r, "dept_name") else None,
            "owner_user_id": r.owner_user_id,
            "owner_name": r.owner_name if hasattr(r, "owner_name") else None,
            "claim_status": r.claim_status or "unlinked",
            "claimed_at": r.claimed_at.isoformat() if hasattr(r, "claimed_at") and r.claimed_at else None,
            "f5_public_ips": ",".join(f5_ips) if f5_ips else "",
            "f5_domains": ",".join(f5_doms) if f5_doms else "",
            "switch_ips": ",".join(sw_ips) if sw_ips else "",
        })
    return items


@router.get("/departments/{dept_id}/vms")
def get_dept_vms(
    dept_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str = Query("", max_length=128),
    power_state: str = Query("", max_length=32),
    os_name: str = Query("", max_length=128),
    network_name: str = Query("", max_length=256),
    vm_folder: str = Query("", max_length=256),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    if dept_id == 0:
        q = db.execute(text(
            "SELECT v.*, d.dwmc as dept_name, u.name as owner_name FROM vm_inventory v "
            "LEFT JOIN departments d ON v.department_id = d.id "
            "LEFT JOIN users u ON v.owner_user_id = u.id "
            "WHERE v.department_id IS NULL OR v.claim_status = 'unlinked'"
        ))
    else:
        q = db.execute(text(
            "SELECT v.*, d.dwmc as dept_name, u.name as owner_name FROM vm_inventory v "
            "LEFT JOIN departments d ON v.department_id = d.id "
            "LEFT JOIN users u ON v.owner_user_id = u.id "
            "WHERE v.department_id = :did"
        ), {"did": dept_id})

    rows = q.fetchall()
    all_items = _enrich_vms(db, rows)
    if search:
        kw = search.lower()
        all_items = [it for it in all_items
                     if kw in (it["vm_name"] or "").lower()
                     or kw in (it["ip_address"] or "").lower()
                     or kw in (it["f5_domains"] or "").lower()]
    if power_state:
        all_items = [it for it in all_items if (it["power_state"] or "") == power_state]
    if os_name:
        all_items = [it for it in all_items if os_name.lower() in (it["os_name"] or "").lower()]
    if network_name:
        all_items = [it for it in all_items if network_name.lower() in (it["network_name"] or "").lower()]
    if vm_folder:
        all_items = [it for it in all_items if vm_folder.lower() in (it["vm_folder"] or "").lower()]

    total = len(all_items)
    start = (page - 1) * size
    return {"items": all_items[start:start + size], "total": total, "page": page, "size": size}


@router.get("/departments/{dept_id}/domains")
def get_dept_domains(
    dept_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    search: str = Query("", max_length=256),
    record_type: str = Query("", max_length=32),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    if dept_id == 0:
        linked_ips = set()
        linked_rows = db.execute(text(
            "SELECT ip_address FROM vm_inventory WHERE department_id IS NOT NULL AND claim_status != 'unlinked'"
        )).fetchall()
        for r in linked_rows:
            for ip in (r.ip_address or "").split(","):
                ip = ip.strip()
                if ip:
                    linked_ips.add(ip)
        results = _collect_domains(db, linked_ips)
    else:
        vm_rows = db.execute(text(
            "SELECT ip_address, vm_name, id FROM vm_inventory WHERE department_id = :did"
        ), {"did": dept_id}).fetchall()
        vm_ips = set()
        vm_by_ip = {}
        for r in vm_rows:
            for ip in (r.ip_address or "").split(","):
                ip = ip.strip()
                if ip:
                    vm_ips.add(ip)
                    vm_by_ip[ip] = (r.vm_name, r.id)
        all_domains = _collect_domains(db)
        results = []
        for d in all_domains:
            if d["ip_address"] and d["ip_address"].strip() in vm_ips:
                ip = d["ip_address"].strip()
                d["vm_name"] = vm_by_ip[ip][0]
                d["vm_id"] = vm_by_ip[ip][1]
                results.append(d)

    if search:
        kw = search.lower()
        results = [d for d in results if kw in d["domain_name"].lower() or kw in (d["ip_address"] or "").lower()]
    if record_type:
        results = [d for d in results if (d["record_type"] or "") == record_type]

    total = len(results)
    start = (page - 1) * size
    return {"items": results[start:start + size], "total": total, "page": page, "size": size}


@router.get("/search")
def search_assets(
    keyword: str = Query("", max_length=256),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    results = []
    kw = keyword.strip()
    if not kw:
        return {"items": results}

    is_admin = current_user.role.value == "admin" if hasattr(current_user.role, "value") else current_user.role == "admin"

    vm_q = db.execute(text(
        "SELECT v.id, v.vm_name, v.ip_address, v.mac_address, v.vm_folder, "
        "v.claim_status, d.dwmc as dept_name "
        "FROM vm_inventory v LEFT JOIN departments d ON v.department_id = d.id "
        "WHERE v.vm_name LIKE :kw OR v.ip_address LIKE :kw OR v.mac_address LIKE :kw"
    ), {"kw": f"%{kw}%"})
    for r in vm_q.fetchall():
        if not is_admin and r.dept_name and current_user.department and r.dept_name != current_user.department.dwmc:
            continue
        results.append({"asset_type": "vm", "id": r.id, "name": r.vm_name,
                        "ip_address": r.ip_address, "mac_address": r.mac_address,
                        "vm_folder": r.vm_folder, "department_name": r.dept_name,
                        "claim_status": r.claim_status or "unlinked"})

    zdns_q = db.execute(text(
        "SELECT domain_name, ip_address, record_type FROM zdns_domain_map "
        "WHERE domain_name LIKE :kw OR ip_address LIKE :kw"
    ), {"kw": f"%{kw}%"})
    for r in zdns_q.fetchall():
        results.append({"asset_type": "domain", "id": None, "name": r.domain_name,
                        "ip_address": r.ip_address, "mac_address": None,
                        "vm_folder": None, "department_name": None, "claim_status": None})

    f5_q = db.execute(text(
        "SELECT domain_name, vs_ip FROM f5_application_map "
        "WHERE domain_name LIKE :kw AND domain_name IS NOT NULL AND domain_name != ''"
    ), {"kw": f"%{kw}%"})
    for r in f5_q.fetchall():
        results.append({"asset_type": "domain", "id": None, "name": r.domain_name,
                        "ip_address": r.vs_ip, "mac_address": None,
                        "vm_folder": None, "department_name": None, "claim_status": None})

    return {"items": results[:100]}
