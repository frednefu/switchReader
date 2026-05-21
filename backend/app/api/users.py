"""用户管理 API — 仅管理员可操作。"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from math import ceil

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserOut, PasswordChange
from app.utils.security import hash_password
from app.api.deps import require_admin

router = APIRouter(prefix="/users", tags=["用户管理"])


def _user_out(user: User) -> UserOut:
    return UserOut.model_validate(user)


@router.get("")
def list_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str = Query("", max_length=128),
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    q = db.query(User).filter(User.id != admin.id)  # 不显示自己
    if search:
        q = q.filter(
            (User.username.contains(search)) | (User.email.contains(search))
        )
    total = q.count()
    pages = ceil(total / size) if total > 0 else 0
    items = q.order_by(User.id).offset((page - 1) * size).limit(size).all()
    return {
        "items": [_user_out(u) for u in items],
        "total": total, "page": page, "size": size, "pages": pages,
    }


@router.post("", response_model=UserOut)
def create_user(body: UserCreate, db: Session = Depends(get_db), admin=Depends(require_admin)):
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已存在")
    if body.email and db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="邮箱已存在")
    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        role=body.role,
        email=body.email,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _user_out(user)


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(get_db), admin=Depends(require_admin)):
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return _user_out(user)


@router.put("/{user_id}", response_model=UserOut)
def update_user(user_id: int, body: UserUpdate, db: Session = Depends(get_db), admin=Depends(require_admin)):
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    if user.id == admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能通过此接口修改自己")
    if body.email is not None:
        existing = db.query(User).filter(User.email == body.email, User.id != user_id).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="邮箱已被其他用户使用")
        user.email = body.email
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    db.commit()
    db.refresh(user)
    return _user_out(user)


@router.delete("/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), admin=Depends(require_admin)):
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    if user.id == admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能删除自己")
    db.delete(user)
    db.commit()
    return {"message": "用户已删除"}


@router.put("/{user_id}/reset-password")
def reset_password(user_id: int, body: PasswordChange, db: Session = Depends(get_db), admin=Depends(require_admin)):
    """管理员重置其他用户的密码。"""
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    user.password_hash = hash_password(body.new_password)
    db.commit()
    return {"message": "密码已重置"}
