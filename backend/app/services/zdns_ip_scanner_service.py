"""ZDNS IP 可达性扫描 — 对域名映射中的 IP 执行 ping 探测，更新在线状态。"""
import asyncio
import logging
import platform
import subprocess
from datetime import datetime

from app.database import SessionLocal
from app.models.zdns import ZDNSDevice, ZDNSDomainMap
from app.models.scan_result import ScanResult
from app.models.f5 import F5PoolMember, F5ApplicationMap
from app.models.scan_log import ScanLog, ScanStatus, TriggerType

logger = logging.getLogger(__name__)


def _ping_ip(ip_address: str, timeout: int = 3) -> bool:
    """跨平台 ICMP ping，返回 True 表示可达。"""
    if platform.system() == "Windows":
        cmd = ["ping", "-n", "1", "-w", str(timeout * 1000), ip_address]
    else:
        cmd = ["ping", "-c", "1", "-W", str(timeout), ip_address]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout + 5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, Exception):
        return False


async def _run_zdns_ip_scan_async(zdns_device_id: int, scan_log_id: int | None = None):
    """异步执行 IP 可达性扫描，在线程池中运行 ping。"""
    from datetime import datetime as dt

    loop = asyncio.get_running_loop()
    start_time = dt.now()
    device = None
    total_checked = 0
    online_count = 0
    offline_count = 0

    db = SessionLocal()
    try:
        device = db.query(ZDNSDevice).get(zdns_device_id)
        if not device or not device.is_active:
            return

        device.last_ip_scan_status = "running"
        device.last_ip_scan_error = None
        db.commit()

        # 获取该设备所有域名映射 IP（去重非空）
        rows = db.query(ZDNSDomainMap).filter(
            ZDNSDomainMap.zdns_device_id == zdns_device_id,
            ZDNSDomainMap.ip_address != "",
        ).all()

        if not rows:
            device.last_ip_scan_status = "success"
            device.last_ip_scan_time = dt.now()
            device.last_ip_scan_duration = 0.0
            db.commit()
            return

        unique_ips = list(set(r.ip_address for r in rows))

        # 批量查交换机 scan_results：已存在于交换机中的 IP 直接视为在线
        switch_ips = set()
        if unique_ips:
            sr_rows = db.query(ScanResult.ip_address).filter(
                ScanResult.ip_address.in_(unique_ips)
            ).distinct().all()
            switch_ips = {r[0] for r in sr_rows}

        # 批量查 F5 成员：状态为 up 的 IP 也视为在线
        f5_up_ips = set()
        if unique_ips:
            pm_rows = db.query(F5PoolMember.member_ip).filter(
                F5PoolMember.member_ip.in_(unique_ips),
                F5PoolMember.member_state == "up",
            ).distinct().all()
            f5_up_ips = {r[0] for r in pm_rows}
            am_rows = db.query(F5ApplicationMap.member_ip).filter(
                F5ApplicationMap.member_ip.in_(unique_ips),
                F5ApplicationMap.member_state == "up",
            ).distinct().all()
            f5_up_ips.update(r[0] for r in am_rows)

        # 确定需要 ping 的 IP：不在交换机中且不在 F5 up 中的
        known_online = switch_ips | f5_up_ips
        ips_to_ping = [ip for ip in unique_ips if ip not in known_online]

        # 为已知在线的 IP 更新状态
        for r in rows:
            if r.ip_address in known_online:
                r.ip_status = "online"

        # 对需要探测的 IP 执行 ping（限并发 20）
        semaphore = asyncio.Semaphore(20)

        async def _ping_with_limit(ip):
            async with semaphore:
                reachable = await loop.run_in_executor(None, _ping_ip, ip)
                return ip, reachable

        if ips_to_ping:
            tasks = [_ping_with_limit(ip) for ip in ips_to_ping]
            results = await asyncio.gather(*tasks)

            ping_results = dict(results)
            for r in rows:
                if r.ip_address in ping_results:
                    total_checked += 1
                    if ping_results[r.ip_address]:
                        r.ip_status = "online"
                        online_count += 1
                    else:
                        r.ip_status = "offline"
                        offline_count += 1

        db.commit()

        duration = round((dt.now() - start_time).total_seconds(), 1)
        device.last_ip_scan_status = "success"
        device.last_ip_scan_time = dt.now()
        device.last_ip_scan_duration = duration
        db.commit()
        logger.info(
            "ZDNS IP扫描完成 device_id=%s, 已在线=%s, 探测=%s(在线%s/离线%s), 耗时%ss",
            zdns_device_id, len(known_online), total_checked, online_count, offline_count, duration,
        )
    except Exception as e:
        duration = round((dt.now() - start_time).total_seconds(), 1)
        logger.exception("ZDNS IP扫描失败 device_id=%s", zdns_device_id)
        try:
            if device:
                device.last_ip_scan_status = "failed"
                device.last_ip_scan_error = str(e)
                device.last_ip_scan_duration = duration
                db.commit()
        except Exception:
            pass
    finally:
        db.close()

    # 更新扫描日志
    if scan_log_id:
        _db = SessionLocal()
        try:
            log = _db.query(ScanLog).get(scan_log_id)
            if log:
                log.status = ScanStatus.success
                log.hosts_found = online_count
                log.routes_found = offline_count
                log.completed_at = dt.now()
                if log.started_at:
                    log.duration_seconds = round((dt.now() - log.started_at).total_seconds(), 1)
                _db.commit()
        except Exception:
            pass
        finally:
            _db.close()


async def trigger_zdns_ip_scan(device: ZDNSDevice, triggered_by: str = "manual") -> int:
    """触发异步 IP 扫描，立即返回 scan_log_id。"""
    db = SessionLocal()
    try:
        db_device = db.query(ZDNSDevice).get(device.id)
        if db_device:
            db_device.last_ip_scan_status = "running"
            db_device.last_ip_scan_error = None

        trigger = TriggerType.manual if triggered_by == "manual" else TriggerType.scheduled
        scan_log = ScanLog(
            source_type="zdns_ip",
            source_id=device.id,
            source_name=device.name,
            status=ScanStatus.running,
            triggered_by=trigger,
            started_at=datetime.now(),
        )
        db.add(scan_log)
        db.commit()
        db.refresh(scan_log)
        scan_log_id = scan_log.id
    finally:
        db.close()
    from app.tasks.scan_tasks import scan_zdns_ip_task
    scan_zdns_ip_task.delay(device.id, scan_log_id)
    return scan_log_id
