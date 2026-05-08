from __future__ import annotations

import pytest

from app.services.celtmind_sync import CeltmindSyncService


class FakeQuestionsTable:
    def __init__(self) -> None:
        self.records: list[dict] = []

    async def get_one(self, *, filters: dict, columns: str = "*") -> dict | None:
        for record in self.records:
            if (
                record["question_text"] == filters["question_text"]
                and record["category"] == filters["category"]
            ):
                return record
        return None


class FakeAssessmentRepository:
    def __init__(self) -> None:
        self.questions = FakeQuestionsTable()
        self.options_by_question: dict[str, list[dict]] = {}

    async def upsert_question(self, payload: dict) -> dict:
        existing = await self.questions.get_one(
            filters={
                "question_text": payload["question_text"],
                "category": payload["category"],
            }
        )
        if existing:
            return existing
        record = {**payload, "id": f"question-{len(self.questions.records) + 1}"}
        self.questions.records.append(record)
        return record

    async def upsert_options(self, payloads: list[dict]) -> list[dict]:
        if payloads:
            self.options_by_question[payloads[0]["question_id"]] = payloads
        return payloads


class FakeSyncRepository:
    def __init__(self) -> None:
        self.registry: dict[str, dict] = {}
        self.runs: dict[str, dict] = {}

    async def create_run(self, payload: dict) -> dict:
        run = {"id": "run-1", **payload}
        self.runs["run-1"] = run
        return run

    async def update_run(self, run_id: str, payload: dict) -> dict:
        self.runs[run_id].update(payload)
        return self.runs[run_id]

    async def get_file_registry(self, file_name: str) -> dict | None:
        return self.registry.get(file_name)

    async def upsert_file_registry(self, payload: dict) -> dict:
        self.registry[payload["file_name"]] = payload
        return payload


class FakeEventService:
    async def emit(self, **kwargs) -> dict:
        return kwargs


class FakeRagService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def upsert_documents(
        self,
        *,
        scope: str,
        source_type: str,
        documents: list[dict],
        user_id: str | None = None,
    ) -> list[dict]:
        self.calls.append(
            {
                "scope": scope,
                "source_type": source_type,
                "documents": documents,
                "user_id": user_id,
            }
        )
        return documents


@pytest.mark.asyncio
async def test_ingest_file_normalizes_questions_and_maps_correct_option(tmp_path) -> None:
    csv_path = tmp_path / "ml_basics.csv"
    csv_path.write_text(
        "question,option1,option2,option3,option4,option5,correct_option\n"
        "What is overfitting,High bias,High variance,Low error,Noise,None,2\n",
        encoding="utf-8",
    )

    sync_service = CeltmindSyncService(
        sync_repository=FakeSyncRepository(),
        assessment_repository=FakeAssessmentRepository(),
        event_service=FakeEventService(),
        celtmind_path=tmp_path,
    )

    result = await sync_service.ingest_file(csv_path)
    question = sync_service.assessment_repository.questions.records[0]
    options = sync_service.assessment_repository.options_by_question[question["id"]]

    assert result.inserted_questions == 1
    assert question["question_text"] == "What is overfitting?"
    assert question["category"] == "ml basics"
    assert len([option for option in options if option["is_correct"]]) == 1
    assert options[1]["is_correct"] is True


@pytest.mark.asyncio
async def test_ingest_file_is_idempotent_for_unchanged_checksum(tmp_path) -> None:
    csv_path = tmp_path / "sql.csv"
    csv_path.write_text(
        "question,option1,option2,option3,option4,option5,correct_option\n"
        "What is a join,Combine rows,Delete rows,Sort rows,Hash rows,None,1\n",
        encoding="utf-8",
    )

    repository = FakeSyncRepository()
    assessment_repository = FakeAssessmentRepository()
    sync_service = CeltmindSyncService(
        sync_repository=repository,
        assessment_repository=assessment_repository,
        event_service=FakeEventService(),
        celtmind_path=tmp_path,
    )

    first = await sync_service.ingest_file(csv_path)
    second = await sync_service.ingest_file(csv_path)

    assert first.inserted_questions == 1
    assert second.inserted_questions == 0
    assert second.updated_questions == 0


@pytest.mark.asyncio
async def test_ingest_file_seeds_question_documents_into_global_scope(tmp_path) -> None:
    csv_path = tmp_path / "analytics.csv"
    csv_path.write_text(
        "question,option1,option2,option3,option4,correct_option\n"
        "What is a KPI,Metric,Query,Schema,Index,1\n",
        encoding="utf-8",
    )

    rag_service = FakeRagService()
    sync_service = CeltmindSyncService(
        sync_repository=FakeSyncRepository(),
        assessment_repository=FakeAssessmentRepository(),
        event_service=FakeEventService(),
        rag_service=rag_service,
        celtmind_path=tmp_path,
    )

    await sync_service.ingest_file(csv_path)

    assert rag_service.calls
    assert rag_service.calls[0]["scope"] == "global"
    assert rag_service.calls[0]["source_type"] == "celtmind.question"
