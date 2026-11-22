from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.api.dependencies import exigir_perfis, get_db
from src.api.errors import BusinessError
from src.infrastructure.audit import registrar_auditoria
from src.infrastructure.database.models import (
    EstoqueModel,
    ItemPedidoModel,
    PedidoModel,
    ProdutoModel,
    UnidadeModel,
    UsuarioModel,
)


router = APIRouter(prefix="/pedidos", tags=["Pedidos"])
CENTAVO = Decimal("0.01")


class CanalPedido(str, Enum):
    BALCAO = "BALCAO"
    DELIVERY = "DELIVERY"
    APP = "APP"


class StatusPedido(str, Enum):
    AGUARDANDO_PAGAMENTO = "AGUARDANDO_PAGAMENTO"
    EM_PREPARO = "EM_PREPARO"
    PRONTO = "PRONTO"
    ENTREGUE = "ENTREGUE"
    CANCELADO = "CANCELADO"


class ItemPedidoInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    produto_id: int = Field(alias="produtoId", gt=0)
    quantidade: int = Field(gt=0)


class PedidoCreateInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    canal_pedido: CanalPedido = Field(alias="canalPedido")
    unidade_id: int = Field(alias="unidadeId", gt=0)
    itens: list[ItemPedidoInput] = Field(min_length=1)
    cliente_id: int | None = Field(default=None, alias="clienteId", gt=0)

    @field_validator("itens")
    @classmethod
    def reject_duplicate_products(
        cls, items: list[ItemPedidoInput]
    ) -> list[ItemPedidoInput]:
        product_ids = [item.produto_id for item in items]
        if len(product_ids) != len(set(product_ids)):
            raise ValueError("Não repita produtos na lista de itens")
        return items


class ItemPedidoResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    produto_id: int = Field(alias="produtoId")
    nome_produto: str = Field(alias="nomeProduto")
    quantidade: int
    preco_unitario: Decimal = Field(alias="precoUnitario")
    subtotal: Decimal


class PedidoResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    cliente_id: int | None = Field(alias="clienteId")
    criado_por_id: int = Field(alias="criadoPorId")
    unidade_id: int = Field(alias="unidadeId")
    canal_pedido: CanalPedido = Field(alias="canalPedido")
    status: StatusPedido
    valor_bruto: Decimal = Field(alias="valorBruto")
    valor_desconto: Decimal = Field(alias="valorDesconto")
    total: Decimal
    criado_em: str = Field(alias="criadoEm")
    itens: list[ItemPedidoResponse]


class PedidoPageMeta(BaseModel):
    page: int
    limit: int
    total: int


class PaginatedPedidosResponse(BaseModel):
    items: list[PedidoResponse]
    meta: PedidoPageMeta


def _money(amount: Decimal) -> Decimal:
    return amount.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def _serialize_orders(
    session: Session, orders: list[PedidoModel]
) -> list[PedidoResponse]:
    items_by_order: dict[int, list[ItemPedidoResponse]] = {}
    if orders:
        item_rows = session.execute(
            select(ItemPedidoModel, ProdutoModel.nome)
            .join(ProdutoModel, ProdutoModel.id == ItemPedidoModel.produto_id)
            .where(
                ItemPedidoModel.pedido_id.in_([order.id for order in orders])
            )
            .order_by(ItemPedidoModel.pedido_id, ItemPedidoModel.produto_id)
        ).all()
        for item, name in item_rows:
            items_by_order.setdefault(item.pedido_id, []).append(
                ItemPedidoResponse(
                    produto_id=item.produto_id,
                    nome_produto=name,
                    quantidade=item.quantidade,
                    preco_unitario=item.preco_unitario,
                    subtotal=item.subtotal,
                )
            )

    return [
        PedidoResponse(
            id=order.id,
            cliente_id=order.cliente_id,
            criado_por_id=order.criado_por_id,
            unidade_id=order.unidade_id,
            canal_pedido=order.canal_pedido,
            status=order.status,
            valor_bruto=order.valor_bruto,
            valor_desconto=order.valor_desconto,
            total=order.total,
            criado_em=order.created_at.isoformat(),
            itens=items_by_order.get(order.id, []),
        )
        for order in orders
    ]


def _serialize_order(session: Session, order: PedidoModel) -> PedidoResponse:
    return _serialize_orders(session, [order])[0]


@router.post(
    "",
    response_model=PedidoResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_order(
    payload: PedidoCreateInput,
    session: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        UsuarioModel, Depends(exigir_perfis("CLIENTE", "ATENDENTE"))
    ],
) -> PedidoResponse:
    unit = session.scalar(
        select(UnidadeModel).where(
            UnidadeModel.id == payload.unidade_id,
            UnidadeModel.ativa.is_(True),
        )
    )
    if unit is None:
        raise BusinessError(
            code="UNIT_NOT_FOUND",
            message="Unidade não encontrada",
            status_code=404,
            details={"unidadeId": payload.unidade_id},
        )

    product_ids = [item.produto_id for item in payload.itens]
    products = {
        product.id: product
        for product in session.scalars(
            select(ProdutoModel).where(ProdutoModel.id.in_(product_ids))
        )
    }
    stocks = {
        stock.produto_id: stock
        for stock in session.scalars(
            select(EstoqueModel).where(
                EstoqueModel.unidade_id == unit.id,
                EstoqueModel.produto_id.in_(product_ids),
            )
        )
    }

    priced_items: list[tuple[ItemPedidoInput, ProdutoModel, Decimal]] = []
    for item in payload.itens:
        product = products.get(item.produto_id)
        stock = stocks.get(item.produto_id)
        if product is None or not product.ativo or stock is None:
            raise BusinessError(
                code="PRODUCT_NOT_FOUND_IN_UNIT",
                message="Produto não encontrado no cardápio da unidade",
                status_code=404,
                details={"produtoId": item.produto_id, "unidadeId": unit.id},
            )

        available = stock.quantidade if stock.disponivel else 0
        if item.quantidade > available:
            raise BusinessError(
                code="ESTOQUE_INSUFICIENTE",
                message="Estoque insuficiente para o produto solicitado",
                status_code=409,
                details={
                    "produtoId": item.produto_id,
                    "quantidadeSolicitada": item.quantidade,
                    "quantidadeDisponivel": available,
                },
            )

        priced_items.append((item, product, _money(product.preco)))

    if current_user.perfil == "CLIENTE":
        cliente_id = current_user.id
    else:
        cliente_id = payload.cliente_id
        if cliente_id is not None:
            customer = session.scalar(
                select(UsuarioModel).where(
                    UsuarioModel.id == cliente_id,
                    UsuarioModel.perfil == "CLIENTE",
                )
            )
            if customer is None:
                raise BusinessError(
                    code="CUSTOMER_NOT_FOUND",
                    message="Cliente não encontrado",
                    status_code=404,
                    details={"clienteId": cliente_id},
                )

    bruto = _money(
        sum(
            (
                unit_price * item.quantidade
                for item, _, unit_price in priced_items
            ),
            Decimal("0.00"),
        )
    )
    desconto = Decimal("0.00")
    total = _money(bruto - desconto)
    order = PedidoModel(
        cliente_id=cliente_id,
        criado_por_id=current_user.id,
        unidade_id=unit.id,
        canal_pedido=payload.canal_pedido.value,
        status=StatusPedido.AGUARDANDO_PAGAMENTO.value,
        valor_bruto=bruto,
        valor_desconto=desconto,
        total=total,
    )

    try:
        session.add(order)
        session.flush()
        session.add_all(
            [
                ItemPedidoModel(
                    pedido_id=order.id,
                    produto_id=product.id,
                    quantidade=item.quantidade,
                    preco_unitario=unit_price,
                    subtotal=_money(unit_price * item.quantidade),
                )
                for item, product, unit_price in priced_items
            ]
        )
        registrar_auditoria(
            session,
            usuario_id=current_user.id,
            unidade_id=unit.id,
            acao="PEDIDO_CRIADO",
            entidade="PEDIDO",
            entidade_id=order.id,
            detalhes={
                "status": StatusPedido.AGUARDANDO_PAGAMENTO.value,
                "quantidadeItens": len(priced_items),
                "total": str(total),
            },
        )
        session.commit()
    except Exception:
        session.rollback()
        raise

    return _serialize_order(session, order)


@router.get("", response_model=PaginatedPedidosResponse)
def list_orders(
    session: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        UsuarioModel,
        Depends(
            exigir_perfis("CLIENTE", "ATENDENTE", "GERENTE", "COZINHA")
        ),
    ],
    canal_pedido: Annotated[CanalPedido | None, Query(alias="canalPedido")] = None,
    status_pedido: Annotated[StatusPedido | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> PaginatedPedidosResponse:
    filters = []
    if canal_pedido is not None:
        filters.append(PedidoModel.canal_pedido == canal_pedido.value)
    if status_pedido is not None:
        filters.append(PedidoModel.status == status_pedido.value)

    if current_user.perfil == "CLIENTE":
        filters.append(PedidoModel.cliente_id == current_user.id)
    elif current_user.perfil == "COZINHA":
        if (
            status_pedido is not None
            and status_pedido is not StatusPedido.EM_PREPARO
        ):
            raise BusinessError(
                code="KITCHEN_QUEUE_ONLY",
                message="Cozinha pode consultar apenas pedidos em preparo",
                status_code=403,
            )
        filters.append(
            PedidoModel.status == StatusPedido.EM_PREPARO.value
        )

    total = session.scalar(
        select(func.count(PedidoModel.id)).where(*filters)
    )
    orders = list(
        session.scalars(
            select(PedidoModel)
            .where(*filters)
            .order_by(PedidoModel.created_at.desc(), PedidoModel.id.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
    )
    return PaginatedPedidosResponse(
        items=_serialize_orders(session, orders),
        meta=PedidoPageMeta(page=page, limit=limit, total=total or 0),
    )


@router.get("/{order_id}", response_model=PedidoResponse)
def get_order(
    order_id: int,
    session: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        UsuarioModel,
        Depends(
            exigir_perfis("CLIENTE", "ATENDENTE", "GERENTE", "COZINHA")
        ),
    ],
) -> PedidoResponse:
    order = session.get(PedidoModel, order_id)
    if order is None or (
        current_user.perfil == "CLIENTE"
        and order.cliente_id != current_user.id
    ):
        raise BusinessError(
            code="ORDER_NOT_FOUND",
            message="Pedido não encontrado",
            status_code=404,
            details={"pedidoId": order_id},
        )
    if (
        current_user.perfil == "COZINHA"
        and order.status != StatusPedido.EM_PREPARO.value
    ):
        raise BusinessError(
            code="ORDER_NOT_FOUND",
            message="Pedido não encontrado",
            status_code=404,
            details={"pedidoId": order_id},
        )
    return _serialize_order(session, order)
