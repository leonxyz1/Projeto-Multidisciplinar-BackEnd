from collections.abc import Generator
import os
import unittest
from unittest.mock import patch

import bcrypt
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.api.dependencies import get_db
from src.infrastructure.database.connection import Base
from src.infrastructure.database.models import UsuarioModel
from src.main import app


JWT_SECRET = "test-secret-for-auth-api-tests-32-bytes"


class AuthApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
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

    def register_client(self) -> dict[str, object]:
        response = self.client.post(
            "/auth/cadastro",
            json={
                "nome": "Cliente de Teste",
                "email": "cliente@example.com",
                "senha": "senha-segura-123",
                "perfil": "GERENTE",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def login(self, email: str) -> str:
        response = self.client.post(
            "/auth/login",
            data={"username": email, "password": "senha-segura-123"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["token_type"], "bearer")
        self.assertEqual(body["expires_in"], 1800)
        return body["access_token"]

    def test_registration_hashes_password_and_does_not_allow_role_escalation(self) -> None:
        body = self.register_client()
        self.assertEqual(body["perfil"], "CLIENTE")
        self.assertNotIn("senha_hash", body)

        with Session(self.engine) as session:
            user = session.scalar(
                select(UsuarioModel).where(
                    UsuarioModel.email == "cliente@example.com"
                )
            )
            self.assertNotEqual(user.senha_hash, "senha-segura-123")
            self.assertTrue(
                bcrypt.checkpw(
                    b"senha-segura-123", user.senha_hash.encode("utf-8")
                )
            )

        duplicate = self.client.post(
            "/auth/cadastro",
            json={
                "nome": "Outro Cliente",
                "email": "CLIENTE@example.com",
                "senha": "senha-segura-123",
                "perfil": "GERENTE",
            },
        )
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(duplicate.json()["error"], "EMAIL_ALREADY_REGISTERED")

    def test_login_jwt_and_bearer_authentication(self) -> None:
        self.register_client()
        token = self.login("cliente@example.com")

        claims = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        self.assertEqual(claims["perfil"], "CLIENTE")
        self.assertTrue(claims["sub"].isdigit())

        me = self.client.get(
            "/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["email"], "cliente@example.com")
        bad_password = self.client.post(
            "/auth/login",
            data={"username": "cliente@example.com", "password": "senha-incorreta"},
        )
        self.assertEqual(bad_password.status_code, 401)

        self.assertEqual(self.client.get("/auth/me").status_code, 401)
        invalid = self.client.get(
            "/auth/me", headers={"Authorization": "Bearer invalid-token"}
        )
        self.assertEqual(invalid.status_code, 401)

    def test_validation_and_http_errors_use_standard_response(self) -> None:
        invalid_body = self.client.post("/auth/cadastro", json={})
        self.assertEqual(invalid_body.status_code, 422)
        validation_error = invalid_body.json()
        self.assertEqual(
            set(validation_error),
            {"error", "message", "details", "timestamp", "path"},
        )
        self.assertEqual(validation_error["error"], "VALIDATION_ERROR")
        self.assertEqual(validation_error["path"], "/auth/cadastro")
        self.assertTrue(validation_error["details"])

        unauthorized = self.client.get("/auth/me")
        self.assertEqual(unauthorized.status_code, 401)
        auth_error = unauthorized.json()
        self.assertEqual(
            set(auth_error),
            {"error", "message", "details", "timestamp", "path"},
        )
        self.assertEqual(auth_error["error"], "HTTP_401")
        self.assertEqual(auth_error["path"], "/auth/me")
        self.assertEqual(unauthorized.headers["www-authenticate"], "Bearer")

    def test_stock_requires_manager_profile(self) -> None:
        self.register_client()
        client_token = self.login("cliente@example.com")
        forbidden = self.client.get(
            "/estoque", headers={"Authorization": f"Bearer {client_token}"}
        )
        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(forbidden.json()["error"], "HTTP_403")

        with Session(self.engine) as session:
            session.add(
                UsuarioModel(
                    nome="Gerente de Teste",
                    email="gerente@example.com",
                    senha_hash=bcrypt.hashpw(
                        b"senha-segura-123", bcrypt.gensalt()
                    ).decode("utf-8"),
                    perfil="GERENTE",
                )
            )
            session.commit()

        manager_token = self.login("gerente@example.com")
        allowed = self.client.get(
            "/estoque", headers={"Authorization": f"Bearer {manager_token}"}
        )
        self.assertEqual(allowed.status_code, 200, allowed.text)


if __name__ == "__main__":
    unittest.main()
