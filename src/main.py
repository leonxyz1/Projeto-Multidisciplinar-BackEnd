from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.api.audit import router as audit_router
from src.api.auth import router as auth_router
from src.api.errors import (
    BusinessError,
    business_error_handler,
    error_response,
    error_responses,
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


app = FastAPI(
    title="Raízes do Nordeste API",
    description=(
        "API para autenticação, consulta de cardápios e estoques por unidade, "
        "criação e acompanhamento de pedidos, pagamentos mock e auditoria."
    ),
    version="1.0.0",
    openapi_tags=[
        {"name": "Autenticação", "description": "Cadastro, login e identidade."},
        {"name": "Pedidos", "description": "Criação, pagamento e status de pedidos."},
        {"name": "Estoque", "description": "Consulta de estoque."},
        {"name": "Unidades", "description": "Unidades e cardápios por unidade."},
        {"name": "Auditoria", "description": "Eventos sensíveis, visíveis a gerentes."},
        {"name": "Saúde", "description": "Verificação de disponibilidade da API."},
    ],
    lifespan=lifespan,
)
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
app.include_router(audit_router)
app.include_router(orders_router)
app.include_router(stock_router)
app.include_router(units_router)


@app.get("/saude", tags=["Saúde"], responses=error_responses(500))
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
