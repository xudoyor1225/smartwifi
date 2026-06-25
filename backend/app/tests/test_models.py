"""Tests for SQLAlchemy models and database schema definition."""


import pytest
from sqlalchemy import inspect

from app.models import (
    Admin,
    AnomalyAlert,
    AuditLog,
    BandwidthConfig,
    Base,
    BlockingScenario,
    Device,
    DeviceSession,
    FirewallRule,
    LoginAttempt,
    QueueRule,
    Report,
    RouterConfig,
    Tenant,
    TrafficData,
)


class TestModelRegistry:
    """Tests that all models are registered in the metadata."""

    def test_all_14_tables_registered(self):
        tables = Base.metadata.tables
        assert len(tables) == 14

    def test_expected_table_names(self):
        expected = {
            "tenants",
            "admins",
            "router_configs",
            "devices",
            "blocking_scenarios",
            "firewall_rules",
            "bandwidth_configs",
            "queue_rules",
            "traffic_data",
            "anomaly_alerts",
            "device_sessions",
            "reports",
            "audit_logs",
            "login_attempts",
        }
        actual = set(Base.metadata.tables.keys())
        assert actual == expected


class TestTenantModel:
    """Tests for the Tenant model schema."""

    def test_tablename(self):
        assert Tenant.__tablename__ == "tenants"

    def test_has_required_columns(self):
        mapper = inspect(Tenant)
        column_names = {c.key for c in mapper.column_attrs}
        expected = {"id", "name", "subscription_tier", "is_active", "created_at", "updated_at"}
        assert expected.issubset(column_names)

    def test_id_is_uuid_primary_key(self):
        mapper = inspect(Tenant)
        pk_cols = [c.name for c in mapper.mapper.primary_key]
        assert pk_cols == ["id"]


class TestAdminModel:
    """Tests for the Admin model schema."""

    def test_tablename(self):
        assert Admin.__tablename__ == "admins"

    def test_has_tenant_id_foreign_key(self):
        mapper = inspect(Admin)
        column_names = {c.key for c in mapper.column_attrs}
        assert "tenant_id" in column_names

    def test_has_required_columns(self):
        mapper = inspect(Admin)
        column_names = {c.key for c in mapper.column_attrs}
        expected = {
            "id", "tenant_id", "username", "password_hash",
            "email", "is_active", "last_login", "created_at",
        }
        assert expected.issubset(column_names)

    def test_has_tenant_id_index(self):
        indexes = {idx.name for idx in Admin.__table__.indexes}
        assert "ix_admins_tenant_id" in indexes

    def test_has_unique_username_per_tenant_index(self):
        indexes = {idx.name for idx in Admin.__table__.indexes}
        assert "ix_admins_username_tenant" in indexes


class TestRouterConfigModel:
    """Tests for the RouterConfig model schema."""

    def test_tablename(self):
        assert RouterConfig.__tablename__ == "router_configs"

    def test_has_required_columns(self):
        mapper = inspect(RouterConfig)
        column_names = {c.key for c in mapper.column_attrs}
        expected = {
            "id", "tenant_id", "ip_address", "api_port",
            "api_username", "encrypted_password", "encryption_iv",
            "connection_status", "last_connected", "created_at",
        }
        assert expected.issubset(column_names)

    def test_tenant_id_is_unique(self):
        col = RouterConfig.__table__.c.tenant_id
        assert col.unique is True


class TestDeviceModel:
    """Tests for the Device model schema."""

    def test_tablename(self):
        assert Device.__tablename__ == "devices"

    def test_has_required_columns(self):
        mapper = inspect(Device)
        column_names = {c.key for c in mapper.column_attrs}
        expected = {
            "id", "tenant_id", "mac_address", "ip_address",
            "hostname", "manufacturer", "manufacturer_logo_url",
            "status", "is_vip", "total_bytes", "first_seen", "last_seen",
        }
        assert expected.issubset(column_names)

    def test_has_mac_tenant_unique_index(self):
        indexes = {idx.name for idx in Device.__table__.indexes}
        assert "ix_devices_mac_tenant" in indexes


class TestBlockingScenarioModel:
    """Tests for the BlockingScenario model schema."""

    def test_tablename(self):
        assert BlockingScenario.__tablename__ == "blocking_scenarios"

    def test_has_required_columns(self):
        mapper = inspect(BlockingScenario)
        column_names = {c.key for c in mapper.column_attrs}
        expected = {
            "id", "tenant_id", "app_name", "app_logo_url",
            "version", "is_active", "rule_definitions",
            "created_at", "updated_at",
        }
        assert expected.issubset(column_names)


class TestFirewallRuleModel:
    """Tests for the FirewallRule model schema."""

    def test_tablename(self):
        assert FirewallRule.__tablename__ == "firewall_rules"

    def test_has_required_columns(self):
        mapper = inspect(FirewallRule)
        column_names = {c.key for c in mapper.column_attrs}
        expected = {
            "id", "scenario_id", "tenant_id", "rule_type",
            "pattern", "mikrotik_rule_id", "is_applied", "applied_at",
        }
        assert expected.issubset(column_names)

    def test_has_tenant_id_index(self):
        indexes = {idx.name for idx in FirewallRule.__table__.indexes}
        assert "ix_firewall_rules_tenant_id" in indexes


class TestBandwidthConfigModel:
    """Tests for the BandwidthConfig model schema."""

    def test_tablename(self):
        assert BandwidthConfig.__tablename__ == "bandwidth_configs"

    def test_has_required_columns(self):
        mapper = inspect(BandwidthConfig)
        column_names = {c.key for c in mapper.column_attrs}
        expected = {
            "id", "tenant_id", "global_download_mbps",
            "global_upload_mbps", "uplink_capacity_mbps", "updated_at",
        }
        assert expected.issubset(column_names)

    def test_tenant_id_is_unique(self):
        col = BandwidthConfig.__table__.c.tenant_id
        assert col.unique is True


class TestQueueRuleModel:
    """Tests for the QueueRule model schema."""

    def test_tablename(self):
        assert QueueRule.__tablename__ == "queue_rules"

    def test_has_required_columns(self):
        mapper = inspect(QueueRule)
        column_names = {c.key for c in mapper.column_attrs}
        expected = {
            "id", "tenant_id", "device_id", "download_limit_mbps",
            "upload_limit_mbps", "mikrotik_queue_id", "rule_type", "created_at",
        }
        assert expected.issubset(column_names)


class TestTrafficDataModel:
    """Tests for the TrafficData model schema."""

    def test_tablename(self):
        assert TrafficData.__tablename__ == "traffic_data"

    def test_has_required_columns(self):
        mapper = inspect(TrafficData)
        column_names = {c.key for c in mapper.column_attrs}
        expected = {
            "id", "tenant_id", "src_ip", "dst_ip", "src_port",
            "dst_port", "protocol", "bytes_transferred", "packets",
            "category", "collected_at",
        }
        assert expected.issubset(column_names)


class TestAnomalyAlertModel:
    """Tests for the AnomalyAlert model schema."""

    def test_tablename(self):
        assert AnomalyAlert.__tablename__ == "anomaly_alerts"

    def test_has_required_columns(self):
        mapper = inspect(AnomalyAlert)
        column_names = {c.key for c in mapper.column_attrs}
        expected = {
            "id", "tenant_id", "severity", "anomaly_type",
            "observed_value", "baseline_value", "deviation_std",
            "description", "is_read", "detected_at",
        }
        assert expected.issubset(column_names)


class TestDeviceSessionModel:
    """Tests for the DeviceSession model schema."""

    def test_tablename(self):
        assert DeviceSession.__tablename__ == "device_sessions"

    def test_has_required_columns(self):
        mapper = inspect(DeviceSession)
        column_names = {c.key for c in mapper.column_attrs}
        expected = {
            "id", "device_id", "tenant_id", "bytes_downloaded",
            "bytes_uploaded", "session_start", "session_end",
        }
        assert expected.issubset(column_names)


class TestReportModel:
    """Tests for the Report model schema."""

    def test_tablename(self):
        assert Report.__tablename__ == "reports"

    def test_has_required_columns(self):
        mapper = inspect(Report)
        column_names = {c.key for c in mapper.column_attrs}
        expected = {
            "id", "tenant_id", "admin_id", "format", "status",
            "file_path", "period_start", "period_end",
            "generated_at", "expires_at",
        }
        assert expected.issubset(column_names)


class TestAuditLogModel:
    """Tests for the AuditLog model schema."""

    def test_tablename(self):
        assert AuditLog.__tablename__ == "audit_logs"

    def test_has_required_columns(self):
        mapper = inspect(AuditLog)
        column_names = {c.key for c in mapper.column_attrs}
        expected = {
            "id", "tenant_id", "admin_id", "action",
            "target_type", "target_id", "request_data",
            "response_data", "result", "created_at",
        }
        assert expected.issubset(column_names)


class TestLoginAttemptModel:
    """Tests for the LoginAttempt model schema."""

    def test_tablename(self):
        assert LoginAttempt.__tablename__ == "login_attempts"

    def test_has_required_columns(self):
        mapper = inspect(LoginAttempt)
        column_names = {c.key for c in mapper.column_attrs}
        expected = {"id", "ip_address", "username", "success", "attempted_at"}
        assert expected.issubset(column_names)

    def test_has_no_tenant_id(self):
        """LoginAttempt is not tenant-scoped."""
        mapper = inspect(LoginAttempt)
        column_names = {c.key for c in mapper.column_attrs}
        assert "tenant_id" not in column_names

    def test_has_ip_address_index(self):
        indexes = {idx.name for idx in LoginAttempt.__table__.indexes}
        assert "ix_login_attempts_ip_address" in indexes


class TestTenantScopedTables:
    """Tests that all tenant-scoped tables have tenant_id FK and index."""

    TENANT_SCOPED_MODELS = [
        Admin,
        RouterConfig,
        Device,
        BlockingScenario,
        FirewallRule,
        BandwidthConfig,
        QueueRule,
        TrafficData,
        AnomalyAlert,
        DeviceSession,
        Report,
        AuditLog,
    ]

    @pytest.mark.parametrize(
        "model",
        TENANT_SCOPED_MODELS,
        ids=lambda m: m.__tablename__,
    )
    def test_has_tenant_id_column(self, model):
        mapper = inspect(model)
        column_names = {c.key for c in mapper.column_attrs}
        assert "tenant_id" in column_names

    @pytest.mark.parametrize(
        "model",
        TENANT_SCOPED_MODELS,
        ids=lambda m: m.__tablename__,
    )
    def test_has_tenant_id_index(self, model):
        indexes = {idx.name for idx in model.__table__.indexes}
        expected_index = f"ix_{model.__tablename__}_tenant_id"
        assert expected_index in indexes
