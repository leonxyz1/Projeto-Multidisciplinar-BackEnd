from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.api.dependencies import exigir_perfis, get_db
from src.api.errors import BusinessError, error_responses
from src.api.stock import StockResponse
from src.infrastructure.database.models import (
    EstoqueModel,
    ProdutoModel,
    UnidadeModel,
)


router = APIRouter(prefix="/unidades", tags=["Unidades"])


class UnitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    endereco: str
    ativa: bool


class UnitProductResponse(BaseModel):
    id: int
    sku: str
    nome: str
    descricao: str | None
    preco: Decimal
    sazonal: bool
    quantidade: int
    disponivel: bool


class ProductPageMeta(BaseModel):
    page: int
    limit: int
    total: int


class PaginatedProductsResponse(BaseModel):
    items: list[UnitProductResponse]
    meta: ProductPageMeta


def _ensure_active_unit(session: Session, unit_id: int) -> None:
    unit_exists = session.scalar(
        select(UnidadeModel.id).where(
            UnidadeModel.id == unit_id,
            UnidadeModel.ativa.is_(True),
        )
    )
    if unit_exists is None:
        raise BusinessError(
            code="UNIT_NOT_FOUND",
            message="Unidade não encontrada",
            status_code=404,
            details={"unidade_id": unit_id},
        )


@router.get(
    "",
    response_model=list[UnitResponse],
    responses=error_responses(500),
)
def list_active_units(
    session: Annotated[Session, Depends(get_db)],
) -> list[UnidadeModel]:
    return list(
        session.scalars(
            select(UnidadeModel)
            .where(UnidadeModel.ativa.is_(True))
            .order_by(UnidadeModel.id)
        )
    )


@router.get(
    "/{unit_id}/produtos",
    response_model=PaginatedProductsResponse,
    responses=error_responses(404, 422, 500),
)
def list_unit_products(
    unit_id: int,
    session: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> PaginatedProductsResponse:
    _ensure_active_unit(session, unit_id)
    filters = (
        EstoqueModel.unidade_id == unit_id,
        ProdutoModel.ativo.is_(True),
    )
    total = session.scalar(
        select(func.count(ProdutoModel.id))
        .join(EstoqueModel, EstoqueModel.produto_id == ProdutoModel.id)
        .where(*filters)
    )
    rows = session.execute(
        select(ProdutoModel, EstoqueModel)
        .join(EstoqueModel, EstoqueModel.produto_id == ProdutoModel.id)
        .where(*filters)
        .order_by(ProdutoModel.id)
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()
    items = [
        UnitProductResponse(
            id=product.id,
            sku=product.sku,
            nome=product.nome,
            descricao=product.descricao,
            preco=product.preco,
            sazonal=product.sazonal,
            quantidade=stock.quantidade,
            disponivel=stock.disponivel and stock.quantidade > 0,
        )
        for product, stock in rows
    ]
    return PaginatedProductsResponse(
        items=items,
        meta=ProductPageMeta(page=page, limit=limit, total=total or 0),
    )


@router.get(
    "/{unit_id}/estoque",
    response_model=list[StockResponse],
    dependencies=[Depends(exigir_perfis("ATENDENTE", "GERENTE"))],
    responses=error_responses(401, 403, 404, 500),
)
def list_unit_stock(
    unit_id: int,
    session: Annotated[Session, Depends(get_db)],
) -> list[EstoqueModel]:
    _ensure_active_unit(session, unit_id)
    return list(
        session.scalars(
            select(EstoqueModel)
            .where(EstoqueModel.unidade_id == unit_id)
            .order_by(EstoqueModel.produto_id)
        )
    )
