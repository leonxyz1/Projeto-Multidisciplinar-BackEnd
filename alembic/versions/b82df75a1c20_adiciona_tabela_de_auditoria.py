"""adiciona tabela de auditoria

Revision ID: b82df75a1c20
Revises: e7a5d624908d
Create Date: 2026-11-22 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b82df75a1c20"
down_revision: Union[str, Sequence[str], None] = "e7a5d624908d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "auditorias",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("unidade_id", sa.Integer(), nullable=False),
        sa.Column("acao", sa.String(length=60), nullable=False),
        sa.Column("entidade", sa.String(length=60), nullable=False),
        sa.Column("entidade_id", sa.Integer(), nullable=False),
        sa.Column("detalhes", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["unidade_id"], ["unidades.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("auditorias")
