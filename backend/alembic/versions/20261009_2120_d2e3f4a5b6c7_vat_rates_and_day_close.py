"""vat rates on products/receipt lines + day_closes table

Revision ID: 20261009_2120_d2e3f4a5b6c7
Revises: 20260701_1955_c1d2e3f4a5b6
Create Date: 2026-10-09 21:20:00.000000+00:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20261009_2120_d2e3f4a5b6c7"
down_revision: str | Sequence[str] | None = "20260701_1955_c1d2e3f4a5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("vat_rate", sa.Integer(), nullable=False, server_default=sa.text("19"))
        )
    with op.batch_alter_table("receipt_lines", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("vat_rate", sa.Integer(), nullable=False, server_default=sa.text("19"))
        )

    op.create_table(
        "day_closes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("z_number", sa.Integer(), nullable=False, unique=True),
        sa.Column("cash_session", sa.String(length=40), nullable=False),
        sa.Column("opening_float_cents", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("expected_cash_cents", sa.Integer(), nullable=False),
        sa.Column("counted_cash_cents", sa.Integer(), nullable=False),
        sa.Column("difference_cents", sa.Integer(), nullable=False),
        sa.Column("total_cents", sa.Integer(), nullable=False),
        sa.Column("cashier_name", sa.String(length=80), nullable=True),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("report_json", sa.Text(), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_day_closes_cash_session", "day_closes", ["cash_session"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_day_closes_cash_session", table_name="day_closes")
    op.drop_table("day_closes")
    with op.batch_alter_table("receipt_lines", schema=None) as batch_op:
        batch_op.drop_column("vat_rate")
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.drop_column("vat_rate")
