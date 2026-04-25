"""add Nokē hierarchy (customer/gateway/building/unit) + anomaly NOC workflow

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-25 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Telemetry: customer/gateway/building/unit denormalization ───────
    op.add_column("telemetry", sa.Column("customer_id",   sa.String(length=64),  nullable=True))
    op.add_column("telemetry", sa.Column("customer_name", sa.String(length=128), nullable=True))
    op.add_column("telemetry", sa.Column("gateway_id",    sa.String(length=64),  nullable=True))
    op.add_column("telemetry", sa.Column("building",      sa.String(length=16),  nullable=True))
    op.add_column("telemetry", sa.Column("unit_id",       sa.String(length=32),  nullable=True))
    op.create_index("ix_telemetry_customer_id", "telemetry", ["customer_id"])
    op.create_index("ix_telemetry_gateway_id",  "telemetry", ["gateway_id"])

    # ── Anomalies: same denormalization + NOC workflow state ────────────
    op.add_column("anomalies", sa.Column("customer_id",   sa.String(length=64),  nullable=True))
    op.add_column("anomalies", sa.Column("customer_name", sa.String(length=128), nullable=True))
    op.add_column("anomalies", sa.Column("gateway_id",    sa.String(length=64),  nullable=True))
    op.add_column("anomalies", sa.Column("building",      sa.String(length=16),  nullable=True))
    op.add_column("anomalies", sa.Column("unit_id",       sa.String(length=32),  nullable=True))
    op.add_column(
        "anomalies",
        sa.Column("status", sa.String(length=24), nullable=False, server_default="open"),
    )
    op.add_column("anomalies", sa.Column("assignee",    sa.String(length=64),         nullable=True))
    op.add_column("anomalies", sa.Column("acted_at",    sa.DateTime(timezone=True),   nullable=True))
    op.add_column("anomalies", sa.Column("action_note", sa.Text(),                    nullable=True))
    op.create_index("ix_anomalies_customer_id", "anomalies", ["customer_id"])
    op.create_index("ix_anomalies_status",      "anomalies", ["status"])


def downgrade() -> None:
    op.drop_index("ix_anomalies_status",      table_name="anomalies")
    op.drop_index("ix_anomalies_customer_id", table_name="anomalies")
    op.drop_column("anomalies", "action_note")
    op.drop_column("anomalies", "acted_at")
    op.drop_column("anomalies", "assignee")
    op.drop_column("anomalies", "status")
    op.drop_column("anomalies", "unit_id")
    op.drop_column("anomalies", "building")
    op.drop_column("anomalies", "gateway_id")
    op.drop_column("anomalies", "customer_name")
    op.drop_column("anomalies", "customer_id")

    op.drop_index("ix_telemetry_gateway_id",  table_name="telemetry")
    op.drop_index("ix_telemetry_customer_id", table_name="telemetry")
    op.drop_column("telemetry", "unit_id")
    op.drop_column("telemetry", "building")
    op.drop_column("telemetry", "gateway_id")
    op.drop_column("telemetry", "customer_name")
    op.drop_column("telemetry", "customer_id")
