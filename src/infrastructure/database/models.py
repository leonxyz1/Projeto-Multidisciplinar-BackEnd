from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .connection import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UnidadeModel(Base):
    __tablename__ = "unidades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    endereco: Mapped[str] = mapped_column(String(255), nullable=False)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class UsuarioModel(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    unidade_id: Mapped[int | None] = mapped_column(
        ForeignKey("unidades.id"), nullable=True
    )
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(
        String(150), unique=True, index=True, nullable=False
    )
    senha_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    perfil: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class ProdutoModel(Base):
    __tablename__ = "produtos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    preco: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    sazonal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class EstoqueModel(Base):
    __tablename__ = "estoques"

    unidade_id: Mapped[int] = mapped_column(
        ForeignKey("unidades.id"), primary_key=True
    )
    produto_id: Mapped[int] = mapped_column(
        ForeignKey("produtos.id"), primary_key=True
    )
    quantidade: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    disponivel: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    unidade: Mapped[UnidadeModel] = relationship()
    produto: Mapped[ProdutoModel] = relationship()


class FidelidadeModel(Base):
    __tablename__ = "fidelidades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id"), unique=True, nullable=False
    )
    aceita_fidelidade: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    pontos_saldo: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    usuario: Mapped[UsuarioModel] = relationship()


class PedidoModel(Base):
    __tablename__ = "pedidos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cliente_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id"), nullable=True
    )
    criado_por_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id"), nullable=False
    )
    unidade_id: Mapped[int] = mapped_column(
        ForeignKey("unidades.id"), nullable=False
    )
    canal_pedido: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    valor_bruto: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    valor_desconto: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0.00"), nullable=False
    )
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    cliente: Mapped[UsuarioModel | None] = relationship(foreign_keys=[cliente_id])
    criado_por: Mapped[UsuarioModel] = relationship(foreign_keys=[criado_por_id])
    unidade: Mapped[UnidadeModel] = relationship()


class ItemPedidoModel(Base):
    __tablename__ = "itens_pedido"

    pedido_id: Mapped[int] = mapped_column(ForeignKey("pedidos.id"), primary_key=True)
    produto_id: Mapped[int] = mapped_column(ForeignKey("produtos.id"), primary_key=True)
    quantidade: Mapped[int] = mapped_column(Integer, nullable=False)
    preco_unitario: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    pedido: Mapped[PedidoModel] = relationship()
    produto: Mapped[ProdutoModel] = relationship()


class PagamentoModel(Base):
    __tablename__ = "pagamentos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pedido_id: Mapped[int] = mapped_column(ForeignKey("pedidos.id"), nullable=False)
    chave_idempotencia: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )
    metodo: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    valor: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    pedido: Mapped[PedidoModel] = relationship()
