from collections.abc import Generator
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.api.dependencies import get_db
from src.infrastructure.database.connection import Base
from src.infrastructure.database.models import UnidadeModel
from src.infrastructure.database.seed import seed_data
from src.main import app


JWT_SECRET = "test-secret-for-units-api-tests-32-bytes"


class UnitsApiTests(unittest.TestCase):
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
                UnidadeModel(
                    nome="Unidade Inativa",
                    endereco="Rua sem atendimento, 0",
                    ativa=False,
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

    def unit_id(self, name: str) -> int:
        with Session(self.engine) as session:
            return session.scalar(
                select(UnidadeModel.id).where(UnidadeModel.nome == name)
            )

    def login(self, email: str) -> str:
        response = self.client.post(
            "/auth/login",
            data={"username": email, "password": "senha123"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["access_token"]

    def test_active_units_and_unit_specific_paginated_menus(self) -> None:
        units = self.client.get("/unidades")
        self.assertEqual(units.status_code, 200, units.text)
        self.assertEqual(
            {unit["nome"] for unit in units.json()},
            {"Unidade Centro", "Unidade Shopping"},
        )

        center_id = self.unit_id("Unidade Centro")
        shopping_id = self.unit_id("Unidade Shopping")
        center_page = self.client.get(
            f"/unidades/{center_id}/produtos?page=1&limit=2"
        )
        center_second_page = self.client.get(
            f"/unidades/{center_id}/produtos?page=2&limit=2"
        )
        shopping_menu = self.client.get(f"/unidades/{shopping_id}/produtos")
        self.assertEqual(center_page.status_code, 200, center_page.text)
        self.assertEqual(
            center_second_page.status_code, 200, center_second_page.text
        )
        self.assertEqual(shopping_menu.status_code, 200, shopping_menu.text)

        page_body = center_page.json()
        self.assertEqual(len(page_body["items"]), 2)
        self.assertEqual(page_body["meta"], {"page": 1, "limit": 2, "total": 3})
        second_page_items = center_second_page.json()["items"]
        self.assertEqual(len(second_page_items), 1)
        self.assertNotEqual(
            page_body["items"][0]["id"], second_page_items[0]["id"]
        )

        center_items = {
            item["sku"]: item for item in self.client.get(
                f"/unidades/{center_id}/produtos"
            ).json()["items"]
        }
        shopping_items = {
            item["sku"]: item for item in shopping_menu.json()["items"]
        }
        self.assertEqual(center_items["TESTE-001"]["quantidade"], 50)
        self.assertEqual(shopping_items["TESTE-001"]["quantidade"], 25)
        self.assertFalse(center_items["TESTE-003"]["disponivel"])
        self.assertTrue(shopping_items["TESTE-003"]["disponivel"])

    def test_unit_menu_validates_pagination_and_missing_unit(self) -> None:
        unit_id = self.unit_id("Unidade Centro")
        invalid_page = self.client.get(
            f"/unidades/{unit_id}/produtos?page=0"
        )
        invalid_limit = self.client.get(
            f"/unidades/{unit_id}/produtos?limit=101"
        )
        missing_unit = self.client.get("/unidades/999/produtos")

        self.assertEqual(invalid_page.status_code, 422)
        self.assertEqual(invalid_page.json()["error"], "VALIDATION_ERROR")
        self.assertEqual(invalid_limit.status_code, 422)
        self.assertEqual(invalid_limit.json()["error"], "VALIDATION_ERROR")
        self.assertEqual(missing_unit.status_code, 404)
        self.assertEqual(missing_unit.json()["error"], "UNIT_NOT_FOUND")

    def test_unit_stock_requires_attendant_or_manager(self) -> None:
        unit_id = self.unit_id("Unidade Centro")
        path = f"/unidades/{unit_id}/estoque"

        unauthenticated = self.client.get(path)
        self.assertEqual(unauthenticated.status_code, 401)
        self.assertEqual(unauthenticated.json()["error"], "HTTP_401")

        client_token = self.login("cliente@teste.local")
        forbidden = self.client.get(
            path, headers={"Authorization": f"Bearer {client_token}"}
        )
        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(forbidden.json()["error"], "HTTP_403")

        attendant_token = self.login("atendente@teste.local")
        allowed = self.client.get(
            path, headers={"Authorization": f"Bearer {attendant_token}"}
        )
        self.assertEqual(allowed.status_code, 200, allowed.text)
        self.assertEqual(len(allowed.json()), 3)

        manager_token = self.login("gerente@teste.local")
        manager_allowed = self.client.get(
            path, headers={"Authorization": f"Bearer {manager_token}"}
        )
        self.assertEqual(manager_allowed.status_code, 200, manager_allowed.text)

        missing_unit = self.client.get(
            "/unidades/999/estoque",
            headers={"Authorization": f"Bearer {attendant_token}"},
        )
        self.assertEqual(missing_unit.status_code, 404)
        self.assertEqual(missing_unit.json()["error"], "UNIT_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
