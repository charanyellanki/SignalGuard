"""initial schema: telemetry, anomalies, pg_notify trigger

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "telemetry",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("device_id", sa.String(length=64), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("battery_voltage", sa.Float(), nullable=False),
        sa.Column("lock_events_count", sa.Integer(), nullable=False),
        sa.Column("signal_strength_dbm", sa.Float(), nullable=False),
        sa.Column("temperature_c", sa.Float(), nullable=False),
    )
    op.create_index(
        "ix_telemetry_device_ts",
        "telemetry",
        ["device_id", sa.text("timestamp DESC")],
    )
    op.create_index("ix_telemetry_timestamp", "telemetry", ["timestamp"])

    op.create_table(
        "anomalies",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("device_id", sa.String(length=64), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("anomaly_type", sa.String(length=64), nullable=False),
        sa.Column("detected_by_model", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
    )
    op.create_index("ix_anomalies_device_id", "anomalies", ["device_id"])
    op.create_index("ix_anomalies_timestamp", "anomalies", ["timestamp"])
    op.create_index("ix_anomalies_severity", "anomalies", ["severity"])

    # pg_notify trigger: payload is just the new row id. WS handler re-reads
    # the row from Postgres so we stay well under the 8 kB NOTIFY payload cap.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION notify_anomaly() RETURNS TRIGGER AS $$
        BEGIN
            PERFORM pg_notify('anomalies', NEW.id::text);
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER anomalies_notify
        AFTER INSERT ON anomalies
        FOR EACH ROW EXECUTE FUNCTION notify_anomaly();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS anomalies_notify ON anomalies;")
    op.execute("DROP FUNCTION IF EXISTS notify_anomaly();")
    op.drop_index("ix_anomalies_severity", table_name="anomalies")
    op.drop_index("ix_anomalies_timestamp", table_name="anomalies")
    op.drop_index("ix_anomalies_device_id", table_name="anomalies")
    op.drop_table("anomalies")
    op.drop_index("ix_telemetry_timestamp", table_name="telemetry")
    op.drop_index("ix_telemetry_device_ts", table_name="telemetry")
    op.drop_table("telemetry")
