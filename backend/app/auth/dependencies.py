from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.jwt import decode_access_token
from app.db.models.enums import AccountStatus, UserRole
from app.db.models.users import User
from app.db.session import get_db


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def authentication_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    token: str = Depends(oauth2_scheme), session: Session = Depends(get_db)
) -> User:
    try:
        payload = decode_access_token(token)
        subject = payload.get("sub")
        if payload.get("type") != "access" or not isinstance(subject, str):
            raise authentication_error()
        user_id = UUID(subject)
    except (ValueError, jwt.InvalidTokenError, RuntimeError):
        raise authentication_error() from None

    user = session.scalar(select(User).where(User.id == user_id))
    if user is None or user.account_status is not AccountStatus.ACTIVE:
        raise authentication_error()
    return user


def require_role(role: UserRole):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role is not role:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return dependency


require_consumer = require_role(UserRole.CONSUMER)
require_worker = require_role(UserRole.WORKER)
require_admin = require_role(UserRole.ADMIN)