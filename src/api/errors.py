from datetime import UTC, datetime
from typing import Any

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class BusinessError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


def error_response(
    request: Request,
    *,
    code: str,
    message: str,
    status_code: int,
    details: Any = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        headers=headers,
        content=jsonable_encoder(
            {
                "error": code,
                "message": message,
                "details": details,
                "timestamp": datetime.now(UTC).isoformat(),
                "path": request.url.path,
            }
        ),
    )


async def business_error_handler(
    request: Request, exc: BusinessError
) -> JSONResponse:
    return error_response(
        request,
        code=exc.code,
        message=exc.message,
        status_code=exc.status_code,
        details=exc.details,
    )


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    details = [
        {"loc": error["loc"], "msg": error["msg"], "type": error["type"]}
        for error in exc.errors()
    ]
    return error_response(
        request,
        code="VALIDATION_ERROR",
        message="Erro de validação da requisição",
        status_code=422,
        details=details,
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    message = exc.detail if isinstance(exc.detail, str) else "Erro na requisição"
    details = None if isinstance(exc.detail, str) else exc.detail
    return error_response(
        request,
        code=f"HTTP_{exc.status_code}",
        message=message,
        status_code=exc.status_code,
        details=details,
        headers=exc.headers,
    )
