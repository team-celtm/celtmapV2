from __future__ import annotations

import re

_whitespace = re.compile(r"\s+")
_non_alnum = re.compile(r"[^a-z0-9]+")


def normalize_question_text(value: str) -> str:
    normalized = _whitespace.sub(" ", value.strip())
    return normalized.rstrip("?") + "?" if normalized else normalized


def normalize_free_text(value: str) -> str:
    return _whitespace.sub(" ", value.strip())


def normalize_name(value: str) -> str:
    collapsed = normalize_free_text(value).lower()
    return _non_alnum.sub("-", collapsed).strip("-")
