from __future__ import annotations

from datetime import datetime

from app.core.pagination import make_time_cursor


def build_cursor_page(items: list[dict], limit: int) -> dict:
    next_cursor = None
    if items and len(items) >= limit and items[-1].get("created_at"):
        created_at = items[-1]["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        next_cursor = make_time_cursor(created_at, str(items[-1].get("id", "")))
    return {
        "items": items,
        "page_info": {
            "next_cursor": next_cursor,
            "limit": limit,
        },
    }
