from __future__ import annotations

import pytest

from app.repositories.assessment_repository import AssessmentRepository


class FakeQuestionsTable:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows
        self.calls: list[dict] = []

    async def list(self, *, filters: dict, limit: int) -> list[dict]:
        self.calls.append(filters.copy())
        return [
            row for row in self.rows if all(row.get(key) == value for key, value in filters.items())
        ][:limit]


class FakeRecordsTable:
    def __init__(self, rows: list[dict] | None = None) -> None:
        self.rows = rows or []
        self.inserted_payloads: list[dict] = []
        self.last_filters: dict | None = None

    async def list(self, *, filters: dict, limit: int) -> list[dict]:
        self.last_filters = filters
        return [
            row for row in self.rows if all(row.get(key) == value for key, value in filters.items())
        ][:limit]

    async def insert(self, payload: dict) -> dict:
        self.inserted_payloads.append(payload.copy())
        return payload


@pytest.mark.asyncio
async def test_get_questions_falls_back_to_mcq_when_situational_bank_is_empty() -> None:
    repository = object.__new__(AssessmentRepository)
    repository.questions = FakeQuestionsTable(
        [
            {
                "id": "q-1",
                "is_active": True,
                "question_type": "MCQ",
                "category": "python",
                "difficulty": "medium",
                "skill_id": "skill-1",
                "skill_request_id": "request-1",
            }
        ]
    )

    questions = await repository.get_questions(
        category="python",
        difficulty="medium",
        limit=10,
        question_type="SITUATIONAL",
        skill_id="skill-1",
        skill_request_id="request-1",
    )

    assert [question["id"] for question in questions] == ["q-1"]
    assert repository.questions.calls[0]["question_type"] == "SITUATIONAL"
    assert any(call["question_type"] == "MCQ" for call in repository.questions.calls[1:])


@pytest.mark.asyncio
async def test_list_user_assessments_includes_rows_without_is_active_flag() -> None:
    repository = object.__new__(AssessmentRepository)
    repository.assessments = FakeRecordsTable(
        [
            {"id": "assessment-1", "user_id": "user-1"},
            {"id": "assessment-2", "user_id": "user-1", "is_active": False},
        ]
    )

    rows = await repository.list_user_assessments("user-1", limit=10)

    assert [row["id"] for row in rows] == ["assessment-1"]
    assert repository.assessments.last_filters == {"user_id": "user-1"}


@pytest.mark.asyncio
async def test_create_written_session_sets_is_active_by_default() -> None:
    repository = object.__new__(AssessmentRepository)
    repository.written_sessions = FakeRecordsTable()

    await repository.create_written_session({"user_id": "user-1", "prompt": "Explain cloud HA."})

    assert repository.written_sessions.inserted_payloads[0]["is_active"] is True
