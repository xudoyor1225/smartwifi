"""Tests for Row-Level Security configuration and tenant context helpers.

Validates that:
- The RLS migration defines policies for all tenant-scoped tables
- The tenant context helper functions work correctly
- The migration revision chain is correct
"""

import importlib.util
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.core.database import (
    clear_tenant_context,
    get_tenant_db,
    set_tenant_context,
)


# Tables that should have RLS enabled
TENANT_SCOPED_TABLES = [
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
]

# Tables that should NOT have RLS
NON_TENANT_TABLES = [
    "tenants",
    "login_attempts",
]


def _load_rls_migration():
    """Load the RLS migration module by file path."""
    migration_path = (
        Path(__file__).parent.parent.parent
        / "alembic"
        / "versions"
        / "20240101_0002_002_row_level_security.py"
    )
    spec = importlib.util.spec_from_file_location(
        "rls_migration", migration_path
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestRLSMigrationStructure:
    """Tests for the RLS migration file structure and content."""

    def test_migration_revision_chain(self):
        """Migration 002 should depend on migration 001."""
        mod = _load_rls_migration()
        assert mod.revision == "002"
        assert mod.down_revision == "001"

    def test_migration_covers_all_tenant_scoped_tables(self):
        """Migration should define RLS for all tenant-scoped tables."""
        mod = _load_rls_migration()
        assert set(mod.TENANT_SCOPED_TABLES) == set(TENANT_SCOPED_TABLES)

    def test_migration_does_not_include_non_tenant_tables(self):
        """Migration should NOT include tables without tenant_id."""
        mod = _load_rls_migration()
        for table in NON_TENANT_TABLES:
            assert table not in mod.TENANT_SCOPED_TABLES

    def test_migration_has_upgrade_and_downgrade(self):
        """Migration should have both upgrade and downgrade functions."""
        mod = _load_rls_migration()
        assert callable(mod.upgrade)
        assert callable(mod.downgrade)


class TestTenantContextHelpers:
    """Tests for the set/clear tenant context helper functions."""

    @pytest.mark.asyncio
    async def test_set_tenant_context_executes_set_config(self):
        """set_tenant_context should execute SET CONFIG with the tenant_id."""
        mock_session = AsyncMock()
        tenant_id = str(uuid.uuid4())

        await set_tenant_context(mock_session, tenant_id)

        mock_session.execute.assert_called_once()
        call_args = mock_session.execute.call_args
        # The first positional arg is the text() clause
        sql_text = str(call_args[0][0].text)
        assert "set_config" in sql_text
        assert "app.current_tenant_id" in sql_text
        # The second positional arg is the params dict
        assert call_args[0][1] == {"tenant_id": tenant_id}

    @pytest.mark.asyncio
    async def test_clear_tenant_context_resets_to_empty(self):
        """clear_tenant_context should reset the session variable to empty."""
        mock_session = AsyncMock()

        await clear_tenant_context(mock_session)

        mock_session.execute.assert_called_once()
        call_args = mock_session.execute.call_args
        sql_text = str(call_args[0][0].text)
        assert "set_config" in sql_text
        assert "app.current_tenant_id" in sql_text

    @pytest.mark.asyncio
    async def test_set_tenant_context_converts_uuid_to_string(self):
        """set_tenant_context should handle UUID objects by converting to string."""
        mock_session = AsyncMock()
        tenant_uuid = uuid.uuid4()

        await set_tenant_context(mock_session, str(tenant_uuid))

        call_args = mock_session.execute.call_args
        assert call_args[0][1] == {"tenant_id": str(tenant_uuid)}


class TestGetTenantDb:
    """Tests for the get_tenant_db dependency."""

    @pytest.mark.asyncio
    async def test_get_tenant_db_sets_and_clears_context(self):
        """get_tenant_db should set tenant context on entry and clear on exit."""
        tenant_id = str(uuid.uuid4())
        mock_session = AsyncMock()

        with patch(
            "app.core.database.async_session_factory"
        ) as mock_factory:
            # Configure the context manager
            mock_cm = AsyncMock()
            mock_cm.__aenter__.return_value = mock_session
            mock_cm.__aexit__.return_value = None
            mock_factory.return_value = mock_cm

            async for session in get_tenant_db(tenant_id):
                # During the session, set_tenant_context should have been called
                assert mock_session.execute.call_count == 1
                first_call = mock_session.execute.call_args_list[0]
                sql_text = str(first_call[0][0].text)
                assert "set_config" in sql_text
                assert session is mock_session

            # After exiting, clear_tenant_context should have been called
            assert mock_session.execute.call_count == 2
            second_call = mock_session.execute.call_args_list[1]
            sql_text = str(second_call[0][0].text)
            assert "set_config" in sql_text

    @pytest.mark.asyncio
    async def test_get_tenant_db_closes_session(self):
        """get_tenant_db should close the session after use."""
        tenant_id = str(uuid.uuid4())
        mock_session = AsyncMock()

        with patch(
            "app.core.database.async_session_factory"
        ) as mock_factory:
            mock_cm = AsyncMock()
            mock_cm.__aenter__.return_value = mock_session
            mock_cm.__aexit__.return_value = None
            mock_factory.return_value = mock_cm

            async for _ in get_tenant_db(tenant_id):
                pass

            mock_session.close.assert_called_once()
