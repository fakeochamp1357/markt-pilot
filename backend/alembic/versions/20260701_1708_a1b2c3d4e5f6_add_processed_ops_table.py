"""add processed_ops table for client-op idempotency

Revision ID: 20260701_1708_a1b2c3d4e5f6
Revises: 7180072e5311
Create Date: 2026-07-01 17:08:00.000000+00:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260701_1708_a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "7180072e5311"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "processed_ops",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_op_id", sa.String(length=64), nullable=False),
        sa.Column("endpoint", sa.String(length=120), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("response_json", sa.String(length=2000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_op_id", name="uq_processed_ops_client_op_id"),
    )
    with op.batch_alter_table("processed_ops", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_processed_ops_client_op_id"), ["client_op_id"], unique=True
        )
        batch_op.create_index(
            batch_op.f("ix_processed_ops_endpoint"), ["endpoint"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("processed_ops", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_processed_ops_endpoint"))
        batch_op.drop_index(batch_op.f("ix_processed_ops_client_op_id"))
    op.drop_table("processed_ops")
