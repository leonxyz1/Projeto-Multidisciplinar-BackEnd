import unittest
from decimal import Decimal

import bcrypt
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from src.infrastructure.database.connection import Base
from src.infrastructure.database.models import (
    EstoqueModel,
    FidelidadeModel,
    PedidoModel,
    ProdutoModel,
    UnidadeModel,
    UsuarioModel,
)
from src.infrastructure.database.seed import seed_data


class DatabaseSeedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_seed_is_idempotent_and_preserves_decimal_prices(self) -> None:
        with self.session.begin():
            seed_data(self.session)
        with self.session.begin():
            seed_data(self.session)

        self.assertEqual(
            self.session.scalar(select(func.count()).select_from(UnidadeModel)), 2
        )
        self.assertEqual(
            self.session.scalar(select(func.count()).select_from(UsuarioModel)), 3
        )
        self.assertEqual(
            self.session.scalar(select(func.count()).select_from(ProdutoModel)), 3
        )
        self.assertEqual(
            self.session.scalar(select(func.count()).select_from(EstoqueModel)), 6
        )
        self.assertEqual(
            self.session.scalar(select(func.count()).select_from(FidelidadeModel)), 1
        )
        self.assertEqual(
            self.session.scalar(
                select(ProdutoModel.preco).where(ProdutoModel.sku == "TESTE-001")
            ),
            Decimal("39.90"),
        )
        self.assertEqual(
            self.session.scalar(
                select(func.count())
                .select_from(ProdutoModel)
                .where(ProdutoModel.sazonal.is_(True))
            ),
            1,
        )
        loyalty = self.session.scalar(select(FidelidadeModel))
        self.assertTrue(loyalty.aceita_fidelidade)
        self.assertEqual(loyalty.pontos_saldo, 100)

        center = self.session.scalar(
            select(UnidadeModel).where(UnidadeModel.nome == "Unidade Centro")
        )
        unavailable = self.session.scalar(
            select(EstoqueModel).where(
                EstoqueModel.unidade_id == center.id, EstoqueModel.quantidade == 0
            )
        )
        self.assertFalse(unavailable.disponivel)
        self.assertEqual(unavailable.unidade_id, center.id)
        self.assertEqual(
            self.session.scalar(
                select(EstoqueModel.quantidade).where(
                    EstoqueModel.unidade_id == center.id,
                    EstoqueModel.produto_id
                    == self.session.scalar(
                        select(ProdutoModel.id).where(
                            ProdutoModel.sku == "TESTE-001"
                        )
                    ),
                )
            ),
            50,
        )

        client = self.session.scalar(
            select(UsuarioModel).where(UsuarioModel.email == "cliente@teste.local")
        )
        self.assertIsNone(client.unidade_id)
        self.assertTrue(bcrypt.checkpw(b"senha123", client.senha_hash.encode()))

    def test_order_relationships_distinguish_customer_and_creator(self) -> None:
        with self.session.begin():
            seed_data(self.session)
        client = self.session.scalar(
            select(UsuarioModel).where(UsuarioModel.perfil == "CLIENTE")
        )
        attendant = self.session.scalar(
            select(UsuarioModel).where(UsuarioModel.perfil == "ATENDENTE")
        )
        unit = self.session.scalar(select(UnidadeModel))

        order = PedidoModel(
            cliente=client,
            criado_por=attendant,
            unidade=unit,
            canal_pedido="BALCAO",
            status="CRIADO",
            valor_bruto=Decimal("39.90"),
            total=Decimal("39.90"),
        )
        self.session.add(order)
        self.session.flush()

        self.assertEqual(order.cliente.email, "cliente@teste.local")
        self.assertEqual(order.criado_por.email, "atendente@teste.local")


if __name__ == "__main__":
    unittest.main()
