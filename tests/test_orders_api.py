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
    EstoqueModel,
    ItemPedidoModel,
    MovimentacaoEstoqueModel,
    PagamentoModel,
    PedidoModel,
    ProdutoModel,
    UnidadeModel,
    UsuarioModel,
)
from src.infrastructure.database.seed import seed_data
from src.infrastructure.audit import registrar_auditoria
from src.infrastructure.payment_gateway import mock_payment_gateway
from src.infrastructure.security import hash_password
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
            session.add(
                UsuarioModel(
                    nome="Cozinha Teste",
                    email="cozinha@teste.local",
                    senha_hash=hash_password("senha123"),
                    perfil="COZINHA",
                )
            )

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

    def create_order(self, token: str, channel: str = "APP") -> dict[str, object]:
        response = self.client.post(
            "/pedidos",
            json=self.request_body(canal=channel),
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def pay_order(
        self, token: str, order_id: int, form: str, key: str
    ):
        return self.client.post(
            f"/pedidos/{order_id}/pagamento",
            json={"formaPagamento": form},
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": key,
            },
        )

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

    def test_customer_list_and_detail_are_scoped_to_authenticated_user(self) -> None:
        first_customer_token = self.login("cliente@teste.local")
        first_order = self.create_order(first_customer_token)

        registration = self.client.post(
            "/auth/cadastro",
            json={
                "nome": "Segundo Cliente",
                "email": "segundo@example.com",
                "senha": "senha123",
            },
        )
        self.assertEqual(registration.status_code, 201, registration.text)
        second_customer_token = self.login("segundo@example.com")
        second_order = self.create_order(second_customer_token)

        second_customer_list = self.client.get(
            f"/pedidos?clienteId={first_order['clienteId']}",
            headers={"Authorization": f"Bearer {second_customer_token}"},
        )
        self.assertEqual(second_customer_list.status_code, 200)
        body = second_customer_list.json()
        self.assertEqual(body["meta"]["total"], 1)
        self.assertEqual([item["id"] for item in body["items"]], [second_order["id"]])

        foreign_order = self.client.get(
            f"/pedidos/{first_order['id']}",
            headers={"Authorization": f"Bearer {second_customer_token}"},
        )
        own_order = self.client.get(
            f"/pedidos/{second_order['id']}",
            headers={"Authorization": f"Bearer {second_customer_token}"},
        )
        self.assertEqual(foreign_order.status_code, 404)
        self.assertEqual(foreign_order.json()["error"], "ORDER_NOT_FOUND")
        self.assertEqual(own_order.status_code, 200, own_order.text)

    def test_order_filters_pagination_and_kitchen_queue(self) -> None:
        client_token = self.login("cliente@teste.local")
        preparing = self.create_order(client_token, channel="APP")
        waiting = self.create_order(client_token, channel="BALCAO")
        with Session(self.engine) as session:
            session.get(PedidoModel, preparing["id"]).status = "EM_PREPARO"
            session.get(PedidoModel, waiting["id"]).status = "AGUARDANDO_PAGAMENTO"
            session.commit()

        manager_token = self.login("gerente@teste.local")
        filtered = self.client.get(
            "/pedidos?canalPedido=APP&status=EM_PREPARO&page=1&limit=1",
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        self.assertEqual(filtered.status_code, 200, filtered.text)
        self.assertEqual(filtered.json()["meta"]["total"], 1)
        self.assertEqual(filtered.json()["items"][0]["id"], preparing["id"])
        self.assertEqual(len(filtered.json()["items"]), 1)

        invalid_filter = self.client.get(
            "/pedidos?status=INVALIDO",
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        invalid_channel = self.client.get(
            "/pedidos?canalPedido=INVALIDO",
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        self.assertEqual(invalid_filter.status_code, 422)
        self.assertEqual(invalid_filter.json()["error"], "VALIDATION_ERROR")
        self.assertEqual(invalid_channel.status_code, 422)
        self.assertEqual(invalid_channel.json()["error"], "VALIDATION_ERROR")

        attendant_token = self.login("atendente@teste.local")
        attendant_list = self.client.get(
            "/pedidos?page=1&limit=1",
            headers={"Authorization": f"Bearer {attendant_token}"},
        )
        self.assertEqual(attendant_list.status_code, 200)
        self.assertEqual(attendant_list.json()["meta"]["total"], 2)
        attendant_second_page = self.client.get(
            "/pedidos?page=2&limit=1",
            headers={"Authorization": f"Bearer {attendant_token}"},
        )
        self.assertEqual(attendant_second_page.status_code, 200)
        self.assertEqual(len(attendant_second_page.json()["items"]), 1)
        self.assertNotEqual(
            attendant_list.json()["items"][0]["id"],
            attendant_second_page.json()["items"][0]["id"],
        )

        kitchen_token = self.login("cozinha@teste.local")
        kitchen_queue = self.client.get(
            "/pedidos", headers={"Authorization": f"Bearer {kitchen_token}"}
        )
        self.assertEqual(kitchen_queue.status_code, 200)
        self.assertEqual(kitchen_queue.json()["meta"]["total"], 1)
        self.assertEqual(
            kitchen_queue.json()["items"][0]["status"], "EM_PREPARO"
        )
        kitchen_filtered = self.client.get(
            "/pedidos?status=AGUARDANDO_PAGAMENTO",
            headers={"Authorization": f"Bearer {kitchen_token}"},
        )
        self.assertEqual(kitchen_filtered.status_code, 403)
        self.assertEqual(
            kitchen_filtered.json()["error"], "KITCHEN_QUEUE_ONLY"
        )

        hidden_order = self.client.get(
            f"/pedidos/{waiting['id']}",
            headers={"Authorization": f"Bearer {kitchen_token}"},
        )
        visible_order = self.client.get(
            f"/pedidos/{preparing['id']}",
            headers={"Authorization": f"Bearer {kitchen_token}"},
        )
        self.assertEqual(hidden_order.status_code, 404)
        self.assertEqual(visible_order.status_code, 200, visible_order.text)

    def test_approved_payment_is_idempotent_and_decrements_stock_once(self) -> None:
        token = self.login("cliente@teste.local")
        order = self.create_order(token)
        key = "approved-payment-key"

        with patch(
            "src.api.orders.mock_payment_gateway.charge",
            wraps=mock_payment_gateway.charge,
        ) as charge:
            first = self.pay_order(token, order["id"], "PIX", key)
            replay = self.pay_order(token, order["id"], "CARTAO", key)

        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(replay.status_code, 200, replay.text)
        self.assertEqual(charge.call_count, 1)
        self.assertEqual(first.json(), replay.json())
        self.assertEqual(first.json()["statusTransacao"], "APROVADO")
        self.assertEqual(first.json()["pedidoStatus"], "EM_PREPARO")

        product_id = self.database_id(ProdutoModel, sku="TESTE-001")
        unit_id = self.database_id(UnidadeModel, nome="Unidade Centro")
        with Session(self.engine) as session:
            self.assertEqual(
                session.get(EstoqueModel, (unit_id, product_id)).quantidade, 49
            )
            self.assertEqual(
                session.scalar(select(func.count()).select_from(PagamentoModel)),
                1,
            )
            movement = session.scalar(select(MovimentacaoEstoqueModel))
            self.assertEqual(movement.tipo, "SAIDA")
            self.assertEqual(movement.quantidade, 1)
            self.assertEqual(
                session.get(PedidoModel, order["id"]).status, "EM_PREPARO"
            )

        different_key = self.pay_order(token, order["id"], "PIX", "new-key")
        self.assertEqual(different_key.status_code, 409)
        self.assertEqual(different_key.json()["error"], "PAYMENT_NOT_ALLOWED")

    def test_declined_and_failed_gateway_attempts_are_persisted(self) -> None:
        token = self.login("cliente@teste.local")
        declined_order = self.create_order(token)
        with patch(
            "src.api.orders.mock_payment_gateway.charge",
            wraps=mock_payment_gateway.charge,
        ) as charge:
            declined = self.pay_order(
                token, declined_order["id"], "CARTAO", "declined-key"
            )
            declined_replay = self.pay_order(
                token, declined_order["id"], "PIX", "declined-key"
            )
        self.assertEqual(declined.status_code, 200, declined.text)
        self.assertEqual(declined.json()["statusTransacao"], "RECUSADO")
        self.assertEqual(declined_replay.json(), declined.json())
        self.assertEqual(charge.call_count, 1)

        failing_order = self.create_order(token)
        with patch(
            "src.api.orders.mock_payment_gateway.charge",
            wraps=mock_payment_gateway.charge,
        ) as charge:
            failure = self.pay_order(
                token, failing_order["id"], "FALHA_GATEWAY", "failure-key"
            )
            failure_replay = self.pay_order(
                token, failing_order["id"], "PIX", "failure-key"
            )
        self.assertEqual(failure.status_code, 502)
        self.assertEqual(failure.json()["error"], "PAYMENT_GATEWAY_ERROR")
        self.assertEqual(failure_replay.status_code, 502)
        self.assertEqual(failure_replay.json()["error"], "PAYMENT_GATEWAY_ERROR")
        self.assertEqual(charge.call_count, 1)

        with Session(self.engine) as session:
            self.assertEqual(
                session.scalar(
                    select(PedidoModel.status).where(
                        PedidoModel.id == declined_order["id"]
                    )
                ),
                "AGUARDANDO_PAGAMENTO",
            )
            self.assertEqual(
                session.scalar(
                    select(PedidoModel.status).where(
                        PedidoModel.id == failing_order["id"]
                    )
                ),
                "AGUARDANDO_PAGAMENTO",
            )
            payments = list(session.scalars(select(PagamentoModel)))
            self.assertEqual(len(payments), 2)
            self.assertTrue(all(payment.payload["gateway"] for payment in payments))

    def test_stock_race_rolls_back_all_decrements_and_keeps_order_pending(self) -> None:
        token = self.login("cliente@teste.local")
        request = self.request_body()
        request["itens"] = [
            {"produtoId": self.database_id(ProdutoModel, sku="TESTE-001"), "quantidade": 1},
            {"produtoId": self.database_id(ProdutoModel, sku="TESTE-002"), "quantidade": 1},
        ]
        created = self.client.post(
            "/pedidos",
            json=request,
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(created.status_code, 201, created.text)
        product_one_id = self.database_id(ProdutoModel, sku="TESTE-001")
        product_two_id = self.database_id(ProdutoModel, sku="TESTE-002")
        unit_id = self.database_id(UnidadeModel, nome="Unidade Centro")
        with Session(self.engine) as session:
            session.get(EstoqueModel, (unit_id, product_two_id)).quantidade = 0
            session.commit()

        response = self.pay_order(
            token, created.json()["id"], "PIX", "stock-race-key"
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"], "ESTOQUE_INSUFICIENTE")
        self.assertEqual(
            response.json()["details"]["produtoId"], product_two_id
        )

        with Session(self.engine) as session:
            self.assertEqual(
                session.get(EstoqueModel, (unit_id, product_one_id)).quantidade,
                50,
            )
            self.assertEqual(
                session.get(PedidoModel, created.json()["id"]).status,
                "AGUARDANDO_PAGAMENTO",
            )
            self.assertEqual(
                session.scalar(
                    select(func.count()).select_from(MovimentacaoEstoqueModel)
                ),
                0,
            )
            payment = session.scalar(select(PagamentoModel))
            self.assertEqual(payment.status, "ERRO_ESTOQUE")

        replay = self.pay_order(
            token, created.json()["id"], "PIX", "stock-race-key"
        )
        self.assertEqual(replay.status_code, 409)
        self.assertEqual(replay.json()["error"], "ESTOQUE_INSUFICIENTE")

    def test_payment_requires_valid_form_and_idempotency_key(self) -> None:
        token = self.login("cliente@teste.local")
        order = self.create_order(token)
        invalid_form = self.client.post(
            f"/pedidos/{order['id']}/pagamento",
            json={"formaPagamento": "INVALIDO"},
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": "invalid-form-key",
            },
        )
        missing_key = self.client.post(
            f"/pedidos/{order['id']}/pagamento",
            json={"formaPagamento": "PIX"},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(invalid_form.status_code, 422)
        self.assertEqual(invalid_form.json()["error"], "VALIDATION_ERROR")
        self.assertEqual(missing_key.status_code, 422)
        self.assertEqual(missing_key.json()["error"], "VALIDATION_ERROR")

    def test_customer_cannot_pay_another_customers_order(self) -> None:
        owner_token = self.login("cliente@teste.local")
        order = self.create_order(owner_token)
        registration = self.client.post(
            "/auth/cadastro",
            json={
                "nome": "Outro Cliente",
                "email": "pagador@example.com",
                "senha": "senha123",
            },
        )
        self.assertEqual(registration.status_code, 201, registration.text)
        other_token = self.login("pagador@example.com")

        with patch(
            "src.api.orders.mock_payment_gateway.charge",
            wraps=mock_payment_gateway.charge,
        ) as charge:
            response = self.pay_order(
                other_token, order["id"], "PIX", "foreign-order-key"
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"], "ORDER_NOT_FOUND")
        charge.assert_not_called()

    def test_approved_payment_rolls_back_if_audit_fails(self) -> None:
        token = self.login("cliente@teste.local")
        order = self.create_order(token)
        calls = 0

        def fail_first_audit(*args: object, **kwargs: object) -> None:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("audit failure")
            registrar_auditoria(*args, **kwargs)

        with patch(
            "src.api.orders.registrar_auditoria",
            side_effect=fail_first_audit,
        ):
            response = self.pay_order(
                token, order["id"], "PIX", "audit-failure-key"
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"], "PAYMENT_PROCESSING_ERROR")
        with Session(self.engine) as session:
            self.assertEqual(
                session.get(PedidoModel, order["id"]).status,
                "AGUARDANDO_PAGAMENTO",
            )
            stock = session.get(
                EstoqueModel,
                (
                    self.database_id(UnidadeModel, nome="Unidade Centro"),
                    self.database_id(ProdutoModel, sku="TESTE-001"),
                ),
            )
            self.assertEqual(stock.quantidade, 50)
            self.assertEqual(
                session.scalar(
                    select(func.count()).select_from(MovimentacaoEstoqueModel)
                ),
                0,
            )
            payment = session.scalar(select(PagamentoModel))
            self.assertEqual(payment.status, "ERRO_PROCESSAMENTO")


if __name__ == "__main__":
    unittest.main()
