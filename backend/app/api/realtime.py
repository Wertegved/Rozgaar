from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.dependencies import get_current_user
from app.core.config import get_settings
from app.db.models.users import User


router = APIRouter(prefix="/realtime", tags=["realtime"])


@router.get("/token")
def realtime_token(user: User = Depends(get_current_user)) -> dict[str, object]:
    settings = get_settings()
    if not settings.supabase_jwt_secret or not settings.supabase_url or not settings.supabase_anon_key:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Realtime is not configured")

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=15)
    token = jwt.encode(
        {
            "sub": str(user.id),
            "role": "authenticated",
            "aud": "authenticated",
            "app_role": user.role.value,
            "iat": now,
            "exp": expires_at,
        },
        settings.supabase_jwt_secret,
        algorithm="HS256",
    )
    return {
        "access_token": token,
        "expires_in": 900,
        "supabase_url": settings.supabase_url,
        "supabase_anon_key": settings.supabase_anon_key,
        "channel": f"user:{user.id}",
    }