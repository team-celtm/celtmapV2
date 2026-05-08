from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from app.config.settings import get_settings
from app.integrations.cache import CacheClient
from app.integrations.llm import OpenAIProvider
from app.integrations.supabase import get_supabase_client
from app.integrations.transcription import PlaceholderTranscriptionProvider
from app.repositories.assessment_repository import AssessmentRepository
from app.repositories.interview_repository import InterviewRepository
from app.repositories.ops_repository import OpsRepository
from app.repositories.rag_repository import RagRepository
from app.repositories.report_repository import ReportRepository
from app.repositories.schedule_repository import ScheduleRepository
from app.repositories.skill_repository import SkillRepository
from app.repositories.sync_repository import SyncRepository
from app.services.domain_event_service import DomainEventService
from app.services.evaluation_service import EvaluationService
from app.services.ops_service import OpsService
from app.services.rag_service import RagService
from app.services.schedule_service import ScheduleService
from app.services.skill_request_service import SkillRequestService
from app.services.skill_service import SkillService
from app.tasks.celery_app import celery_app
from app.tasks.graph import sync_user_graph
from app.tasks.ops import mark_worker_heartbeat, persist_job_failure
from app.tasks.projections import refresh_dashboard_projection
from app.tasks.reports import generate_user_report


def _skill_id(skill_name: str) -> str:
    return skill_name.strip().lower().replace(" ", "_")


@celery_app.task(
    bind=True,
    name="app.tasks.evaluate_interview_session",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def evaluate_interview_session(
    self: Any,
    session_id: str,
    user_id: str | None = None,
    trigger_event_id: str | None = None,
) -> dict:
    settings = get_settings()
    client = get_supabase_client(settings)
    interview_repository = InterviewRepository(client)
    skill_repository = SkillRepository(client)
    event_service = DomainEventService(SyncRepository(client))
    skill_service = SkillService(skill_repository, event_service)
    openai_provider = OpenAIProvider(settings)
    ops_service = OpsService(OpsRepository(client))
    evaluation_service = EvaluationService(openai_provider)
    rag_service = RagService(
        settings=settings,
        cache=CacheClient(settings),
        repository=RagRepository(client),
        report_repository=ReportRepository(client),
        llm_provider=openai_provider,
        ops_service=ops_service,
    )
    skill_request_service = SkillRequestService(
        repository=skill_repository,
        assessment_repository=AssessmentRepository(client),
        rag_service=rag_service,
        llm_provider=openai_provider,
        ops_service=ops_service,
        schedule_service=ScheduleService(ScheduleRepository(client)),
    )
    transcription_provider = PlaceholderTranscriptionProvider(settings)

    mark_worker_heartbeat()
    try:
        return asyncio.run(
            _evaluate_session(
                session_id=session_id,
                user_id=user_id,
                trigger_event_id=trigger_event_id,
                interview_repository=interview_repository,
                skill_repository=skill_repository,
                skill_service=skill_service,
                skill_request_service=skill_request_service,
                evaluation_service=evaluation_service,
                rag_service=rag_service,
                transcription_provider=transcription_provider,
            )
        )
    except Exception as exc:
        if self.request.retries >= 3:
            asyncio.run(
                interview_repository.update_session(
                    session_id,
                    {
                        "status": "failed",
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
            )
            asyncio.run(
                persist_job_failure(
                    settings=settings,
                    task_name="app.tasks.evaluate_interview_session",
                    task_id=getattr(self.request, "id", None),
                    entity_type="interview_session",
                    entity_id=session_id,
                    payload={
                        "session_id": session_id,
                        "user_id": user_id,
                        "trigger_event_id": trigger_event_id,
                    },
                    error=exc,
                    retry_count=self.request.retries,
                )
            )
        raise


async def _evaluate_session(
    *,
    session_id: str,
    user_id: str | None,
    trigger_event_id: str | None,
    interview_repository: InterviewRepository,
    skill_repository: SkillRepository,
    skill_service: SkillService,
    skill_request_service: SkillRequestService,
    evaluation_service: EvaluationService,
    rag_service: RagService,
    transcription_provider: PlaceholderTranscriptionProvider,
) -> dict:
    session = await interview_repository.get_session(session_id)
    if session is None:
        return {"status": "missing", "session_id": session_id}

    latest_evaluation = await interview_repository.get_latest_evaluation(session_id)
    session_metadata = dict(session.get("metadata") or {})
    if (
        session.get("status") == "completed"
        and latest_evaluation is not None
        and session_metadata.get("transcript_ingested_at")
    ):
        return {
            "status": "completed",
            "session_id": session_id,
            "user_id": user_id or session["user_id"],
            "score": latest_evaluation["score"],
            "event_id": trigger_event_id,
        }

    resolved_user_id = user_id or session["user_id"]
    transcript = session.get("transcript")
    if not transcript and session.get("media_reference"):
        transcript = await transcription_provider.transcribe_reference(session["media_reference"])
        await interview_repository.update_session(
            session_id,
            {
                "transcript": transcript,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    transcript = transcript or ""
    query = session.get("role_name") or transcript[:200] or "interview evaluation"
    context_documents = await rag_service.semantic_search(
        query=query,
        top_k=3,
        user_id=resolved_user_id,
    )
    evaluation = await evaluation_service.evaluate_transcript(transcript, context_documents)

    if latest_evaluation is None:
        await interview_repository.create_evaluation(
            {
                "session_id": session_id,
                "score": evaluation["score"],
                "feedback": evaluation["feedback"],
                "detected_skills": evaluation.get("detected_skills", []),
                "hidden_skills": evaluation.get("hidden_skills", []),
                "metrics": evaluation.get("evaluation_metrics", {}),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    await _persist_transcript_turns(
        interview_repository=interview_repository,
        session_id=session_id,
        question_answer_pairs=evaluation.get("question_answer_pairs", []),
        context_documents=context_documents,
    )

    session_metadata.update(
        {
            "transcript_ingested_at": datetime.now(timezone.utc).isoformat(),
            "transcript_turn_count": len(evaluation.get("question_answer_pairs", [])),
            "latest_evaluation_metrics": evaluation.get("evaluation_metrics", {}),
        }
    )
    await interview_repository.update_session(
        session_id,
        {
            "status": "completed",
            "metadata": session_metadata,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    if session.get("skill_request_id"):
        await skill_request_service.record_interview_score(
            session["skill_request_id"],
            float(evaluation["score"]),
        )

    current_skills = await skill_repository.list_user_skills(resolved_user_id)
    current_by_name = {item["skill_name"]: item for item in current_skills}

    for detected_skill in evaluation.get("detected_skills", []):
        skill_name = str(detected_skill["skill_name"])
        interview_score = round(float(detected_skill["confidence_score"]) * 100, 2)
        existing = current_by_name.get(skill_name, {})
        proficiency_score = skill_service.compute_weighted_skill_score(
            assessment_score=existing.get("assessment_score"),
            written_score=existing.get("written_score"),
            interview_score=interview_score,
            artifact_score=existing.get("artifact_score"),
        )
        await skill_repository.upsert_user_skill(
            {
                "user_id": resolved_user_id,
                "skill_id": existing.get("skill_id") or _skill_id(skill_name),
                "skill_name": skill_name,
                "proficiency_score": proficiency_score,
                "assessment_score": existing.get("assessment_score"),
                "written_score": existing.get("written_score"),
                "interview_score": interview_score,
                "artifact_score": existing.get("artifact_score"),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    for hidden_skill in evaluation.get("hidden_skills", []):
        await skill_repository.upsert_hidden_candidate(
            {
                "user_id": resolved_user_id,
                "skill_name": hidden_skill["skill_name"],
                "confidence_score": hidden_skill["confidence_score"],
                "source": "interview",
                "evidence": hidden_skill.get("evidence", transcript[:250]),
                "status": "pending",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    refresh_dashboard_projection.delay(resolved_user_id)
    generate_user_report.delay(resolved_user_id)
    sync_user_graph.delay(resolved_user_id, trigger_event_id)

    return {
        "status": "completed",
        "session_id": session_id,
        "user_id": resolved_user_id,
        "score": evaluation["score"],
        "event_id": trigger_event_id,
    }


async def _persist_transcript_turns(
    *,
    interview_repository: InterviewRepository,
    session_id: str,
    question_answer_pairs: list[dict],
    context_documents: list[dict],
) -> None:
    existing_questions = await interview_repository.list_session_questions(session_id)
    if existing_questions:
        return

    source_document = context_documents[0] if context_documents else None
    for pair in question_answer_pairs:
        question_text = str(pair.get("question_text") or "").strip()
        answer_text = str(pair.get("answer_text") or "").strip()
        if not question_text and not answer_text:
            continue

        question = await interview_repository.create_question(
            {
                "session_id": session_id,
                "question_text": question_text or "Interview follow-up",
                "source_document": source_document,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        await interview_repository.create_answer(
            {
                "session_id": session_id,
                "question_id": question["id"],
                "answer_text": answer_text,
                "metadata": {
                    "evaluation_metrics": pair.get("evaluation_metrics", {}),
                    "evidence": pair.get("evidence"),
                },
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
