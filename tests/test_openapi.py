import unittest

from src.main import app


class OpenApiTests(unittest.TestCase):
    def test_api_metadata_and_resource_tags_are_documented(self) -> None:
        schema = app.openapi()
        self.assertEqual(schema["info"]["title"], "Raízes do Nordeste API")
        self.assertTrue(schema["info"]["description"])
        self.assertTrue(schema["info"]["version"])
        tag_names = {tag["name"] for tag in schema["tags"]}
        self.assertTrue(
            {"Autenticação", "Pedidos", "Estoque", "Unidades", "Auditoria"}
            <= tag_names
        )

    def test_sensitive_routes_document_error_contract(self) -> None:
        paths = app.openapi()["paths"]
        create_responses = paths["/pedidos"]["post"]["responses"]
        for status_code in ("401", "403", "404", "409", "422"):
            self.assertIn(status_code, create_responses)
        payment_responses = paths["/pedidos/{order_id}/pagamento"]["post"][
            "responses"
        ]
        self.assertIn("502", payment_responses)
        self.assertIn("503", payment_responses)
        audit_responses = paths["/auditoria"]["get"]["responses"]
        self.assertIn("403", audit_responses)
        self.assertIn("422", audit_responses)

    def test_registration_response_does_not_expose_password_hash(self) -> None:
        schema = app.openapi()
        user_response = schema["components"]["schemas"]["UserResponse"]
        self.assertNotIn("senha_hash", user_response["properties"])


if __name__ == "__main__":
    unittest.main()
