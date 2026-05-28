from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ApiConfigCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    base_url: str = Field(..., min_length=1, max_length=256)
    app_key: str = Field(..., min_length=1, max_length=256)
    app_secret: str = Field(..., min_length=1, max_length=256)


class ApiConfigUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    app_key: Optional[str] = None
    app_secret: Optional[str] = None
    is_active: Optional[bool] = None


class ApiConfigOut(BaseModel):
    id: int
    name: str
    base_url: str
    app_key: str
    app_secret: str = ""  # 脱敏：返回时置空
    is_active: bool
    last_sync_at: Optional[datetime] = None
    sync_status: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ApiConfigTestResult(BaseModel):
    success: bool
    message: str
    token_expires_in: Optional[int] = None
