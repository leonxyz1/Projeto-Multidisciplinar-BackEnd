from enum import Enum


class OrderChannel(str, Enum):
    BALCAO = "BALCAO"
    DELIVERY = "DELIVERY"
    APP = "APP"


class OrderStatus(str, Enum):
    AGUARDANDO_PAGAMENTO = "AGUARDANDO_PAGAMENTO"
    EM_PREPARO = "EM_PREPARO"
    PRONTO = "PRONTO"
    ENTREGUE = "ENTREGUE"
    CANCELADO = "CANCELADO"


def can_pay_order(status: str) -> bool:
    return status == OrderStatus.AGUARDANDO_PAGAMENTO.value
