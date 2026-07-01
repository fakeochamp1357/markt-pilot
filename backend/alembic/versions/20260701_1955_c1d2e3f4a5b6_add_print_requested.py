"""add print_requested flag to receipts

Revision ID: 20260701_1955_c1d2e3f4a5b6
Revises: 20260701_1914_b2c3d4e5f6a7
Create Date: 2026-07-01 19:55:00.000000+00:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260701_1955_c1d2e3f4a5b6"
down_revision: str | Sequence[str] | None = "20260701_1914_b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("receipts", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "print_requested",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("1"),  # SQLite: 1 = True
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("receipts", schema=None) as batch_op:
        batch_op.drop_column("print_requested")
