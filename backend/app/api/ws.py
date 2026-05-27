"""WebSocket 端点 — 扫描进度实时推送。"""
import asyncio
import json
import logging

from fastapi import WebSocket, WebSocketDisconnect, Query

from app.utils.security import decode_access_token
from app.services.progress_broker import get_redis_pubsub

logger = logging.getLogger(__name__)


async def ws_scan_progress(
    websocket: WebSocket,
    token: str = Query(...),
):
    """WebSocket 端点：扫描进度实时推送。

    客户端连接后，服务端订阅 Redis channel:scan:list，
    收到消息后推送给客户端。客户端自行维护任务列表。
    """
    # 验证 JWT
    payload = decode_access_token(token)
    if payload is None:
        await websocket.close(code=4001, reason="未授权")
        return

    username = payload.get("sub", "unknown")
    logger.info("WebSocket 已连接 user=%s", username)

    try:
        await websocket.accept()
    except Exception:
        return

    r = get_redis_pubsub()
    pubsub = r.pubsub()
    pubsub.subscribe("channel:scan:list")

    try:
        # 持续从 Redis 读取并推送到 WebSocket
        while True:
            # 非阻塞检查 WebSocket 是否断开
            try:
                message = pubsub.get_message(ignore_subscribe_messages=True, timeout=0.5)
            except Exception:
                await asyncio.sleep(0.5)
                continue

            if message and message.get("type") == "message":
                try:
                    data = message.get("data")
                    if data:
                        await websocket.send_text(data)
                except Exception:
                    logger.warning("发送 WebSocket 消息失败 user=%s", username)
                    break

            # 检查客户端是否发送了关闭信号
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
            except asyncio.TimeoutError:
                pass
            except WebSocketDisconnect:
                break
            except Exception:
                pass
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WebSocket 异常 user=%s", username)
    finally:
        try:
            pubsub.close()
        except Exception:
            pass
        logger.info("WebSocket 已断开 user=%s", username)
