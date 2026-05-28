"""外部 API 服务 — 对接学校数据中台，获取教职工和院系所信息。"""
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.models.api_config import ApiConfig

logger = logging.getLogger(__name__)


class TokenExpiredError(Exception):
    """token 已失效，需刷新后重试。"""
    pass

TOKEN_PATH = "/open_api/authentication/get_access_token"
STAFF_PATH = "/open_api/customization/view/full"
DEPT_PATH = "/open_api/customization/view_alpha/full"


def _get_active_config(db: Session) -> Optional[ApiConfig]:
    return db.query(ApiConfig).filter(ApiConfig.is_active == True).first()


def _ensure_token(db: Session, config: ApiConfig) -> str:
    """确保有有效的 access_token，过期则自动刷新。"""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if config.access_token and config.token_expires_at and config.token_expires_at > now:
        return config.access_token

    url = f"{config.base_url.rstrip('/')}{TOKEN_PATH}"
    try:
        resp = httpx.get(url, params={"key": config.app_key, "secret": config.app_secret}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") == 10000:
            result = data["result"]
            config.access_token = result["access_token"]
            expires_in = int(result.get("expires_in", 7200))
            config.token_expires_at = datetime.now(timezone.utc).replace(tzinfo=None).fromtimestamp(
                datetime.now(timezone.utc).timestamp() + expires_in - 60
            )
            db.commit()
            db.refresh(config)
            return config.access_token
        else:
            raise RuntimeError(f"获取 token 失败：{data.get('message', '未知错误')}")
    except httpx.HTTPError as e:
        raise RuntimeError(f"获取 token 网络错误：{e}")


def test_connection(db: Session) -> dict:
    """测试 API 连接并返回 token 信息。"""
    config = _get_active_config(db)
    if not config:
        return {"success": False, "message": "未找到启用的 API 配置，请先保存配置"}
    try:
        token = _ensure_token(db, config)
        expires_in = None
        if config.token_expires_at:
            expires_in = int((config.token_expires_at - datetime.now(timezone.utc).replace(tzinfo=None)).total_seconds())
        return {"success": True, "message": "连接成功", "token_expires_in": max(0, expires_in)}
    except Exception as e:
        return {"success": False, "message": str(e)}


def _call_staff_api(config: ApiConfig, token: str, params: dict) -> list[dict]:
    """调用教职工查询 API，返回 data 列表。"""
    url = f"{config.base_url.rstrip('/')}{STAFF_PATH}"
    payload = {"access_token": token, **params, "page": 1, "per_page": 50}
    resp = httpx.post(url, json=payload, timeout=30)
    if resp.status_code == 400:
        data = resp.json()
        if "access token" in data.get("message", ""):
            raise TokenExpiredError()
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") == 10000:
        return data["result"].get("data", [])
    # 20013 = 查询结果为空，不是错误
    if data.get("code") == 20013:
        return []
    raise RuntimeError(f"查询教职工失败：{data.get('message', '未知错误')}")


def fetch_staff(db: Session, gh: str = "", xm: str = "") -> list[dict]:
    """按工号和姓名查询教职工（OR 模糊匹配）。返回匹配列表。"""
    config = _get_active_config(db)
    if not config:
        raise RuntimeError("未找到启用的 API 配置")

    for attempt in range(2):
        token = _ensure_token(db, config)
        results: dict[str, dict] = {}
        try:
            if gh:
                for item in _call_staff_api(config, token, {"GH": gh}):
                    g = item.get("GH", "")
                    if g and g not in results:
                        results[g] = item
            if xm:
                for item in _call_staff_api(config, token, {"XM": xm}):
                    g = item.get("GH", "")
                    if g and g not in results:
                        results[g] = item
            return list(results.values())
        except TokenExpiredError:
            if attempt == 0:
                config.access_token = None
                config.token_expires_at = None
                db.commit()
                continue
            raise RuntimeError("token 已失效，刷新后仍然失败")
        except httpx.HTTPError as e:
            raise RuntimeError(f"查询教职工网络错误：{e}")


def fetch_departments_page(db: Session, page: int = 1, per_page: int = 500) -> dict:
    """分页拉取院系所数据。"""
    config = _get_active_config(db)
    if not config:
        raise RuntimeError("未找到启用的 API 配置")

    for attempt in range(2):
        token = _ensure_token(db, config)
        url = f"{config.base_url.rstrip('/')}{DEPT_PATH}"
        try:
            resp = httpx.post(
                url,
                json={"access_token": token, "page": page, "per_page": per_page},
                timeout=60,
            )
            if resp.status_code == 400:
                data = resp.json()
                if "access token" in data.get("message", ""):
                    if attempt == 0:
                        config.access_token = None
                        config.token_expires_at = None
                        db.commit()
                        continue
                    raise RuntimeError("token 已失效")
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") == 10000:
                result = data["result"]
                return {
                    "items": result.get("data", []),
                    "total": int(result.get("total", 0)),
                    "page": int(result.get("page", page)),
                    "per_page": int(result.get("per_page", per_page)),
                    "max_page": int(result.get("max_page", 1)),
                }
            else:
                raise RuntimeError(f"查询院系所失败：{data.get('message', '未知错误')}")
        except httpx.HTTPError as e:
            raise RuntimeError(f"查询院系所网络错误：{e}")


def fetch_all_departments(db: Session) -> list[dict]:
    """全量拉取所有院系所数据（自动翻页）。"""
    all_items = []
    page = 1
    while True:
        page_data = fetch_departments_page(db, page=page, per_page=500)
        all_items.extend(page_data["items"])
        logger.info(f"已拉取院系所第 {page}/{page_data['max_page']} 页，累计 {len(all_items)} 条")
        if page >= page_data["max_page"]:
            break
        page += 1
    return all_items
