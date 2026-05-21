from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserLogin, PasswordChange, ProfileUpdate, TokenOut, UserOut
from app.utils.security import hash_password, verify_password, create_access_token
from app.api.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/login", response_model=TokenOut)
def login(body: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用")

    token = create_access_token(data={"sub": str(user.id)})
    return TokenOut(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return UserOut.model_validate(current_user)


@router.put("/profile", response_model=UserOut)
def update_profile(body: ProfileUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.email is not None:
        existing = db.query(User).filter(User.email == body.email, User.id != current_user.id).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="邮箱已被其他用户使用")
        current_user.email = body.email
    if body.avatar_url is not None:
        current_user.avatar_url = body.avatar_url
    db.commit()
    db.refresh(current_user)
    return UserOut.model_validate(current_user)


@router.put("/change-password")
def change_password(body: PasswordChange, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(body.old_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="原密码错误")
    current_user.password_hash = hash_password(body.new_password)
    db.commit()
    return {"message": "密码修改成功"}
