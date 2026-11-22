from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.dependencies import exigir_perfis, get_db
from src.api.errors import error_responses
from src.infrastructure.database.models import AuditoriaModel


router = APIRouter(prefix="/auditoria", tags=["Auditoria"])


class AuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    usuario_id: int
    unidade_id: int
    acao: str
    entidade: str
    entidade_id: int
    detalhes: dict[str, object]
    created_at: datetime


@router.get(
    "",
    response_model=list[AuditResponse],
    dependencies=[Depends(exigir_perfis("GERENTE"))],
    responses=error_responses(401, 403, 422, 500),
)
def list_audit(
    session: Annotated[Session, Depends(get_db)],
    entidade: Annotated[str | None, Query(min_length=1, max_length=60)] = None,
    entidade_id: Annotated[int | None, Query(ge=1)] = None,
) -> list[AuditoriaModel]:
    filters = []
    if entidade is not None:
        filters.append(AuditoriaModel.entidade == entidade)
    if entidade_id is not None:
        filters.append(AuditoriaModel.entidade_id == entidade_id)
    return list(
        session.scalars(
            select(AuditoriaModel)
            .where(*filters)
            .order_by(AuditoriaModel.created_at.desc(), AuditoriaModel.id.desc())
        )
    )
