from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.api.router import router as api_router
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.health.router import health, ready


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response


def create_application() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.environment)

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )
    application.add_middleware(SecurityHeadersMiddleware)
    application.include_router(api_router, prefix="/api/v1")
    application.add_api_route(
        "/health",
        health,
        methods=["GET"],
        include_in_schema=False,
        operation_id="root_health_check",
    )
    application.add_api_route(
        "/ready",
        ready,
        methods=["GET"],
        include_in_schema=False,
        operation_id="root_readiness_check",
    )
    register_error_handlers(application)
    return application


app = create_application()