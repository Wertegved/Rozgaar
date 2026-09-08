from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt

from app.core.config import get_settings
from app.db.models.enums import UserRole


class TokenConfigurationError(RuntimeError):
    pass


def create_access_token(user_id: UUID, role: UserRole) -> str:
    settings = get_settings()
    if not settings.jwt_secret_key:
        raise TokenConfigurationError("JWT_SECRET_KEY is not configured")

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "role": role.value,
        "type": "access",
        "iat": now,
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, object]:
    settings = get_settings()
    if not settings.jwt_secret_key:
        raise TokenConfigurationError("JWT_SECRET_KEY is not configured")
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])