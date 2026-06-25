"""Configure PostgreSQL Row-Level Security policies for multi-tenant isolation.

Creates an application database role with RLS enforcement, enables RLS on all
tenant-scoped tables, and creates policies that filter rows based on the
session variable `app.current_tenant_id`.

Revision ID: 002
Revises: 001
Create Date: 2024-01-01 00:01:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Tables that require RLS (all have tenant_id column)
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


def upgrade() -> None:
    # 1. Create application role if it does not exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'smartwifi_app') THEN
                CREATE ROLE smartwifi_app LOGIN;
            END IF;
        END
        $$;
    """)

    # 2. Grant usage on schema and table permissions to the application role
    op.execute("GRANT USAGE ON SCHEMA public TO smartwifi_app;")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO smartwifi_app;"
    )
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO smartwifi_app;")

    # Grant default privileges for future tables
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO smartwifi_app;"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT USAGE, SELECT ON SEQUENCES TO smartwifi_app;"
    )

    # 3. Create helper function to set current tenant context
    op.execute("""
        CREATE OR REPLACE FUNCTION set_current_tenant(p_tenant_id TEXT)
        RETURNS VOID AS $$
        BEGIN
            PERFORM set_config('app.current_tenant_id', p_tenant_id, FALSE);
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("GRANT EXECUTE ON FUNCTION set_current_tenant(TEXT) TO smartwifi_app;")

    # 4. Enable RLS and create policies on all tenant-scoped tables
    for table in TENANT_SCOPED_TABLES:
        # Enable Row-Level Security on the table
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")

        # Force RLS for table owner as well (ensures RLS applies even for superusers
        # using the app role)
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")

        # Create policy for SELECT - only see rows belonging to current tenant
        op.execute(f"""
            CREATE POLICY {table}_tenant_isolation_select ON {table}
                FOR SELECT
                TO smartwifi_app
                USING (tenant_id = current_setting('app.current_tenant_id')::uuid);
        """)

        # Create policy for INSERT - can only insert rows for current tenant
        op.execute(f"""
            CREATE POLICY {table}_tenant_isolation_insert ON {table}
                FOR INSERT
                TO smartwifi_app
                WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid);
        """)

        # Create policy for UPDATE - can only update rows belonging to current tenant
        op.execute(f"""
            CREATE POLICY {table}_tenant_isolation_update ON {table}
                FOR UPDATE
                TO smartwifi_app
                USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
                WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid);
        """)

        # Create policy for DELETE - can only delete rows belonging to current tenant
        op.execute(f"""
            CREATE POLICY {table}_tenant_isolation_delete ON {table}
                FOR DELETE
                TO smartwifi_app
                USING (tenant_id = current_setting('app.current_tenant_id')::uuid);
        """)


def downgrade() -> None:
    # Remove RLS policies and disable RLS on all tenant-scoped tables
    for table in TENANT_SCOPED_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation_select ON {table};")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation_insert ON {table};")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation_update ON {table};")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation_delete ON {table};")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")

    # Drop helper function
    op.execute("DROP FUNCTION IF EXISTS set_current_tenant(TEXT);")

    # Revoke default privileges
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM smartwifi_app;"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "REVOKE USAGE, SELECT ON SEQUENCES FROM smartwifi_app;"
    )

    # Revoke permissions
    op.execute(
        "REVOKE SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public FROM smartwifi_app;"
    )
    op.execute("REVOKE USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public FROM smartwifi_app;")
    op.execute("REVOKE USAGE ON SCHEMA public FROM smartwifi_app;")

    # Drop the application role
    op.execute("DROP ROLE IF EXISTS smartwifi_app;")
