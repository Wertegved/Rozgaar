from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.hashing import hash_password, verify_password
from app.auth.jwt import create_access_token
from app.core.errors import APIError
from app.db.models.enums import AccountStatus, UserRole
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