"""POS Module: receipts, receipt_lines + Product.Pfand/Pack-Size

Revision ID: 20260701_1914_b2c3d4e5f6a7
Revises: 20260701_1708_a1b2c3d4e5f6
Create Date: 2026-07-01 19:14:00.000000+00:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260701_1914_b2c3d4e5f6a7"
down_revision: str | Sequence[str] | None = "20260701_1708_a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- Products: deposit_cents / pieces_per_pack / pack_unit / pack_barcode ---
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("deposit_cents", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column(
                "pieces_per_pack", sa.Integer(), nullable=False, server_default="1"
            )
        )
        batch_op.add_column(sa.Column("pack_unit", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("pack_barcode", sa.String(length=32), nullable=True))
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_products_pack_barcode"), ["pack_barcode"], unique=False
        )

    # --- receipts (Header) ---
    op.create_table(
        "receipts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("receipt_number", sa.String(length=40), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("original_receipt_id", sa.Integer(), nullable=True),
        sa.Column("cash_session", sa.String(length=40), nullable=False),
        sa.Column("payment_method", sa.String(length=16), nullable=False),
        sa.Column("tendered_cents", sa.Integer(), nullable=False),
        sa.Column("change_cents", sa.Integer(), nullable=False),
        sa.Column("total_cents", sa.Integer(), nullable=False),
        sa.Column("cashier_name", sa.String(length=80), nullable=True),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["original_receipt_id"], ["receipts.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("receipt_number", name="uq_receipts_receipt_number"),
    )
    with op.batch_alter_table("receipts", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_receipts_cash_session"), ["cash_session"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_receipts_created_at"), ["created_at"], unique=False
        )

    # --- receipt_lines (Positionen) ---
    op.create_table(
        "receipt_lines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("receipt_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("name_snapshot", sa.String(length=200), nullable=False),
        sa.Column("unit_snapshot", sa.String(length=20), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column("unit_price_cents", sa.Integer(), nullable=False),
        sa.Column("line_total_cents", sa.Integer(), nullable=False),
        sa.Column("comment", sa.String(length=200), nullable=True),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["receipt_id"], ["receipts.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("receipt_lines", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_receipt_lines_product_id"), ["product_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_receipt_lines_receipt_id"), ["receipt_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("receipt_lines", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_receipt_lines_receipt_id"))
        batch_op.drop_index(batch_op.f("ix_receipt_lines_product_id"))
    op.drop_table("receipt_lines")

    with op.batch_alter_table("receipts", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_receipts_created_at"))
        batch_op.drop_index(batch_op.f("ix_receipts_cash_session"))
    op.drop_table("receipts")

    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_products_pack_barcode"))
        batch_op.drop_column("pack_barcode")
        batch_op.drop_column("pack_unit")
        batch_op.drop_column("pieces_per_pack")
        batch_op.drop_column("deposit_cents")
