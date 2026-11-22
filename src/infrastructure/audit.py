from sqlalchemy.orm import Session

from src.infrastructure.database.models import AuditoriaModel


def registrar_auditoria(
    session: Session,
    *,
    usuario_id: int,
    unidade_id: int,
    acao: str,
    entidade: str,
    entidade_id: int,
    detalhes: dict[str, object],
) -> AuditoriaModel:
    record = AuditoriaModel(
        usuario_id=usuario_id,
        unidade_id=unidade_id,
        acao=acao,
        entidade=entidade,
        entidade_id=entidade_id,
        detalhes=detalhes,
    )
    session.add(record)
    return record
