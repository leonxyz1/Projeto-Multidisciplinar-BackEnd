from dataclasses import dataclass
from decimal import Decimal


class GatewayUnavailableError(Exception):
    pass


@dataclass(frozen=True)
class GatewayResult:
    approved: bool
    message: str
    payload: dict[str, object]


class MockPaymentGateway:
    def charge(self, amount: Decimal, payment_form: str) -> GatewayResult:
        if payment_form == "FALHA_GATEWAY":
            raise GatewayUnavailableError("Gateway mock indisponível")

        approved = payment_form == "PIX"
        result = "APROVADO" if approved else "RECUSADO"
        message = (
            "Pagamento aprovado"
            if approved
            else "Pagamento recusado pelo gateway"
        )
        return GatewayResult(
            approved=approved,
            message=message,
            payload={
                "gateway": "mock",
                "resultado": result,
                "valor": str(amount),
                "formaPagamento": payment_form,
            },
        )


mock_payment_gateway = MockPaymentGateway()
