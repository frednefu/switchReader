"""Worker 共享密钥认证 — 独立于用户 JWT 认证，用于 Worker 注册/心跳/注销。"""
import secrets
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import settings
from app.utils.security import decode_access_token

worker_security_scheme = HTTPBearer()


def verify_worker_token(
    credentials: HTTPAuthorizationCredentials = Depends(worker_security_scheme),
) -> str:
    """验证 Worker 共享密钥（时序安全比较），返回 'worker' 标识。"""
    if not secrets.compare_digest(credentials.credentials, settings.worker_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的 Worker 认证令牌")
    return "worker"


def verify_worker_or_admin(
    credentials: HTTPAuthorizationCredentials = Depends(worker_security_scheme),
) -> str:
    """双认证：先尝试 Worker 共享密钥，失败则尝试 Admin JWT。
    返回 'worker' 或 'admin' 标识调用来源。"""
    # 1) Worker token
    if secrets.compare_digest(credentials.credentials, settings.worker_token):
        return "worker"
    # 2) Admin JWT — 验证令牌有效性 + 管理员角色
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="认证失败：需要 Worker Token 或 Admin JWT")
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的认证令牌")
    # 验证管理员角色
    from app.database import SessionLocal
    from app.models.user import User, UserRole
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user or not user.is_active or user.role != UserRole.admin:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="需要管理员权限才能注册 Worker")
    finally:
        db.close()
    return "admin"
