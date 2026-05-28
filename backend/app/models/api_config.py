from sqlalchemy import Column, Integer, String, Boolean, DateTime, func
from app.database import Base


class ApiConfig(Base):
    __tablename__ = "api_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False, comment="配置名称")
    base_url = Column(String(256), nullable=False, comment="API 基础地址")
    app_key = Column(String(256), nullable=False, comment="APP KEY")
    app_secret = Column(String(256), nullable=False, comment="APP SECRET")
    access_token = Column(String(512), nullable=True, comment="缓存的 access_token")
    token_expires_at = Column(DateTime, nullable=True, comment="token 过期时间")
    is_active = Column(Boolean, default=False, comment="是否启用")
    last_sync_at = Column(DateTime, nullable=True, comment="上次同步时间")
    sync_status = Column(String(32), nullable=True, comment="同步状态（idle/syncing/success/failed）")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
