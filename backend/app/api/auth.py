import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, oauth2_scheme
from app.core.config import get_settings
from app.db.session import get_db
from app.infrastructure.redis import consume_rate_limit
from app.providers.email import FakeEmailProvider
from app.schemas.auth import (
    AuthResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    UserResponse,
)
from app.services.auth_service import login_user, request_password_reset, register_user, reset_password
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)


def get_email_service() -> EmailService:
    return EmailService()


router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, session: Session = Depends(get_db)) -> UserResponse:
    return register_user(session, data)


@router.post("/login", response_model=AuthResponse)
def login(data: LoginRequest, session: Session = Depends(get_db)) -> AuthResponse:
    token, user = login_user(session, data)
    return AuthResponse(access_token=token, user=user)


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(
    data: ForgotPasswordRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_db),
    email_service: EmailService = Depends(get_email_service),
) -> MessageResponse:
    client_ip = request.client.host if request.client else "unknown"
    if not consume_rate_limit(
        f"password-reset:ip:{client_ip}",
        limit=10,
        window_seconds=3600,
        fail_closed=get_settings().environment.lower() != "development",
    ):
        return MessageResponse(message="If an account exists for that email, a reset link is on its way.")

    result = request_password_reset(session, str(data.email))
    if result is None:
        return MessageResponse(message="If an account exists for that email, a reset link is on its way.")

    user, raw_token = result
    reset_link = f"{get_settings().consumer_web_url.rstrip('/')}/#reset-password={raw_token}"
    if get_settings().environment == "development" and isinstance(email_service.provider, FakeEmailProvider):
        logger.warning("Password reset link for %s: %s", user.email, reset_link)

    background_tasks.add_task(
        email_service.send,
        str(user.email),
        "Reset your Rozgaar password",
        f"Use the link below to reset your password. This link expires in {get_settings().password_reset_token_expire_minutes} minutes.\n\n{reset_link}\n\nIf you did not request this, you can ignore this email.",
    )
    return MessageResponse(message="If an account exists for that email, a reset link is on its way.")


@router.post("/reset-password", response_model=MessageResponse)
def reset_password_route(
    data: ResetPasswordRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_db),
    email_service: EmailService = Depends(get_email_service),
) -> MessageResponse:
    user = reset_password(session, data.token, data.new_password)
    background_tasks.add_task(
        email_service.send,
        str(user.email),
        "Your Rozgaar password was changed",
        "Your Rozgaar password was changed successfully. If you did not make this change, contact support immediately.",
    )
    return MessageResponse(message="Your password has been reset successfully.")


@router.get("/me", response_model=UserResponse)
def current_user(user=Depends(get_current_user)) -> UserResponse:
    return user