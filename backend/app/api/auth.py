from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.api.deps import DbSession
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import RefreshRequest, Token
from app.schemas.user import UserCreate, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_tokens(db: DbSession, user: User) -> Token:
    access = create_access_token(user.id, user.role)
    refresh, jti, expires_at = create_refresh_token(user.id)
    db.add(RefreshToken(user_id=user.id, jti=jti, expires_at=expires_at))
    db.commit()
    return Token(access_token=access, refresh_token=refresh)


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(data: UserCreate, db: DbSession):
    email = data.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    # Role is never taken from the request: new accounts are always customers.
    user = User(
        email=email,
        full_name=data.full_name,
        hashed_password=hash_password(data.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # two requests raced past the check above
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession):
    # OAuth2 form fields are named "username"; we use it for the email.
    user = db.scalar(select(User).where(User.email == form.username.lower()))
    if (
        user is None
        or not user.is_active
        or not verify_password(form.password, user.hashed_password)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _issue_tokens(db, user)


@router.post("/refresh", response_model=Token)
def refresh(body: RefreshRequest, db: DbSession):
    invalid = HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    try:
        payload = decode_token(body.refresh_token, expected_type="refresh")
    except jwt.InvalidTokenError:
        raise invalid

    stored = db.scalar(select(RefreshToken).where(RefreshToken.jti == payload["jti"]))
    if stored is None:
        raise invalid

    if stored.revoked:
        # A revoked token being reused suggests it was stolen: revoke the whole family.
        db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == stored.user_id)
            .values(revoked=True)
        )
        db.commit()
        raise invalid

    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise invalid

    # Rotation: each refresh token can be used exactly once.
    stored.revoked = True
    return _issue_tokens(db, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(body: RefreshRequest, db: DbSession) -> Response:
    try:
        payload = decode_token(body.refresh_token, expected_type="refresh")
    except jwt.InvalidTokenError:
        return Response(status_code=status.HTTP_204_NO_CONTENT)  # idempotent

    stored = db.scalar(select(RefreshToken).where(RefreshToken.jti == payload["jti"]))
    if stored is not None:
        stored.revoked = True
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)