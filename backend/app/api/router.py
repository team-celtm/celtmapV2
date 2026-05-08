from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.v1.routes import (
    admin,
    assessments,
    auth,
    copilot,
    dashboard,
    interview,
    learning,
    mcq,
    placement,
    profile,
    reports,
    schedule,
    sessions,
    settings,
    skill_requests,
    skills,
    trajectory,
    written_assessments,
)
from app.config.settings import Settings
from app.dependencies.auth import get_current_user
from app.dependencies.services import (
    get_app_settings,
    get_interview_service,
    get_learning_service,
    get_profile_service,
    get_skill_service,
)
from app.integrations.cache import CacheClient
from app.integrations.neo4j_client import get_neo4j_driver
from app.integrations.supabase import get_supabase_client
from app.observability.metrics import metrics
from app.repositories.ops_repository import OpsRepository
from app.schemas.common import AuthenticatedUser, HealthResponse
from app.schemas.interview import (
    CompatibilityInterviewStartRequest,
    CompatibilityInterviewSubmission,
)
from app.services.interview_service import InterviewService
from app.services.learning_service import LearningService
from app.services.profile_service import ProfileService
from app.services.skill_service import SkillService
from app.tasks.domain_events import process_retryable_domain_events


def create_api_router() -> APIRouter:
    api_router = APIRouter()
    api_router.include_router(auth.router)
    api_router.include_router(profile.router)
    api_router.include_router(settings.router)
    api_router.include_router(copilot.router)
    api_router.include_router(admin.router)
    api_router.include_router(mcq.router)
    api_router.include_router(assessments.router)
    api_router.include_router(placement.router)
    api_router.include_router(written_assessments.router)
    api_router.include_router(skills.router)
    api_router.include_router(skill_requests.router)
    api_router.include_router(learning.router)
    api_router.include_router(trajectory.router)
    api_router.include_router(interview.router)
    api_router.include_router(sessions.router)
    api_router.include_router(schedule.router)
    api_router.include_router(reports.router)
    api_router.include_router(dashboard.router)
    return api_router


def create_compat_router() -> APIRouter:
    compat_router = APIRouter()

    @compat_router.post("/interview/start")
    async def compat_start_interview(
        current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
        interview_service: Annotated[InterviewService, Depends(get_interview_service)],
        payload: CompatibilityInterviewStartRequest | None = None,
    ) -> dict:
        role_name = payload.role_name if payload else None
        session = await interview_service.create_session(
            user_id=current_user.id,
            role_name=role_name,
            skill_request_id=payload.skill_request_id if payload else None,
            interview_type=payload.interview_type if payload else "role",
        )
        return {"sessionId": session["id"], "status": "started"}

    @compat_router.post("/interview/submit")
    async def compat_submit_interview(
        payload: CompatibilityInterviewSubmission,
        current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
        interview_service: Annotated[InterviewService, Depends(get_interview_service)],
    ) -> dict:
        session_id = payload.session_id
        if session_id is None:
            session = await interview_service.create_session(
                user_id=current_user.id,
                role_name=payload.role_name,
                skill_request_id=payload.skill_request_id,
                interview_type=payload.interview_type,
            )
            session_id = session["id"]

        if payload.transcript:
            await interview_service.submit_transcript(session_id, payload.transcript)
        if payload.media_reference:
            await interview_service.submit_media_reference(session_id, payload.media_reference)

        if payload.transcript or payload.media_reference:
            await interview_service.complete_session(
                session_id=session_id,
                user_id=current_user.id,
            )
            process_retryable_domain_events.delay()
            return {
                "sessionId": session_id,
                "status": "submitted",
                "feedback": "Interview queued for evaluation",
            }

        return {
            "sessionId": session_id,
            "status": "pending_input",
            "feedback": "Transcript or media reference required before evaluation can be queued",
        }

    @compat_router.get("/learning-path")
    async def compat_learning_path(
        current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
        learning_service: Annotated[LearningService, Depends(get_learning_service)],
        profile_service: Annotated[ProfileService, Depends(get_profile_service)],
        skill_service: Annotated[SkillService, Depends(get_skill_service)],
    ) -> dict:
        profile_data = await profile_service.get_profile(current_user.id, current_user.email)
        role_name = profile_data.get("focus_role")
        if role_name is None:
            role_fit = await skill_service.get_role_fit(current_user.id)
            role_name = role_fit["role_name"]
        path = await learning_service.get_learning_path(current_user.id, role_name)
        recommended = [
            {
                "id": index,
                "type": "gap",
                "title": module["skill_name"],
                "desc": f"Week {module['week']} priority module",
            }
            for index, module in enumerate(path["modules"][:3], start=1)
        ]
        modules = [
            {
                "id": f"module-{module['week']}",
                "title": module["title"],
                "status": "recommended" if module["week"] == 1 else "pending",
                "score": round(max(0, 100 - module["gap_severity"] * 100), 2),
            }
            for module in path["modules"]
        ]
        return {"recommended": recommended, "modules": modules}

    @compat_router.get("/sessions")
    async def compat_sessions(
        current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
        interview_service: Annotated[InterviewService, Depends(get_interview_service)],
    ) -> dict:
        session_rows = await interview_service.list_sessions(current_user.id, limit=10, cursor=None)
        recent = []
        for session in session_rows:
            result = await interview_service.get_result(session["id"])
            recent.append(
                {
                    "id": session["id"],
                    "date": session.get("created_at"),
                    "role": session.get("role_name"),
                    "score": result["score"] if result else 0,
                    "duration": session.get("duration_seconds"),
                    "weakness": None,
                }
            )
        return {"recent": recent}

    @compat_router.get("/role-fit")
    async def compat_role_fit(
        current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
        skill_service: Annotated[SkillService, Depends(get_skill_service)],
    ) -> dict:
        role_fit = await skill_service.get_role_fit(current_user.id)
        skills_data = await skill_service.list_user_skills(current_user.id)
        top_skill = None
        if skills_data:
            top_skill = sorted(skills_data, key=lambda item: item["proficiency_score"], reverse=True)[
                0
            ]["skill_name"]
        return {
            "role": role_fit["role_name"],
            "probability": role_fit["fit_score"],
            "totalHours": None,
            "topSkill": top_skill,
        }

    @compat_router.get("/skills")
    async def compat_skills(
        current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
        skill_service: Annotated[SkillService, Depends(get_skill_service)],
    ) -> dict:
        skills_data = await skill_service.list_user_skills(current_user.id)
        return {item["skill_name"]: item["proficiency_score"] for item in skills_data}

    return compat_router


def create_system_router() -> APIRouter:
    router = APIRouter()

    @router.get("/health", response_model=HealthResponse, tags=["system"])
    async def health(
        settings: Annotated[Settings, Depends(get_app_settings)],
    ) -> HealthResponse:
        supabase_ok = False
        redis_ok = False
        neo4j_ok = False
        worker_ok = False

        try:
            client = get_supabase_client(settings)
            await asyncio.to_thread(
                lambda: client.table("profiles").select("id").limit(1).execute()
            )
            supabase_ok = True
        except Exception:
            supabase_ok = False

        try:
            redis_ok = CacheClient(settings).ping()
        except Exception:
            redis_ok = False

        try:
            driver = get_neo4j_driver(settings)
            if driver is not None:
                async with driver.session() as session:
                    await session.run("RETURN 1")
                    neo4j_ok = True
        except Exception:
            neo4j_ok = False

        last_worker_heartbeat = metrics.snapshot().get("last_worker_heartbeat")
        if last_worker_heartbeat:
            heartbeat_at = datetime.fromisoformat(last_worker_heartbeat)
            worker_ok = (datetime.now(timezone.utc) - heartbeat_at).total_seconds() <= 300

        overall = "ok"
        return HealthResponse(
            status=overall,
            services={
                "supabase": supabase_ok,
                "redis": redis_ok,
                "neo4j": neo4j_ok,
                "worker": worker_ok,
            },
            timestamp=datetime.now(timezone.utc),
        )

    @router.get("/system/metrics", tags=["system"])
    async def system_metrics(
        settings: Annotated[Settings, Depends(get_app_settings)],
    ) -> dict:
        cache = CacheClient(settings)
        metrics_snapshot = metrics.snapshot()
        recent_failures: list[dict] = []
        try:
            client = get_supabase_client(settings)
            recent_failures = await OpsRepository(client).list_recent_job_failures(limit=10)
        except Exception:
            recent_failures = []

        queue_lengths = {
            "default": cache.list_length("celery"),
            "dead_letter": cache.list_length(settings.dead_letter_queue_name),
        }
        last_worker_heartbeat = metrics_snapshot.get("last_worker_heartbeat")
        worker_online = False
        if last_worker_heartbeat:
            worker_online = (
                datetime.now(timezone.utc) - datetime.fromisoformat(last_worker_heartbeat)
            ).total_seconds() <= 300

        return {
            "api": {
                "request_count": metrics_snapshot["request_count"],
                "error_count": metrics_snapshot["error_count"],
                "rate_limited_count": metrics_snapshot["rate_limited_count"],
                "latency_ms_avg": metrics_snapshot["latency_ms_avg"],
                "latency_ms_by_route": metrics_snapshot["latency_ms_by_route"],
            },
            "queues": queue_lengths,
            "workers": {
                "online": worker_online,
                "last_heartbeat": last_worker_heartbeat,
                "failure_count": metrics_snapshot["worker_failures"],
            },
            "failures": {
                "dead_letter_count": queue_lengths["dead_letter"],
                "recent_failure_count": len(recent_failures),
                "recent": [
                    {
                        "task_name": row.get("task_name"),
                        "task_id": row.get("task_id"),
                        "entity_type": row.get("entity_type"),
                        "entity_id": row.get("entity_id"),
                        "status": row.get("status"),
                        "created_at": row.get("created_at"),
                    }
                    for row in recent_failures
                ],
            },
        }

    return router
