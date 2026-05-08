from __future__ import annotations

from app.integrations.llm import _ensure_json_output_messages


def test_ensure_json_output_messages_adds_json_instruction_when_missing() -> None:
    messages = [{"role": "user", "content": "Score this written assessment."}]

    updated = _ensure_json_output_messages(messages)

    assert updated[0]["role"] == "system"
    assert "json" in updated[0]["content"].lower()
    assert updated[1:] == messages


def test_ensure_json_output_messages_preserves_existing_json_instruction() -> None:
    messages = [{"role": "user", "content": "Return valid JSON with score and feedback."}]

    updated = _ensure_json_output_messages(messages)

    assert updated == messages
