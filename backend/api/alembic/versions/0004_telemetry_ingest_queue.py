"""telemetry ingest queue fields (replace Kafka)

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-25 00:00:01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "telemetry",
        sa.Column("processed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "telemetry",
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_telemetry_processed", "telemetry", ["processed"])


def downgrade() -> None:
    op.drop_index("ix_telemetry_processed", table_name="telemetry")
    op.drop_column("telemetry", "processed_at")
    op.drop_column("telemetry", "processed")
