from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.auth import router as auth_router
from src.api.stock import router as stock_router
from src.infrastructure.security import get_jwt_secret


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    get_jwt_secret()
    yield


app = FastAPI(title="Raízes do Nordeste API", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(stock_router)


@app.get("/saude")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
