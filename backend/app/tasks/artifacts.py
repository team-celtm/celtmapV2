from __future__ import annotations

import asyncio
import logging
from app.utils.async_runner import run_async
from datetime import datetime, timezone
from typing import Any

from app.config.settings import Settings, get_settings
from app.integrations.supabase import get_supabase_client
from app.repositories.profile_repository import ProfileRepository
from app.repositories.skill_repository import SkillRepository
from app.repositories.sync_repository import SyncRepository
from app.services.domain_event_service import DomainEventService
from app.services.skill_service import SkillService
from app.tasks.celery_app import celery_app
from app.tasks.ops import mark_worker_heartbeat, persist_job_failure
from app.tasks.projections import refresh_dashboard_projection
from app.tasks.reports import generate_user_report
from app.utils.keywords import HIDDEN_SKILL_KEYWORDS
from app.utils.extraction import extract_text_from_bytes
from app.integrations.cache import CacheClient
from app.integrations.llm import OpenAIProvider
from app.repositories.rag_repository import RagRepository
from app.repositories.report_repository import ReportRepository
from app.repositories.ops_repository import OpsRepository
from app.services.ops_service import OpsService
from app.services.rag_service import RagService

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="app.tasks.extract_uploaded_artifact",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def extract_uploaded_artifact(self: Any, artifact_id: str) -> dict:
    settings = get_settings()
    client = get_supabase_client(settings)
    mark_worker_heartbeat()
    try:
        return run_async(
            process_uploaded_artifact_now(
                artifact_id=artifact_id,
                client=client,
                settings=settings,
            )
        )
    except Exception as exc:
        logger.error(f"Task extract_uploaded_artifact failed for artifact {artifact_id}: {exc}", exc_info=True)
        profile_repository = ProfileRepository(client)
        retries = getattr(self.request, "retries", 0)
        max_retries = getattr(self, "max_retries", 3)
        if retries >= max_retries or settings.celery_eager_mode:
            artifact = run_async(profile_repository.get_artifact(artifact_id))
            if artifact is not None:
                metadata = dict(artifact.get("metadata") or {})
                metadata["processing_status"] = "failed"
                metadata["processing_error"] = str(exc)
                run_async(
                    profile_repository.update_artifact(
                        artifact_id,
                        {"metadata": metadata, "processed_at": datetime.now(timezone.utc).isoformat()},
                    )
                )
            run_async(
                persist_job_failure(
                    settings=settings,
                    task_name="app.tasks.extract_uploaded_artifact",
                    task_id=getattr(self.request, "id", None),
                    entity_type="uploaded_artifact",
                    entity_id=artifact_id,
                    payload={"artifact_id": artifact_id},
                    error=exc,
                    retry_count=retries,
                )
            )
        raise


async def process_uploaded_artifact_now(
    *,
    artifact_id: str,
    client: Any | None = None,
    settings: Settings | None = None,
) -> dict:
    resolved_settings = settings or get_settings()
    resolved_client = client or get_supabase_client(resolved_settings)
    profile_repository = ProfileRepository(resolved_client)
    skill_repository = SkillRepository(resolved_client)
    skill_service = SkillService(skill_repository, DomainEventService(SyncRepository(resolved_client)))

    return await _extract_artifact(
        artifact_id=artifact_id,
        profile_repository=profile_repository,
        skill_repository=skill_repository,
        skill_service=skill_service,
        client=resolved_client,
        settings=resolved_settings,
    )


async def _extract_artifact(
    *,
    artifact_id: str,
    profile_repository: ProfileRepository,
    skill_repository: SkillRepository,
    skill_service: SkillService,
    client: Any,
    settings: Settings,
) -> dict:
    artifact = await profile_repository.get_artifact(artifact_id)
    if artifact is None:
        return {"status": "missing", "artifact_id": artifact_id}

    metadata = dict(artifact.get("metadata") or {})
    if artifact.get("processed_at") and metadata.get("processing_status") == "completed":
        return {
            "status": "already_processed",
            "artifact_id": artifact_id,
            "user_id": artifact.get("user_id"),
        }

    metadata["processing_status"] = "processing"
    await profile_repository.update_artifact(
        artifact_id,
        {
            "metadata": metadata,
        },
    )

    extracted_text = str(artifact.get("extracted_text") or "").strip()

    # If no text was extracted synchronously, or if it looks like junk/placeholder, try real parsing
    if not extracted_text or extracted_text.startswith("Artifact uploaded:"):
        try:
            # Download from storage
            bucket = artifact.get("bucket_name")
            if not bucket and artifact.get("file_url"):
                # Parse bucket from URL: .../public/{bucket}/{path}
                url_parts = str(artifact.get("file_url")).split("/public/")
                if len(url_parts) > 1:
                    bucket = url_parts[1].split("/")[0]

            if not bucket:
                bucket = settings.artifact_bucket

            path = artifact.get("storage_path")
            if path:
                content = await asyncio.to_thread(
                    lambda: client.storage.from_(bucket).download(path)
                )
                if content:
                    extracted_text = extract_text_from_bytes(
                        content,
                        artifact.get("file_name"),
                        str(metadata.get("content_type") or artifact.get("file_type") or ""),
                    ).strip()
        except Exception as exc:
            logger.error("Artifact extraction fallback failed for %s: %s", artifact_id, exc)
            if "OCR extraction failed" in str(exc):
                metadata["processing_error"] = "OCR extraction failed"

    if not extracted_text or extracted_text.startswith("Artifact uploaded:"):
        metadata["processing_status"] = "failed"
        metadata["processing_error"] = metadata.get("processing_error") or "Text extraction failed after fallback attempt"
        logger.error("Artifact %s failed extraction at fallback — marking failed", artifact_id)
        await profile_repository.update_artifact(
            artifact_id,
            {
                "metadata": metadata,
                "processed_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return {
            "status": "failed",
            "artifact_id": artifact_id,
            "user_id": artifact.get("user_id"),
        }

    final_metadata = {
        **metadata,
        "processing_status": "completed",
        "rag_indexed": False,
    }
    await profile_repository.update_artifact(
        artifact_id,
        {
            "extracted_text": extracted_text or None,
            "metadata": final_metadata,
            "processed_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    lowered = f"{artifact['file_name']} {artifact['file_type']} {extracted_text}".lower()
    detected = []
    
    # Simple derivation detection for visibility
    derived_subjects = []
    if any(kw in lowered for kw in ["math", "science", "english", "logic"]):
        derived_subjects = [kw for kw in ["math", "science", "english", "logic"] if kw in lowered]
        
    final_metadata["derived_subjects"] = derived_subjects
    final_metadata["processing_details"] = "RAG indexed for personalized mentoring"
    
    for skill_name, keywords in HIDDEN_SKILL_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            detected.append(skill_name)
            candidate_payload = {
                "user_id": artifact["user_id"],
                "skill_name": skill_name,
                "confidence_score": 0.62,
                "source": artifact["file_type"],
                "evidence": artifact["file_name"],
                "artifact_id": artifact_id,  # Link back to source artifact
                "status": "pending",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            try:
                await skill_repository.upsert_hidden_candidate(candidate_payload)
            except Exception:
                # Graceful fallback: artifact_id column may not exist yet in DB
                fallback_payload = {k: v for k, v in candidate_payload.items() if k != "artifact_id"}
                await skill_repository.upsert_hidden_candidate(fallback_payload)

    # Index into RAG for the personalized Copilot
    if extracted_text and not extracted_text.startswith("Artifact uploaded:"):
        llm_provider = None
        try:
            cache = CacheClient(settings)
            rag_repo = RagRepository(client)
            report_repo = ReportRepository(client)
            llm_provider = OpenAIProvider(settings)
            # Minimal ops service for logging
            ops_repo = OpsRepository(client)
            ops_ser = OpsService(ops_repo)

            rag_service = RagService(
                settings=settings,
                cache=cache,
                repository=rag_repo,
                report_repository=report_repo,
                profile_repository=profile_repository,
                llm_provider=llm_provider,
                ops_service=ops_ser,
            )

            await rag_service.upsert_documents(
                scope="user",
                user_id=artifact["user_id"],
                source_type="artifact",
                documents=[
                    {
                        "content": extracted_text,
                        "title": artifact["file_name"],
                        "source_ref": artifact["storage_path"],
                        "metadata": {
                            "artifact_id": artifact_id,
                            "file_type": artifact["file_type"],
                        },
                    }
                ],
            )
            final_metadata["rag_indexed"] = True
            await profile_repository.update_artifact(
                artifact_id,
                {
                    "metadata": final_metadata,
                },
            )
        except Exception as exc:
            logger.warning(
                "Artifact RAG indexing failed for %s: %s",
                artifact_id,
                exc,
            )
            # RAG indexing failure should not block the main extraction completion
            pass
        finally:
            if llm_provider is not None:
                await llm_provider.close()

    # Dispatch background tasks — all are best-effort; failures must NOT crash the upload.
    try:
        from app.tasks.trajectory import bootstrap_user_trajectory
        bootstrap_user_trajectory.delay(artifact["user_id"])
    except Exception as exc:
        logger.warning("bootstrap_user_trajectory dispatch failed (non-fatal): %s", exc)

    try:
        refresh_dashboard_projection.delay(artifact["user_id"])
    except Exception as exc:
        logger.warning("refresh_dashboard_projection dispatch failed (non-fatal): %s", exc)

    try:
        generate_user_report.delay(artifact["user_id"])
    except Exception as exc:
        logger.warning("generate_user_report dispatch failed (non-fatal): %s", exc)

    return {
        "status": "completed",
        "artifact_id": artifact_id,
        "user_id": artifact["user_id"],
        "detected_skills": detected,
    }
