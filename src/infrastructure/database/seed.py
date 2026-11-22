from decimal import Decimal
from typing import TypeVar

import bcrypt
from sqlalchemy import select
from sqlalchemy.orm import Session

from .connection import SessionLocal
from .models import (
    EstoqueModel,
    FidelidadeModel,
    ProdutoModel,
    UnidadeModel,
    UsuarioModel,
)

ModelT = TypeVar("ModelT")


def _get_or_create(
    session: Session,
    model: type[ModelT],
    lookup: dict[str, object],
    values: dict[str, object],
) -> ModelT:
    instance = session.scalar(select(model).filter_by(**lookup))
    if instance is None:
        instance = model(**lookup, **values)
        session.add(instance)
        session.flush()
    return instance


def seed_data(session: Session) -> None:
    centro = _get_or_create(
        session,
        UnidadeModel,
        {"nome": "Unidade Centro"},
        {"endereco": "Rua Central, 100", "ativa": True},
    )
    shopping = _get_or_create(
        session,
        UnidadeModel,
        {"nome": "Unidade Shopping"},
        {"endereco": "Avenida do Shopping, 200", "ativa": True},
    )

    senha_hash = bcrypt.hashpw(b"senha123", bcrypt.gensalt()).decode("utf-8")
    cliente = _get_or_create(
        session,
        UsuarioModel,
        {"email": "cliente@teste.local"},
        {
            "nome": "Cliente Teste",
            "unidade_id": None,
            "senha_hash": senha_hash,
            "perfil": "CLIENTE",
        },
    )
    _get_or_create(
        session,
        UsuarioModel,
        {"email": "atendente@teste.local"},
        {
            "nome": "Atendente Teste",
            "unidade_id": centro.id,
            "senha_hash": senha_hash,
            "perfil": "ATENDENTE",
        },
    )
    _get_or_create(
        session,
        UsuarioModel,
        {"email": "gerente@teste.local"},
        {
            "nome": "Gerente Teste",
            "unidade_id": centro.id,
            "senha_hash": senha_hash,
            "perfil": "GERENTE",
        },
    )
    fidelidade = session.scalar(
        select(FidelidadeModel).where(FidelidadeModel.usuario_id == cliente.id)
    )
    if fidelidade is None:
        session.add(
            FidelidadeModel(
                usuario_id=cliente.id,
                aceita_fidelidade=True,
                pontos_saldo=100,
            )
        )

    produtos = (
        {
            "sku": "TESTE-001",
            "nome": "Hambúrguer Clássico",
            "descricao": "Hambúrguer de teste",
            "preco": Decimal("39.90"),
            "sazonal": False,
            "ativo": True,
        },
        {
            "sku": "TESTE-002",
            "nome": "Combo Família",
            "descricao": "Combo de teste",
            "preco": Decimal("59.90"),
            "sazonal": True,
            "ativo": True,
        },
        {
            "sku": "TESTE-003",
            "nome": "Sobremesa do Dia",
            "descricao": "Sobremesa de teste",
            "preco": Decimal("12.50"),
            "sazonal": False,
            "ativo": True,
        },
    )
    estoque_inicial = (50, 2, 0)
    for dados, quantidade in zip(produtos, estoque_inicial, strict=True):
        produto = _get_or_create(
            session,
            ProdutoModel,
            {"sku": dados["sku"]},
            {key: value for key, value in dados.items() if key != "sku"},
        )
        estoque = session.get(EstoqueModel, (centro.id, produto.id))
        if estoque is None:
            session.add(
                EstoqueModel(
                    unidade_id=centro.id,
                    produto_id=produto.id,
                    quantidade=quantidade,
                    disponivel=quantidade > 0,
                )
            )
        shopping_estoque = session.get(EstoqueModel, (shopping.id, produto.id))
        if shopping_estoque is None:
            session.add(
                EstoqueModel(
                    unidade_id=shopping.id,
                    produto_id=produto.id,
                    quantidade=quantidade,
                    disponivel=quantidade > 0,
                )
            )


def main() -> None:
    with SessionLocal.begin() as session:
        seed_data(session)


if __name__ == "__main__":
    main()
