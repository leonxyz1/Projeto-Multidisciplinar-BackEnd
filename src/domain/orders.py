from enum import Enum


class OrderChannel(str, Enum):
    APP = "APP"
    TOTEM = "TOTEM"
    BALCAO = "BALCAO"
    PICKUP = "PICKUP"
    WEB = "WEB"


class OrderStatus(str, Enum):
    AGUARDANDO_PAGAMENTO = "AGUARDANDO_PAGAMENTO"
    EM_PREPARO = "EM_PREPARO"
    PRONTO = "PRONTO"
    ENTREGUE = "ENTREGUE"
    CANCELADO = "CANCELADO"


TRANSICOES: dict[str, frozenset[str]] = {
    OrderStatus.AGUARDANDO_PAGAMENTO.value: frozenset(
        {OrderStatus.EM_PREPARO.value, OrderStatus.CANCELADO.value}
    ),
    OrderStatus.EM_PREPARO.value: frozenset({OrderStatus.PRONTO.value}),
    OrderStatus.PRONTO.value: frozenset({OrderStatus.ENTREGUE.value}),
    OrderStatus.ENTREGUE.value: frozenset(),
    OrderStatus.CANCELADO.value: frozenset(),
}

PERFIS_POR_TRANSICAO: dict[tuple[str, str], frozenset[str]] = {
    (
        OrderStatus.AGUARDANDO_PAGAMENTO.value,
        OrderStatus.EM_PREPARO.value,
    ): frozenset({"PAGAMENTO"}),
    (
        OrderStatus.AGUARDANDO_PAGAMENTO.value,
        OrderStatus.CANCELADO.value,
    ): frozenset({"CLIENTE", "ATENDENTE", "GERENTE"}),
    (
        OrderStatus.EM_PREPARO.value,
        OrderStatus.PRONTO.value,
    ): frozenset({"COZINHA"}),
    (
        OrderStatus.PRONTO.value,
        OrderStatus.ENTREGUE.value,
    ): frozenset({"ATENDENTE"}),
}


def pode_transitar(origem: str, destino: str, perfil: str) -> bool:
    return (
        destino in TRANSICOES.get(origem, frozenset())
        and perfil in PERFIS_POR_TRANSICAO.get((origem, destino), frozenset())
    )


def can_pay_order(status: str) -> bool:
    return pode_transitar(
        status,
        OrderStatus.EM_PREPARO.value,
        "PAGAMENTO",
    )
