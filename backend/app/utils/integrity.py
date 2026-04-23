import hashlib
import json
from datetime import datetime
from uuid import UUID


def _serialize(value: object) -> str:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def compute_record_hash(record_data: dict, previous_hash: str | None) -> str:
    payload = {
        "previous_hash": previous_hash or "",
        "data": {k: _serialize(v) for k, v in sorted(record_data.items())},
    }
    serialized = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(serialized.encode()).hexdigest()


def verify_record_hash(record_data: dict, previous_hash: str | None, stored_hash: str) -> bool:
    computed = compute_record_hash(record_data, previous_hash)
    return computed == stored_hash
