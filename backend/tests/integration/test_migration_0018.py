"""PostgreSQL DDL tests for migration 0018 — Platform Security Hardening.

Verifies at the database level that the migration was applied correctly:
  P6 — operations table has risk_level, required_approvals, co_approvals columns
  P3 — audit_logs is append-only (BEFORE UPDATE/DELETE trigger raises exception)
  P2 — RLS enabled and forced on audit_logs, devices, and operations

Requirements:
  - A running PostgreSQL instance with migration 0018 applied.
  - Set the env variable TEST_PG_URL to a DSN without the async driver prefix.

    export TEST_PG_URL=postgresql://fm_user:password@localhost:5432/firemanager

  If TEST_PG_URL is not set the entire module is skipped.

Usage:
  docker compose -f infra/docker-compose.yml exec api \\
      env TEST_PG_URL=postgresql://fm_user:pass@postgres:5432/firemanager \\
      pytest tests/integration/test_migration_0018.py -v
"""
import os
import uuid

import pytest
import pytest_asyncio

try:
    import asyncpg
    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False

PG_URL = os.getenv("TEST_PG_URL", "").replace("+asyncpg", "").replace(
    "postgresql+psycopg", "postgresql"
)

pytestmark = pytest.mark.skipif(
    not PG_URL or not HAS_ASYNCPG,
    reason="TEST_PG_URL not set or asyncpg not installed — skipping PostgreSQL DDL tests",
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="module")
async def pg():
    """Module-scoped read-only connection for DDL introspection queries."""
    conn = await asyncpg.connect(PG_URL)
    yield conn
    await conn.close()


@pytest_asyncio.fixture
async def pg_fn():
    """Function-scoped connection for tests that write data (uses a rolled-back transaction)."""
    conn = await asyncpg.connect(PG_URL)
    yield conn
    await conn.close()


# ── P6: Multi-sig columns ─────────────────────────────────────────────────────

class TestP6MultiSigColumns:
    async def _column(self, pg, table: str, column: str) -> dict | None:
        row = await pg.fetchrow(
            """SELECT column_name, data_type, column_default, is_nullable
               FROM information_schema.columns
               WHERE table_name = $1 AND column_name = $2""",
            table, column,
        )
        return dict(row) if row else None

    async def test_risk_level_column_exists(self, pg):
        col = await self._column(pg, "operations", "risk_level")
        assert col is not None, "Column risk_level missing from operations"
        assert col["is_nullable"] == "NO"

    async def test_risk_level_default_is_medium(self, pg):
        col = await self._column(pg, "operations", "risk_level")
        assert col is not None
        assert "medium" in (col["column_default"] or "")

    async def test_required_approvals_column_exists(self, pg):
        col = await self._column(pg, "operations", "required_approvals")
        assert col is not None, "Column required_approvals missing from operations"
        assert col["is_nullable"] == "NO"

    async def test_required_approvals_default_is_1(self, pg):
        col = await self._column(pg, "operations", "required_approvals")
        assert col is not None
        assert "1" in (col["column_default"] or "")

    async def test_co_approvals_column_exists(self, pg):
        col = await self._column(pg, "operations", "co_approvals")
        assert col is not None, "Column co_approvals missing from operations"
        assert col["is_nullable"] == "NO"

    async def test_co_approvals_is_jsonb(self, pg):
        col = await self._column(pg, "operations", "co_approvals")
        assert col is not None
        assert col["data_type"] == "jsonb"

    async def test_co_approvals_default_is_empty_array(self, pg):
        col = await self._column(pg, "operations", "co_approvals")
        assert col is not None
        default = col["column_default"] or ""
        # PostgreSQL stores it as "'[]'::jsonb" or similar
        assert "[]" in default, f"Expected '[]' in default, got: {default!r}"

    async def test_risk_level_index_exists(self, pg):
        row = await pg.fetchrow(
            "SELECT indexname FROM pg_indexes "
            "WHERE tablename = 'operations' AND indexname = 'ix_operations_risk_level'"
        )
        assert row is not None, "Index ix_operations_risk_level not found on operations"


# ── P3: Immutable audit log ───────────────────────────────────────────────────

class TestP3ImmutableAuditLog:
    async def _trigger_exists(self, pg, trigger_name: str) -> bool:
        row = await pg.fetchrow(
            """SELECT trigger_name FROM information_schema.triggers
               WHERE event_object_table = 'audit_logs'
               AND trigger_name = $1""",
            trigger_name,
        )
        return row is not None

    async def test_immutable_update_trigger_exists(self, pg):
        assert await self._trigger_exists(pg, "audit_logs_immutable_update"), \
            "Trigger audit_logs_immutable_update not found on audit_logs"

    async def test_immutable_delete_trigger_exists(self, pg):
        assert await self._trigger_exists(pg, "audit_logs_immutable_delete"), \
            "Trigger audit_logs_immutable_delete not found on audit_logs"

    async def test_trigger_function_exists(self, pg):
        row = await pg.fetchrow(
            """SELECT routine_name FROM information_schema.routines
               WHERE routine_name = 'prevent_audit_log_modification'
               AND routine_type = 'FUNCTION'"""
        )
        assert row is not None, "Function prevent_audit_log_modification not found"

    async def test_triggers_fire_before_not_after(self, pg):
        for trigger_name in ("audit_logs_immutable_update", "audit_logs_immutable_delete"):
            row = await pg.fetchrow(
                """SELECT action_timing FROM information_schema.triggers
                   WHERE event_object_table = 'audit_logs' AND trigger_name = $1""",
                trigger_name,
            )
            assert row is not None
            assert row["action_timing"] == "BEFORE", \
                f"Trigger {trigger_name} should be BEFORE, got {row['action_timing']}"

    async def test_no_trigger_fires_on_insert(self, pg):
        row = await pg.fetchrow(
            """SELECT trigger_name FROM information_schema.triggers
               WHERE event_object_table = 'audit_logs'
               AND event_manipulation = 'INSERT'
               AND trigger_name IN (
                   'audit_logs_immutable_update', 'audit_logs_immutable_delete'
               )"""
        )
        assert row is None, "Immutability trigger must NOT fire on INSERT"

    async def test_update_raises_exception(self, pg_fn):
        """Functional: UPDATE on audit_logs must be blocked by the trigger."""
        record_id = uuid.uuid4()
        blocked = False

        txn = pg_fn.transaction()
        await txn.start()
        try:
            # Insert a minimal row (all FK fields are nullable)
            await pg_fn.execute(
                "INSERT INTO audit_logs (id, action, record_hash) VALUES ($1, $2, $3)",
                record_id, "test_action", "a" * 64,
            )
            # Attempt UPDATE inside a savepoint — trigger will abort it
            try:
                async with pg_fn.transaction():
                    await pg_fn.execute(
                        "UPDATE audit_logs SET action = 'tampered' WHERE id = $1",
                        record_id,
                    )
            except asyncpg.exceptions.RaiseError as exc:
                blocked = True
                assert "append-only" in str(exc).lower() or "audit_logs" in str(exc)
        finally:
            await txn.rollback()

        assert blocked, "UPDATE on audit_logs should have been blocked by trigger"

    async def test_delete_raises_exception(self, pg_fn):
        """Functional: DELETE on audit_logs must be blocked by the trigger."""
        record_id = uuid.uuid4()
        blocked = False

        txn = pg_fn.transaction()
        await txn.start()
        try:
            await pg_fn.execute(
                "INSERT INTO audit_logs (id, action, record_hash) VALUES ($1, $2, $3)",
                record_id, "test_delete_action", "b" * 64,
            )
            try:
                async with pg_fn.transaction():
                    await pg_fn.execute(
                        "DELETE FROM audit_logs WHERE id = $1", record_id
                    )
            except asyncpg.exceptions.RaiseError as exc:
                blocked = True
                assert "append-only" in str(exc).lower() or "audit_logs" in str(exc)
        finally:
            await txn.rollback()

        assert blocked, "DELETE on audit_logs should have been blocked by trigger"


# ── P2: Row-Level Security ────────────────────────────────────────────────────

class TestP2RowLevelSecurity:
    async def _rls_status(self, pg, table: str) -> dict:
        row = await pg.fetchrow(
            "SELECT rowsecurity, relforcerowsecurity "
            "FROM pg_class WHERE relname = $1 AND relkind = 'r'",
            table,
        )
        return dict(row) if row else {}

    async def _policy_exists(self, pg, table: str, policy: str) -> bool:
        row = await pg.fetchrow(
            "SELECT policyname FROM pg_policies WHERE tablename = $1 AND policyname = $2",
            table, policy,
        )
        return row is not None

    # audit_logs
    async def test_rls_enabled_on_audit_logs(self, pg):
        s = await self._rls_status(pg, "audit_logs")
        assert s.get("rowsecurity") is True, "RLS not enabled on audit_logs"

    async def test_rls_forced_on_audit_logs(self, pg):
        s = await self._rls_status(pg, "audit_logs")
        assert s.get("relforcerowsecurity") is True, "FORCE ROW LEVEL SECURITY not set on audit_logs"

    async def test_base_allow_policy_on_audit_logs(self, pg):
        assert await self._policy_exists(pg, "audit_logs", "audit_logs_base_allow"), \
            "Policy audit_logs_base_allow not found"

    # devices
    async def test_rls_enabled_on_devices(self, pg):
        s = await self._rls_status(pg, "devices")
        assert s.get("rowsecurity") is True, "RLS not enabled on devices"

    async def test_rls_forced_on_devices(self, pg):
        s = await self._rls_status(pg, "devices")
        assert s.get("relforcerowsecurity") is True, "FORCE ROW LEVEL SECURITY not set on devices"

    async def test_base_allow_policy_on_devices(self, pg):
        assert await self._policy_exists(pg, "devices", "devices_base_allow"), \
            "Policy devices_base_allow not found"

    # operations
    async def test_rls_enabled_on_operations(self, pg):
        s = await self._rls_status(pg, "operations")
        assert s.get("rowsecurity") is True, "RLS not enabled on operations"

    async def test_rls_forced_on_operations(self, pg):
        s = await self._rls_status(pg, "operations")
        assert s.get("relforcerowsecurity") is True, "FORCE ROW LEVEL SECURITY not set on operations"

    async def test_base_allow_policy_on_operations(self, pg):
        assert await self._policy_exists(pg, "operations", "operations_base_allow"), \
            "Policy operations_base_allow not found"

    async def test_all_three_policies_are_permissive(self, pg):
        """Base policies must have USING (true) — they allow all rows by default."""
        rows = await pg.fetch(
            """SELECT tablename, policyname, permissive, qual
               FROM pg_policies
               WHERE policyname IN (
                   'audit_logs_base_allow',
                   'devices_base_allow',
                   'operations_base_allow'
               )
               ORDER BY tablename"""
        )
        assert len(rows) == 3, \
            f"Expected 3 base policies, found {len(rows)}: {[r['policyname'] for r in rows]}"
        for row in rows:
            assert row["permissive"] == "PERMISSIVE", \
                f"Policy {row['policyname']} should be PERMISSIVE"
            assert row["qual"] is not None, \
                f"Policy {row['policyname']} has null USING clause"
