"""ZDNS REST API 采集引擎 — 同步 HTTP + 异步包装，生成域名→IP 映射。"""
import json
import ssl
import asyncio
import logging
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from ipaddress import ip_address, IPv4Address, IPv6Address

from app.database import SessionLocal
from app.models.zdns import ZDNSDevice, ZDNSRecord, ZDNSDomainMap

logger = logging.getLogger(__name__)

# 内网 IPv4 前缀
_PRIVATE_V4_NETS = [
    (0x0A000000, 8),   # 10.0.0.0/8
    (0xAC100000, 12),  # 172.16.0.0/12
    (0xC0A80000, 16),  # 192.168.0.0/16
    (0x64400000, 10),  # 100.64.0.0/10 (CGN)
    (0xA9FE0000, 16),  # 169.254.0.0/16
]


def _is_private_v4(ip_str: str) -> bool:
    """判断 IPv4 是否为内网地址。"""
    try:
        parts = ip_str.split(".")
        if len(parts) != 4:
            return False
        num = sum(int(p) << (24 - 8 * i) for i, p in enumerate(parts))
        for prefix, bits in _PRIVATE_V4_NETS:
            mask = ((1 << 32) - 1) ^ ((1 << (32 - bits)) - 1)
            if (num & mask) == (prefix & mask):
                return True
        return False
    except (ValueError, TypeError):
        return False


def _is_private_ip(ip_str: str) -> str:
    """判断 IP 的内外网类型，返回 "内网" / "外网" / "未知"。

    IPv4 内网: 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 100.64.0.0/10, 169.254.0.0/16
    IPv6 内网: fd00::/8 (ULA), fe80::/10 (Link-Local)
    """
    ip_str = ip_str.strip()
    if not ip_str:
        return "未知"
    try:
        addr = ip_address(ip_str)
        if isinstance(addr, IPv4Address):
            return "内网" if _is_private_v4(ip_str) else "外网"
        if isinstance(addr, IPv6Address):
            if addr.is_link_local or addr.is_private:
                return "内网"
            return "外网"
    except ValueError:
        pass
    return "未知"


def _make_zdns_request(host: str, username: str, password: str, port: int,
                       path: str, body: dict | None = None) -> dict | list:
    """向 ZDNS API 发送 GET 请求并解析 JSON 响应。"""
    url = f"https://{host}:{port}{path}"

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    from base64 import b64encode
    credentials = b64encode(f"{username}:{password}".encode()).decode()

    data_bytes = json.dumps(body).encode("utf-8") if body else None
    req = Request(url, data=data_bytes, method="GET",
                  headers={"Authorization": f"Basic {credentials}",
                           "Content-Type": "application/json",
                           "Accept": "application/json"})

    try:
        resp = urlopen(req, context=ctx, timeout=60)
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}
    except HTTPError as e:
        err_body = ""
        try:
            err_body = e.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            pass
        raise RuntimeError(f"HTTP {e.code}: {err_body or str(e)}") from None
    except URLError as e:
        raise RuntimeError(f"连接失败: {e.reason}") from None


def _do_zdns_scan(host: str, username: str, password: str, port: int) -> dict:
    """同步扫描 ZDNS 设备，返回 {views, zones, records} 原始数据。"""
    logger.info("开始扫描 ZDNS %s", host)

    # 1. 获取所有视图 — ZDNS API 返回 {"resources": [{...}, ...], "page_num":...}
    views_data = _make_zdns_request(host, username, password, port, "/views")
    views = []
    if isinstance(views_data, dict):
        for item in views_data.get("resources", []):
            if isinstance(item, dict):
                views.append(item.get("name", ""))
            elif isinstance(item, str):
                views.append(item)
    elif isinstance(views_data, list):
        views = [v if isinstance(v, str) else v.get("name", "") for v in views_data]

    if not views:
        raise RuntimeError("未能获取到视图列表")

    logger.info("ZDNS %s 发现 %s 个视图", host, len(views))

    # 2. 获取每个视图下的区
    all_zones = {}
    for view in views:
        try:
            zones_data = _make_zdns_request(host, username, password, port,
                                            f"/views/{view}/zones")
            zones = []
            if isinstance(zones_data, dict):
                for item in zones_data.get("resources", []):
                    if isinstance(item, dict):
                        zones.append(item.get("name", ""))
                    elif isinstance(item, str):
                        zones.append(item)
            elif isinstance(zones_data, list):
                zones = [z if isinstance(z, str) else z.get("name", "") for z in zones_data]
            all_zones[view] = zones
            logger.info("  视图 %s: %s 个区", view, len(zones))
        except Exception as e:
            logger.warning("  获取视图 %s 的区列表失败: %s", view, e)
            all_zones[view] = []

    # 3. 分页获取每个区的 DNS 记录
    all_records = []
    for view, zones in all_zones.items():
        for zone in zones:
            page = 1
            page_size = 1000
            while True:
                try:
                    body = {
                        "current_user": username,
                        "page_num": page,
                        "page_size": page_size,
                    }
                    resp = _make_zdns_request(host, username, password, port,
                                              f"/views/{view}/zones/{zone}/rrs", body)
                    resources = resp.get("resources", []) if isinstance(resp, dict) else []
                    total_size = resp.get("total_size", 0) if isinstance(resp, dict) else len(resources)

                    for rr in resources:
                        if not isinstance(rr, dict):
                            continue
                        rname = rr.get("name", "")
                        rtype = rr.get("type", "")
                        rdata = rr.get("rdata", "")

                        # 构建完整域名
                        if rname.endswith("."):
                            full_domain = rname.rstrip(".")
                        elif rname and rname != "@":
                            full_domain = f"{rname}.{zone.rstrip('.')}"
                        else:
                            full_domain = zone.rstrip(".")

                        all_records.append({
                            "record_id": rr.get("id", ""),
                            "name": rname,
                            "full_domain": full_domain,
                            "record_type": rtype,
                            "ttl": _int_or_none(rr.get("ttl")),
                            "rdata": str(rdata) if rdata else "",
                            "view_name": view,
                            "zone_name": zone,
                            "is_enabled": rr.get("is_enable", ""),
                            "strategy": rr.get("strategy", ""),
                            "expire_time": rr.get("expire_time", ""),
                            "expire_style": rr.get("expire_style", ""),
                            "raw_data": json.dumps(rr, ensure_ascii=False),
                        })

                    if len(resources) < page_size:
                        break
                    page += 1
                except Exception as e:
                    logger.warning("  获取区 %s/%s 第 %s 页失败: %s", view, zone, page, e)
                    break

    zone_count = sum(len(z) for z in all_zones.values())
    logger.info("ZDNS %s 扫描完成，%s 个区，%s 条记录", host, zone_count, len(all_records))
    return {"views": views, "zones": all_zones, "records": all_records}


def _int_or_none(val) -> int | None:
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _build_domain_map(records: list) -> list:
    """从 DNS 记录中筛选 A/AAAA 记录，构建域名→IP 映射（含 IP 分类）。"""
    rows = []
    for r in records:
        rtype = r.get("record_type", "")
        if rtype not in ("A", "AAAA"):
            continue
        ip_str = r.get("rdata", "").strip()
        if not ip_str:
            continue

        ip_category = "IPv6" if rtype == "AAAA" else "IPv4"
        network_type = _is_private_ip(ip_str)

        rows.append({
            "domain_name": r["full_domain"],
            "record_type": rtype,
            "ip_address": ip_str,
            "ip_category": ip_category,
            "network_type": network_type,
            "ttl": r.get("ttl"),
            "view_name": r["view_name"],
            "zone_name": r["zone_name"],
            "is_enabled": r.get("is_enabled", ""),
        })
    return rows


async def _run_zdns_scan_async(zdns_device_id: int):
    """异步扫描 ZDNS 设备，采集 DNS 记录并写入数据库。"""
    from app.services.history_service import detect_zdns_changes

    start_time = datetime.now()

    db = SessionLocal()
    device = None
    record_count = 0
    zone_count = 0
    try:
        device = db.query(ZDNSDevice).get(zdns_device_id)
        if not device or not device.is_active:
            return

        device.last_scan_status = "running"
        device.last_scan_error = None
        db.commit()

        loop = asyncio.get_running_loop()
        scan_result = await loop.run_in_executor(
            None, _do_zdns_scan, device.host, device.username, device.password, device.port
        )

        record_count = len(scan_result["records"])
        zone_count = sum(len(zones) for zones in scan_result["zones"].values())

        write_db = SessionLocal()
        try:
            # 快照旧 DomainMap 用于历史 diff
            old_map_rows = write_db.query(ZDNSDomainMap).filter(
                ZDNSDomainMap.zdns_device_id == zdns_device_id
            ).all()
            old_by_key = {(r.domain_name, r.record_type): r for r in old_map_rows}

            # DELETE + INSERT: ZDNSRecord
            write_db.query(ZDNSRecord).filter(
                ZDNSRecord.zdns_device_id == zdns_device_id
            ).delete()
            for rec in scan_result["records"]:
                write_db.add(ZDNSRecord(zdns_device_id=zdns_device_id, **rec))

            # 构建并写入 DomainMap
            map_rows = _build_domain_map(scan_result["records"])
            write_db.query(ZDNSDomainMap).filter(
                ZDNSDomainMap.zdns_device_id == zdns_device_id
            ).delete(synchronize_session='fetch')
            for mr in map_rows:
                write_db.add(ZDNSDomainMap(zdns_device_id=zdns_device_id, **mr))

            write_db.flush()  # 确保 INSERT 已刷入，避免 query 返回旧缓存数据

            # 构建新 DomainMap 的 key 字典用于 diff
            new_map_rows = write_db.query(ZDNSDomainMap).filter(
                ZDNSDomainMap.zdns_device_id == zdns_device_id
            ).all()
            new_by_key = {(r.domain_name, r.record_type): r for r in new_map_rows}

            # 写入历史
            detect_zdns_changes(write_db, zdns_device_id, device.name, old_by_key, new_by_key)

            write_db.commit()
        except Exception:
            write_db.rollback()
            raise
        finally:
            write_db.close()

        duration = round((datetime.now() - start_time).total_seconds(), 1)
        db_device = db.query(ZDNSDevice).get(zdns_device_id)
        if db_device:
            db_device.last_scan_status = "success"
            db_device.last_scan_time = datetime.now()
            db_device.last_scan_duration = duration
            db_device.last_record_count = record_count
            db_device.last_zone_count = zone_count
            db_device.last_scan_error = None
            db.commit()
        logger.info("ZDNS %s 扫描完成，%s 条记录，%s 个区，耗时 %ss",
                    device.host, record_count, zone_count, duration)
    except Exception as e:
        duration = round((datetime.now() - start_time).total_seconds(), 1)
        logger.exception("ZDNS %s 扫描失败", device.host if device else zdns_device_id)
        try:
            db_device = db.query(ZDNSDevice).get(zdns_device_id)
            if db_device:
                db_device.last_scan_status = "failed"
                db_device.last_scan_error = str(e)
                db_device.last_scan_duration = duration
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


async def trigger_zdns_scan(device: ZDNSDevice):
    """触发异步扫描，立即返回。"""
    db = SessionLocal()
    try:
        db_device = db.query(ZDNSDevice).get(device.id)
        if db_device:
            db_device.last_scan_status = "running"
            db_device.last_scan_error = None
            db.commit()
    finally:
        db.close()
    asyncio.create_task(_run_zdns_scan_async(device.id))


async def test_zdns_connection(host: str, username: str, password: str, port: int = 20120) -> dict:
    """测试 ZDNS 连接（访问 /views 端点验证）。"""
    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(
            None, _make_zdns_request, host, username, password, port, "/views"
        )
        return {"ok": True, "message": "连接成功"}
    except Exception as e:
        return {"ok": False, "message": str(e)}
