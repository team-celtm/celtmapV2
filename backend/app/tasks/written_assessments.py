from __future__ import annotations

import asyncio
import logging
from app.utils.async_runner import run_async
from datetime import datetime, timezone
from typing import Any

from app.config.settings import get_settings
from app.integrations.cache import CacheClient
from app.integrations.llm import OpenAIProvider
from app.integrations.supabase import get_supabase_client
from app.repositories.assessment_repository import AssessmentRepository
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

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="app.tasks.evaluate_written_assessment",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def evaluate_written_assessment(
    self: Any,
    session_id: str,
    user_id: str,
) -> dict:
    mark_worker_heartbeat()
    try:
        return run_async(
            run_written_assessment_evaluation(
                session_id=session_id,
                user_id=user_id,
            )
        )
    except Exception as exc:
        if self.request.retries >= 3:
            settings = get_settings()
            client = get_supabase_client(settings)
            assessment_repository = AssessmentRepository(client)
            run_async(
                assessment_repository.update_written_session(
                    session_id,
                    {
                        "status": "failed",
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
            )
            run_async(
                persist_job_failure(
                    settings=settings,
                    task_name="app.tasks.evaluate_written_assessment",
                    task_id=getattr(self.request, "id", None),
                    entity_type="written_assessment_session",
                    entity_id=session_id,
                    payload={"session_id": session_id, "user_id": user_id},
                    error=exc,
                    retry_count=self.request.retries,
                )
            )
        raise


async def run_written_assessment_evaluation(
    *,
    session_id: str,
    user_id: str,
) -> dict:
    settings = get_settings()
    client = get_supabase_client(settings)
    assessment_repository = AssessmentRepository(client)
    skill_repository = SkillRepository(client)
    report_repository = ReportRepository(client)
    openai_provider = OpenAIProvider(settings)
    ops_service = OpsService(OpsRepository(client))
    rag_service = RagService(
        settings=settings,
        cache=CacheClient(settings),
        repository=RagRepository(client),
        report_repository=report_repository,
        llm_provider=openai_provider,
        ops_service=ops_service,
    )
    skill_request_service = SkillRequestService(
        repository=skill_repository,
        assessment_repository=assessment_repository,
        rag_service=rag_service,
        llm_provider=openai_provider,
        ops_service=ops_service,
        schedule_service=ScheduleService(ScheduleRepository(client)),
    )
    skill_service = SkillService(
        skill_repository,
        DomainEventService(SyncRepository(client)),
    )
    evaluation_service = EvaluationService(openai_provider)
    return await _evaluate_written_session(
        session_id=session_id,
        user_id=user_id,
        assessment_repository=assessment_repository,
        skill_request_service=skill_request_service,
        skill_service=skill_service,
        evaluation_service=evaluation_service,
        rag_service=rag_service,
    )


async def _evaluate_written_session(
    *,
    session_id: str,
    user_id: str,
    assessment_repository: AssessmentRepository,
    skill_request_service: SkillRequestService,
    skill_service: SkillService,
    evaluation_service: EvaluationService,
    rag_service: RagService,
) -> dict:
    session = await assessment_repository.get_written_session(session_id)
    if session is None:
        return {"status": "missing", "session_id": session_id}

    submission_text = session.get("submission_text") or ""
    context_query = session.get("skill_id") or session.get("prompt")[:200] or "written assessment"
    try:
        context_documents = await rag_service.semantic_search(
            query=context_query,
            top_k=3,
            user_id=user_id,
        )
    except Exception:
        logger.warning(
            "Written assessment semantic search failed for session %s",
            session_id,
            exc_info=True,
        )
        context_documents = []
    evaluation = await evaluation_service.evaluate_written_submission(
        prompt_text=session["prompt"],
        submission_text=submission_text,
        rubric=session.get("rubric") or {},
        context_documents=context_documents,
        evaluator_mode=str((session.get("metadata") or {}).get("evaluator_mode") or "teacher"),
    )
    metadata = dict(session.get("metadata") or {})
    evaluation_metadata = evaluation.get("metadata")
    if isinstance(evaluation_metadata, dict):
        metadata.update(evaluation_metadata)
    metadata["evaluator_mode"] = str(metadata.get("evaluator_mode") or "teacher")
    insights = _coerce_string_list(evaluation.get("strengths"))
    loopholes = _coerce_string_list(evaluation.get("risks"))
    recommendations = _coerce_string_list(evaluation.get("recommendations"))
    plagiarism = evaluation.get("plagiarism")
    metadata["insights"] = insights
    metadata["strengths"] = insights
    metadata["loopholes"] = loopholes
    metadata["risks"] = loopholes
    metadata["recommendations"] = recommendations
    if isinstance(plagiarism, dict):
        metadata["plagiarism"] = plagiarism

    completed_at = datetime.now(timezone.utc).isoformat()
    updated_session = await assessment_repository.update_written_session(
        session_id,
        {
            "score": evaluation["score"],
            "feedback": evaluation["feedback"],
            "metadata": metadata,
            "status": "completed",
            "completed_at": completed_at,
            "updated_at": completed_at,
        },
    )

    if session.get("skill_request_id"):
        try:
            await skill_request_service.record_written_score(
                session["skill_request_id"],
                float(evaluation["score"]),
                evaluation["feedback"],
            )
        except Exception:
            logger.warning(
                "Failed to record written score for session %s",
                session_id,
                exc_info=True,
            )
    elif session.get("skill_id"):
        try:
            await skill_service.record_skill_measurement(
                user_id=user_id,
                skill_id=session["skill_id"],
                skill_name=context_query,
                written_score=float(evaluation["score"]),
                source="written_assessment",
            )
        except Exception:
            logger.warning(
                "Failed to record written assessment skill measurement for session %s",
                session_id,
                exc_info=True,
            )

    try:
        role_fit = await skill_service.get_role_fit(user_id)
    except Exception:
        logger.warning(
            "Failed to compute role-fit snapshot for written session %s",
            session_id,
            exc_info=True,
        )
    else:
        readiness_score = role_fit.get("fit_score")
        role_name = str(role_fit.get("role_name") or "").strip()
        metadata["readiness_score"] = (
            float(readiness_score) if readiness_score is not None else None
        )
        if role_name:
            metadata["role_name"] = role_name
        updated_session = await assessment_repository.update_written_session(
            session_id,
            {
                "metadata": metadata,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    # Hidden Skill Discovery
    hidden_skills = evaluation.get("hidden_skills") or []
    if hidden_skills and isinstance(hidden_skills, list):
        for hs in hidden_skills:
            try:
                if not isinstance(hs, dict):
                    continue
                skill_name = str(hs.get("skill_name") or "").strip()
                if not skill_name:
                    continue
                
                await skill_service.add_hidden_candidate(
                    user_id=user_id,
                    skill_name=skill_name,
                    confidence_score=float(hs.get("confidence_score") or 0.6),
                    evidence=str(hs.get("evidence") or f"Discovered during written assessment {session_id}"),
                    source="written_evaluation",
                )
            except Exception:
                logger.warning(
                    "Failed to record hidden skill candidate %s for user %s",
                    hs,
                    user_id,
                    exc_info=True,
                )

    _dispatch_noncritical_followups(user_id)

    return {
        "status": "completed",
        "session_id": session_id,
        "user_id": user_id,
        "score": updated_session.get("score"),
    }


def _coerce_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _dispatch_noncritical_followups(user_id: str) -> None:
    settings = get_settings()
    is_eager = settings.celery_eager_mode
    
    followups = [
        ("sync_user_graph", sync_user_graph),
        ("refresh_dashboard_projection", refresh_dashboard_projection),
        ("generate_user_report", generate_user_report),
    ]

    for name, task in followups:
        try:
            if is_eager:
                logger.debug("Running follow-up task %s synchronously for user %s", name, user_id)
                task(user_id)
            else:
                task.delay(user_id)
        except Exception:
            logger.warning(
                "Written assessment follow-up task %s failed for user %s",
                name,
                user_id,
                exc_info=True,
            )
