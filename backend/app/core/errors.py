from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.exc import IntegrityError


class APIError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail


async def api_error_handler(_: Request, error: APIError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={"error": {"detail": error.detail}},
    )


async def validation_error_handler(
    _: Request, error: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"error": {"detail": jsonable_encoder(error.errors())}},
    )


async def database_conflict_handler(_: Request, __: IntegrityError) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={"error": {"detail": "The requested account conflicts with existing data"}},
    )


def register_error_handlers(application: Any) -> None:
    application.add_exception_handler(APIError, api_error_handler)
    application.add_exception_handler(RequestValidationError, validation_error_handler)
    application.add_exception_handler(IntegrityError, database_conflict_handler)