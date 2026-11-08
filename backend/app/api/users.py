from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.models.user import User
from app.schemas.user import UserRead

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
def read_me(user: CurrentUser):
    return user


@router.get("", response_model=list[UserRead])
def list_users(
    db: DbSession,
    _admin: AdminUser,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    return db.scalars(select(User).order_by(User.id).offset(skip).limit(limit)).all()