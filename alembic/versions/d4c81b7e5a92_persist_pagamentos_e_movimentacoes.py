"""persiste payloads de pagamento e movimentos de estoque

Revision ID: d4c81b7e5a92
Revises: b82df75a1c20
Create Date: 2026-11-22 15:23:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4c81b7e5a92"
down_revision: Union[str, Sequence[str], None] = "b82df75a1c20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("pagamentos", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "payload",
                sa.JSON(),
                server_default=sa.text("'{}'"),
                nullable=False,
            )
        )

    op.create_table(
        "movimentacoes_estoque",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("pedido_id", sa.Integer(), nullable=False),
        sa.Column("unidade_id", sa.Integer(), nullable=False),
        sa.Column("produto_id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("quantidade", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["pedido_id"], ["pedidos.id"]),
        sa.ForeignKeyConstraint(["produto_id"], ["produtos.id"]),
        sa.ForeignKeyConstraint(["unidade_id"], ["unidades.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("movimentacoes_estoque")
    with op.batch_alter_table("pagamentos", schema=None) as batch_op:
        batch_op.drop_column("payload")
