"""Unit tests for app.services.audit_log_service and app.utils.integrity.

Validates hash-chained audit log: write_audit creates entries with correct
hashes, verify_chain detects tampering and chain breaks.
"""
import pytest

from app.services.audit_log_service import verify_chain, write_audit
from app.utils.integrity import compute_record_hash, verify_record_hash


# ── compute_record_hash (pure function, no DB) ────────────────────────────────

class TestComputeRecordHash:
    def test_returns_64_char_hex(self):
        h = compute_record_hash({"action": "test"}, None)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_deterministic(self):
        data = {"action": "login", "user_id": None, "ip_address": "1.2.3.4"}
        assert compute_record_hash(data, None) == compute_record_hash(data, None)

    def test_different_previous_hash_changes_result(self):
        data = {"action": "login"}
        h1 = compute_record_hash(data, None)
        h2 = compute_record_hash(data, "abc123")
        assert h1 != h2

    def test_different_action_changes_result(self):
        h1 = compute_record_hash({"action": "login"}, None)
        h2 = compute_record_hash({"action": "logout"}, None)
        assert h1 != h2

    def test_none_previous_hash_treated_as_empty_string(self):
        data = {"action": "x"}
        h_none = compute_record_hash(data, None)
        h_empty = compute_record_hash(data, "")
        assert h_none == h_empty


class TestVerifyRecordHash:
    def test_valid_hash_returns_true(self):
        data = {"action": "test", "user_id": None}
        h = compute_record_hash(data, None)
        assert verify_record_hash(data, None, h) is True

    def test_tampered_data_returns_false(self):
        data = {"action": "test", "user_id": None}
        h = compute_record_hash(data, None)
        data["action"] = "tampered"
        assert verify_record_hash(data, None, h) is False

    def test_wrong_stored_hash_returns_false(self):
        data = {"action": "test"}
        assert verify_record_hash(data, None, "deadbeef" * 8) is False


# ── write_audit (requires DB) ─────────────────────────────────────────────────

class TestWriteAudit:
    async def test_creates_entry_with_action(self, db_session):
        entry = await write_audit(db_session, action="test.action")
        assert entry.id is not None
        assert entry.action == "test.action"

    async def test_first_entry_has_no_previous_hash(self, db_session):
        entry = await write_audit(db_session, action="first.event")
        assert entry.previous_hash is None

    async def test_second_entry_links_to_first(self, db_session):
        first = await write_audit(db_session, action="event.one")
        second = await write_audit(db_session, action="event.two")
        assert second.previous_hash == first.record_hash

    async def test_record_hash_is_64_chars(self, db_session):
        entry = await write_audit(db_session, action="hash.check")
        assert len(entry.record_hash) == 64

    async def test_optional_fields_nullable(self, db_session):
        entry = await write_audit(db_session, action="no.context")
        assert entry.user_id is None
        assert entry.device_id is None
        assert entry.operation_id is None
        assert entry.ip_address is None

    async def test_details_stored(self, db_session):
        entry = await write_audit(
            db_session,
            action="with.details",
            details={"key": "value", "count": 42},
        )
        assert entry.details == {"key": "value", "count": 42}

    async def test_ip_address_stored(self, db_session):
        entry = await write_audit(
            db_session,
            action="with.ip",
            ip_address="10.20.30.40",
        )
        assert entry.ip_address == "10.20.30.40"

    async def test_hash_is_reproducible_from_fields(self, db_session):
        entry = await write_audit(
            db_session,
            action="reproducible",
            ip_address="1.2.3.4",
            details={"x": 1},
        )
        record_data = {
            "action": entry.action,
            "user_id": entry.user_id,
            "device_id": entry.device_id,
            "operation_id": entry.operation_id,
            "details": str(entry.details) if entry.details else "",
            "ip_address": entry.ip_address or "",
        }
        expected = compute_record_hash(record_data, entry.previous_hash)
        assert entry.record_hash == expected


# ── verify_chain (requires DB) ────────────────────────────────────────────────

class TestVerifyChain:
    async def test_empty_db_returns_no_violations(self, db_session):
        violations = await verify_chain(db_session)
        assert violations == []

    async def test_single_entry_intact_chain(self, db_session):
        await write_audit(db_session, action="solo.event")
        violations = await verify_chain(db_session)
        assert violations == []

    async def test_three_entries_intact_chain(self, db_session):
        for i in range(3):
            await write_audit(db_session, action=f"seq.event.{i}")
        violations = await verify_chain(db_session)
        assert violations == []

    async def test_tampered_hash_detected(self, db_session):
        from sqlalchemy import select
        from app.models.audit_log import AuditLog

        await write_audit(db_session, action="pre.tamper")
        entry = await write_audit(db_session, action="to.tamper")

        # Directly corrupt the stored hash
        entry.record_hash = "0" * 64
        db_session.add(entry)
        await db_session.flush()

        violations = await verify_chain(db_session)
        assert any(v["issue"] == "hash_mismatch" for v in violations)

    async def test_violation_contains_entry_id(self, db_session):
        from app.models.audit_log import AuditLog

        entry = await write_audit(db_session, action="flagged.entry")
        entry.record_hash = "f" * 64
        db_session.add(entry)
        await db_session.flush()

        violations = await verify_chain(db_session)
        ids = [v["id"] for v in violations]
        assert str(entry.id) in ids
