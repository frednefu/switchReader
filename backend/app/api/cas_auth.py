"""CAS 统一身份认证路由。"""
from urllib.parse import urlencode

from fastapi import APIRouter, Query, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.utils.security import create_access_token
from app.services import cas_service
from app.config import settings

router = APIRouter(prefix="/auth/cas", tags=["CAS 认证"])


@router.get("/login")
def cas_login(service: str = Query(None)):
    """重定向到 CAS 服务器登录页面。"""
    url = cas_service.get_login_url(service)
    return RedirectResponse(url=url)


@router.get("/callback")
def cas_callback(
    ticket: str = Query(None),
    db: Session = Depends(get_db),
):
    """CAS 回调：验证 ticket，签发 JWT，重定向到前端。"""
    frontend_url = settings.cas_service_url.rsplit("/api", 1)[0]

    if not ticket:
        return RedirectResponse(url=f"{frontend_url}/login?error=no_ticket")

    # 验证票据
    cas_username = cas_service.verify_ticket(ticket)
    if not cas_username:
        return RedirectResponse(url=f"{frontend_url}/login?error=cas_failed")

    # 查找用户：先按 username 匹配，再按工号 gh 匹配
    user = db.query(User).filter(User.username == cas_username).first()
    if not user:
        user = db.query(User).filter(User.gh == cas_username).first()
    if not user:
        # 尝试通过 name 匹配（有些 CAS 返回姓名）
        user = db.query(User).filter(User.name == cas_username).first()

    if not user:
        return RedirectResponse(url=f"{frontend_url}/login?error=cas_unauthorized&user={cas_username}")
    if not user.is_active:
        return RedirectResponse(url=f"{frontend_url}/login?error=cas_disabled&user={cas_username}")

    # 签发 JWT
    token = create_access_token(data={"sub": str(user.id)})
    return RedirectResponse(url=f"{frontend_url}/?cas_token={token}")


@router.get("/logout")
def cas_logout(redirect: str = Query(None)):
    """重定向到 CAS 服务器登出页面。"""
    url = cas_service.get_logout_url(redirect)
    return RedirectResponse(url=url)
