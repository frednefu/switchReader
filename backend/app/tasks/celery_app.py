"""Celery 应用实例 — Redis broker + backend，含 Worker 自动注册/注销。"""
import hashlib
import os
import socket
import urllib.request
import json
import logging

from celery import Celery
from celery.signals import worker_ready, worker_shutdown

from app.config import settings

logger = logging.getLogger(__name__)

celery_app = Celery(
    "omniview",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.scan_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=3600,
    broker_connection_retry_on_startup=True,
)


def _register_worker():
    """向 API 服务器注册当前 Worker。"""
    api_base = os.environ.get("API_BASE_URL", "http://backend:8000")
    worker_name = os.environ.get("WORKER_NAME", socket.gethostname())
    version = os.environ.get("WORKER_VERSION", "2.0.0")
    worker_token = settings.worker_token

    try:
        data = json.dumps({
            "worker_name": worker_name,
            "capabilities": {"task_types": ["switch", "vcenter", "f5", "zdns", "qax"]},
            "version": version,
        }).encode()
        req = urllib.request.Request(
            f"{api_base}/api/workers/register",
            data=data,
            headers={
                "Authorization": f"Bearer {worker_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read().decode())
        logger.info("Worker 注册成功: %s (ID=%s)", result["worker_name"], result["worker_id"])
        return result["worker_id"]
    except Exception as e:
        logger.warning("Worker 注册失败: %s", e)
        return None


_WORKER_ID = None


@worker_ready.connect
def on_worker_ready(sender=None, **kwargs):
    """Worker 就绪后自动注册。"""
    global _WORKER_ID
    _WORKER_ID = _register_worker()


@worker_shutdown.connect
def on_worker_shutdown(sender=None, **kwargs):
    """Worker 关闭时自动注销。"""
    global _WORKER_ID
    if not _WORKER_ID:
        return
    api_base = os.environ.get("API_BASE_URL", "http://backend:8000")
    worker_token = settings.worker_token
    try:
        req = urllib.request.Request(
            f"{api_base}/api/workers/{_WORKER_ID}/deregister",
            headers={"Authorization": f"Bearer {worker_token}"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10)
        logger.info("Worker (ID=%s) 已注销", _WORKER_ID)
    except Exception as e:
        logger.warning("Worker 注销失败: %s", e)
