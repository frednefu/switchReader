"""Celery 扫描任务 — 各数据源的异步扫描执行。

每个任务在被 Worker 拉取后：
1. 从数据库加载设备信息
2. 调用对应的 _run_*_scan_async 执行扫描
3. _run_*_scan_async 内部会自行更新 scan_log 和设备状态
"""

import asyncio
import logging

from app.tasks.celery_app import celery_app
from app.database import SessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=1, default_retry_delay=60)
def scan_switch_task(self, switch_id: int, scan_log_id: int):
    """交换机 SNMP 扫描任务。"""
    from app.models.switch import Switch
    from app.services.scanner_service import _run_scan_async

    db = SessionLocal()
    try:
        sw = db.query(Switch).get(switch_id)
        if not sw:
            logger.warning("交换机不存在 switch_id=%s", switch_id)
            return {"error": "switch_not_found"}
        sw_obj = sw
    finally:
        db.close()

    try:
        asyncio.run(_run_scan_async(sw_obj, scan_log_id))
    except Exception as e:
        logger.exception("Celery 交换机扫描失败 switch_id=%s", switch_id)
        raise


@celery_app.task(bind=True, max_retries=1, default_retry_delay=60)
def scan_vcenter_task(self, vcenter_id: int, scan_log_id: int):
    """vCenter 扫描任务。"""
    from app.services.vcenter_scanner_service import _run_vcenter_scan_async

    try:
        asyncio.run(_run_vcenter_scan_async(vcenter_id, scan_log_id))
    except Exception as e:
        logger.exception("Celery vCenter 扫描失败 vcenter_id=%s", vcenter_id)
        raise


@celery_app.task(bind=True, max_retries=1, default_retry_delay=60)
def scan_f5_task(self, device_id: int, scan_log_id: int):
    """F5 设备扫描任务。"""
    from app.services.f5_scanner_service import _run_f5_scan_async

    try:
        asyncio.run(_run_f5_scan_async(device_id, scan_log_id))
    except Exception as e:
        logger.exception("Celery F5 扫描失败 device_id=%s", device_id)
        raise


@celery_app.task(bind=True, max_retries=1, default_retry_delay=60)
def scan_zdns_task(self, device_id: int, scan_log_id: int):
    """ZDNS 设备扫描任务。"""
    from app.services.zdns_scanner_service import _run_zdns_scan_async

    try:
        asyncio.run(_run_zdns_scan_async(device_id, scan_log_id))
    except Exception as e:
        logger.exception("Celery ZDNS 扫描失败 device_id=%s", device_id)
        raise


@celery_app.task(bind=True, max_retries=1, default_retry_delay=60)
def scan_zdns_ip_task(self, device_id: int, scan_log_id: int):
    """ZDNS IP 可达性扫描任务。"""
    from app.services.zdns_ip_scanner_service import _run_zdns_ip_scan_async

    try:
        asyncio.run(_run_zdns_ip_scan_async(device_id, scan_log_id))
    except Exception as e:
        logger.exception("Celery ZDNS IP扫描失败 device_id=%s", device_id)
        raise


@celery_app.task(bind=True, max_retries=1, default_retry_delay=60)
def scan_qax_task(self, device_id: int, scan_log_id: int):
    """椒图设备扫描任务。"""
    from app.services.qax_scanner_service import _run_qax_scan_async

    try:
        asyncio.run(_run_qax_scan_async(device_id, scan_log_id))
    except Exception as e:
        logger.exception("Celery 椒图扫描失败 device_id=%s", device_id)
        raise
