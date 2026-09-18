import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.hashing import hash_password, verify_password
from app.auth.jwt import create_access_token
from app.core.config import get_settings
from app.core.errors import APIError
from app.db.models.enums import AccountStatus, UserRole
from app.db.models.password_reset_tokens import PasswordResetToken
from app.db.models.users import ConsumerProfile, User, WorkerProfile
from app.schemas.auth import LoginRequest, RegisterRequest


INVALID_CREDENTIALS = "Invalid email or password"


def register_user(session: Session, data: RegisterRequest) -> User:
    if data.role is UserRole.ADMIN:
        raise APIError(403, "Public admin registration is not allowed")

    user = User(
        name=data.name,
        phone=data.phone,
        email=str(data.email),
        password_hash=hash_password(data.password),
        role=data.role,
        account_status=AccountStatus.ACTIVE,
    )
    session.add(user)
    try:
        session.flush()
        if data.role is UserRole.CONSUMER:
            session.add(ConsumerProfile(user_id=user.id))
        elif data.role is UserRole.WORKER:
            session.add(WorkerProfile(user_id=user.id))
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise APIError(409, "An account with those details already exists") from error

    session.refresh(user)
    return user


def authenticate_user(session: Session, data: LoginRequest) -> User:
    user = session.scalar(select(User).where(User.email == str(data.email)))
    if user is None or not user.password_hash or not verify_password(data.password, user.password_hash):
        raise APIError(401, INVALID_CREDENTIALS)
    if user.account_status is not AccountStatus.ACTIVE:
        raise APIError(401, INVALID_CREDENTIALS)
    return user


def login_user(session: Session, data: LoginRequest) -> tuple[str, User]:
    user = authenticate_user(session, data)
    return create_access_token(user.id, user.role), user


def request_password_reset(session: Session, email: str) -> tuple[User, str] | None:
    now = datetime.now(timezone.utc)
    session.execute(delete(PasswordResetToken).where(PasswordResetToken.expires_at < now - timedelta(days=1)))
    user = session.scalar(select(User).where(User.email == email))
    if user is None or user.account_status is not AccountStatus.ACTIVE or user.role is not UserRole.CONSUMER:
        return None

    recent = session.scalar(
        select(func.count()).select_from(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.created_at >= now - timedelta(hours=1),
        )
    )
    if recent >= 3:
        return None

    session.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
    )

    raw = secrets.token_urlsafe(32)
    session.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hashlib.sha256(raw.encode()).hexdigest(),
            expires_at=now + timedelta(minutes=get_settings().password_reset_token_expire_minutes),
        )
    )
    session.commit()
    return user, raw


def reset_password(session: Session, token: str, new_password: str) -> User:
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    now = datetime.now(timezone.utc)
    user_id = session.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
        .values(used_at=now)
        .returning(PasswordResetToken.user_id)
    ).scalar_one_or_none()
    if user_id is None:
        raise APIError(400, "This reset link is invalid or has expired")

    user = session.get(User, user_id)
    if user is None or user.account_status is not AccountStatus.ACTIVE:
        session.rollback()
        raise APIError(400, "This reset link is invalid or has expired")

    user.password_hash = hash_password(new_password)
    user.password_changed_at = now
    session.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
    )
    session.commit()
    return user