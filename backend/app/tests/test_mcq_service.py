from __future__ import annotations

import pytest

from app.services.mcq_service import MCQService


class FakeEventService:
    async def emit(self, **kwargs) -> None:
        return None


class FakeQuestionTable:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows

    async def list(self, filters: dict, limit: int) -> list[dict]:
        matches = [
            row for row in self.rows if all(row.get(key) == value for key, value in filters.items())
        ]
        return matches[:limit]


class FakeAssessmentRepository:
    def __init__(
        self,
        *,
        question_rows: list[dict] | None = None,
        question_lookup: list[dict] | None = None,
        option_lookup: dict[str, dict] | None = None,
        assessments: list[dict] | None = None,
        written_sessions: list[dict] | None = None,
    ) -> None:
        self.questions = FakeQuestionTable(question_rows or [])
        self.question_rows = question_rows or []
        self.question_lookup = {row["id"]: row for row in (question_lookup or question_rows or [])}
        self.option_lookup = option_lookup or {}
        self.assessments = assessments or []
        self.written_sessions = written_sessions or []
        self.created_assessments: list[dict] = []
        self.inserted_answers: list[dict] = []

    async def get_questions(
        self,
        *,
        category: str | None,
        difficulty: str | None,
        limit: int,
        skill_id: str | None = None,
        skill_request_id: str | None = None,
        question_type: str = "MCQ",
    ) -> list[dict]:
        rows = [
            row
            for row in self.question_rows
            if row.get("question_type") == question_type
            and (category is None or row.get("category") == category)
            and (skill_id is None or row.get("skill_id") == skill_id)
            and (skill_request_id is None or row.get("skill_request_id") == skill_request_id)
        ]
        return rows[:limit]

    async def find_question_bank(
        self,
        *,
        requested_name: str,
        normalized_name: str,
        question_type: str = "MCQ",
        skill_id: str | None = None,
    ) -> dict | None:
        requested_name = requested_name.strip().lower()
        normalized_name = normalized_name.strip().lower()
        for row in self.question_rows:
            if row.get("question_type") != question_type:
                continue
            category = str(row.get("category") or "").strip().lower()
            row_skill_id = str(row.get("skill_id") or "").strip().lower()
            if skill_id and row_skill_id == str(skill_id).strip().lower():
                return row
            if category in {requested_name, normalized_name.replace("-", " ")}:
                return row
        return None

    async def get_options_for_questions(self, question_ids: list[str]) -> list[dict]:
        options: list[dict] = []
        for question_id in question_ids:
            options.extend(
                [
                    option
                    for option in self.option_lookup.values()
                    if option.get("question_id") == question_id
                ]
            )
        return options

    async def get_questions_by_ids(self, question_ids: list[str]) -> list[dict]:
        return [self.question_lookup[question_id] for question_id in question_ids]

    async def get_option(self, option_id: str) -> dict | None:
        return self.option_lookup.get(option_id)

    async def create_assessment(self, payload: dict) -> dict:
        record = {"id": f"assessment-{len(self.created_assessments) + 1}", **payload}
        self.created_assessments.append(record)
        return record

    async def insert_user_answers(self, payloads: list[dict]) -> list[dict]:
        self.inserted_answers.extend(payloads)
        return payloads

    async def list_user_assessments(self, user_id: str, limit: int = 25) -> list[dict]:
        return [row for row in self.assessments if row.get("user_id") == user_id][:limit]

    async def list_written_sessions(self, user_id: str, limit: int = 25) -> list[dict]:
        return [row for row in self.written_sessions if row.get("user_id") == user_id][:limit]


class FakeSkillCatalogRepository:
    def __init__(self, catalog: dict[str, dict] | None = None) -> None:
        self.catalog = catalog or {}

    async def get_skill_by_name(self, normalized_name: str) -> dict | None:
        return self.catalog.get(normalized_name)


class FakeSkillService:
    def __init__(
        self,
        *,
        user_skills: list[dict] | None = None,
        gaps: list[dict] | None = None,
        role_fit: dict | None = None,
        catalog: dict[str, dict] | None = None,
    ) -> None:
        self.user_skills = user_skills or []
        self.gaps = gaps or []
        self.role_fit = role_fit or {
            "role_name": "Cloud Engineer",
            "fit_score": 55.0,
        }
        self.repository = FakeSkillCatalogRepository(catalog)
        self.record_calls: list[dict] = []

    async def list_user_skills(self, user_id: str) -> list[dict]:
        return self.user_skills

    async def get_skill_gaps(self, user_id: str, role_name: str | None = None) -> list[dict]:
        return self.gaps

    async def get_role_fit(self, user_id: str) -> dict:
        return self.role_fit

    async def record_skill_measurement(self, **kwargs) -> dict:
        self.record_calls.append(kwargs)
        return kwargs


class FakeSkillRequestService:
    def __init__(self, requests: list[dict] | None = None) -> None:
        self.requests = requests or []

    async def list_requests(self, user_id: str) -> list[dict]:
        return self.requests

    async def ensure_question_bank(self, **kwargs) -> None:
        raise AssertionError("Question banks should not be generated during reads")


class FakeLearningRepository:
    def __init__(self, modules: list[dict] | None = None) -> None:
        self.modules = modules or []

    async def get_latest_path(self, user_id: str, role_name: str) -> dict | None:
        return {"id": "path-1"} if self.modules else None

    async def list_path_modules(self, path_id: str) -> list[dict]:
        return self.modules


class FakeProfileRepository:
    def __init__(self, profile: dict | None = None) -> None:
        self.profile = profile or {}

    async def get_profile(self, user_id: str) -> dict | None:
        return self.profile


class FakeProfileService:
    def __init__(self) -> None:
        self.profile = {"metadata": {}}
        self.updated_payloads: list[dict] = []

    async def get_profile(self, user_id: str, email: str | None) -> dict:
        return self.profile

    async def update_profile(self, user_id: str, payload: dict) -> dict:
        self.updated_payloads.append(payload)
        self.profile = {
            **self.profile,
            **payload,
        }
        return self.profile


@pytest.mark.asyncio
async def test_get_questions_does_not_generate_question_bank_on_read() -> None:
    repository = FakeAssessmentRepository(
        question_rows=[
            {
                "id": "question-1",
                "question_text": "What is cloud elasticity?",
                "category": "Cloud Computing",
                "difficulty": "medium",
                "skill_id": "cloud-computing",
                "skill_request_id": "request-1",
                "question_type": "mcq",
                "metadata": {},
            }
        ],
        option_lookup={
            "option-1": {
                "id": "option-1",
                "question_id": "question-1",
                "option_text": "Scale on demand",
                "is_correct": True,
            }
        },
    )
    service = MCQService(
        repository=repository,  # type: ignore[arg-type]
        event_service=FakeEventService(),  # type: ignore[arg-type]
        skill_request_service=FakeSkillRequestService(),
    )

    questions = await service.get_questions(
        category="Cloud Computing",
        difficulty=None,
        limit=5,
        skill_request_id="request-1",
    )

    assert len(questions) == 1
    assert questions[0]["skill_request_id"] == "request-1"


@pytest.mark.asyncio
async def test_get_subject_detail_returns_none_when_exact_bank_is_missing() -> None:
    skill_service = FakeSkillService(
        user_skills=[
            {
                "skill_id": "cloud-computing",
                "skill_name": "Cloud Computing",
                "proficiency_score": 44.0,
            }
        ],
        gaps=[
            {
                "skill_name": "Cloud Computing",
                "user_score": 44.0,
                "gap_severity": 0.91,
            }
        ],
        catalog={
            "cloud-computing": {
                "skill_id": "cloud-computing",
                "skill_name": "Cloud Computing",
            }
        },
    )
    learning_repository = FakeLearningRepository(
        modules=[
            {
                "skill_name": "Cloud Computing",
                "gap_severity": 0.91,
                "resources": [],
                "skill_id": "cloud-computing",
            }
        ]
    )
    service = MCQService(
        repository=FakeAssessmentRepository(),  # type: ignore[arg-type]
        event_service=FakeEventService(),  # type: ignore[arg-type]
        skill_service=skill_service,  # type: ignore[arg-type]
        skill_request_service=FakeSkillRequestService(),
        learning_repository=learning_repository,  # type: ignore[arg-type]
        profile_repository=FakeProfileRepository({"focus_role": "Cloud Engineer"}),  # type: ignore[arg-type]
    )

    detail = await service.get_subject_detail("user-1", "cloud-computing")

    assert detail is None


@pytest.mark.asyncio
async def test_get_subject_detail_returns_detail_for_seeded_subject_bank() -> None:
    skill_service = FakeSkillService(
        user_skills=[
            {
                "skill_id": "cloud-computing",
                "skill_name": "Cloud Computing",
                "proficiency_score": 44.0,
            }
        ],
        gaps=[
            {
                "skill_name": "Cloud Computing",
                "user_score": 44.0,
                "gap_severity": 0.91,
            }
        ],
        catalog={
            "cloud-computing": {
                "skill_id": "cloud-computing",
                "skill_name": "Cloud Computing",
            }
        },
    )
    learning_repository = FakeLearningRepository(
        modules=[
            {
                "skill_name": "Cloud Computing",
                "gap_severity": 0.91,
                "resources": [{"title": "Docs", "content": "Read the docs"}],
                "skill_id": "cloud-computing",
            }
        ]
    )
    repository = FakeAssessmentRepository(
        question_rows=[
            {
                "id": "question-1",
                "category": "Cloud Computing",
                "question_type": "MCQ",
                "skill_id": "cloud-computing",
                "is_active": True,
            }
        ]
    )
    service = MCQService(
        repository=repository,  # type: ignore[arg-type]
        event_service=FakeEventService(),  # type: ignore[arg-type]
        skill_service=skill_service,  # type: ignore[arg-type]
        skill_request_service=FakeSkillRequestService(),
        learning_repository=learning_repository,  # type: ignore[arg-type]
        profile_repository=FakeProfileRepository({"focus_role": "Cloud Engineer"}),  # type: ignore[arg-type]
    )

    detail = await service.get_subject_detail("user-1", "cloud-computing")

    assert detail is not None
    assert detail["title"] == "Cloud Computing"
    assert detail["skill_id"] == "cloud-computing"
    assert detail["current_score"] == 44.0


@pytest.mark.asyncio
async def test_get_assessment_log_includes_written_evaluation_details() -> None:
    repository = FakeAssessmentRepository(
        assessments=[
            {
                "id": "assessment-1",
                "user_id": "user-1",
                "assessment_type": "MCQ",
                "category": "Networking",
                "score": 78.0,
                "status": "completed",
                "completed_at": "2026-04-10T10:00:00Z",
            },
            {
                "id": "written-1",
                "user_id": "user-1",
                "assessment_type": "descriptive",
                "overall_score": 84.0,
                "status": "completed",
                "completed_at": "2026-04-11T10:00:00Z",
                "metadata": {
                    "prompt": "Explain how you would harden a cloud migration.",
                    "feedback": "Strong structure with a clear validation plan.",
                    "insights": ["Clear sequencing of the migration stages."],
                    "loopholes": ["Needs a stronger rollback example."],
                    "recommendations": ["Add one concrete cloud-provider example."],
                    "plagiarism": {
                        "risk_score": 22.0,
                        "risk_level": "low",
                        "summary": "Low plagiarism risk.",
                        "signals": ["No strong copy-patterns were detected."],
                    },
                    "readiness_score": 67.5,
                    "role_name": "Cloud Engineer",
                },
            }
        ],
    )
    service = MCQService(
        repository=repository,  # type: ignore[arg-type]
        event_service=FakeEventService(),  # type: ignore[arg-type]
    )

    log_entries = await service.get_assessment_log("user-1", limit=10)

    written_entry = next(entry for entry in log_entries if entry["id"] == "written-1")
    assert written_entry["subject"] == "Explain how you would harden a cloud migration."
    assert written_entry["strengths"] == ["Clear sequencing of the migration stages."]
    assert written_entry["risks"] == ["Needs a stronger rollback example."]
    assert written_entry["recommendations"] == ["Add one concrete cloud-provider example."]
    assert written_entry["plagiarism"]["risk_level"] == "low"
    assert written_entry["readiness_score"] == 67.5
    assert written_entry["role_name"] == "Cloud Engineer"


@pytest.mark.asyncio
async def test_complete_placement_assessment_records_domain_scores() -> None:
    repository = FakeAssessmentRepository(
        question_lookup=[
            {"id": "question-1", "category": "Mathematics", "correct_option": "option-1"},
            {"id": "question-2", "category": "English", "correct_option": "option-3"},
        ],
        option_lookup={
            "option-1": {"id": "option-1", "question_id": "question-1", "is_correct": True},
            "option-2": {"id": "option-2", "question_id": "question-2", "is_correct": False},
        },
    )
    skill_service = FakeSkillService(
        catalog={
            "mathematics": {"skill_id": "mathematics", "skill_name": "Mathematics"},
            "english": {"skill_id": "english", "skill_name": "English"},
        }
    )
    profile_service = FakeProfileService()
    service = MCQService(
        repository=repository,  # type: ignore[arg-type]
        event_service=FakeEventService(),  # type: ignore[arg-type]
        skill_service=skill_service,  # type: ignore[arg-type]
    )

    result = await service.complete_placement_assessment(
        user_id="user-1",
        answers=[
            {"question_id": "question-1", "selected_option_id": "option-1"},
            {"question_id": "question-2", "selected_option_id": "option-2"},
        ],
        role_name="Cloud Engineer",
        profile_service=profile_service,
    )

    assert result["overall_score"] == 50.0
    assert {call["skill_name"] for call in skill_service.record_calls} == {
        "Mathematics",
        "English",
    }
    assert profile_service.updated_payloads[0]["metadata"]["has_completed_placement"] is True
    assert profile_service.updated_payloads[0]["metadata"]["placement_overall_score"] == 50.0
