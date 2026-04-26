"""add site_id / site_name to telemetry and anomalies

Revision ID: 0002
Revises: 0001
Create Date: 2024-01-02 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nullable on add so existing rows survive the migration; new inserts
    # are populated by the embedded simulator + API ingest.
    op.add_column("telemetry", sa.Column("site_id", sa.String(length=64), nullable=True))
    op.add_column("telemetry", sa.Column("site_name", sa.String(length=128), nullable=True))
    op.create_index("ix_telemetry_site_id", "telemetry", ["site_id"])

    op.add_column("anomalies", sa.Column("site_id", sa.String(length=64), nullable=True))
    op.add_column("anomalies", sa.Column("site_name", sa.String(length=128), nullable=True))
    op.create_index("ix_anomalies_site_id", "anomalies", ["site_id"])


def downgrade() -> None:
    op.drop_index("ix_anomalies_site_id", table_name="anomalies")
    op.drop_column("anomalies", "site_name")
    op.drop_column("anomalies", "site_id")
    op.drop_index("ix_telemetry_site_id", table_name="telemetry")
    op.drop_column("telemetry", "site_name")
    op.drop_column("telemetry", "site_id")
