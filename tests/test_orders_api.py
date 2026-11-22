from collections.abc import Generator
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.api.dependencies import get_db
from src.infrastructure.database.connection import Base
from src.infrastructure.database.models import (
    AuditoriaModel,
    ItemPedidoModel,
    PedidoModel,
    ProdutoModel,
    UnidadeModel,
    UsuarioModel,
)
from src.infrastructure.database.seed import seed_data
from src.main import app


JWT_SECRET = "test-secret-for-orders-api-tests-32-bytes"


class OrdersApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        with Session(self.engine) as session, session.begin():
            seed_data(session)

        self.original_overrides = app.dependency_overrides.copy()

        def override_get_db() -> Generator[Session, None, None]:
            with Session(self.engine) as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db
        self.secret_patch = patch.dict(os.environ, {"JWT_SECRET": JWT_SECRET})
        self.secret_patch.start()
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)
        app.dependency_overrides.clear()
        app.dependency_overrides.update(self.original_overrides)
        self.secret_patch.stop()
        self.engine.dispose()

    def database_id(self, model: type, **filters: object) -> int:
        with Session(self.engine) as session:
            return session.scalar(select(model.id).filter_by(**filters))

    def login(self, email: str) -> str:
        response = self.client.post(
            "/auth/login",
            data={"username": email, "password": "senha123"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["access_token"]

    def request_body(
        self,
        *,
        canal: str = "APP",
        unidade_id: int | None = None,
        produto_id: int | None = None,
        quantidade: int = 1,
        **extra: object,
    ) -> dict[str, object]:
        if unidade_id is None:
            unidade_id = self.database_id(UnidadeModel, nome="Unidade Centro")
        if produto_id is None:
            produto_id = self.database_id(ProdutoModel, sku="TESTE-001")
        return {
            "canalPedido": canal,
            "unidadeId": unidade_id,
            "itens": [
                {
                    "produtoId": produto_id,
                    "quantidade": quantidade,
                    **extra,
                }
            ],
        }

    def test_client_creates_order_using_database_price_and_auditing(self) -> None:
        token = self.login("cliente@teste.local")
        response = self.client.post(
            "/pedidos",
            json=self.request_body(quantidade=2, precoUnitario="0.01"),
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.assertEqual(body["canalPedido"], "APP")
        self.assertEqual(body["status"], "AGUARDANDO_PAGAMENTO")
        self.assertEqual(body["valorBruto"], "79.80")
        self.assertEqual(body["valorDesconto"], "0.00")
        self.assertEqual(body["total"], "79.80")
        self.assertEqual(body["itens"][0]["precoUnitario"], "39.90")

        customer_id = self.database_id(UsuarioModel, email="cliente@teste.local")
        self.assertEqual(body["clienteId"], customer_id)
        self.assertEqual(body["criadoPorId"], customer_id)

        with Session(self.engine) as session:
            order = session.get(PedidoModel, body["id"])
            self.assertEqual(order.cliente_id, customer_id)
            self.assertEqual(
                session.scalar(select(func.count()).select_from(ItemPedidoModel)),
                1,
            )
            audit = session.scalar(select(AuditoriaModel))
            self.assertEqual(audit.acao, "PEDIDO_CRIADO")
            self.assertEqual(audit.entidade_id, order.id)

    def test_order_input_missing_unit_product_or_stock_returns_defined_errors(
        self,
    ) -> None:
        token = self.login("cliente@teste.local")
        headers = {"Authorization": f"Bearer {token}"}

        missing_channel = self.client.post(
            "/pedidos",
            json={"unidadeId": 1, "itens": [{"produtoId": 1, "quantidade": 1}]},
            headers=headers,
        )
        duplicate_product_body = self.request_body()
        duplicate_product_body["itens"] = [
            {"produtoId": 1, "quantidade": 1},
            {"produtoId": 1, "quantidade": 1},
        ]
        duplicate_product = self.client.post(
            "/pedidos", json=duplicate_product_body, headers=headers
        )
        missing_unit = self.client.post(
            "/pedidos",
            json=self.request_body(unidade_id=999),
            headers=headers,
        )
        missing_product = self.client.post(
            "/pedidos",
            json=self.request_body(produto_id=999),
            headers=headers,
        )
        insufficient_stock = self.client.post(
            "/pedidos",
            json=self.request_body(
                produto_id=self.database_id(ProdutoModel, sku="TESTE-003")
            ),
            headers=headers,
        )

        self.assertEqual(missing_channel.status_code, 422)
        self.assertEqual(missing_channel.json()["error"], "VALIDATION_ERROR")
        self.assertEqual(duplicate_product.status_code, 422)
        self.assertEqual(duplicate_product.json()["error"], "VALIDATION_ERROR")
        self.assertEqual(missing_unit.status_code, 404)
        self.assertEqual(missing_unit.json()["error"], "UNIT_NOT_FOUND")
        self.assertEqual(missing_product.status_code, 404)
        self.assertEqual(
            missing_product.json()["error"], "PRODUCT_NOT_FOUND_IN_UNIT"
        )
        self.assertEqual(insufficient_stock.status_code, 409)
        self.assertEqual(
            insufficient_stock.json()["error"], "ESTOQUE_INSUFICIENTE"
        )
        self.assertEqual(
            insufficient_stock.json()["details"]["quantidadeDisponivel"], 0
        )

    def test_attendant_can_create_order_for_customer(self) -> None:
        attendant_token = self.login("atendente@teste.local")
        customer_id = self.database_id(UsuarioModel, email="cliente@teste.local")
        body = self.request_body(canal="BALCAO")
        body["clienteId"] = customer_id

        response = self.client.post(
            "/pedidos",
            json=body,
            headers={"Authorization": f"Bearer {attendant_token}"},
        )

        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["clienteId"], customer_id)
        self.assertNotEqual(
            response.json()["criadoPorId"], response.json()["clienteId"]
        )

    def test_failed_audit_rolls_back_order_and_items(self) -> None:
        token = self.login("cliente@teste.local")
        with self.assertLogs("src.main", level="ERROR"):
            with patch(
                "src.api.orders.registrar_auditoria",
                side_effect=RuntimeError("audit failure"),
            ):
                with self.assertRaises(RuntimeError):
                    self.client.post(
                        "/pedidos",
                        json=self.request_body(),
                        headers={"Authorization": f"Bearer {token}"},
                    )

        with Session(self.engine) as session:
            self.assertEqual(
                session.scalar(select(func.count()).select_from(PedidoModel)), 0
            )
            self.assertEqual(
                session.scalar(
                    select(func.count()).select_from(ItemPedidoModel)
                ),
                0,
            )


if __name__ == "__main__":
    unittest.main()
