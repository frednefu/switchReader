"""CAS v3 认证服务 — 统一身份认证对接。"""
import logging
import urllib.parse
import xml.etree.ElementTree as ET

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

CAS_NS = "http://www.yale.edu/tp/cas"


def get_login_url(service_url: str = None) -> str:
    """生成 CAS 登录页面 URL，重定向用户到 CAS 服务器。"""
    svc = service_url or settings.cas_service_url
    params = urllib.parse.urlencode({"service": svc})
    return f"{settings.cas_server_url}/login?{params}"


def verify_ticket(ticket: str, service_url: str = None) -> str | None:
    """调用 CAS v3 服务验证票据。成功返回 username，失败返回 None。"""
    svc = service_url or settings.cas_service_url
    url = f"{settings.cas_server_url}/p3/serviceValidate"
    params = {"ticket": ticket, "service": svc}

    try:
        resp = httpx.get(url, params=params, timeout=15)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)

        # 检查认证成功
        success = root.find(f"{{{CAS_NS}}}authenticationSuccess")
        if success is not None:
            user_el = success.find(f"{{{CAS_NS}}}user")
            if user_el is not None and user_el.text:
                logger.info(f"CAS 验证成功：{user_el.text}")
                return user_el.text.strip()

        # 认证失败
        failure = root.find(f"{{{CAS_NS}}}authenticationFailure")
        if failure is not None:
            code = failure.attrib.get("code", "unknown")
            msg = failure.text or ""
            logger.warning(f"CAS 验证失败：{code} - {msg}")
            return None

        logger.warning("CAS 响应格式异常")
        return None

    except httpx.HTTPError as e:
        logger.error(f"CAS 验证请求失败：{e}")
        return None
    except ET.ParseError as e:
        logger.error(f"CAS 响应 XML 解析失败：{e}")
        return None


def get_logout_url(redirect_url: str = None) -> str:
    """生成 CAS 登出 URL。"""
    target = redirect_url or settings.cas_service_url.rsplit("/api", 1)[0]
    params = urllib.parse.urlencode({"service": target})
    return f"{settings.cas_server_url}/logout?{params}"
