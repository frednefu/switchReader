"""Celery 应用实例 — Redis broker + backend。"""
from celery import Celery
from app.config import settings

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
