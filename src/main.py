from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.api.auth import router as auth_router
from src.api.errors import (
    BusinessError,
    business_error_handler,
    error_response,
    http_exception_handler,
    validation_error_handler,
)
from src.api.orders import router as orders_router
from src.api.stock import router as stock_router
from src.api.units import router as units_router
from src.infrastructure.security import get_jwt_secret


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    get_jwt_secret()
    yield


app = FastAPI(title="Raízes do Nordeste API", lifespan=lifespan)
app.add_exception_handler(BusinessError, business_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Erro interno ao processar a requisição")
    return error_response(
        request,
        code="INTERNAL_SERVER_ERROR",
        message="Erro interno do servidor",
        status_code=500,
    )


app.include_router(auth_router)
app.include_router(orders_router)
app.include_router(stock_router)
app.include_router(units_router)


@app.get("/saude")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
