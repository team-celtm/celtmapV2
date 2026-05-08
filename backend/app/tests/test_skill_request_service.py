from __future__ import annotations

import pytest

from app.models.enums import DomainEventType
from app.services.skill_request_service import SkillRequestService


class FakeSkillRepository:
    def __init__(self) -> None:
        self.skill_request: dict = {}
        self.skill_catalog: dict = {}
        self.subject_catalog: dict = {}

    async def list_skill_requests(self, user_id: str) -> list[dict]:
        return []

    async def get_user_skill_request(self, user_id: str, normalized_name: str) -> dict | None:
        return None

    async def get_skill_by_name(self, normalized_name: str) -> dict | None:
        return None

    async def get_subject_by_name(self, normalized_name: str) -> dict | None:
        return self.subject_catalog.get(normalized_name)

    async def get_reusable_skill_request(self, normalized_name: str) -> dict | None:
        return None

    async def get_skill_request(self, request_id: str) -> dict | None:
        if self.skill_request.get("id") == request_id:
            return self.skill_request
        return None

    async def list_active_skills(self, limit: int = 500) -> list[dict]:
        return []

    async def upsert_skill_catalog(self, payload: dict) -> dict:
        record = {"id": "skill-row", **payload}
        self.skill_catalog = record
        return record

    async def get_skill_by_source_id(self, skill_id: str) -> dict | None:
        if self.skill_catalog.get("skill_id") == skill_id:
            return self.skill_catalog
        return None

    async def upsert_skill_request(self, payload: dict) -> dict:
        record = {"id": "request-1", **payload}
        self.skill_request = record
        return record

    async def update_skill_request(self, request_id: str, payload: dict) -> dict:
        self.skill_request = {**self.skill_request, **payload, "id": request_id}
        return self.skill_request

    async def upsert_subskill(self, payload: dict) -> dict:
        return payload

    async def upsert_user_skill(self, payload: dict) -> dict:
        return payload


class FakeAssessmentRepository:
    def __init__(self) -> None:
        self.questions: list[dict] = []

    async def upsert_question(self, payload: dict) -> dict:
        record = {"id": f"question-{len(self.questions) + 1}", **payload}
        self.questions.append(record)
        return record

    async def upsert_options(self, payload: list[dict]) -> list[dict]:
        return payload

    async def find_question_bank(self, **kwargs) -> dict | None:
        return None


class FakeRagService:
    async def upsert_documents(self, **kwargs) -> None:
        return None

    async def semantic_search(self, **kwargs) -> list[dict]:
        return []


class FakeLLMProvider:
    enabled = False


class ExplodingLLMProvider:
    enabled = True

    async def chat_json(self, **kwargs) -> dict:
        raise AssertionError("chat_json should not be called in fast generation mode")


class FakeOpsService:
    async def log_ai_call(self, **kwargs) -> None:
        return None


class FakeScheduleService:
    def __init__(self) -> None:
        self.events: list[dict] = []

    async def ensure_event(self, user_id: str, payload: dict) -> dict:
        event = {"user_id": user_id, **payload}
        self.events.append(event)
        return event


class FakeEventService:
    def __init__(self) -> None:
        self.events: list[dict] = []

    async def emit(self, **kwargs) -> None:
        self.events.append(kwargs)


@pytest.mark.asyncio
async def test_create_request_schedules_validation_and_dashboard_refresh() -> None:
    schedule_service = FakeScheduleService()
    event_service = FakeEventService()
    assessment_repository = FakeAssessmentRepository()
    service = SkillRequestService(
        repository=FakeSkillRepository(),
        assessment_repository=assessment_repository,
        rag_service=FakeRagService(),
        llm_provider=FakeLLMProvider(),  # type: ignore[arg-type]
        ops_service=FakeOpsService(),  # type: ignore[arg-type]
        schedule_service=schedule_service,  # type: ignore[arg-type]
        event_service=event_service,  # type: ignore[arg-type]
    )

    request = await service.create_request(
        user_id="user-1",
        requested_name="Data Visualization",
        description="Build dashboards and explain metrics.",
    )

    assert request["metadata"]["validation_status"] == "scheduled"
    assert request["metadata"]["validation_ready_at"]
    assert schedule_service.events[0]["title"] == "Validate Data Visualization"
    assert schedule_service.events[0]["event_type"] == "skill_validation"
    assert schedule_service.events[0]["metadata"]["skill_request_id"] == "request-1"
    assert event_service.events[0]["event_type"] == DomainEventType.DASHBOARD_REFRESH_REQUESTED
    assert {"MCQ", "SITUATIONAL", "WRITTEN"} <= {
        question["question_type"] for question in assessment_repository.questions
    }


@pytest.mark.asyncio
async def test_ensure_question_bank_normalizes_string_expected_concepts() -> None:
    repository = FakeSkillRepository()
    assessment_repository = FakeAssessmentRepository()
    service = SkillRequestService(
        repository=repository,
        assessment_repository=assessment_repository,
        rag_service=FakeRagService(),
        llm_provider=FakeLLMProvider(),  # type: ignore[arg-type]
        ops_service=FakeOpsService(),  # type: ignore[arg-type]
    )

    blueprint = service._heuristic_blueprint(
        "Python Fundamentals for ML",
        "python-fundamentals-for-ml",
        "Assess Python and data handling readiness for ML work.",
    )
    blueprint["mcq_questions"][0]["expected_concepts"] = "data cleaning|missing values|Pandas"
    blueprint["situational_questions"][0]["expected_concepts"] = (
        "tradeoff reasoning;validation strategy"
    )
    repository.skill_request = {
        "id": "request-1",
        "user_id": "user-1",
        "requested_name": "Python Fundamentals for ML",
        "normalized_name": "python-fundamentals-for-ml",
        "matched_skill_id": "python-fundamentals-for-ml",
        "generated_payload": blueprint,
        "metadata": {},
        "is_active": True,
    }

    updated_request = await service.ensure_question_bank(request_id="request-1")

    assert updated_request is not None
    assert updated_request["generated_payload"]["mcq_questions"][0]["expected_concepts"] == [
        "data cleaning",
        "missing values",
        "Pandas",
    ]
    assert updated_request["generated_payload"]["situational_questions"][0][
        "expected_concepts"
    ] == [
        "tradeoff reasoning",
        "validation strategy",
    ]
    assert all(
        isinstance(question["expected_concepts"], list)
        for question in assessment_repository.questions
    )


@pytest.mark.asyncio
async def test_create_request_fast_generation_skips_live_llm_calls() -> None:
    repository = FakeSkillRepository()
    assessment_repository = FakeAssessmentRepository()
    service = SkillRequestService(
        repository=repository,
        assessment_repository=assessment_repository,
        rag_service=FakeRagService(),
        llm_provider=ExplodingLLMProvider(),  # type: ignore[arg-type]
        ops_service=FakeOpsService(),  # type: ignore[arg-type]
    )

    request = await service.create_request(
        user_id="user-1",
        requested_name="Artificial Intelligence",
        description="Onboarding bootstrap path.",
        fast_generation=True,
    )

    assert request["generation_status"] == "generated_fast"
    assert request["generated_payload"]["written_prompt"]
    assert {"MCQ", "SITUATIONAL", "WRITTEN"} <= {
        question["question_type"] for question in assessment_repository.questions
    }


def test_heuristic_blueprint_generates_contextual_options() -> None:
    service = SkillRequestService(
        repository=FakeSkillRepository(),
        assessment_repository=FakeAssessmentRepository(),
        rag_service=FakeRagService(),
        llm_provider=FakeLLMProvider(),  # type: ignore[arg-type]
        ops_service=FakeOpsService(),  # type: ignore[arg-type]
    )

    blueprint = service._heuristic_blueprint(
        "Data Visualization",
        "data-visualization",
        "Build dashboards and explain metrics.",
    )

    mcq_option_sets = {
        tuple(option["option_text"] for option in question["options"])
        for question in blueprint["mcq_questions"]
    }
    situational_option_sets = {
        tuple(option["option_text"] for option in question["options"])
        for question in blueprint["situational_questions"]
    }

    assert len(mcq_option_sets) > 1
    assert len(situational_option_sets) > 1
