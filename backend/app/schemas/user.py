from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class UserLogin(BaseModel):
    username: str
    password: str


class UserCreate(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    role: str = "user"


class UserUpdate(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class ProfileUpdate(BaseModel):
    avatar_url: Optional[str] = None
    email: Optional[str] = None


class PasswordChange(BaseModel):
    old_password: str
    new_password: str


class UserOut(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    role: str
    avatar_url: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
