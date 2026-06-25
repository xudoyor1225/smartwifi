"""Initial database schema with all tables, constraints, and indexes.

Revision ID: 001
Revises: None
Create Date: 2024-01-01 00:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # === TENANTS ===
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("subscription_tier", sa.String(50), nullable=False, server_default="basic"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # === ADMINS ===
    op.create_table(
        "admins",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_admins_tenant_id", "admins", ["tenant_id"])
    op.create_index(
        "ix_admins_username_tenant", "admins", ["tenant_id", "username"], unique=True
    )

    # === ROUTER CONFIGS ===
    op.create_table(
        "router_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("ip_address", sa.String(45), nullable=False),
        sa.Column("api_port", sa.Integer(), nullable=False, server_default=sa.text("8728")),
        sa.Column("api_username", sa.String(128), nullable=False),
        sa.Column("encrypted_password", sa.LargeBinary(), nullable=False),
        sa.Column("encryption_iv", sa.LargeBinary(), nullable=False),
        sa.Column(
            "connection_status",
            sa.String(20),
            nullable=False,
            server_default="disconnected",
        ),
        sa.Column("last_connected", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_router_configs_tenant_id", "router_configs", ["tenant_id"])

    # === DEVICES ===
    op.create_table(
        "devices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("mac_address", sa.String(17), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("hostname", sa.String(255), nullable=True),
        sa.Column("manufacturer", sa.String(255), nullable=True),
        sa.Column("manufacturer_logo_url", sa.String(512), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("is_vip", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("total_bytes", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "first_seen",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "last_seen",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_devices_tenant_id", "devices", ["tenant_id"])
    op.create_index(
        "ix_devices_mac_tenant", "devices", ["tenant_id", "mac_address"], unique=True
    )
    op.create_index("ix_devices_status", "devices", ["tenant_id", "status"])

    # === BLOCKING SCENARIOS ===
    op.create_table(
        "blocking_scenarios",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("app_name", sa.String(100), nullable=False),
        sa.Column("app_logo_url", sa.String(512), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "rule_definitions",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_blocking_scenarios_tenant_id", "blocking_scenarios", ["tenant_id"])
    op.create_index(
        "ix_blocking_scenarios_app", "blocking_scenarios", ["tenant_id", "app_name"]
    )

    # === FIREWALL RULES ===
    op.create_table(
        "firewall_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "scenario_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("blocking_scenarios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rule_type", sa.String(20), nullable=False),
        sa.Column("pattern", sa.String(512), nullable=False),
        sa.Column("mikrotik_rule_id", sa.String(100), nullable=True),
        sa.Column("is_applied", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_firewall_rules_tenant_id", "firewall_rules", ["tenant_id"])
    op.create_index("ix_firewall_rules_scenario_id", "firewall_rules", ["scenario_id"])
    op.create_index(
        "ix_firewall_rules_tenant_applied", "firewall_rules", ["tenant_id", "is_applied"]
    )

    # === BANDWIDTH CONFIGS ===
    op.create_table(
        "bandwidth_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "global_download_mbps", sa.Integer(), nullable=False, server_default=sa.text("100")
        ),
        sa.Column(
            "global_upload_mbps", sa.Integer(), nullable=False, server_default=sa.text("50")
        ),
        sa.Column(
            "uplink_capacity_mbps", sa.Integer(), nullable=False, server_default=sa.text("1000")
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_bandwidth_configs_tenant_id", "bandwidth_configs", ["tenant_id"])

    # === QUEUE RULES ===
    op.create_table(
        "queue_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "device_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("devices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("download_limit_mbps", sa.Integer(), nullable=False),
        sa.Column("upload_limit_mbps", sa.Integer(), nullable=False),
        sa.Column("mikrotik_queue_id", sa.String(100), nullable=True),
        sa.Column("rule_type", sa.String(20), nullable=False, server_default="global"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_queue_rules_tenant_id", "queue_rules", ["tenant_id"])
    op.create_index("ix_queue_rules_device_id", "queue_rules", ["device_id"])
    op.create_index(
        "ix_queue_rules_tenant_device", "queue_rules", ["tenant_id", "device_id"]
    )

    # === TRAFFIC DATA (with monthly partitioning) ===
    # Create the parent table as a partitioned table
    op.execute("""
        CREATE TABLE traffic_data (
            id UUID NOT NULL,
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            src_ip VARCHAR(45) NOT NULL,
            dst_ip VARCHAR(45) NOT NULL,
            src_port INTEGER NOT NULL,
            dst_port INTEGER NOT NULL,
            protocol VARCHAR(10) NOT NULL,
            bytes_transferred BIGINT NOT NULL DEFAULT 0,
            packets INTEGER NOT NULL DEFAULT 0,
            category VARCHAR(50),
            collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (id, collected_at)
        ) PARTITION BY RANGE (collected_at);
    """)

    # Create indexes on the partitioned table
    op.execute(
        "CREATE INDEX ix_traffic_data_tenant_id ON traffic_data (tenant_id);"
    )
    op.execute(
        "CREATE INDEX ix_traffic_data_tenant_collected ON traffic_data (tenant_id, collected_at);"
    )
    op.execute(
        "CREATE INDEX ix_traffic_data_collected_at ON traffic_data (collected_at);"
    )

    # Create initial monthly partitions (current month + next 3 months)
    op.execute("""
        CREATE TABLE traffic_data_y2024m01 PARTITION OF traffic_data
            FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
    """)
    op.execute("""
        CREATE TABLE traffic_data_y2024m02 PARTITION OF traffic_data
            FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');
    """)
    op.execute("""
        CREATE TABLE traffic_data_y2024m03 PARTITION OF traffic_data
            FOR VALUES FROM ('2024-03-01') TO ('2024-04-01');
    """)
    op.execute("""
        CREATE TABLE traffic_data_y2024m04 PARTITION OF traffic_data
            FOR VALUES FROM ('2024-04-01') TO ('2024-05-01');
    """)
    op.execute("""
        CREATE TABLE traffic_data_y2024m05 PARTITION OF traffic_data
            FOR VALUES FROM ('2024-05-01') TO ('2024-06-01');
    """)
    op.execute("""
        CREATE TABLE traffic_data_y2024m06 PARTITION OF traffic_data
            FOR VALUES FROM ('2024-06-01') TO ('2024-07-01');
    """)
    op.execute("""
        CREATE TABLE traffic_data_y2024m07 PARTITION OF traffic_data
            FOR VALUES FROM ('2024-07-01') TO ('2024-08-01');
    """)
    op.execute("""
        CREATE TABLE traffic_data_y2024m08 PARTITION OF traffic_data
            FOR VALUES FROM ('2024-08-01') TO ('2024-09-01');
    """)
    op.execute("""
        CREATE TABLE traffic_data_y2024m09 PARTITION OF traffic_data
            FOR VALUES FROM ('2024-09-01') TO ('2024-10-01');
    """)
    op.execute("""
        CREATE TABLE traffic_data_y2024m10 PARTITION OF traffic_data
            FOR VALUES FROM ('2024-10-01') TO ('2024-11-01');
    """)
    op.execute("""
        CREATE TABLE traffic_data_y2024m11 PARTITION OF traffic_data
            FOR VALUES FROM ('2024-11-01') TO ('2024-12-01');
    """)
    op.execute("""
        CREATE TABLE traffic_data_y2024m12 PARTITION OF traffic_data
            FOR VALUES FROM ('2024-12-01') TO ('2025-01-01');
    """)
    op.execute("""
        CREATE TABLE traffic_data_y2025m01 PARTITION OF traffic_data
            FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
    """)
    op.execute("""
        CREATE TABLE traffic_data_y2025m02 PARTITION OF traffic_data
            FOR VALUES FROM ('2025-02-01') TO ('2025-03-01');
    """)
    op.execute("""
        CREATE TABLE traffic_data_y2025m03 PARTITION OF traffic_data
            FOR VALUES FROM ('2025-03-01') TO ('2025-04-01');
    """)
    op.execute("""
        CREATE TABLE traffic_data_y2025m04 PARTITION OF traffic_data
            FOR VALUES FROM ('2025-04-01') TO ('2025-05-01');
    """)
    op.execute("""
        CREATE TABLE traffic_data_y2025m05 PARTITION OF traffic_data
            FOR VALUES FROM ('2025-05-01') TO ('2025-06-01');
    """)
    op.execute("""
        CREATE TABLE traffic_data_y2025m06 PARTITION OF traffic_data
            FOR VALUES FROM ('2025-06-01') TO ('2025-07-01');
    """)
    op.execute("""
        CREATE TABLE traffic_data_y2025m07 PARTITION OF traffic_data
            FOR VALUES FROM ('2025-07-01') TO ('2025-08-01');
    """)
    op.execute("""
        CREATE TABLE traffic_data_y2025m08 PARTITION OF traffic_data
            FOR VALUES FROM ('2025-08-01') TO ('2025-09-01');
    """)
    op.execute("""
        CREATE TABLE traffic_data_y2025m09 PARTITION OF traffic_data
            FOR VALUES FROM ('2025-09-01') TO ('2025-10-01');
    """)
    op.execute("""
        CREATE TABLE traffic_data_y2025m10 PARTITION OF traffic_data
            FOR VALUES FROM ('2025-10-01') TO ('2025-11-01');
    """)
    op.execute("""
        CREATE TABLE traffic_data_y2025m11 PARTITION OF traffic_data
            FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');
    """)
    op.execute("""
        CREATE TABLE traffic_data_y2025m12 PARTITION OF traffic_data
            FOR VALUES FROM ('2025-12-01') TO ('2026-01-01');
    """)

    # === ANOMALY ALERTS ===
    op.create_table(
        "anomaly_alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("anomaly_type", sa.String(50), nullable=False),
        sa.Column("observed_value", sa.Float(), nullable=False),
        sa.Column("baseline_value", sa.Float(), nullable=False),
        sa.Column("deviation_std", sa.Float(), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_anomaly_alerts_tenant_id", "anomaly_alerts", ["tenant_id"])
    op.create_index(
        "ix_anomaly_alerts_tenant_detected", "anomaly_alerts", ["tenant_id", "detected_at"]
    )
    op.create_index(
        "ix_anomaly_alerts_severity", "anomaly_alerts", ["tenant_id", "severity"]
    )

    # === DEVICE SESSIONS ===
    op.create_table(
        "device_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "device_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("devices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("bytes_downloaded", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("bytes_uploaded", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "session_start",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("session_end", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_device_sessions_tenant_id", "device_sessions", ["tenant_id"])
    op.create_index("ix_device_sessions_device_id", "device_sessions", ["device_id"])
    op.create_index(
        "ix_device_sessions_tenant_device", "device_sessions", ["tenant_id", "device_id"]
    )

    # === REPORTS ===
    op.create_table(
        "reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "admin_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("admins.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("format", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("file_path", sa.String(512), nullable=True),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_reports_tenant_id", "reports", ["tenant_id"])
    op.create_index("ix_reports_admin_id", "reports", ["admin_id"])
    op.create_index("ix_reports_tenant_status", "reports", ["tenant_id", "status"])

    # === AUDIT LOGS ===
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "admin_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("admins.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("target_type", sa.String(50), nullable=True),
        sa.Column("target_id", sa.String(100), nullable=True),
        sa.Column("request_data", postgresql.JSONB(), nullable=True),
        sa.Column("response_data", postgresql.JSONB(), nullable=True),
        sa.Column("result", sa.String(20), nullable=False, server_default="success"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_audit_logs_tenant_id", "audit_logs", ["tenant_id"])
    op.create_index("ix_audit_logs_admin_id", "audit_logs", ["admin_id"])
    op.create_index(
        "ix_audit_logs_tenant_created", "audit_logs", ["tenant_id", "created_at"]
    )

    # === LOGIN ATTEMPTS ===
    op.create_table(
        "login_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ip_address", sa.String(45), nullable=False),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column(
            "attempted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_login_attempts_ip_address", "login_attempts", ["ip_address"])
    op.create_index(
        "ix_login_attempts_ip_attempted", "login_attempts", ["ip_address", "attempted_at"]
    )
    op.create_index("ix_login_attempts_attempted_at", "login_attempts", ["attempted_at"])


def downgrade() -> None:
    # Drop tables in reverse dependency order
    op.drop_table("login_attempts")
    op.drop_table("audit_logs")
    op.drop_table("reports")
    op.drop_table("device_sessions")
    op.drop_table("anomaly_alerts")

    # Drop partitioned traffic_data table (cascades to partitions)
    op.execute("DROP TABLE IF EXISTS traffic_data CASCADE;")

    op.drop_table("queue_rules")
    op.drop_table("bandwidth_configs")
    op.drop_table("firewall_rules")
    op.drop_table("blocking_scenarios")
    op.drop_table("devices")
    op.drop_table("router_configs")
    op.drop_table("admins")
    op.drop_table("tenants")
