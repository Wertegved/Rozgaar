from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, oauth2_scheme
from app.db.session import get_db
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, UserResponse
from app.services.auth_service import login_user, register_user


router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, session: Session = Depends(get_db)) -> UserResponse:
    return register_user(session, data)


@router.post("/login", response_model=AuthResponse)
def login(data: LoginRequest, session: Session = Depends(get_db)) -> AuthResponse:
    token, user = login_user(session, data)
    return AuthResponse(access_token=token, user=user)


@router.get("/me", response_model=UserResponse)
def current_user(user=Depends(get_current_user)) -> UserResponse:
    return user