from __future__ import annotations

import base64
import json
from datetime import datetime


def encode_cursor(payload: dict[str, str]) -> str:
    raw = json.dumps(payload).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8")


def decode_cursor(cursor: str | None) -> dict[str, str] | None:
    if not cursor:
        return None
    decoded = base64.urlsafe_b64decode(cursor.encode("utf-8")).decode("utf-8")
    return json.loads(decoded)


def make_time_cursor(created_at: datetime, entity_id: str) -> str:
    return encode_cursor({"created_at": created_at.isoformat(), "id": entity_id})
