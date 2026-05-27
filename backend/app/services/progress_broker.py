"""进度推送代理 — 将扫描状态变化发布到 Redis Pub-Sub，供 WebSocket 订阅。"""
import json
import logging

from redis import Redis

from app.config import settings

logger = logging.getLogger(__name__)

_redis: Redis | None = None


def _get_redis() -> Redis:
    """懒初始化 Redis 连接（同步）。"""
    global _redis
    if _redis is None:
        _redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


def publish_scan_update(scan_log_id: int):
    """发布某次扫描的状态快照到 Redis channel。
    只推送轻量标量字段（不含 steps 和 log_output），避免前端 Vue Proxy 包装大对象导致卡死。
    steps 和终端输出通过 REST API 按需获取。
    """
    from app.database import SessionLocal
    from app.models.scan_log import ScanLog

    try:
        db = SessionLocal()
        try:
            log = db.query(ScanLog).get(scan_log_id)
            if not log:
                return

            payload = {
                "id": log.id,
                "source_type": log.source_type,
                "source_name": log.source_name,
                "source_id": log.source_id,
                "status": log.status.value if hasattr(log.status, 'value') else log.status,
                "progress_pct": log.progress_pct or 0,
                "current_step": log.current_step or "",
                "hosts_found": log.hosts_found or 0,
                "routes_found": log.routes_found or 0,
                "duration_seconds": log.duration_seconds,
                "error_message": log.error_message,
                "started_at": log.started_at.isoformat() if log.started_at else None,
                "completed_at": log.completed_at.isoformat() if log.completed_at else None,
            }
        finally:
            db.close()

        r = _get_redis()
        msg = json.dumps(payload, ensure_ascii=False)
        r.publish(f"channel:scan:{scan_log_id}", msg)
        r.publish("channel:scan:list", msg)
    except Exception:
        logger.exception("发布扫描进度失败 scan_log_id=%s", scan_log_id)


def get_redis_pubsub() -> Redis:
    """返回 Redis 客户端用于订阅（每次调用懒初始化）。"""
    return _get_redis()
