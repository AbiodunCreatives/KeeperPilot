"""extend executions with wallet and protocol targets

Revision ID: 35b487874e5d
Revises: cab0eea8fd85
Create Date: 2026-08-01 02:39:18.631639+00:00

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '35b487874e5d'
down_revision: Union[str, None] = 'cab0eea8fd85'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Batch mode: SQLite cannot ALTER constraints inline; on Postgres this is a
    # set of direct ALTERs. Add nullable columns, index, and FK.
    with op.batch_alter_table("executions") as batch_op:
        batch_op.add_column(sa.Column("wallet_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("source_protocol", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("target_protocol", sa.String(length=64), nullable=True))
        batch_op.create_index(op.f("ix_executions_wallet_id"), ["wallet_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_executions_wallet_id",
            "wallets",
            ["wallet_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("executions") as batch_op:
        batch_op.drop_constraint("fk_executions_wallet_id", type_="foreignkey")
        batch_op.drop_index(op.f("ix_executions_wallet_id"))
        batch_op.drop_column("target_protocol")
        batch_op.drop_column("source_protocol")
        batch_op.drop_column("wallet_id")
