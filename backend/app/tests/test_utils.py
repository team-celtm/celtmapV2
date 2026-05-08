from __future__ import annotations

from app.utils.shuffle import shuffled
from app.utils.text import normalize_question_text


def test_normalize_question_text_trims_whitespace_and_enforces_question_mark() -> None:
    assert normalize_question_text("  What is overfitting   ") == "What is overfitting?"


def test_shuffled_preserves_membership() -> None:
    items = [1, 2, 3, 4, 5]
    result = shuffled(items, seed=7)
    assert sorted(result) == sorted(items)
    assert result != items
