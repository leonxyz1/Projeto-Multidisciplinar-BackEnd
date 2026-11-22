from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.dependencies import exigir_perfis, get_db
from src.infrastructure.database.models import EstoqueModel


router = APIRouter(prefix="/estoque", tags=["Estoque"])


class StockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    unidade_id: int
    produto_id: int
    quantidade: int
    disponivel: bool


@router.get(
    "",
    response_model=list[StockResponse],
    dependencies=[Depends(exigir_perfis("GERENTE"))],
)
def list_stock(
    session: Annotated[Session, Depends(get_db)],
) -> list[EstoqueModel]:
    return list(
        session.scalars(
            select(EstoqueModel).order_by(
                EstoqueModel.unidade_id, EstoqueModel.produto_id
            )
        )
    )
