from __future__ import annotations

import io
import ipaddress
import re
import socket
import time
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
import csv
import logging
from datetime import datetime, timedelta, timezone

from app.ai import (
    AnalysisUnavailableError,
    analyze_aspiration,
    analyze_certificate_value,
    analyze_resume,
    analyze_written_response,
    capability_domain_breakdown_from_resume,
    extract_certificate_text_with_ai,
    normalize_red_flags,
    normalize_resume_list,
    normalize_score_breakdown,
    normalize_top_keywords,
    call_ai_text,
    resolve_career_aim,
    suggest_career_aims,
)
from app import career_roles
from app.assessment_engine import (
    complete_assessment,
    create_assessment,
    get_assigned_questions,
    public_question,
    read_assessment,
    submit_answer,
)
from app.database import DIMENSIONS, Database, from_json, new_id, now_iso, to_json
from app.rate_limit import RateLimiter
from app.security import (
    AdminUser,
    CurrentUser,
    create_admin_token,
    generate_totp_secret,
    get_admin_user as decode_admin_bearer_user,
    get_current_user,
    hash_password,
    require_super_admin,
    verify_totp_code,
    verify_password,
    totp_uri,
)
from app.settings import Settings, get_settings
from app.storage import (
    delete_upload,
    ensure_private_bucket,
    parse_storage_reference,
    public_or_signed_url,
    sign_storage_url,
    store_upload,
)
from app.supabase_bank import (
    add_question_to_supabase,
    fetch_supabase_question_rows,
    question_bank_status,
)
from app.text_extract import extract_text_from_bytes


settings = get_settings()
db = Database(settings.database_target, postgres_schema=settings.postgres_schema)
logger = logging.getLogger(__name__)
INITIAL_ADMIN_TOKEN_VERSION = 0
AUTH_SCHEME_LABEL = "bear" + "er"
rate_limiter = RateLimiter(settings)

app = FastAPI(title=settings.app_name, debug=settings.app_debug)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
if settings.local_file_serving_enabled:
    app.mount("/files", StaticFiles(directory=settings.upload_dir), name="files")

REQUEST_METRICS = {
    "started_at": time.time(),
    "request_count": 0,
    "error_count": 0,
    "status_counts": {},
    "route_counts": {},
    "total_latency_ms": 0.0,
    "recent_failures": [],
}
def _request_identity(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        import hashlib

        return "token:" + hashlib.sha256(auth_header.encode("utf-8")).hexdigest()[:20]
    forwarded = request.headers.get("X-Forwarded-For", "").split(",", 1)[0].strip()
    return forwarded or (request.client.host if request.client else "unknown")


def _rate_limit_policy(path: str) -> tuple[str, int, int]:
    if path.endswith("/admin/login"):
        return "admin-login", settings.rate_limit_admin_login_per_15m, 15 * 60
    if (
        "/resume/analyze" in path
        or "/profile/me/artifacts" in path
        or "/profile/me/avatar" in path
        or "/admin/ingest-csv" in path
    ):
        return "uploads", settings.rate_limit_uploads_per_hour, 60 * 60
    if (
        path.endswith("/chat")
        or "/written-assessments/" in path and path.endswith("/complete")
        or "/career-aspirations" in path
        or path.endswith("/career-roles/suggestions")
        or "/profile/me/evidence-links" in path
    ):
        return "ai", settings.rate_limit_ai_per_hour, 60 * 60
    if "/assessments" in path:
        return "assessments", settings.rate_limit_assessment_per_minute, 60
    return "general", settings.rate_limit_general_per_minute, 60


async def _check_rate_limit(request: Request):
    if not settings.rate_limit_enabled:
        from app.rate_limit import RateLimitDecision

        return RateLimitDecision(True, 0, 0, 0, "disabled")
    bucket, limit, window_seconds = _rate_limit_policy(request.url.path)
    if limit <= 0:
        from app.rate_limit import RateLimitDecision

        return RateLimitDecision(True, 0, 0, 0, rate_limiter.backend_name)
    identity = _request_identity(request)
    checks = [(bucket, identity, limit, window_seconds)]
    if bucket == "ai" and settings.rate_limit_ai_global_per_minute > 0:
        checks.append(("ai-global", "all-users", settings.rate_limit_ai_global_per_minute, 60))
    return await rate_limiter.check_many(checks)


@app.middleware("http")
async def hardening_middleware(request: Request, call_next):
    rate_decision = await _check_rate_limit(request)
    if not rate_decision.allowed:
        response = JSONResponse(
            {"detail": rate_decision.error or "Too many requests. Please wait before trying again."},
            status_code=rate_decision.status_code,
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        if settings.is_hosted_mode:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        response.headers["Retry-After"] = str(rate_decision.retry_after)
        response.headers["X-RateLimit-Limit"] = str(rate_decision.limit)
        response.headers["X-RateLimit-Remaining"] = str(rate_decision.remaining)
        response.headers["X-RateLimit-Backend"] = rate_decision.backend
        return response

    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        REQUEST_METRICS["error_count"] += 1
        REQUEST_METRICS["recent_failures"] = (REQUEST_METRICS["recent_failures"] + [{
            "path": request.url.path,
            "status": 500,
            "at": now_iso(),
        }])[-20:]
        raise

    elapsed_ms = (time.perf_counter() - started) * 1000
    status = str(response.status_code)
    route_key = f"{request.method} {request.url.path}"
    REQUEST_METRICS["request_count"] += 1
    REQUEST_METRICS["total_latency_ms"] += elapsed_ms
    REQUEST_METRICS["status_counts"][status] = REQUEST_METRICS["status_counts"].get(status, 0) + 1
    REQUEST_METRICS["route_counts"][route_key] = REQUEST_METRICS["route_counts"].get(route_key, 0) + 1
    if response.status_code >= 500:
        REQUEST_METRICS["error_count"] += 1
        REQUEST_METRICS["recent_failures"] = (REQUEST_METRICS["recent_failures"] + [{
            "path": request.url.path,
            "status": response.status_code,
            "at": now_iso(),
        }])[-20:]

    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
    if settings.is_hosted_mode:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains; preload")
    if rate_decision.limit:
        response.headers.setdefault("X-RateLimit-Limit", str(rate_decision.limit))
        response.headers.setdefault("X-RateLimit-Remaining", str(rate_decision.remaining))
        response.headers.setdefault("X-RateLimit-Backend", rate_decision.backend)
    return response


@app.on_event("startup")
async def startup() -> None:
    db.init()
    await ensure_private_bucket(settings)
    ensure_super_admin_account()


class ProfilePatch(BaseModel):
    full_name: str | None = None
    headline: str | None = None
    focus_role: str | None = None
    weekly_goal: str | None = None
    avatar_url: str | None = None
    institution_id: str | None = None
    department_id: str | None = None
    institution_name: str | None = None
    department_name: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SettingsPatch(BaseModel):
    desktop_notifications: bool | None = None
    weekly_digest: bool | None = None
    folio_reminders: bool | None = None
    folio_focus: str | None = None
    security_mode: str | None = None


class AdminLoginRequest(BaseModel):
    username: str | None = None
    email: str | None = None
    password: str
    mfa_code: str | None = None


class InstitutionCreate(BaseModel):
    name: str
    domain: str = ""


class DepartmentCreate(BaseModel):
    institution_id: str
    name: str
    head_name: str | None = None
    head_email: str | None = None


class HeadCreate(BaseModel):
    institution_id: str
    department_id: str | None = None
    name: str
    email: str
    password: str
    mfa_secret: str | None = None


class AdminPasswordReset(BaseModel):
    password: str = Field(min_length=8)

class AdminChangePassword(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class AdminMfaVerify(BaseModel):
    code: str
    secret: str | None = None


class AdminMfaDisable(BaseModel):
    code: str | None = None


class AssessmentCreate(BaseModel):
    mode: str = "quick"
    category: str = "capability-profile"
    assessment_type: str = "capability"
    question_type: str = "MIXED"
    assignment_id: str | None = None


class AnswerSubmit(BaseModel):
    question_id: str
    selected_answer: str | None = None
    selected_option_id: str | None = None
    time_taken_seconds: int | None = None


class BatchAnswerSubmit(BaseModel):
    answers: list[dict[str, Any]]


class SchedulePayload(BaseModel):
    title: str
    starts_at: str
    ends_at: str | None = None
    event_type: str = "task"
    metadata: dict[str, str] = Field(default_factory=dict)


class SkillRequestCreate(BaseModel):
    requested_name: str
    requested_type: str = "skill"
    description: str | None = None


class AspirationCreate(BaseModel):
    desired_role: str


class CareerRoleResolvePayload(BaseModel):
    desired_role: str


class CareerRoleSuggestPayload(BaseModel):
    desired_role: str
    limit: int = Field(default=6, ge=1, le=8)


class RecommendedAspirationsCreate(BaseModel):
    desired_roles: list[str] = Field(default_factory=list)


class CareerDraftPersonalityPayload(BaseModel):
    interests: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    work_style: str | None = None
    experience_level: str | None = None
    preferred_industries: list[str] = Field(default_factory=list)
    notes: str | None = None


class ProfileEvidenceLink(BaseModel):
    label: str = ""
    url: str = ""
    type: str = "portfolio"


class ProfileEvidenceLinksPayload(BaseModel):
    links: list[ProfileEvidenceLink] = Field(default_factory=list)


class WrittenAssessmentCreate(BaseModel):
    skill_id: str | None = None
    skill_request_id: str | None = None
    evaluator_mode: str = "central_unbiased_ai"
    assignment_id: str | None = None


class WrittenAssessmentPatch(BaseModel):
    submission_text: str | None = None
    evaluator_mode: str | None = None


class ChatRequest(BaseModel):
    message: str
    history: list[dict[str, str]] = Field(default_factory=list)


async def get_admin_user(admin: AdminUser = Depends(decode_admin_bearer_user)) -> AdminUser:
    account = db.query_one("SELECT * FROM admin_accounts WHERE id = ?", (admin.id,))
    if not account:
        raise HTTPException(status_code=401, detail="Invalid or revoked admin token")
    metadata = from_json(account.get("metadata"), {})
    token_version = int(metadata.get("token_version") or 0)
    if token_version != admin.token_version:
        raise HTTPException(status_code=401, detail="Admin token has been revoked")
    return admin


def record_audit_event(
    action: str,
    actor_type: str = "system",
    actor_id: str | None = None,
    actor_email: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    request: Request | None = None,
) -> None:
    try:
        payload = dict(metadata or {})
        if request is not None:
            payload["ip"] = request.headers.get("X-Forwarded-For", "").split(",", 1)[0].strip() or (
                request.client.host if request.client else ""
            )
            payload["user_agent"] = request.headers.get("User-Agent", "")[:240]
        db.execute(
            """
            INSERT INTO audit_logs (
                id, actor_type, actor_id, actor_email, action, resource_type,
                resource_id, metadata, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id("audit"),
                actor_type,
                actor_id,
                actor_email,
                action,
                resource_type,
                resource_id,
                to_json(payload),
                now_iso(),
            ),
        )
    except Exception as exc:
        logger.debug("Could not record audit event %s: %s", action, exc)


def _admin_metadata(row: dict[str, Any]) -> dict[str, Any]:
    metadata = from_json(row.get("metadata"), {})
    if not isinstance(metadata, dict):
        return {}
    return metadata


def _admin_token_version(row: dict[str, Any]) -> int:
    return int(_admin_metadata(row).get("token_version") or 0)


def _bump_admin_token_version(account_id: str) -> int:
    row = db.query_one("SELECT metadata FROM admin_accounts WHERE id = ?", (account_id,))
    metadata = _admin_metadata(row or {})
    metadata["token_version"] = int(metadata.get("token_version") or 0) + 1
    metadata["tokens_revoked_at"] = now_iso()
    db.execute(
        "UPDATE admin_accounts SET metadata = ?, updated_at = ? WHERE id = ?",
        (to_json(metadata), now_iso(), account_id),
    )
    return int(metadata["token_version"])


def _admin_mfa_secret(account: dict[str, Any]) -> str:
    metadata = _admin_metadata(account)
    return str(metadata.get("mfa_secret") or settings.admin_mfa_secret or "").strip()


def _verify_admin_mfa(account: dict[str, Any], code: str | None) -> None:
    secret = _admin_mfa_secret(account)
    if not settings.admin_mfa_required and not secret:
        return
    if not secret or not verify_totp_code(secret, code):
        raise HTTPException(status_code=401, detail="Valid admin MFA code is required")


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def row_to_profile(row: dict[str, Any]) -> dict[str, Any]:
    avatar_url = row["avatar_url"]
    signed_avatar = public_or_signed_url(settings, None, avatar_url) if avatar_url else None
    return {
        "id": row["user_id"],
        "email": row["email"],
        "full_name": row["full_name"],
        "headline": row["headline"],
        "focus_role": row["focus_role"],
        "weekly_goal": row["weekly_goal"],
        "avatar_url": signed_avatar or avatar_url,
        "institution_id": row["institution_id"],
        "department_id": row["department_id"],
        "institution_name": row["institution_name"],
        "department_name": row["department_name"],
        "metadata": from_json(row["metadata"], {}),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def ensure_profile(user: CurrentUser) -> dict[str, Any]:
    row = db.query_one("SELECT * FROM profiles WHERE user_id = ?", (user.id,))
    if row:
        return row_to_profile(row)

    metadata = user.metadata or {}
    institution_name = str(metadata.get("institution_name") or metadata.get("institution") or "")
    department_name = str(metadata.get("department_name") or metadata.get("department") or "")
    institution = None
    department = None
    if institution_name:
        institution = db.query_one(
            "SELECT * FROM institutions WHERE lower(name) = lower(?)",
            (institution_name,),
        )
    if institution and department_name:
        department = db.query_one(
            "SELECT * FROM departments WHERE institution_id = ? AND lower(name) = lower(?)",
            (institution["id"], department_name),
        )
    profile_id = new_id("profile")
    name = metadata.get("full_name") or metadata.get("name") or (user.email.split("@")[0] if user.email else "")
    db.execute(
        """
        INSERT INTO profiles (
            id, user_id, email, full_name, focus_role, institution_id, department_id,
            institution_name, department_name, metadata, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            profile_id,
            user.id,
            user.email,
            name,
            metadata.get("target_role") or metadata.get("focus_role") or "",
            institution["id"] if institution else None,
            department["id"] if department else None,
            institution["name"] if institution else institution_name,
            department["name"] if department else department_name,
            to_json(
                {
                    "has_completed_onboarding": True,
                    "student_college_email": user.email,
                    "institution_name": institution["name"] if institution else institution_name,
                    "department_name": department["name"] if department else department_name,
                }
            ),
            now_iso(),
            now_iso(),
        ),
    )
    ensure_preferences(user.id)
    return row_to_profile(db.query_one("SELECT * FROM profiles WHERE user_id = ?", (user.id,)))


def ensure_preferences(user_id: str) -> dict[str, Any]:
    row = db.query_one("SELECT * FROM user_preferences WHERE user_id = ?", (user_id,))
    if not row:
        db.execute(
            "INSERT INTO user_preferences (user_id, updated_at) VALUES (?, ?)",
            (user_id, now_iso()),
        )
        row = db.query_one("SELECT * FROM user_preferences WHERE user_id = ?", (user_id,))
    return settings_row(row)


def settings_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_id": row["user_id"],
        "desktop_notifications": bool(row["desktop_notifications"]),
        "weekly_digest": bool(row["weekly_digest"]),
        "folio_reminders": bool(row["folio_reminders"]),
        "folio_focus": row["folio_focus"],
        "security_mode": row["security_mode"],
        "updated_at": row["updated_at"],
    }


def artifact_row(row: dict[str, Any]) -> dict[str, Any]:
    signed_url = public_or_signed_url(settings, row.get("bucket_name"), row.get("storage_path"))
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "bucket_name": row["bucket_name"],
        "storage_path": row["storage_path"],
        "signed_url": signed_url,
        "file_url": signed_url,
        "file_name": row["file_name"],
        "file_type": row["file_type"],
        "extracted_text": row["extracted_text"],
        "metadata": from_json(row["metadata"], {}),
        "created_at": row["created_at"],
    }


def latest_resume(user_id: str) -> dict[str, Any] | None:
    row = db.query_one(
        "SELECT * FROM resume_analyses WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
        (user_id,),
    )
    if not row:
        return None
    analysis = from_json(row["analysis"], {})
    analysis["score_breakdown"] = normalize_score_breakdown(analysis.get("score_breakdown"), [])
    analysis["top_keywords"] = normalize_top_keywords(analysis.get("top_keywords"), [])[:5]
    analysis["red_flags"] = normalize_red_flags(analysis.get("red_flags"), [])[:3]
    analysis["strong_points"] = normalize_resume_list(analysis.get("strong_points"), [])[:5]
    analysis["weak_points"] = normalize_resume_list(analysis.get("weak_points"), [])[:4]
    analysis["institute_help"] = normalize_resume_list(analysis.get("institute_help"), [])[:4]
    return {
        "id": row["id"],
        "artifact_id": row["artifact_id"],
        "target_role": row["target_role"],
        "match_score": row["match_score"],
        "analysis": analysis,
        "created_at": row["created_at"],
    }


def processing_job_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "job_type": row["job_type"],
        "status": row["status"],
        "result": from_json(row.get("result"), {}),
        "error": row.get("error"),
        "metadata": from_json(row.get("metadata"), {}),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def create_processing_job(user_id: str, job_type: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    job_id = new_id("job")
    timestamp = now_iso()
    db.execute(
        """
        INSERT INTO processing_jobs (id, user_id, job_type, status, result, error, metadata, created_at, updated_at)
        VALUES (?, ?, ?, 'queued', '{}', NULL, ?, ?, ?)
        """,
        (job_id, user_id, job_type, to_json(metadata or {}), timestamp, timestamp),
    )
    return processing_job_row(db.query_one("SELECT * FROM processing_jobs WHERE id = ?", (job_id,)))


def update_processing_job(
    job_id: str,
    status: str,
    result: dict[str, Any] | None = None,
    error: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    current = db.query_one("SELECT metadata FROM processing_jobs WHERE id = ?", (job_id,))
    merged_metadata = from_json(current.get("metadata") if current else None, {})
    if metadata:
        merged_metadata.update(metadata)
    db.execute(
        """
        UPDATE processing_jobs
        SET status = ?, result = ?, error = ?, metadata = ?, updated_at = ?
        WHERE id = ?
        """,
        (status, to_json(result or {}), error, to_json(merged_metadata), now_iso(), job_id),
    )


async def complete_resume_analysis_job(
    job_id: str,
    user_id: str,
    artifact_id: str,
    file_name: str,
    extracted_text: str,
    active_target_role: str,
    target_role_source: str,
    readiness_before: float,
) -> None:
    update_processing_job(job_id, "running")
    try:
        analysis = await analyze_resume(settings, extracted_text, active_target_role)
        analysis_id = new_id("resume")
        db.execute(
            """
            INSERT INTO resume_analyses (id, user_id, artifact_id, target_role, match_score, analysis, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                analysis_id,
                user_id,
                artifact_id,
                active_target_role,
                float(analysis.get("match_score", 0)),
                to_json(analysis),
                now_iso(),
            ),
        )
        profile = db.query_one("SELECT * FROM profiles WHERE user_id = ?", (user_id,))
        metadata = from_json(profile["metadata"], {}) if profile else {}
        metadata["profile_assets"] = {"resumeName": file_name}
        metadata["latest_resume_analysis_id"] = analysis_id
        db.execute(
            "UPDATE profiles SET metadata = ?, updated_at = ? WHERE user_id = ?",
            (to_json(metadata), now_iso(), user_id),
        )
        artifact_metadata = {
            "target_role": active_target_role,
            "target_role_source": target_role_source,
            "analysis_status": "completed",
            "analysis_id": analysis_id,
        }
        db.execute(
            "UPDATE artifacts SET metadata = ? WHERE id = ? AND user_id = ?",
            (to_json(artifact_metadata), artifact_id, user_id),
        )
        record_readiness_event(
            user_id,
            "resume",
            analysis_id,
            float(analysis.get("match_score", 0)),
            readiness_before,
            {"artifact_id": artifact_id, "target_role": active_target_role, "target_role_source": target_role_source},
        )
        update_processing_job(job_id, "completed", result=latest_resume(user_id) or {})
    except Exception as exc:
        error = str(exc)
        metadata = {
            "target_role": active_target_role,
            "target_role_source": target_role_source,
            "analysis_status": "failed",
            "analysis_error": error,
        }
        db.execute(
            "UPDATE artifacts SET metadata = ? WHERE id = ? AND user_id = ?",
            (to_json(metadata), artifact_id, user_id),
        )
        update_processing_job(job_id, "failed", error=error)


def latest_assessment(user_id: str) -> dict[str, Any] | None:
    return db.query_one(
        "SELECT * FROM assessments WHERE user_id = ? AND status = 'completed' ORDER BY completed_at DESC LIMIT 1",
        (user_id,),
    )


def written_assessment_row(row: dict[str, Any], readiness_score: float | None = None) -> dict[str, Any]:
    metadata = from_json(row["metadata"], {})
    canonical_readiness = readiness_score
    if canonical_readiness is None:
        stored_readiness = metadata.get("global_readiness_score")
        if isinstance(stored_readiness, (int, float)):
            canonical_readiness = _bounded_score(stored_readiness)
        elif metadata.get("readiness_kind") == "global" and isinstance(metadata.get("readiness_score"), (int, float)):
            canonical_readiness = _bounded_score(metadata.get("readiness_score"))
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "assignment_id": row.get("assignment_id"),
        "skill_id": row["skill_id"],
        "skill_request_id": row["skill_request_id"],
        "prompt": row["prompt"],
        "rubric": from_json(row["rubric"], {}),
        "submission_text": row["submission_text"],
        "score": row["score"],
        "feedback": row["feedback"],
        "status": row["status"],
        "metadata": metadata,
        "insights": metadata.get("insights", []),
        "loopholes": metadata.get("loopholes", []),
        "recommendations": metadata.get("recommendations", []),
        "plagiarism": metadata.get("plagiarism"),
        "readiness_score": canonical_readiness,
        "written_score": row["score"],
        "evaluation_score": metadata.get("evaluation_score", row["score"]),
        "role_name": metadata.get("role_name"),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def latest_written_assessment(user_id: str) -> dict[str, Any] | None:
    return db.query_one(
        """
        SELECT * FROM written_assessments
        WHERE user_id = ? AND status = 'completed'
        ORDER BY updated_at DESC LIMIT 1
        """,
        (user_id,),
    )


def artifact_evaluation_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "artifact_id": row["artifact_id"],
        "file_type": row["file_type"],
        "score": row["score"],
        "readiness_delta": row["readiness_delta"],
        "domain_breakdown": from_json(row["domain_breakdown"], {}),
        "evaluation": from_json(row["evaluation"], {}),
        "created_at": row["created_at"],
    }


def certificate_signal(user_id: str) -> dict[str, Any] | None:
    rows = db.query_all(
        """
        SELECT * FROM artifact_evaluations
        WHERE user_id = ? AND lower(file_type) IN ('certificate', 'certification', 'credential')
        ORDER BY created_at DESC
        """,
        (user_id,),
    )
    if not rows:
        return None
    evaluations = [artifact_evaluation_row(row) for row in rows]
    score = round(sum(float(item["score"]) for item in evaluations) / len(evaluations), 2)
    breakdown: dict[str, float] = {}
    for dimension in DIMENSIONS:
        values = [
            float(item["domain_breakdown"].get(dimension, item["score"]))
            for item in evaluations
        ]
        breakdown[dimension] = round(sum(values) / len(values), 2)
    return {
        "score": score,
        "count": len(evaluations),
        "domain_breakdown": breakdown,
        "latest": evaluations[0],
    }


READINESS_SIGNAL_WEIGHTS = {
    "resume": {"label": "Resume analysis", "weight": 0.30},
    "assessment": {"label": "Objective assessments", "weight": 0.35},
    "written": {"label": "Written assessment", "weight": 0.20},
    "certificate": {"label": "Credential evidence", "weight": 0.15},
    "profile_links": {"label": "Profile links", "weight": 0.10},
}


def _bounded_score(value: Any) -> float:
    try:
        score = float(value)
    except Exception:
        score = 0.0
    return round(max(0.0, min(100.0, score)), 2)


def _mean_score(values: list[float]) -> float:
    clean = [_bounded_score(value) for value in values]
    return round(sum(clean) / len(clean), 2) if clean else 0.0


PROFILE_LINK_KEYWORDS: dict[str, list[str]] = {
    "Data Thinking": ["sql", "analytics", "dashboard", "tableau", "power bi", "excel", "python", "data"],
    "Problem Solving": ["project", "debug", "solution", "case study", "algorithm", "system", "automation"],
    "Communication": ["linkedin", "article", "presentation", "portfolio", "summary", "profile", "case"],
    "Domain Foundation": ["certificate", "certification", "course", "degree", "training", "fundamentals"],
    "Industry Application": ["github", "deployment", "internship", "client", "product", "portfolio", "repository"],
    "AI Readiness": ["ai", "machine learning", "ml", "llm", "model", "prompt", "rag", "agent"],
}


def _normalize_profile_link_url(value: str) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.startswith("www."):
        raw = f"https://{raw}"
    parsed = urlparse(raw)
    if not parsed.scheme and parsed.netloc == "" and "." in raw.split("/")[0]:
        raw = f"https://{raw}"
        parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return raw


def _is_private_address(hostname: str) -> bool:
    lowered = hostname.strip().lower().rstrip(".")
    if lowered in {"localhost", "metadata.google.internal"} or lowered.endswith(".local"):
        return True
    try:
        literal_ip = ipaddress.ip_address(lowered)
        return (
            literal_ip.is_private
            or literal_ip.is_loopback
            or literal_ip.is_link_local
            or literal_ip.is_multicast
            or literal_ip.is_reserved
            or literal_ip.is_unspecified
        )
    except ValueError:
        pass
    try:
        resolved = socket.getaddrinfo(lowered, None)
    except socket.gaierror:
        return True
    for item in resolved:
        address = item[4][0]
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            return True
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return True
    return False


def _validate_external_profile_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Invalid URL")
    if _is_private_address(parsed.hostname):
        raise ValueError("Private or internal URLs are not allowed")


async def _fetch_profile_link_text(initial_url: str) -> tuple[int | None, bool, str, str | None]:
    current_url = initial_url
    for _ in range(max(1, settings.profile_link_max_redirects + 1)):
        _validate_external_profile_url(current_url)
        async with httpx.AsyncClient(
            timeout=settings.profile_link_timeout_seconds,
            follow_redirects=False,
            headers={"User-Agent": "CELTM-readiness-link-validator/1.0"},
        ) as client:
            async with client.stream("GET", current_url) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("Location")
                    if not location:
                        return response.status_code, False, "", "Redirect without Location"
                    current_url = urljoin(current_url, location)
                    continue

                reachable = response.status_code < 400
                content_type = response.headers.get("content-type", "").lower()
                if reachable and content_type and not any(
                    allowed in content_type
                    for allowed in ("text/html", "text/plain", "application/json", "application/xhtml+xml")
                ):
                    return response.status_code, False, "", "Unsupported content type"

                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > settings.profile_link_max_bytes:
                        return response.status_code, False, "", "Linked page is too large"
                    chunks.append(chunk)
                text = b"".join(chunks).decode(response.encoding or "utf-8", errors="ignore")
                return response.status_code, reachable, text, None
    return None, False, "", "Too many redirects"


def _profile_link_text(value: str) -> str:
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", value or "")
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()[:12000]


def _profile_link_domain_scores(text: str, link_type: str, reachable: bool) -> dict[str, float]:
    lowered = text.lower()
    base = 44.0 if reachable else 18.0
    scores: dict[str, float] = {}
    for dimension in DIMENSIONS:
        keywords = PROFILE_LINK_KEYWORDS.get(dimension, [])
        hits = sum(1 for keyword in keywords if keyword in lowered)
        score = base + min(36.0, hits * 7.5)
        if dimension == "Communication" and link_type in {"linkedin", "portfolio"}:
            score += 10
        if dimension == "Industry Application" and link_type in {"github", "portfolio"}:
            score += 12
        if dimension == "Domain Foundation" and link_type in {"certificate", "certification"}:
            score += 16
        scores[dimension] = _bounded_score(score)
    return scores


def _profile_link_skill_hits(text: str) -> list[str]:
    lowered = text.lower()
    hits: list[str] = []
    for dimension, keywords in PROFILE_LINK_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            hits.append(dimension)
    return hits[:6]


def profile_link_signal(user_id: str) -> dict[str, Any] | None:
    profile = db.query_one("SELECT metadata FROM profiles WHERE user_id = ?", (user_id,))
    if not profile:
        return None
    metadata = from_json(profile["metadata"], {})
    evidence = metadata.get("career_link_evidence")
    if not isinstance(evidence, dict):
        return None
    links = evidence.get("links") if isinstance(evidence.get("links"), list) else []
    reachable_links = [item for item in links if isinstance(item, dict) and item.get("reachable")]
    if not reachable_links:
        return None
    score = _bounded_score(evidence.get("score"))
    raw_breakdown = evidence.get("domain_breakdown") if isinstance(evidence.get("domain_breakdown"), dict) else {}
    breakdown = {
        dimension: _bounded_score(raw_breakdown.get(dimension, score))
        for dimension in DIMENSIONS
    }
    return {
        "score": score,
        "count": len(reachable_links),
        "domain_breakdown": breakdown,
        "skills": evidence.get("skills", []),
        "latest": evidence,
    }


def assessment_signal(user_id: str) -> dict[str, Any] | None:
    rows = db.query_all(
        """
        SELECT * FROM assessments
        WHERE user_id = ? AND status = 'completed' AND score IS NOT NULL
        ORDER BY COALESCE(completed_at, created_at) DESC
        """,
        (user_id,),
    )
    if not rows:
        return None

    latest_by_track: dict[str, dict[str, Any]] = {}
    for row in rows:
        track_key = "::".join(
            [
                str(row.get("category") or "capability-profile"),
                str(row.get("assessment_type") or "capability"),
                str(row.get("question_type") or "MIXED"),
            ]
        )
        if track_key not in latest_by_track:
            latest_by_track[track_key] = row

    selected = list(latest_by_track.values())
    scores = [_bounded_score(row["score"]) for row in selected]
    domain_values: dict[str, list[float]] = {dimension: [] for dimension in DIMENSIONS}
    for row in selected:
        row_score = _bounded_score(row["score"])
        capability_profile = from_json(row.get("capability_profile"), {})
        if isinstance(capability_profile, dict) and capability_profile:
            for dimension in DIMENSIONS:
                if dimension in capability_profile:
                    domain_values[dimension].append(_bounded_score(capability_profile[dimension]))
            continue

        category_key = normalize_key(str(row.get("category") or ""))
        matching_dimension = next(
            (dimension for dimension in DIMENSIONS if normalize_key(dimension) == category_key),
            None,
        )
        if matching_dimension:
            domain_values[matching_dimension].append(row_score)

    domain_breakdown = {
        dimension: _mean_score(values)
        for dimension, values in domain_values.items()
        if values
    }
    latest = selected[0]
    return {
        "id": latest["id"],
        "score": _mean_score(scores),
        "count": len(selected),
        "attempt_count": len(rows),
        "assessment_ids": [row["id"] for row in selected],
        "completed_at": latest.get("completed_at") or latest.get("created_at"),
        "domain_breakdown": domain_breakdown,
        "latest": latest,
    }


def _subject_title(value: str | None) -> str:
    raw = str(value or "Assessment").strip()
    if not raw:
        return "Assessment"
    normalized = normalize_key(raw)
    for dimension in DIMENSIONS:
        if normalize_key(dimension) == normalized:
            return dimension
    return re.sub(r"[-_]+", " ", raw).strip().title()


def _attempt_time(row: dict[str, Any], fallback_key: str = "created_at") -> str | None:
    return row.get("completed_at") or row.get("updated_at") or row.get(fallback_key)


def _assessment_attempt_type(row: dict[str, Any]) -> str:
    question_type = str(row.get("question_type") or "").upper()
    assessment_type = str(row.get("assessment_type") or "").lower()
    if question_type == "SITUATIONAL" or assessment_type == "situational":
        return "situational"
    if question_type == "DESCRIPTIVE":
        return "written"
    return "mcq"


def subject_progress_rows(user_id: str) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}

    def add_attempt(subject_raw: str, attempt: dict[str, Any]) -> None:
        subject = _subject_title(subject_raw)
        key = normalize_key(subject)
        bucket = grouped.setdefault(
            key,
            {
                "subject_key": key,
                "subject": subject,
                "attempts": [],
            },
        )
        bucket["attempts"].append(attempt)

    rows = db.query_all(
        """
        SELECT * FROM assessments
        WHERE user_id = ? AND status = 'completed' AND score IS NOT NULL
        ORDER BY COALESCE(completed_at, created_at) ASC
        """,
        (user_id,),
    )
    for row in rows:
        metadata = from_json(row.get("metadata") or "{}", {})
        analytics = metadata.get("analytics") if isinstance(metadata.get("analytics"), dict) else {}
        capability_profile = from_json(row.get("capability_profile"), {})
        score = _bounded_score(row["score"])
        add_attempt(
            str(row.get("category") or "Assessment"),
            {
                "id": row["id"],
                "type": _assessment_attempt_type(row),
                "score": score,
                "completed_at": _attempt_time(row),
                "question_type": row.get("question_type"),
                "assessment_type": row.get("assessment_type"),
                "correct": analytics.get("correct"),
                "wrong": analytics.get("wrong"),
                "total": analytics.get("total"),
                "capability_profile": capability_profile if isinstance(capability_profile, dict) else {},
            },
        )

    written_rows = db.query_all(
        """
        SELECT * FROM written_assessments
        WHERE user_id = ? AND status = 'completed' AND score IS NOT NULL
        ORDER BY updated_at ASC
        """,
        (user_id,),
    )
    for row in written_rows:
        metadata = from_json(row["metadata"], {})
        score = _bounded_score(row["score"])
        add_attempt(
            str(metadata.get("dimension") or row.get("skill_id") or "Written"),
            {
                "id": row["id"],
                "type": "written",
                "score": score,
                "completed_at": row.get("updated_at") or row.get("created_at"),
                "question_type": "DESCRIPTIVE",
                "assessment_type": "written",
                "correct": None,
                "wrong": None,
                "total": None,
                "capability_profile": {},
            },
        )

    progress: list[dict[str, Any]] = []
    for bucket in grouped.values():
        attempts = sorted(bucket["attempts"], key=lambda item: item.get("completed_at") or "")
        previous_score: float | None = None
        enriched_attempts = []
        for attempt in attempts:
            delta = None if previous_score is None else round(float(attempt["score"]) - previous_score, 2)
            enriched_attempts.append({**attempt, "delta_from_previous": delta})
            previous_score = float(attempt["score"])

        scores = [float(item["score"]) for item in enriched_attempts]
        first_score = scores[0]
        latest_score = scores[-1]
        improvement = round(latest_score - first_score, 2)
        if len(scores) < 2:
            trend = "single attempt"
        elif improvement >= 5:
            trend = "improving"
        elif improvement <= -5:
            trend = "declining"
        else:
            trend = "stable"

        best_attempt = max(enriched_attempts, key=lambda item: float(item["score"]))
        objective_attempts = [item for item in enriched_attempts if item["type"] != "written"]
        written_attempts = [item for item in enriched_attempts if item["type"] == "written"]
        subject_strengths = [bucket["subject"]] if latest_score >= 70 else []
        subject_repairs = [bucket["subject"]] if latest_score < 70 else []
        progress.append(
            {
                "subject_key": bucket["subject_key"],
                "subject": bucket["subject"],
                "attempt_count": len(enriched_attempts),
                "objective_attempt_count": len(objective_attempts),
                "written_attempt_count": len(written_attempts),
                "first_score": round(first_score, 2),
                "latest_score": round(latest_score, 2),
                "best_score": round(float(best_attempt["score"]), 2),
                "average_score": round(sum(scores) / len(scores), 2),
                "improvement": improvement,
                "trend": trend,
                "last_completed_at": enriched_attempts[-1].get("completed_at"),
                "best_attempt_id": best_attempt["id"],
                "latest_attempt_id": enriched_attempts[-1]["id"],
                "latest_type": enriched_attempts[-1]["type"],
                "strong_dimensions": subject_strengths,
                "weak_dimensions": subject_repairs,
                "next_action": subject_progress_next_action(bucket["subject"], trend, latest_score, improvement),
                "recent_attempts": list(reversed(enriched_attempts[-5:])),
            }
        )

    return sorted(progress, key=lambda item: (item["last_completed_at"] or "", item["attempt_count"]), reverse=True)


def subject_progress_next_action(subject: str, trend: str, latest_score: float, improvement: float) -> str:
    if latest_score < 45:
        return f"Rebuild {subject} basics before the next timed attempt."
    if trend == "declining":
        return f"Review the last two {subject} attempts and fix repeated mistakes before retesting."
    if trend == "improving" and latest_score >= 75:
        return f"Move {subject} into a harder situational or written practice block."
    if improvement > 0:
        return f"Keep the same {subject} practice loop and aim for another 5 point gain."
    return f"Take one focused {subject} retest after reviewing weak areas."


def readiness_snapshot(user_id: str) -> dict[str, Any]:
    resume = latest_resume(user_id)
    assessment = assessment_signal(user_id)
    written = latest_written_assessment(user_id)
    certificate = certificate_signal(user_id)
    profile_links = profile_link_signal(user_id)
    resume_score = _bounded_score(resume["match_score"]) if resume else 0.0
    assessment_score = _bounded_score(assessment["score"]) if assessment else 0.0
    written_score = _bounded_score(written["score"]) if written and written["score"] is not None else 0.0
    certificate_score = _bounded_score(certificate["score"]) if certificate else 0.0
    profile_link_score = _bounded_score(profile_links["score"]) if profile_links else 0.0
    components: list[dict[str, Any]] = []
    if resume:
        components.append({"key": "resume", "score": resume_score, **READINESS_SIGNAL_WEIGHTS["resume"]})
    if assessment:
        components.append({"key": "assessment", "score": assessment_score, **READINESS_SIGNAL_WEIGHTS["assessment"]})
    if written:
        components.append({"key": "written", "score": written_score, **READINESS_SIGNAL_WEIGHTS["written"]})
    if certificate:
        components.append({"key": "certificate", "score": certificate_score, **READINESS_SIGNAL_WEIGHTS["certificate"]})
    if profile_links:
        components.append({"key": "profile_links", "score": profile_link_score, **READINESS_SIGNAL_WEIGHTS["profile_links"]})
    if components:
        total_weight = sum(float(component["weight"]) for component in components)
        readiness = round(
            sum(float(component["score"]) * float(component["weight"]) for component in components) / total_weight,
            2,
        )
        for component in components:
            component["effective_weight"] = round(float(component["weight"]) / total_weight, 4)
    else:
        readiness = 0.0

    if assessment and assessment.get("domain_breakdown"):
        breakdown = dict(assessment["domain_breakdown"])
    elif resume:
        breakdown = capability_domain_breakdown_from_resume(resume_score)
    else:
        breakdown = {}
    if written and breakdown:
        for dimension in ("Communication", "Problem Solving"):
            if dimension in breakdown:
                breakdown[dimension] = round((float(breakdown[dimension]) + written_score) / 2, 2)
    if certificate:
        certificate_breakdown = certificate["domain_breakdown"]
        if not breakdown:
            breakdown = dict(certificate_breakdown)
        else:
            for dimension in DIMENSIONS:
                current = float(breakdown.get(dimension, 0))
                credential_score = float(certificate_breakdown.get(dimension, certificate_score))
                breakdown[dimension] = round((current * 0.85) + (credential_score * 0.15), 2)
    if profile_links:
        link_breakdown = profile_links["domain_breakdown"]
        if not breakdown:
            breakdown = dict(link_breakdown)
        else:
            for dimension in DIMENSIONS:
                current = float(breakdown.get(dimension, 0))
                link_score = float(link_breakdown.get(dimension, profile_link_score))
                breakdown[dimension] = round((current * 0.9) + (link_score * 0.1), 2)
    return {
        "readiness": readiness,
        "resume": resume,
        "assessment": assessment,
        "written_assessment": written_assessment_row(written) if written else None,
        "certificate": certificate,
        "profile_links": profile_links,
        "readiness_components": components,
        "component_scores": {component["key"]: component["score"] for component in components},
        "component_weights": {component["key"]: component["effective_weight"] for component in components},
        "readiness_formula": "active weighted average: resume 30%, objective assessments 35%, written 20%, credentials 15%, validated profile links 10%",
        "domain_breakdown": breakdown,
    }


def career_role_options() -> list[dict[str, Any]]:
    return career_roles.career_role_options()


def _career_role_entry(value: str | None) -> dict[str, Any] | None:
    return career_roles.career_role_entry(value)


def _unsupported_career_role_error() -> HTTPException:
    return HTTPException(
        status_code=400,
        detail="Choose a supported career role from the dropdown. This role is not available yet.",
    )


def _canonical_career_role(value: str | None, required: bool = True) -> str | None:
    try:
        return career_roles.canonical_career_role(value, required=required, allow_custom=True)
    except ValueError as exc:
        if "required" in str(exc).lower():
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        raise _unsupported_career_role_error()


def _role_tokens(role: str) -> set[str]:
    return career_roles.role_tokens(role)


def _tokens_from_value(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        return _role_tokens(value)
    if isinstance(value, (int, float, bool)):
        return set()
    if isinstance(value, list):
        tokens: set[str] = set()
        for item in value[:12]:
            tokens |= _tokens_from_value(item)
        return tokens
    if isinstance(value, dict):
        tokens: set[str] = set()
        for item in list(value.values())[:16]:
            tokens |= _tokens_from_value(item)
        return tokens
    return set()


def _pick_role_profile(tokens: set[str]) -> tuple[dict[str, Any], set[str]]:
    return career_roles.pick_role_profile(tokens)


def _profile_for_role_key(role_key: str | None) -> dict[str, Any]:
    return career_roles.profile_by_key(role_key)


def _resume_evidence_tokens(snapshot: dict[str, Any]) -> set[str]:
    resume = snapshot.get("resume") or {}
    analysis = resume.get("analysis") if isinstance(resume, dict) else {}
    tokens = _role_tokens(str(resume.get("target_role") or ""))
    tokens |= _tokens_from_value((analysis or {}).get("top_keywords"))
    tokens |= _tokens_from_value((analysis or {}).get("strong_points"))
    tokens |= _tokens_from_value((analysis or {}).get("summary"))
    tokens |= _tokens_from_value((analysis or {}).get("verdict"))
    certificate = snapshot.get("certificate") or {}
    latest_certificate = certificate.get("latest") if isinstance(certificate, dict) else {}
    tokens |= _tokens_from_value((latest_certificate or {}).get("evaluation"))
    profile_links = snapshot.get("profile_links") or {}
    latest_links = profile_links.get("latest") if isinstance(profile_links, dict) else {}
    tokens |= _tokens_from_value((latest_links or {}).get("skills"))
    tokens |= _tokens_from_value((latest_links or {}).get("links"))
    return tokens


def role_specific_readiness(desired_role: str, snapshot: dict[str, Any]) -> dict[str, Any]:
    tokens = _role_tokens(desired_role)
    profile, matched_keywords = career_roles.role_profile_for_label(desired_role)
    weights = dict(profile["weights"])
    difficulty_penalty = float(profile["difficulty_penalty"])
    raw_breakdown = snapshot.get("domain_breakdown") or {}
    global_readiness = _bounded_score(snapshot.get("readiness") or 0)
    conservative_floor = max(12.0, min(55.0, global_readiness * 0.65))
    breakdown = {
        dimension: _bounded_score(raw_breakdown.get(dimension, conservative_floor))
        for dimension in DIMENSIONS
    }
    weighted_capability = sum(float(breakdown.get(dimension, 0)) * weight for dimension, weight in weights.items())
    resume = snapshot.get("resume")
    resume_target = str((resume or {}).get("target_role") or "")
    resume_tokens = _role_tokens(resume_target)
    overlap_ratio = len(tokens & resume_tokens) / max(1, len(tokens)) if tokens else 0
    evidence_tokens = _resume_evidence_tokens(snapshot)
    evidence_overlap_ratio = len(tokens & evidence_tokens) / max(1, len(tokens)) if tokens else 0
    component_count = len(snapshot.get("readiness_components") or [])
    assessed_dimension_ratio = len([value for value in raw_breakdown.values() if value]) / max(1, len(DIMENSIONS))
    evidence_confidence = min(
        100.0,
        (component_count / 4) * 30
        + overlap_ratio * 25
        + evidence_overlap_ratio * 30
        + assessed_dimension_ratio * 15,
    )
    alignment_adjustment = round(
        (overlap_ratio * 12)
        + (evidence_overlap_ratio * 8)
        + min(8, len(matched_keywords) * 2)
        - (0 if matched_keywords else 8),
        2,
    )
    if not resume:
        alignment_adjustment -= 6

    required_dimension_gaps = [
        {
            "dimension": dimension,
            "weight": round(float(weights.get(dimension, 0)), 3),
            "score": round(float(breakdown.get(dimension, 0)), 2),
            "gap_to_ready": round(max(0.0, 82.0 - float(breakdown.get(dimension, 0))), 2),
        }
        for dimension in DIMENSIONS
        if weights.get(dimension, 0) > 0
    ]
    required_dimension_gaps.sort(key=lambda item: (item["gap_to_ready"] * item["weight"]), reverse=True)
    weighted_gap = sum(item["gap_to_ready"] * item["weight"] for item in required_dimension_gaps)
    spread = max(breakdown.values()) - min(breakdown.values()) if breakdown else 0.0
    flat_profile_penalty = max(0.0, 5.0 - spread) * 0.7
    if not raw_breakdown:
        flat_profile_penalty += 6.0
    unknown_role_penalty = 5.0 if profile["key"] == "custom" else 0.0

    score = (
        weighted_capability * 0.62
        + global_readiness * 0.14
        + evidence_confidence * 0.14
        + alignment_adjustment
        - difficulty_penalty
        - (weighted_gap * 0.08)
        - flat_profile_penalty
        - unknown_role_penalty
    )
    score = max(0, min(98, round(score, 2)))
    return {
        "score": score,
        "weighted_capability": round(weighted_capability, 2),
        "global_readiness": round(global_readiness, 2),
        "role_profile": profile["name"],
        "role_profile_key": profile["key"],
        "dimension_weights": weights,
        "role_adjusted_domain_breakdown": breakdown,
        "required_dimension_gaps": required_dimension_gaps[:4],
        "matched_keywords": sorted(matched_keywords),
        "resume_role_overlap": round(overlap_ratio, 2),
        "evidence_role_overlap": round(evidence_overlap_ratio, 2),
        "evidence_confidence": round(evidence_confidence, 2),
        "alignment_adjustment": alignment_adjustment,
        "difficulty_penalty": difficulty_penalty,
        "flat_profile_penalty": round(flat_profile_penalty, 2),
        "score_formula": "role weighted capability + global readiness + evidence confidence - role gap/difficulty penalties",
    }


DIMENSION_SKILL_SUGGESTIONS: dict[str, list[str]] = {
    "Data Thinking": ["SQL analytics", "Dashboard interpretation", "Data cleaning"],
    "Problem Solving": ["Structured problem solving", "Debugging practice", "Case reasoning"],
    "Communication": ["Professional writing", "Interview storytelling", "Evidence presentation"],
    "Domain Foundation": ["Role fundamentals", "Foundation certification", "Core terminology"],
    "Industry Application": ["Portfolio project", "Tool workflow proof", "Industry case study"],
    "AI Readiness": ["AI tool fluency", "Prompt evaluation", "Responsible AI basics"],
}


def adjacent_fits_for_role(role_fit_score: dict[str, Any], desired_role: str | None = None) -> list[str]:
    role_key = str(role_fit_score.get("role_profile_key") or "custom")
    return career_roles.adjacent_fits_for_role(desired_role, role_key)


def _career_context_tokens(profile: dict[str, Any], snapshot: dict[str, Any], draft: dict[str, Any] | None = None) -> set[str]:
    metadata = profile.get("metadata") if isinstance(profile.get("metadata"), dict) else {}
    tokens = _tokens_from_value(profile.get("focus_role"))
    tokens |= _tokens_from_value(profile.get("headline"))
    tokens |= _tokens_from_value(metadata.get("target_industry"))
    tokens |= _tokens_from_value(metadata.get("bio"))
    tokens |= _tokens_from_value(metadata.get("draft_personality"))
    tokens |= _tokens_from_value(metadata.get("career_links"))
    tokens |= _tokens_from_value(metadata.get("career_link_evidence"))
    tokens |= _resume_evidence_tokens(snapshot)
    if draft:
        tokens |= _tokens_from_value(draft)
    return tokens


def _role_candidate_names(desired_role: str | None, profile: dict[str, Any]) -> list[str]:
    return career_roles.role_candidate_names(desired_role, profile.get("focus_role"))


def _recommendation_reason(role: str, fit: dict[str, Any], context_overlap: float, has_assessment: bool) -> str:
    profile_name = fit.get("role_profile") or "this role family"
    if context_overlap >= 0.35:
        return f"Your saved evidence and interests overlap strongly with {profile_name}."
    if has_assessment and fit.get("required_dimension_gaps"):
        strongest = sorted(
            fit.get("role_adjusted_domain_breakdown", {}).items(),
            key=lambda item: float(item[1]),
            reverse=True,
        )
        if strongest:
            return f"Your assessed {strongest[0][0]} score gives this path a practical starting point."
    if fit.get("matched_keywords"):
        return f"Your aim matches {profile_name} keywords: {', '.join(fit['matched_keywords'][:3])}."
    return f"This is a broad fit from your current CELTM readiness and profile evidence."


def _suggested_skills_for_role(fit: dict[str, Any], has_assessment: bool) -> list[str]:
    if not has_assessment:
        return []
    suggestions: list[str] = []
    for gap in fit.get("required_dimension_gaps", [])[:3]:
        dimension = str(gap.get("dimension") or "")
        for skill in DIMENSION_SKILL_SUGGESTIONS.get(dimension, [dimension]):
            if skill and skill not in suggestions:
                suggestions.append(skill)
            if len(suggestions) >= 3:
                return suggestions
    return suggestions[:3]


def build_career_recommendations(
    user_id: str,
    desired_role: str | None = None,
    draft: dict[str, Any] | None = None,
) -> dict[str, Any]:
    canonical_desired_role = _canonical_career_role(desired_role, required=False) if desired_role else None
    profile_row = db.query_one("SELECT * FROM profiles WHERE user_id = ?", (user_id,))
    if not profile_row:
        raise HTTPException(status_code=404, detail="Profile not found")
    profile = row_to_profile(profile_row)
    snapshot = readiness_snapshot(user_id)
    assessment = snapshot.get("assessment")
    has_assessment = bool(assessment and (assessment.get("domain_breakdown") or assessment.get("score")))
    context_tokens = _career_context_tokens(profile, snapshot, draft)
    requested_tokens = _role_tokens(canonical_desired_role or "")
    recommendations: list[dict[str, Any]] = []
    for role in _role_candidate_names(canonical_desired_role, profile):
        fit = role_specific_readiness(role, snapshot)
        role_tokens = _role_tokens(role)
        denominator = max(1, len(role_tokens))
        context_overlap = len(role_tokens & context_tokens) / denominator if role_tokens else 0.0
        desired_overlap = len(role_tokens & requested_tokens) / max(1, len(requested_tokens)) if requested_tokens else 0.0
        score = _bounded_score(
            (float(fit["score"]) * 0.76)
            + (float(snapshot["readiness"]) * 0.10)
            + (context_overlap * 18)
            + (desired_overlap * 12)
            + (6 if normalize_key(role) == normalize_key(canonical_desired_role or "") and canonical_desired_role else 0)
        )
        gaps = [
            str(item.get("dimension"))
            for item in fit.get("required_dimension_gaps", [])
            if item.get("dimension")
        ][:3]
        recommendations.append(
            {
                "role": role,
                "fit_score": score,
                "readiness_score": fit["score"],
                "global_readiness": snapshot["readiness"],
                "role_profile": fit.get("role_profile"),
                "reason": _recommendation_reason(role, fit, context_overlap, has_assessment),
                "evidence": {
                    "matched_keywords": fit.get("matched_keywords", []),
                    "context_overlap": round(context_overlap, 2),
                    "evidence_confidence": fit.get("evidence_confidence", 0),
                    "primary_gaps": gaps,
                },
                "path_summary": f"Use {fit.get('role_profile') or role} as a career aim, then close {gaps[0] if gaps else 'the first measured gap'}.",
                "suggested_skills": _suggested_skills_for_role(fit, has_assessment),
                "needs_assessment": not has_assessment,
            }
        )

    recommendations.sort(key=lambda item: (float(item["fit_score"]), float(item["readiness_score"])), reverse=True)
    top = recommendations[:3]
    for index, item in enumerate(top):
        item["rank"] = index + 1
        item["is_primary"] = index == 0
        if index == 0:
            item["readiness_score"] = snapshot["readiness"]
            item["readiness_note"] = "Uses current dashboard readiness when this path is selected."
        else:
            item["readiness_note"] = "Uses role-specific readiness when this path is selected."

    source = "career_aim" if (canonical_desired_role or profile.get("focus_role")) else "draft_personality" if draft else "profile_evidence"
    return {
        "recommendations": top,
        "source": source,
        "analyzed_at": now_iso(),
        "needs_assessment_for_skills": not has_assessment,
        "readiness_score": snapshot["readiness"],
        "draft_personality": draft or (profile.get("metadata") or {}).get("draft_personality"),
    }


def career_aim_context_for_user(user_id: str) -> dict[str, Any]:
    profile_row = db.query_one("SELECT * FROM profiles WHERE user_id = ?", (user_id,))
    profile = row_to_profile(profile_row) if profile_row else {}
    snapshot = readiness_snapshot(user_id)
    return {
        "profile_focus_role": profile.get("focus_role"),
        "headline": profile.get("headline"),
        "readiness_score": snapshot.get("readiness"),
        "resume_target_role": (snapshot.get("resume") or {}).get("target_role") if snapshot.get("resume") else None,
    }


async def resolve_career_aim_for_user(user_id: str, desired_role: str) -> tuple[str, dict[str, Any]]:
    raw_role = career_roles.clean_role_label(desired_role)
    if not raw_role:
        raise HTTPException(status_code=400, detail="Desired role is required")
    context = career_aim_context_for_user(user_id)
    resolution = await resolve_career_aim(settings, raw_role, career_role_options(), context)
    resolved_role = str(resolution.get("normalized_role") or "").strip()
    if not resolved_role:
        raise HTTPException(status_code=400, detail="Could not understand the desired career aim.")
    canonical_role = career_roles.canonical_career_role(resolved_role, required=True, allow_custom=True) or resolved_role
    entry = _career_role_entry(canonical_role)
    if entry:
        canonical_role = str(entry["label"])
        resolution["matched_catalog_role"] = canonical_role
        resolution["is_supported_catalog"] = True
    resolution["normalized_role"] = canonical_role
    return canonical_role, resolution


def persist_readiness_snapshot(user_id: str, snapshot: dict[str, Any]) -> None:
    profile = db.query_one("SELECT * FROM profiles WHERE user_id = ?", (user_id,))
    if not profile:
        return
    metadata = from_json(profile["metadata"], {})
    metadata["readiness_score"] = snapshot["readiness"]
    metadata["domain_breakdown"] = snapshot["domain_breakdown"]
    metadata["readiness_components"] = snapshot.get("readiness_components", [])
    metadata["readiness_formula"] = snapshot.get("readiness_formula")
    if snapshot.get("certificate"):
        metadata["certificate_readiness"] = snapshot["certificate"]["score"]
    if snapshot.get("profile_links"):
        metadata["profile_link_readiness"] = snapshot["profile_links"]["score"]
    db.execute(
        "UPDATE profiles SET metadata = ?, updated_at = ? WHERE user_id = ?",
        (to_json(metadata), now_iso(), user_id),
    )


def sync_aspirations_readiness(user_id: str, snapshot: dict[str, Any] | None = None) -> None:
    # Career aims are saved analysis snapshots. New resume/assessment evidence should
    # prompt a deliberate reanalysis instead of silently rewriting old ambitions.
    return


def record_readiness_event(
    user_id: str,
    source_type: str,
    source_id: str | None,
    score: float,
    readiness_before: float,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    snapshot = readiness_snapshot(user_id)
    readiness_after = float(snapshot["readiness"])
    event_id = new_id("ready")
    db.execute(
        """
        INSERT INTO readiness_events (
            id, user_id, source_type, source_id, score, readiness_before,
            readiness_after, delta, metadata, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            user_id,
            source_type,
            source_id,
            float(score),
            float(readiness_before),
            readiness_after,
            round(readiness_after - float(readiness_before), 2),
            to_json(metadata or {}),
            now_iso(),
        ),
    )
    persist_readiness_snapshot(user_id, snapshot)
    sync_aspirations_readiness(user_id, snapshot)
    return {"id": event_id, "readiness_before": readiness_before, "readiness_after": readiness_after}


def skill_rows(user_id: str) -> list[dict[str, Any]]:
    snapshot = readiness_snapshot(user_id)
    breakdown = {dimension: 0.0 for dimension in DIMENSIONS}
    breakdown.update(snapshot["domain_breakdown"] or {})
    written_score = snapshot["written_assessment"]["score"] if snapshot["written_assessment"] else None
    certificate_breakdown = (snapshot["certificate"] or {}).get("domain_breakdown", {}) if snapshot.get("certificate") else {}
    return [
        {
            "skill_id": normalize_key(name),
            "skill_name": name,
            "verified_score": round(float(score), 2),
            "assessment_score": round(float(score), 2),
            "written_score": written_score if name in {"Communication", "Problem Solving"} else None,
            "interview_score": None,
            "artifact_score": (
                round(float(certificate_breakdown[name]), 2)
                if name in certificate_breakdown
                else (snapshot["resume"]["match_score"] if snapshot["resume"] else None)
            ),
            "updated_at": (
                snapshot["assessment"]["completed_at"]
                if snapshot["assessment"]
                else (
                    snapshot["written_assessment"]["updated_at"]
                    if snapshot["written_assessment"]
                    else (snapshot["resume"]["created_at"] if snapshot["resume"] else None)
                )
            ),
        }
        for name, score in breakdown.items()
    ]


def gap_rows(user_id: str) -> list[dict[str, Any]]:
    rows = skill_rows(user_id)
    if not rows:
        rows = [{"skill_name": dimension, "verified_score": 0} for dimension in DIMENSIONS]
    gaps = []
    for item in rows:
        score = float(item["verified_score"])
        gaps.append(
            {
                "skill_name": item["skill_name"],
                "target_weight": 85,
                "user_score": score,
                "gap_severity": round(max(0, 85 - score) / 85, 3),
            }
        )
    return sorted(gaps, key=lambda row: row["gap_severity"], reverse=True)


def role_fit(user_id: str, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    profile = profile or row_to_profile(db.query_one("SELECT * FROM profiles WHERE user_id = ?", (user_id,)))
    snapshot = readiness_snapshot(user_id)
    role_name = profile.get("focus_role") or "Unassigned"
    skills = skill_rows(user_id)
    matched = [item["skill_name"] for item in skills if item["verified_score"] >= 70]
    missing = [gap["skill_name"] for gap in gap_rows(user_id)[:4]]
    return {
        "role_name": role_name or "Unassigned",
        "fit_score": snapshot["readiness"],
        "matched_skills": matched,
        "missing_skills": missing,
    }


def progress_card(user_id: str, include_subject_progress: bool = False) -> dict[str, Any]:
    profile = row_to_profile(db.query_one("SELECT * FROM profiles WHERE user_id = ?", (user_id,)))
    snapshot = readiness_snapshot(user_id)
    resume = snapshot["resume"]
    analysis = resume["analysis"] if resume else {}
    strong = analysis.get("strong_points") or [item["skill_name"] for item in skill_rows(user_id)[:5]]
    weak = analysis.get("weak_points") or [item["skill_name"] for item in gap_rows(user_id)[:4]]
    help_items = analysis.get("institute_help") or [
        "Schedule a mentor review",
        "Assign project-based practice",
        "Run mock interview feedback",
        "Review resume proof links",
    ]
    card = {
        "user_id": user_id,
        "name": profile.get("full_name") or profile.get("email") or "Student",
        "email": profile.get("email"),
        "institution_name": profile.get("institution_name"),
        "department_name": profile.get("department_name"),
        "readiness_score": snapshot["readiness"],
        "resume_score": resume["match_score"] if resume else None,
        "assessment_score": snapshot["assessment"]["score"] if snapshot["assessment"] else None,
        "written_score": snapshot["written_assessment"]["score"] if snapshot["written_assessment"] else None,
        "credential_score": snapshot["certificate"]["score"] if snapshot["certificate"] else None,
        "readiness_components": snapshot.get("readiness_components", []),
        "readiness_formula": snapshot.get("readiness_formula"),
        "strong_points": strong[:5],
        "weak_points": weak[:4],
        "institute_help": help_items[:4],
        "target_role": profile.get("focus_role") or "",
    }
    if include_subject_progress:
        card["subject_progress"] = subject_progress_rows(user_id)
    return card


UPLOAD_EXTENSIONS = {
    "avatar": {".jpg", ".jpeg", ".png", ".webp"},
    "resume": {".pdf", ".docx", ".txt"},
    "artifact": {".pdf", ".docx", ".txt", ".jpg", ".jpeg", ".png", ".webp"},
    "csv": {".csv"},
}

GENERIC_UPLOAD_MIME_TYPES = {"", "application/octet-stream", "binary/octet-stream"}

UPLOAD_MIME_TYPES = {
    "avatar": {"image/jpeg", "image/png", "image/webp"},
    "resume": {
        "application/pdf",
        "application/x-pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
    },
    "artifact": {
        "application/pdf",
        "application/x-pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
        "image/jpeg",
        "image/png",
        "image/webp",
    },
    "csv": {"text/csv", "application/csv", "application/vnd.ms-excel", "text/plain"},
}


def _upload_limit_bytes(kind: str) -> int:
    if kind == "avatar":
        return settings.max_avatar_upload_bytes
    if kind == "resume":
        return settings.max_resume_upload_bytes
    if kind == "csv":
        return settings.max_csv_upload_bytes
    return settings.max_artifact_upload_bytes


def _extension(filename: str | None) -> str:
    raw = str(filename or "").lower().strip()
    if "." not in raw:
        return ""
    return "." + raw.rsplit(".", 1)[-1]


def _looks_like_extension(ext: str, content: bytes) -> bool:
    sample = content[:32]
    if ext == ".pdf":
        return sample.startswith(b"%PDF")
    if ext == ".docx":
        return sample.startswith(b"PK\x03\x04")
    if ext in {".jpg", ".jpeg"}:
        return sample.startswith(b"\xff\xd8\xff")
    if ext == ".png":
        return sample.startswith(b"\x89PNG\r\n\x1a\n")
    if ext == ".webp":
        return sample.startswith(b"RIFF") and sample[8:12] == b"WEBP"
    if ext in {".txt", ".csv"}:
        return b"\x00" not in content[:4096]
    return False


def scan_upload_content(content: bytes, filename: str | None) -> None:
    if not settings.upload_scan_enabled:
        return
    if not settings.clamav_tcp_host:
        if settings.fail_closed_upload_scan:
            raise HTTPException(status_code=503, detail="Upload malware scanning is not configured")
        return
    try:
        with socket.create_connection(
            (settings.clamav_tcp_host, settings.clamav_tcp_port),
            timeout=settings.clamav_timeout_seconds,
        ) as sock:
            sock.settimeout(settings.clamav_timeout_seconds)
            sock.sendall(b"zINSTREAM\0")
            for index in range(0, len(content), 1024 * 1024):
                chunk = content[index:index + 1024 * 1024]
                sock.sendall(len(chunk).to_bytes(4, "big") + chunk)
            sock.sendall((0).to_bytes(4, "big"))
            response = sock.recv(4096).decode("utf-8", errors="ignore")
    except HTTPException:
        raise
    except Exception as exc:
        if settings.fail_closed_upload_scan:
            raise HTTPException(status_code=503, detail="Upload malware scan is unavailable") from exc
        logger.warning("Upload scan skipped for %s: %s", filename or "upload", exc)
        return
    if "FOUND" in response.upper():
        raise HTTPException(status_code=400, detail="Upload rejected by malware scanner")
    if "OK" not in response.upper() and settings.fail_closed_upload_scan:
        raise HTTPException(status_code=503, detail="Upload malware scan returned an invalid response")


async def read_validated_upload(file: UploadFile, kind: str) -> bytes:
    ext = _extension(file.filename)
    allowed_extensions = UPLOAD_EXTENSIONS[kind]
    if ext not in allowed_extensions:
        allowed = ", ".join(sorted(allowed_extensions))
        raise HTTPException(status_code=400, detail=f"Unsupported file type. Allowed: {allowed}")

    content_type = str(file.content_type or "").split(";", 1)[0].strip().lower()
    if content_type not in GENERIC_UPLOAD_MIME_TYPES and content_type not in UPLOAD_MIME_TYPES[kind]:
        allowed_types = ", ".join(sorted(UPLOAD_MIME_TYPES[kind]))
        raise HTTPException(status_code=400, detail=f"Unsupported upload MIME type. Allowed: {allowed_types}")

    limit = _upload_limit_bytes(kind)
    content = await file.read(limit + 1)
    if len(content) > limit:
        raise HTTPException(status_code=413, detail=f"Upload exceeds the {round(limit / 1024 / 1024, 1)} MB limit")
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if not _looks_like_extension(ext, content):
        raise HTTPException(status_code=400, detail="Uploaded file content does not match the file extension")
    scan_upload_content(content, file.filename)
    return content


def extract_limited_text(filename: str, content: bytes) -> str:
    try:
        text = extract_text_from_bytes(filename, content)
    except Exception:
        return ""
    return text[: settings.max_extracted_text_chars].strip()


async def save_upload(user_id: str, file: UploadFile, content: bytes, category: str):
    try:
        return await store_upload(
            settings,
            user_id,
            file.filename,
            content,
            file.content_type,
            category,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _is_certificate_file_type(file_type: str | None) -> bool:
    return str(file_type or "").strip().lower() in {"certificate", "certification", "credential"}


def _is_image_upload(filename: str | None) -> bool:
    return str(filename or "").lower().endswith((".jpg", ".jpeg", ".png", ".webp"))


async def evaluate_and_store_certificate_artifact(
    artifact_id: str,
    user_id: str,
    readiness_before: float | None = None,
) -> dict[str, Any]:
    artifact = db.query_one("SELECT * FROM artifacts WHERE id = ? AND user_id = ?", (artifact_id, user_id))
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    if not _is_certificate_file_type(artifact["file_type"]):
        return artifact_row(artifact)

    before = readiness_before if readiness_before is not None else readiness_snapshot(user_id)["readiness"]
    role_name = role_fit(user_id)["role_name"]
    try:
        evaluation = await analyze_certificate_value(
            settings,
            artifact["file_name"],
            artifact["extracted_text"] or "",
            role_name,
        )
    except AnalysisUnavailableError as exc:
        metadata = from_json(artifact["metadata"], {})
        metadata.update(
            {
                "evaluation_status": "failed",
                "evaluation_error": str(exc),
                "evaluation_failed_at": now_iso(),
            }
        )
        db.execute(
            "UPDATE artifacts SET metadata = ? WHERE id = ? AND user_id = ?",
            (to_json(metadata), artifact_id, user_id),
        )
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    score = float(evaluation.get("score", 0))
    domain_breakdown = evaluation.get("domain_breakdown") if isinstance(evaluation.get("domain_breakdown"), dict) else {}
    evaluation_id = new_id("arteval")
    db.execute(
        """
        INSERT INTO artifact_evaluations (
            id, user_id, artifact_id, file_type, score, readiness_delta,
            domain_breakdown, evaluation, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            evaluation_id,
            user_id,
            artifact_id,
            artifact["file_type"],
            score,
            float(evaluation.get("readiness_delta", 0)),
            to_json(domain_breakdown),
            to_json(evaluation),
            now_iso(),
        ),
    )
    metadata = from_json(artifact["metadata"], {})
    metadata.update(
        {
            "evaluation_status": "completed",
            "credential_evaluation": evaluation,
            "credential_score": score,
            "credential_readiness_delta": evaluation.get("readiness_delta", 0),
            "evaluated_at": now_iso(),
        }
    )
    db.execute(
        "UPDATE artifacts SET metadata = ? WHERE id = ? AND user_id = ?",
        (to_json(metadata), artifact_id, user_id),
    )
    record_readiness_event(
        user_id,
        "certificate",
        artifact_id,
        score,
        before,
        {
            "file_name": artifact["file_name"],
            "verdict": evaluation.get("verdict"),
            "detected_skills": evaluation.get("detected_skills", []),
            "readiness_delta": evaluation.get("readiness_delta", 0),
        },
    )
    return artifact_row(db.query_one("SELECT * FROM artifacts WHERE id = ?", (artifact_id,)))


def _dimension_from_skill(skill_id: str) -> str | None:
    normalized = normalize_key(skill_id)
    for dimension in DIMENSIONS:
        if normalize_key(dimension) == normalized:
            return dimension
    return None


CENTRAL_WRITTEN_EVALUATOR_MODE = "central_unbiased_ai"
WRITTEN_COMMAND_TERMS = (
    "analyze",
    "analyse",
    "assess",
    "compare",
    "describe",
    "draft",
    "evaluate",
    "explain",
    "justify",
    "propose",
    "write",
)
WRITTEN_CHOICE_PATTERNS = (
    r"\bwhich\s+(choice|option|answer|output|statement)\b",
    r"\b(best|correct)\s+(choice|option|answer|output|statement)\b",
    r"\bselect\s+(the\s+)?(best|correct|most)\b",
    r"\bchoose\s+(the\s+)?(best|correct|most)\b",
    r"\boptions?\s*[:\-]",
    r"(^|\n)\s*[A-D]\s*[\).:-]\s+\S+",
)


def _looks_like_choice_prompt(question_text: str) -> bool:
    text = str(question_text or "").strip().lower()
    if not text:
        return True
    return any(re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE) for pattern in WRITTEN_CHOICE_PATTERNS)


def _written_prompt_rank(row: dict[str, Any]) -> int:
    text = str(row.get("question_text") or "")
    lowered = text.lower()
    has_written_command = any(term in lowered for term in WRITTEN_COMMAND_TERMS)
    if _looks_like_choice_prompt(text):
        return 0
    if has_written_command:
        return 2
    return 1


def _written_prompt_from_question(
    question: dict[str, Any],
    role_name: str,
    assignment_title: str | None = None,
) -> tuple[str, bool]:
    raw_prompt = str(question.get("question_text") or "").strip()
    dimension = str(question.get("dimension") or "Communication")
    subject = _subject_name_from_question(question)
    difficulty = str(question.get("difficulty") or "Intermediate")
    scenario = str(question.get("scenario") or "").strip()
    needs_rewrite = (
        _looks_like_choice_prompt(raw_prompt)
        or len(re.findall(r"\b\w+\b", raw_prompt)) < 10
        or not any(term in raw_prompt.lower() for term in WRITTEN_COMMAND_TERMS)
    )
    if not needs_rewrite:
        prompt = raw_prompt
        if scenario:
            prompt = f"{scenario}\n\n{prompt}"
        prompt += (
            "\n\nWrite a structured answer with: context, decision, evidence, risk or trade-off, "
            "and a concrete next action. Do not answer with a single option letter."
        )
        return prompt, False

    topic = raw_prompt or assignment_title or f"{subject} practice case"
    topic = re.sub(r"\s+", " ", topic).strip()
    context = scenario or (
        f"A learner is practicing {subject} for {role_name or 'their target role'} and must prove "
        "the reasoning behind the decision, not just choose an answer."
    )
    prompt = (
        f"Written practice case - {subject} ({difficulty})\n"
        f"Readiness dimension: {dimension}\n\n"
        f"Topic from the question bank: {topic}\n\n"
        f"Context: {context}\n\n"
        "Write a 180-300 word structured response that explains the correct decision, the evidence "
        "you would check, the risk or trade-off, and the next action. This is not an MCQ; do not "
        "answer with A/B/C/D or a one-line choice."
    )
    return prompt, True


def _select_written_question_from_pool(question_pool: list[dict[str, Any]], category: str | None) -> dict[str, Any] | None:
    field = None
    value = None
    if category:
        try:
            field, value = _category_match_field(category, question_pool)
        except HTTPException:
            field = "dimension"
            value = _dimension_from_skill(category) or category
    rows = [
        row
        for row in question_pool
        if row.get("question_type") == "DESCRIPTIVE"
        and _question_matches_category(row, field, value)
    ]
    if rows:
        return sorted(
            rows,
            key=lambda row: (
                -_written_prompt_rank(row),
                str(row.get("dimension") or ""),
                str(row.get("difficulty") or ""),
                str(row.get("id") or ""),
            ),
        )[0]
    if category:
        return _select_written_question_from_pool(question_pool, None)
    return None


def _select_written_question_from_pool_ids(question_pool: list[dict[str, Any]], question_ids: list[str]) -> dict[str, Any] | None:
    clean_ids = [str(question_id or "").strip() for question_id in question_ids if str(question_id or "").strip()]
    row_by_id = {
        row.get("id"): row
        for row in question_pool
        if row.get("question_type") == "DESCRIPTIVE"
    }
    rows = [row_by_id[question_id] for question_id in clean_ids if question_id in row_by_id]
    if not rows:
        return None
    return sorted(rows, key=lambda row: (-_written_prompt_rank(row), clean_ids.index(str(row.get("id")))))[0]


def _parse_datetime(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="starts_at must be a valid ISO datetime") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _assignment_window(row: dict[str, Any]) -> tuple[datetime, datetime]:
    starts = _parse_datetime(row["starts_at"])
    raw_end = row.get("ends_at")
    if raw_end:
        ends = _parse_datetime(raw_end)
    else:
        duration = max(1, int(row["duration_minutes"] or 30))
        ends = starts + timedelta(minutes=duration)
    return starts, ends


def assignment_row(row: dict[str, Any], user_id: str | None = None) -> dict[str, Any]:
    starts, ends = _assignment_window(row)
    now = datetime.now(timezone.utc)
    attempt = None
    question_ids = from_json(row.get("question_ids"), [])
    metadata = from_json(row.get("metadata"), {})
    if user_id:
        if row["question_type"] == "DESCRIPTIVE":
            attempt = db.query_one(
                """
                SELECT id, status, score, updated_at AS completed_at FROM written_assessments
                WHERE user_id = ? AND assignment_id = ?
                ORDER BY created_at DESC LIMIT 1
                """,
                (user_id, row["id"]),
            )
        else:
            attempt = db.query_one(
                """
                SELECT id, status, score, completed_at FROM assessments
                WHERE user_id = ? AND assignment_id = ?
                ORDER BY created_at DESC LIMIT 1
                """,
                (user_id, row["id"]),
            )
    is_completed = bool(attempt and attempt["status"] == "completed")
    is_terminated = row["status"] == "terminated"
    is_missed = row["status"] == "active" and now > ends and not attempt
    return {
        "id": row["id"],
        "institution_id": row["institution_id"],
        "department_id": row["department_id"],
        "title": row["title"],
        "category": row["category"],
        "assessment_type": row["assessment_type"],
        "question_type": row["question_type"],
        "question_set_id": row.get("question_set_id"),
        "question_ids": question_ids,
        "question_count": len(question_ids),
        "mode": row["mode"],
        "starts_at": row["starts_at"],
        "ends_at": ends.isoformat(),
        "duration_minutes": row["duration_minutes"],
        "instructions": row["instructions"],
        "status": row["status"],
        "created_by_email": row["created_by_email"],
        "terminated_at": row.get("terminated_at"),
        "terminated_by_email": row.get("terminated_by_email"),
        "created_at": row["created_at"],
        "metadata": metadata,
        "can_start": row["status"] == "active" and starts <= now <= ends and not is_completed,
        "is_upcoming": now < starts,
        "is_expired": now > ends,
        "missed": is_missed,
        "terminated": is_terminated,
        "attempt_id": attempt["id"] if attempt else None,
        "attempt_status": attempt["status"] if attempt else None,
        "attempt_score": attempt["score"] if attempt else None,
        "completed_at": attempt["completed_at"] if attempt else None,
    }


def _validate_assignment_for_student(assignment_id: str, user_id: str, profile: dict[str, Any]) -> dict[str, Any]:
    row = db.query_one("SELECT * FROM assessment_assignments WHERE id = ?", (assignment_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Assigned test not found")
    if row["status"] == "terminated":
        raise HTTPException(status_code=403, detail="This assigned test was terminated by admin")
    if row["status"] != "active":
        raise HTTPException(status_code=404, detail="Assigned test not found")
    if not profile.get("department_id") or profile["department_id"] != row["department_id"]:
        raise HTTPException(status_code=403, detail="This assigned test is not for your department")
    starts, ends = _assignment_window(row)
    now = datetime.now(timezone.utc)
    if now < starts:
        raise HTTPException(status_code=403, detail="This assigned test is not open yet")
    if now > ends:
        raise HTTPException(status_code=403, detail="This assigned test has closed")
    return row


def _validate_admin_department(admin: AdminUser, department_id: str) -> dict[str, Any]:
    department = db.query_one("SELECT * FROM departments WHERE id = ?", (department_id,))
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")
    if admin.role == "institution_admin":
        if admin.department_id and admin.department_id != department_id:
            raise HTTPException(status_code=403, detail="You can assign tests only to your department")
        if admin.institution_id and admin.institution_id != department["institution_id"]:
            raise HTTPException(status_code=403, detail="Department is outside your institution")
    return department


QUESTION_CSV_HEADERS = [
    "category",
    "difficulty",
    "question_type",
    "question_text",
    "scenario",
    "option_a",
    "option_b",
    "option_c",
    "option_d",
    "correct_answer",
    "explanation",
    "sample_answer",
]


def _row_value(row: dict[str, Any], *keys: str) -> str:
    normalized = {
        re.sub(r"[^a-z0-9]+", "_", str(key or "").strip().lower()).strip("_"): value
        for key, value in row.items()
    }
    for key in keys:
        normalized_key = re.sub(r"[^a-z0-9]+", "_", key.strip().lower()).strip("_")
        value = normalized.get(normalized_key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "assign", "assigned"}


def _parse_csv_options(row: dict[str, Any]) -> list[str]:
    options = [
        _row_value(row, "option_a", "a"),
        _row_value(row, "option_b", "b"),
        _row_value(row, "option_c", "c"),
        _row_value(row, "option_d", "d"),
    ]
    if not any(options):
        raw_options = _row_value(row, "options", "choices", "mcq_options")
        options = [item.strip() for item in re.split(r"[|;]", raw_options) if item.strip()]
        if len(options) < 2 and "," in raw_options:
            options = [item.strip() for item in raw_options.split(",") if item.strip()]
    return [option for option in options if option]


def _infer_csv_question_type(row: dict[str, Any]) -> str:
    raw = _row_value(row, "question_type", "type", "assessment_type").lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", raw).strip("_")
    if normalized in {"written", "descriptive", "subjective", "essay", "long_answer", "short_answer"}:
        return "DESCRIPTIVE"
    if normalized in {"situational", "scenario", "case", "case_study", "situation"}:
        return "SITUATIONAL"
    if normalized in {"mcq", "multiple_choice", "multiplechoice", "objective"}:
        return "MCQ"
    options = _parse_csv_options(row)
    if len(options) < 2:
        return "DESCRIPTIVE"
    return "SITUATIONAL" if _row_value(row, "scenario", "case", "situation") else "MCQ"


def _csv_question_payload(row: dict[str, Any]) -> dict[str, Any]:
    question_type = _infer_csv_question_type(row)
    options = [] if question_type == "DESCRIPTIVE" else _parse_csv_options(row)
    question_text = _row_value(row, "question_text", "question", "prompt")
    dimension = _row_value(row, "dimension", "subject", "category", "skill_name")
    if not question_text:
        raise ValueError("question_text is required")
    if not dimension:
        raise ValueError("category/subject is required")
    if question_type in {"MCQ", "SITUATIONAL"} and len(options) < 2:
        raise ValueError("MCQ/situational rows require at least two options")
    return {
        "dimension": dimension,
        "difficulty": _row_value(row, "difficulty", "level") or "Basic",
        "question_type": question_type,
        "scenario": _row_value(row, "scenario", "case", "situation"),
        "question_text": question_text,
        "options": options,
        "correct_answer": _row_value(row, "correct_answer", "correct_option", "answer") or "A",
        "explanation": _row_value(row, "explanation", "rationale", "feedback"),
        "sample_answer": _row_value(row, "sample_answer", "model_answer", "expected_answer"),
    }


def _question_set_row(row: dict[str, Any]) -> dict[str, Any]:
    metadata = from_json(row.get("metadata"), {})
    question_ids = from_json(row.get("question_ids"), [])
    return {
        "id": row["id"],
        "title": row["title"],
        "source": row["source"],
        "category": row["category"],
        "question_type": row["question_type"],
        "question_ids": question_ids,
        "question_count": row["question_count"],
        "type_counts": metadata.get("type_counts", {}),
        "metadata": metadata,
        "created_by_email": row["created_by_email"],
        "created_at": row["created_at"],
    }


def _create_question_set(
    *,
    title: str,
    source: str,
    category: str,
    question_type: str,
    question_ids: list[str],
    admin: AdminUser,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    seen = set()
    clean_ids = []
    for question_id in question_ids:
        clean_id = str(question_id or "").strip()
        if clean_id and clean_id not in seen:
            seen.add(clean_id)
            clean_ids.append(clean_id)
    if not clean_ids:
        raise HTTPException(status_code=400, detail="Question set requires at least one question")
    question_set_id = new_id("qset")
    db.execute(
        """
        INSERT INTO question_sets (
            id, title, source, category, question_type, question_ids, question_count,
            created_by_admin_id, created_by_email, metadata, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            question_set_id,
            title.strip() or "Imported question set",
            source,
            category.strip() or "Imported questions",
            question_type.upper(),
            to_json(clean_ids),
            len(clean_ids),
            admin.id,
            admin.email,
            to_json(metadata or {}),
            now_iso(),
        ),
    )
    return _question_set_row(db.query_one("SELECT * FROM question_sets WHERE id = ?", (question_set_id,)))


def _load_question_set(question_set_id: str, admin: AdminUser | None = None) -> dict[str, Any]:
    row = db.query_one("SELECT * FROM question_sets WHERE id = ?", (question_set_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Question set not found")
    return _question_set_row(row)


def _assignment_question_ids(
    question_ids: list[str],
    qtype: str,
    question_pool: list[dict[str, Any]],
) -> tuple[list[str], dict[str, Any]]:
    if question_pool is None:
        raise HTTPException(status_code=503, detail="Supabase question bank is required for fixed assignments")
    allowed_types = {"MCQ", "SITUATIONAL"} if qtype == "MIXED" else {qtype}
    clean_ids = []
    seen = set()
    for question_id in question_ids:
        clean_id = str(question_id or "").strip()
        if clean_id and clean_id not in seen:
            seen.add(clean_id)
            clean_ids.append(clean_id)
    if not clean_ids:
        return [], {"requested": 0, "usable": 0, "skipped": 0}
    clean_set = set(clean_ids)
    rows = [row for row in question_pool if row.get("id") in clean_set]
    row_by_id = {row["id"]: row for row in rows}
    ordered_rows = [row_by_id[question_id] for question_id in clean_ids if question_id in row_by_id]
    usable_ids = [
        row["id"]
        for row in ordered_rows
        if row["question_type"] in allowed_types
        and (qtype == "DESCRIPTIVE" or str(row["options"] or "[]") != "[]")
    ]
    type_counts = Counter(str(row["question_type"] or "").upper() for row in ordered_rows)
    return usable_ids, {
        "requested": len(clean_ids),
        "found": len(ordered_rows),
        "usable": len(usable_ids),
        "skipped": len(clean_ids) - len(usable_ids),
        "type_counts": dict(type_counts),
        "allowed_types": sorted(allowed_types),
    }


def _live_question_rows_or_503() -> list[dict[str, Any]]:
    try:
        rows, metadata = fetch_supabase_question_rows(settings)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Supabase question bank is unavailable. {type(exc).__name__}: {exc}",
        ) from exc
    if not rows:
        raise HTTPException(status_code=503, detail="Supabase returned no usable assessment questions")
    status = {
        "source": "supabase",
        "status": "ready",
        "message": "Question bank fetched live from Supabase.",
        "total_questions": len(rows),
        "mcq_count": sum(1 for row in rows if row.get("question_type") == "MCQ"),
        "descriptive_count": sum(1 for row in rows if row.get("question_type") == "DESCRIPTIVE"),
        "situational_count": sum(1 for row in rows if row.get("question_type") == "SITUATIONAL"),
        "synced_at": now_iso(),
        "metadata": metadata,
    }
    db.execute(
        """
        INSERT INTO question_bank_status (
            id, source, status, message, total_questions, mcq_count,
            descriptive_count, situational_count, synced_at, metadata
        )
        VALUES ('primary', ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            source = excluded.source,
            status = excluded.status,
            message = excluded.message,
            total_questions = excluded.total_questions,
            mcq_count = excluded.mcq_count,
            descriptive_count = excluded.descriptive_count,
            situational_count = excluded.situational_count,
            synced_at = excluded.synced_at,
            metadata = excluded.metadata
        """,
        (
            status["source"],
            status["status"],
            status["message"],
            status["total_questions"],
            status["mcq_count"],
            status["descriptive_count"],
            status["situational_count"],
            status["synced_at"],
            to_json(status["metadata"]),
        ),
    )
    return rows


@app.get("/health")
def health() -> dict[str, Any]:
    bank = question_bank_status(db)
    return {
        "status": "ok",
        "app": settings.app_name,
        "services": {
            "database": "supabase_postgres" if db.using_postgres else "sqlite",
            "sqlite": settings.database_path.exists() if not db.using_postgres else False,
            "supabase_auth": bool(settings.supabase_url and settings.supabase_api_key),
            "question_bank": bank["status"] == "ready",
            "question_bank_source": bank["source"],
            "openai": bool(settings.openai_api_key),
            "rag": False,
            "redis": bool(settings.redis_url),
            "rate_limit_backend": rate_limiter.backend_name,
            "neo4j": False,
        },
        "timestamp": now_iso(),
    }


def verify_monitoring_access(
    x_monitoring_token: str | None = Header(default=None, alias="X-Monitoring-Token"),
) -> None:
    if not settings.is_hosted_mode and not settings.monitoring_token:
        return
    if not settings.monitoring_token or x_monitoring_token != settings.monitoring_token:
        raise HTTPException(status_code=403, detail="Monitoring token is required")


@app.get("/system/metrics")
@app.get("/api/v1/system/metrics")
def system_metrics(_: None = Depends(verify_monitoring_access)) -> dict[str, Any]:
    request_count = int(REQUEST_METRICS["request_count"])
    total_latency = float(REQUEST_METRICS["total_latency_ms"])
    audit_count = db.query_one("SELECT COUNT(*) AS count FROM audit_logs") or {"count": 0}
    return {
        "status": "ok",
        "uptime_seconds": round(time.time() - float(REQUEST_METRICS["started_at"]), 2),
        "request_count": request_count,
        "error_count": REQUEST_METRICS["error_count"],
        "average_latency_ms": round(total_latency / request_count, 2) if request_count else 0,
        "status_counts": REQUEST_METRICS["status_counts"],
        "top_routes": sorted(
            REQUEST_METRICS["route_counts"].items(),
            key=lambda item: item[1],
            reverse=True,
        )[:20],
        "recent_failures": REQUEST_METRICS["recent_failures"],
        "audit_log_count": int(audit_count.get("count") or 0),
        "rate_limit_backend": rate_limiter.backend_name,
        "rate_limit_buckets": rate_limiter.bucket_count,
        "rate_limit_redis_error": rate_limiter.redis_error,
        "storage_backend": settings.effective_storage_backend,
        "database": "postgres" if db.using_postgres else "sqlite",
        "timestamp": now_iso(),
    }


@app.get("/api/v1/question-bank/status")
def get_question_bank_status() -> dict[str, Any]:
    _live_question_rows_or_503()
    return question_bank_status(db)


@app.get("/api/v1/institutions")
def public_institutions() -> list[dict[str, Any]]:
    institutions = db.query_all("SELECT * FROM institutions ORDER BY name")
    departments = db.query_all("SELECT * FROM departments ORDER BY name")
    dept_by_inst: dict[str, list[dict[str, Any]]] = {}
    for dept in departments:
        dept_by_inst.setdefault(dept["institution_id"], []).append(dept)
    return [
        {
            "id": inst["id"],
            "name": inst["name"],
            "domain": inst["domain"],
            "departments": dept_by_inst.get(inst["id"], []),
        }
        for inst in institutions
    ]


@app.get("/api/v1/profile/me")
def get_profile(user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    return ensure_profile(user)


@app.patch("/api/v1/profile/me")
def update_profile(payload: ProfilePatch, user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    ensure_profile(user)
    current = db.query_one("SELECT * FROM profiles WHERE user_id = ?", (user.id,))
    metadata = from_json(current["metadata"], {})
    metadata.update(payload.metadata or {})
    institution_name = payload.institution_name or current["institution_name"]
    department_name = payload.department_name or current["department_name"]
    institution_id = payload.institution_id or current["institution_id"]
    department_id = payload.department_id or current["department_id"]
    focus_role = payload.focus_role
    if focus_role is not None:
        focus_role = _canonical_career_role(focus_role, required=False) or ""
    if institution_id:
        inst = db.query_one("SELECT * FROM institutions WHERE id = ?", (institution_id,))
        if inst:
            institution_name = inst["name"]
    if department_id:
        dept = db.query_one("SELECT * FROM departments WHERE id = ?", (department_id,))
        if dept:
            department_name = dept["name"]
    db.execute(
        """
        UPDATE profiles
        SET full_name = COALESCE(?, full_name),
            headline = COALESCE(?, headline),
            focus_role = COALESCE(?, focus_role),
            weekly_goal = COALESCE(?, weekly_goal),
            avatar_url = COALESCE(?, avatar_url),
            institution_id = ?,
            department_id = ?,
            institution_name = ?,
            department_name = ?,
            metadata = ?,
            updated_at = ?
        WHERE user_id = ?
        """,
        (
            payload.full_name,
            payload.headline,
            focus_role,
            payload.weekly_goal,
            payload.avatar_url,
            institution_id,
            department_id,
            institution_name,
            department_name,
            to_json(metadata),
            now_iso(),
            user.id,
        ),
    )
    return row_to_profile(db.query_one("SELECT * FROM profiles WHERE user_id = ?", (user.id,)))


async def _crawl_profile_link(link: ProfileEvidenceLink) -> dict[str, Any]:
    normalized_url = _normalize_profile_link_url(link.url)
    link_type = normalize_key(link.type or link.label or "portfolio").replace("-", "_")
    result: dict[str, Any] = {
        "label": str(link.label or link.type or "Profile link").strip()[:80],
        "url": normalized_url or str(link.url or "").strip(),
        "type": link_type,
        "reachable": False,
        "status_code": None,
        "summary": "",
        "score": 0,
        "domain_breakdown": {dimension: 0 for dimension in DIMENSIONS},
        "skills": [],
    }
    if not normalized_url:
        result["error"] = "Invalid URL"
        return result
    try:
        status_code, reachable, raw_text, fetch_error = await _fetch_profile_link_text(normalized_url)
        result["status_code"] = status_code
        result["reachable"] = reachable
        if fetch_error:
            result["error"] = fetch_error
        text = _profile_link_text(raw_text if result["reachable"] else "")
    except Exception as exc:
        result["error"] = str(exc)[:160]
        text = ""

    if result["reachable"]:
        domain_breakdown = _profile_link_domain_scores(
            f"{result['label']} {result['url']} {text}",
            link_type,
            True,
        )
        score = _mean_score(list(domain_breakdown.values()))
        result["domain_breakdown"] = domain_breakdown
        result["score"] = score
        result["summary"] = text[:320]
        result["skills"] = _profile_link_skill_hits(f"{result['label']} {result['url']} {text}")
    return result


@app.post("/api/v1/profile/me/evidence-links")
async def validate_profile_evidence_links(
    payload: ProfileEvidenceLinksPayload,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    ensure_profile(user)
    readiness_before = readiness_snapshot(user.id)["readiness"]
    cleaned_links = [
        ProfileEvidenceLink(label=link.label, url=link.url, type=link.type)
        for link in payload.links
        if str(link.url or "").strip()
    ][:12]
    crawled = [await _crawl_profile_link(link) for link in cleaned_links]
    reachable = [item for item in crawled if item.get("reachable")]
    if reachable:
        score = _mean_score([float(item.get("score") or 0) for item in reachable])
        domain_breakdown = {
            dimension: _mean_score([
                float((item.get("domain_breakdown") or {}).get(dimension, item.get("score") or 0))
                for item in reachable
            ])
            for dimension in DIMENSIONS
        }
        skills = sorted({skill for item in reachable for skill in item.get("skills", [])})
    else:
        score = 0.0
        domain_breakdown = {dimension: 0.0 for dimension in DIMENSIONS}
        skills = []

    evidence = {
        "score": score,
        "domain_breakdown": domain_breakdown,
        "skills": skills,
        "links": crawled,
        "validated_at": now_iso(),
    }
    profile_row = db.query_one("SELECT * FROM profiles WHERE user_id = ?", (user.id,))
    metadata = from_json(profile_row["metadata"], {})
    metadata["career_links"] = [
        {"label": item.label, "url": _normalize_profile_link_url(item.url) or item.url, "type": item.type}
        for item in cleaned_links
    ]
    metadata["career_link_evidence"] = evidence
    db.execute(
        "UPDATE profiles SET metadata = ?, updated_at = ? WHERE user_id = ?",
        (to_json(metadata), now_iso(), user.id),
    )
    event = record_readiness_event(
        user.id,
        "profile_links",
        None,
        score,
        readiness_before,
        {"link_count": len(cleaned_links), "reachable_count": len(reachable), "skills": skills},
    )
    return {
        "profile": row_to_profile(db.query_one("SELECT * FROM profiles WHERE user_id = ?", (user.id,))),
        "evidence": evidence,
        "readiness_event": event,
        "readiness": readiness_snapshot(user.id),
    }


@app.post("/api/v1/profile/me/avatar")
async def upload_avatar(file: UploadFile = File(...), user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    ensure_profile(user)
    content = await read_validated_upload(file, "avatar")
    current = db.query_one("SELECT avatar_url FROM profiles WHERE user_id = ?", (user.id,))
    stored = await save_upload(user.id, file, content, "avatars")
    db.execute(
        "UPDATE profiles SET avatar_url = ?, updated_at = ? WHERE user_id = ?",
        (stored.reference, now_iso(), user.id),
    )
    if current and current.get("avatar_url"):
        await delete_upload(settings, None, current["avatar_url"])
    return row_to_profile(db.query_one("SELECT * FROM profiles WHERE user_id = ?", (user.id,)))


@app.get("/api/v1/settings/me")
def get_user_settings(user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    ensure_profile(user)
    return ensure_preferences(user.id)


@app.patch("/api/v1/settings/me")
@app.patch("/api/v1/settings/me/notifications")
@app.patch("/api/v1/settings/me/security")
def update_user_settings(payload: SettingsPatch, user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    ensure_profile(user)
    current = ensure_preferences(user.id)
    db.execute(
        """
        UPDATE user_preferences
        SET desktop_notifications = ?,
            weekly_digest = ?,
            folio_reminders = ?,
            folio_focus = ?,
            security_mode = ?,
            updated_at = ?
        WHERE user_id = ?
        """,
        (
            int(payload.desktop_notifications if payload.desktop_notifications is not None else current["desktop_notifications"]),
            int(payload.weekly_digest if payload.weekly_digest is not None else current["weekly_digest"]),
            int(payload.folio_reminders if payload.folio_reminders is not None else current["folio_reminders"]),
            payload.folio_focus if payload.folio_focus is not None else current["folio_focus"],
            payload.security_mode if payload.security_mode is not None else current["security_mode"],
            now_iso(),
            user.id,
        ),
    )
    return settings_row(db.query_one("SELECT * FROM user_preferences WHERE user_id = ?", (user.id,)))


@app.get("/api/v1/profile/me/artifacts")
def list_artifacts(user: CurrentUser = Depends(get_current_user)) -> list[dict[str, Any]]:
    ensure_profile(user)
    return [
        artifact_row(row)
        for row in db.query_all(
            "SELECT * FROM artifacts WHERE user_id = ? ORDER BY created_at DESC",
            (user.id,),
        )
    ]


@app.get("/api/v1/profile/me/artifacts/{artifact_id}/signed-url")
def get_artifact_signed_url(artifact_id: str, user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    current = db.query_one("SELECT * FROM artifacts WHERE id = ? AND user_id = ?", (artifact_id, user.id))
    if not current:
        raise HTTPException(status_code=404, detail="Artifact not found")
    signed_url = public_or_signed_url(settings, current.get("bucket_name"), current.get("storage_path"))
    if not signed_url:
        raise HTTPException(status_code=503, detail="Could not create a signed artifact URL")
    return {
        "artifact_id": artifact_id,
        "url": signed_url,
        "expires_in": settings.signed_url_ttl_seconds if current.get("bucket_name") != "local-phase1" else None,
    }


@app.post("/api/v1/profile/me/artifacts")
async def upload_artifact(
    file: UploadFile = File(...),
    file_type: str = Form(default="certificate"),
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    ensure_profile(user)
    readiness_before = readiness_snapshot(user.id)["readiness"]
    content = await read_validated_upload(file, "artifact")
    text = extract_limited_text(file.filename or "", content)
    if _is_certificate_file_type(file_type) and _is_image_upload(file.filename) and len(text.strip()) < 40:
        text = await extract_certificate_text_with_ai(settings, file.filename or "", content)
    stored = await save_upload(user.id, file, content, "artifacts")
    artifact_id = new_id("artifact")
    metadata = {"source": "upload"}
    if _is_certificate_file_type(file_type):
        metadata["evaluation_status"] = "pending"
    db.execute(
        """
        INSERT INTO artifacts (
            id, user_id, bucket_name, storage_path, file_name, file_type, extracted_text, metadata, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            artifact_id,
            user.id,
            stored.bucket_name,
            stored.storage_path,
            file.filename or "upload",
            file_type,
            text,
            to_json(metadata),
            now_iso(),
        ),
    )
    if _is_certificate_file_type(file_type):
        return await evaluate_and_store_certificate_artifact(artifact_id, user.id, readiness_before)
    return artifact_row(db.query_one("SELECT * FROM artifacts WHERE id = ?", (artifact_id,)))


@app.put("/api/v1/profile/me/artifacts/{artifact_id}")
async def replace_artifact(
    artifact_id: str,
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    current = db.query_one("SELECT * FROM artifacts WHERE id = ? AND user_id = ?", (artifact_id, user.id))
    if not current:
        raise HTTPException(status_code=404, detail="Artifact not found")
    readiness_before = readiness_snapshot(user.id)["readiness"]
    content = await read_validated_upload(file, "artifact")
    text = extract_limited_text(file.filename or "", content)
    if _is_certificate_file_type(current["file_type"]) and _is_image_upload(file.filename) and len(text.strip()) < 40:
        text = await extract_certificate_text_with_ai(settings, file.filename or "", content)
    stored = await save_upload(user.id, file, content, "artifacts")
    metadata = from_json(current["metadata"], {})
    if _is_certificate_file_type(current["file_type"]):
        metadata["evaluation_status"] = "pending"
        db.execute("DELETE FROM artifact_evaluations WHERE artifact_id = ? AND user_id = ?", (artifact_id, user.id))
    db.execute(
        """
        UPDATE artifacts
        SET bucket_name = ?, storage_path = ?, file_name = ?, extracted_text = ?, metadata = ?, created_at = ?
        WHERE id = ? AND user_id = ?
        """,
        (stored.bucket_name, stored.storage_path, file.filename or current["file_name"], text, to_json(metadata), now_iso(), artifact_id, user.id),
    )
    await delete_upload(settings, current.get("bucket_name"), current.get("storage_path"))
    if _is_certificate_file_type(current["file_type"]):
        return await evaluate_and_store_certificate_artifact(artifact_id, user.id, readiness_before)
    return artifact_row(db.query_one("SELECT * FROM artifacts WHERE id = ?", (artifact_id,)))


@app.delete("/api/v1/profile/me/artifacts/{artifact_id}")
async def delete_artifact(artifact_id: str, user: CurrentUser = Depends(get_current_user)) -> dict[str, str]:
    current = db.query_one("SELECT * FROM artifacts WHERE id = ? AND user_id = ?", (artifact_id, user.id))
    readiness_before = readiness_snapshot(user.id)["readiness"]
    db.execute("DELETE FROM artifacts WHERE id = ? AND user_id = ?", (artifact_id, user.id))
    if current:
        await delete_upload(settings, current.get("bucket_name"), current.get("storage_path"))
    if current and _is_certificate_file_type(current["file_type"]):
        record_readiness_event(
            user.id,
            "certificate_deleted",
            artifact_id,
            0,
            readiness_before,
            {"file_name": current["file_name"]},
        )
    return {"status": "deleted"}


@app.post("/api/v1/resume/analyze")
async def analyze_resume_upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    target_role: str = Form(default="AI Engineer or AI Intern or ML Intern"),
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    profile = ensure_profile(user)
    profile_target_role = str(profile.get("focus_role") or "").strip()
    requested_target_role = str(target_role or "").strip()
    active_target_role = profile_target_role or requested_target_role or "AI Engineer or AI Intern or ML Intern"
    target_role_source = "profile.focus_role" if profile_target_role else ("request.target_role" if requested_target_role else "default")
    readiness_before = readiness_snapshot(user.id)["readiness"]
    content = await read_validated_upload(file, "resume")
    extracted_text = extract_limited_text(file.filename or "", content)
    if not extracted_text:
        raise HTTPException(status_code=400, detail="Could not extract readable text from this resume")
    stored = await save_upload(user.id, file, content, "resumes")
    artifact_id = new_id("artifact")
    db.execute(
        """
        INSERT INTO artifacts (
            id, user_id, bucket_name, storage_path, file_name, file_type, extracted_text, metadata, created_at
        )
        VALUES (?, ?, ?, ?, ?, 'resume', ?, ?, ?)
        """,
        (
            artifact_id,
            user.id,
            stored.bucket_name,
            stored.storage_path,
            file.filename or "resume",
            extracted_text,
            to_json({"target_role": active_target_role, "target_role_source": target_role_source}),
            now_iso(),
        ),
    )
    if settings.async_ai_jobs_enabled:
        queued_metadata = {
            "target_role": active_target_role,
            "target_role_source": target_role_source,
            "analysis_status": "queued",
        }
        db.execute(
            "UPDATE artifacts SET metadata = ? WHERE id = ? AND user_id = ?",
            (to_json(queued_metadata), artifact_id, user.id),
        )
        job = create_processing_job(
            user.id,
            "resume_analysis",
            {
                "artifact_id": artifact_id,
                "target_role": active_target_role,
                "target_role_source": target_role_source,
            },
        )
        background_tasks.add_task(
            complete_resume_analysis_job,
            job["id"],
            user.id,
            artifact_id,
            file.filename or "resume",
            extracted_text,
            active_target_role,
            target_role_source,
            readiness_before,
        )
        return {
            "status": "queued",
            "job_id": job["id"],
            "artifact_id": artifact_id,
            "poll_url": f"/api/v1/jobs/{job['id']}",
        }
    try:
        analysis = await analyze_resume(settings, extracted_text, active_target_role)
    except AnalysisUnavailableError as exc:
        metadata = {"target_role": active_target_role, "target_role_source": target_role_source, "analysis_status": "failed", "analysis_error": str(exc)}
        db.execute(
            "UPDATE artifacts SET metadata = ? WHERE id = ? AND user_id = ?",
            (to_json(metadata), artifact_id, user.id),
        )
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    analysis_id = new_id("resume")
    db.execute(
        """
        INSERT INTO resume_analyses (id, user_id, artifact_id, target_role, match_score, analysis, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            analysis_id,
            user.id,
            artifact_id,
            active_target_role,
            float(analysis.get("match_score", 0)),
            to_json(analysis),
            now_iso(),
        ),
    )
    profile = db.query_one("SELECT * FROM profiles WHERE user_id = ?", (user.id,))
    metadata = from_json(profile["metadata"], {})
    metadata["profile_assets"] = {"resumeName": file.filename or "resume"}
    metadata["latest_resume_analysis_id"] = analysis_id
    db.execute(
        """
        UPDATE profiles SET metadata = ?, updated_at = ?
        WHERE user_id = ?
        """,
        (to_json(metadata), now_iso(), user.id),
    )
    record_readiness_event(
        user.id,
        "resume",
        analysis_id,
        float(analysis.get("match_score", 0)),
        readiness_before,
        {"artifact_id": artifact_id, "target_role": active_target_role, "target_role_source": target_role_source},
    )
    return latest_resume(user.id)


@app.get("/api/v1/resume/latest")
def get_latest_resume(user: CurrentUser = Depends(get_current_user)) -> dict[str, Any] | None:
    ensure_profile(user)
    return latest_resume(user.id)


@app.get("/api/v1/jobs/{job_id}")
def get_processing_job(job_id: str, user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    row = db.query_one("SELECT * FROM processing_jobs WHERE id = ? AND user_id = ?", (job_id, user.id))
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    return processing_job_row(row)


@app.get("/api/v1/dashboard/summary")
def dashboard_summary(user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    ensure_profile(user)
    snapshot = readiness_snapshot(user.id)
    skills = skill_rows(user.id)
    return {
        "user_id": user.id,
        "readiness_score": snapshot["readiness"],
        "role_fit": snapshot["readiness"],
        "top_skills": [item["skill_name"] for item in skills[:5]],
        "domain_breakdown": snapshot["domain_breakdown"],
        "readiness_components": snapshot.get("readiness_components", []),
        "component_scores": snapshot.get("component_scores", {}),
        "component_weights": snapshot.get("component_weights", {}),
        "readiness_formula": snapshot.get("readiness_formula"),
        "pending_hidden_skills": 0,
        "next_event": None,
        "latest_report_id": snapshot["resume"]["id"] if snapshot["resume"] else None,
        "latest_report_created_at": snapshot["resume"]["created_at"] if snapshot["resume"] else None,
    }


@app.get("/api/v1/readiness/events")
def readiness_events(user: CurrentUser = Depends(get_current_user)) -> list[dict[str, Any]]:
    ensure_profile(user)
    rows = db.query_all(
        "SELECT * FROM readiness_events WHERE user_id = ? ORDER BY created_at DESC LIMIT 30",
        (user.id,),
    )
    return [
        {
            "id": row["id"],
            "source_type": row["source_type"],
            "source_id": row["source_id"],
            "score": row["score"],
            "readiness_before": row["readiness_before"],
            "readiness_after": row["readiness_after"],
            "delta": row["delta"],
            "metadata": from_json(row["metadata"], {}),
            "created_at": row["created_at"],
        }
        for row in rows
    ]


@app.get("/api/v1/skills/me")
def skills_me(user: CurrentUser = Depends(get_current_user)) -> list[dict[str, Any]]:
    ensure_profile(user)
    return skill_rows(user.id)


@app.get("/api/v1/skills/me/gaps")
def skills_gaps(user: CurrentUser = Depends(get_current_user)) -> list[dict[str, Any]]:
    ensure_profile(user)
    return gap_rows(user.id)


@app.get("/api/v1/skills/me/role-fit")
def skills_role_fit(user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    profile = ensure_profile(user)
    return role_fit(user.id, profile)


@app.get("/api/v1/skills/me/hidden")
def hidden_skills(user: CurrentUser = Depends(get_current_user)) -> list[dict[str, Any]]:
    ensure_profile(user)
    resume = latest_resume(user.id)
    analysis = resume["analysis"] if resume else {}
    candidates = []
    seen: set[str] = set()
    for index, keyword in enumerate(analysis.get("top_keywords", [])[:3], start=1):
        if str(keyword.get("status", "")).lower() == "present":
            name = str(keyword.get("keyword", "Evidence-backed skill")).strip()
            key = normalize_key(name)
            if key in seen:
                continue
            seen.add(key)
            candidates.append(
                {
                    "id": f"hidden-{index}",
                    "skill_name": name,
                    "confidence_score": 0.72,
                    "source": "resume",
                    "evidence": keyword.get("detail", "Detected from resume wording."),
                    "artifact_id": resume.get("artifact_id"),
                    "status": "pending",
                    "created_at": resume.get("created_at"),
                }
            )
    assessments = db.query_all(
        "SELECT * FROM assessments WHERE user_id = ? AND status = 'completed' ORDER BY completed_at DESC",
        (user.id,)
    )
    for assessment in assessments:
        metadata = from_json(assessment["metadata"], {})
        inference = metadata.get("inference", {}) if isinstance(metadata.get("inference"), dict) else {}
        for index, raw_skill in enumerate(inference.get("hidden_skills", [])[:4], start=1):
            name = str(raw_skill).strip()
            key = normalize_key(name)
            if not name or key in seen:
                continue
            seen.add(key)
            candidates.append(
                {
                    "id": f"assessment-{assessment['id']}-hidden-{index}",
                    "skill_name": name,
                    "confidence_score": 0.78,
                    "source": "assessment",
                    "evidence": "Detected from rule-based assessment strengths.",
                    "artifact_id": None,
                    "status": "pending",
                    "created_at": assessment.get("completed_at"),
                }
            )
    certificate = certificate_signal(user.id)
    if certificate:
        latest = certificate["latest"]
        evaluation = latest.get("evaluation", {})
        for index, raw_skill in enumerate(evaluation.get("detected_skills", [])[:4], start=1):
            name = str(raw_skill).strip()
            key = normalize_key(name)
            if not name or key in seen:
                continue
            seen.add(key)
            candidates.append(
                {
                    "id": f"certificate-hidden-{index}",
                    "skill_name": name,
                    "confidence_score": 0.68 if latest["score"] < 70 else 0.82,
                    "source": "certificate",
                    "evidence": "; ".join(evaluation.get("reasons", [])[:2]) or "Detected from uploaded credential evaluation.",
                    "artifact_id": latest["artifact_id"],
                    "status": "pending",
                    "created_at": latest.get("created_at"),
                }
            )
    return candidates


@app.post("/api/v1/skills/me/hidden/{candidate_id}/{action}")
def update_hidden_skill(candidate_id: str, action: str, user: CurrentUser = Depends(get_current_user)) -> dict[str, Any] | None:
    ensure_profile(user)
    if action not in {"approve", "reject"}:
        raise HTTPException(status_code=400, detail="Unsupported hidden skill action")
    return None


@app.get("/api/v1/skills/requests")
def skill_requests(user: CurrentUser = Depends(get_current_user)) -> list[dict[str, Any]]:
    ensure_profile(user)
    return []


@app.post("/api/v1/skills/requests")
def create_skill_request(payload: SkillRequestCreate, user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    ensure_profile(user)
    try:
        question_rows = _live_question_rows_or_503()
        available = {normalize_key(str(row.get("subject_name") or row.get("dimension") or "")): str(row.get("subject_name") or row.get("dimension") or "") for row in question_rows}
    except HTTPException:
        available = {normalize_key(dimension): dimension for dimension in DIMENSIONS}
    available = {key: value for key, value in available.items() if key and value}
    key = normalize_key(payload.requested_name)
    if key not in available:
        raise HTTPException(status_code=404, detail="Subject not available at the moment")
    return {
        "id": new_id("skillreq"),
        "user_id": user.id,
        "requested_name": available[key],
        "normalized_name": key,
        "requested_type": payload.requested_type,
        "status": "available",
        "generation_status": "rule_based",
        "generated_payload": {"description": f"Capability track for {available[key]}."},
        "metadata": {},
        "is_active": True,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }


def _subject_name_from_question(row: dict[str, Any]) -> str:
    return str(row.get("subject_name") or row.get("dimension") or "Assessment").strip() or "Assessment"


HIDDEN_ASSESSMENT_SUBJECTS = {"General Knowledge"}

def _unique_subject_sequence(subjects: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for subject in subjects:
        label = str(subject or "").strip()
        key = normalize_key(label)
        if label and key not in seen:
            seen.add(key)
            ordered.append(label)
    return ordered


def _subjects_needed_for_role(focus_role: str | None) -> tuple[str, str, list[str]]:
    return career_roles.subjects_for_role(focus_role)


def _subject_count_maps(question_rows: list[dict[str, Any]]) -> tuple[Counter[str], Counter[str], Counter[str]]:
    mcq_counts = Counter(
        _subject_name_from_question(row)
        for row in question_rows
        if row["question_type"] == "MCQ" and str(row.get("options") or "[]") != "[]"
    )
    situational_counts = Counter(
        _subject_name_from_question(row)
        for row in question_rows
        if row["question_type"] == "SITUATIONAL" and str(row.get("options") or "[]") != "[]"
    )
    written_counts = Counter(
        _subject_name_from_question(row)
        for row in question_rows
        if row["question_type"] == "DESCRIPTIVE"
    )
    return mcq_counts, situational_counts, written_counts


def _subject_card_payload(
    subject: str,
    role_label: str,
    subject_scores: dict[str, float],
    dimension_by_subject: dict[str, str],
    mcq_counts: Counter[str],
    situational_counts: Counter[str],
    written_counts: Counter[str],
) -> dict[str, Any]:
    key = normalize_key(subject)
    score = subject_scores.get(key)
    mcq_count = int(mcq_counts.get(subject, 0))
    situational_count = int(situational_counts.get(subject, 0))
    written_count = int(written_counts.get(subject, 0))
    resource_count = mcq_count + situational_count + written_count
    is_available = resource_count > 0
    return {
        "key": key,
        "title": subject,
        "description": (
            f"Pinpoint practice and analysis for {subject}."
            if is_available
            else f"{subject} is relevant for {role_label}, but live questions are still being prepared."
        ),
        "source": "Supabase subject bank" if is_available else "Coming soon",
        "dimension": dimension_by_subject.get(subject),
        "severity": round(max(0, 100 - score) / 100, 3) if score is not None else 1,
        "current_score": score,
        "resource_count": resource_count,
        "mcq_count": mcq_count,
        "situational_count": situational_count,
        "written_count": written_count,
        "is_available": is_available,
        "availability": {
            "mcq": mcq_count > 0,
            "situational": situational_count > 0,
            "written": written_count > 0,
        },
        "skill_id": key if is_available else None,
        "skill_request_id": None,
    }


def _category_match_field(category: str, question_rows: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    category_key = normalize_key(category)
    if category_key in {"", "capability", "capability-profile", "all"}:
        return None, None
    for subject in sorted({_subject_name_from_question(row) for row in question_rows if _subject_name_from_question(row) not in HIDDEN_ASSESSMENT_SUBJECTS}):
        if normalize_key(subject) == category_key:
            return "subject_name", subject
    for dimension in DIMENSIONS:
        if normalize_key(dimension) == category_key:
            return "dimension", dimension
    raise HTTPException(status_code=404, detail="Subject not available at the moment")


def _question_matches_category(row: dict[str, Any], field: str | None, value: str | None) -> bool:
    if not field or not value:
        return True
    if field == "subject_name":
        return normalize_key(_subject_name_from_question(row)) == normalize_key(value)
    return normalize_key(str(row.get("dimension") or "")) == normalize_key(value)


def _subject_attempt_scores(user_id: str) -> dict[str, float]:
    rows = db.query_all(
        """
        SELECT category, score, completed_at, created_at FROM assessments
        WHERE user_id = ? AND status = 'completed' AND score IS NOT NULL
        ORDER BY COALESCE(completed_at, created_at) ASC
        """,
        (user_id,),
    )
    scores: dict[str, float] = {}
    for row in rows:
        key = normalize_key(str(row.get("category") or ""))
        if key:
            scores[key] = _bounded_score(row["score"])
    written_rows = db.query_all(
        """
        SELECT skill_id, metadata, score, updated_at, created_at FROM written_assessments
        WHERE user_id = ? AND status = 'completed' AND score IS NOT NULL
        ORDER BY COALESCE(updated_at, created_at) ASC
        """,
        (user_id,),
    )
    for row in written_rows:
        metadata = from_json(row["metadata"], {})
        key = normalize_key(str(metadata.get("subject") or row.get("skill_id") or ""))
        if key:
            scores[key] = _bounded_score(row["score"])
    return scores


@app.get("/api/v1/assessments/subjects")
def assessment_subjects(user: CurrentUser = Depends(get_current_user)) -> list[dict[str, Any]]:
    profile = ensure_profile(user)
    try:
        question_rows = _live_question_rows_or_503()
    except HTTPException:
        return []
    subject_scores = _subject_attempt_scores(user.id)
    available_subjects = sorted({_subject_name_from_question(row) for row in question_rows if _subject_name_from_question(row) not in HIDDEN_ASSESSMENT_SUBJECTS})
    available_by_key = {normalize_key(subject): subject for subject in available_subjects}
    _, role_label, needed_subjects = _subjects_needed_for_role(profile.get("focus_role"))
    subjects = [
        available_by_key.get(normalize_key(subject), subject)
        for subject in _unique_subject_sequence(needed_subjects)
    ]
    mcq_counts, situational_counts, written_counts = _subject_count_maps(question_rows)
    dimension_by_subject = {
        subject: next((row["dimension"] for row in question_rows if _subject_name_from_question(row) == subject), "Domain Foundation")
        for subject in available_subjects
    }
    return [
        _subject_card_payload(
            subject,
            role_label,
            subject_scores,
            dimension_by_subject,
            mcq_counts,
            situational_counts,
            written_counts,
        )
        for subject in subjects
    ]


@app.get("/api/v1/assessments/subjects/{subject_id}")
def assessment_subject_detail(subject_id: str, user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    subject = next((item for item in assessment_subjects(user) if item["key"] == subject_id), None)
    if subject:
        return subject
    profile = ensure_profile(user)
    question_rows = _live_question_rows_or_503()
    available_subjects = sorted({_subject_name_from_question(row) for row in question_rows if _subject_name_from_question(row) not in HIDDEN_ASSESSMENT_SUBJECTS})
    direct_subject = next((item for item in available_subjects if normalize_key(item) == subject_id), None)
    if not direct_subject:
        raise HTTPException(status_code=404, detail="Subject not available at the moment")
    mcq_counts, situational_counts, written_counts = _subject_count_maps(question_rows)
    dimension_by_subject = {
        item: next((row["dimension"] for row in question_rows if _subject_name_from_question(row) == item), "Domain Foundation")
        for item in available_subjects
    }
    return _subject_card_payload(
        direct_subject,
        str(profile.get("focus_role") or "this path"),
        _subject_attempt_scores(user.id),
        dimension_by_subject,
        mcq_counts,
        situational_counts,
        written_counts,
    )


@app.get("/api/v1/assessments/assignments")
def student_assessment_assignments(user: CurrentUser = Depends(get_current_user)) -> list[dict[str, Any]]:
    profile = ensure_profile(user)
    department_id = profile.get("department_id")
    if not department_id:
        return []
    rows = db.query_all(
        """
        SELECT * FROM assessment_assignments
        WHERE department_id = ?
        ORDER BY starts_at DESC
        """,
        (department_id,),
    )
    return [assignment_row(row, user.id) for row in rows]


@app.post("/api/v1/assessments")
def create_assessment_route(payload: AssessmentCreate, user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    profile = ensure_profile(user)
    live_question_rows = _live_question_rows_or_503()
    assignment = None
    mode = payload.mode
    category = payload.category
    assessment_type = payload.assessment_type
    question_type = payload.question_type
    assignment_question_ids: list[str] | None = None
    if payload.assignment_id:
        existing = db.query_one(
            """
            SELECT * FROM assessments
            WHERE user_id = ? AND assignment_id = ?
            ORDER BY created_at DESC LIMIT 1
            """,
            (user.id, payload.assignment_id),
        )
        if existing and existing["status"] == "completed":
            return read_assessment(db, existing["id"], user.id)
        assignment = _validate_assignment_for_student(payload.assignment_id, user.id, profile)
        if existing:
            return read_assessment(db, existing["id"], user.id)
        mode = assignment["mode"]
        category = assignment["category"]
        assessment_type = assignment["assessment_type"]
        question_type = assignment["question_type"]
        parsed_question_ids = from_json(assignment.get("question_ids"), [])
        if isinstance(parsed_question_ids, list) and parsed_question_ids:
            assignment_question_ids = [str(item) for item in parsed_question_ids]
    return create_assessment(
        db,
        user.id,
        mode=mode,
        assessment_type=assessment_type,
        question_type=question_type,
        category=category,
        assignment_id=payload.assignment_id,
        question_ids=assignment_question_ids,
        question_pool=live_question_rows,
    )


@app.get("/api/v1/assessments/{assessment_id}/questions")
def get_assessment_questions(assessment_id: str, user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    ensure_profile(user)
    from app.assessment_engine import get_assigned_questions
    return get_assigned_questions(db, assessment_id, user.id)


@app.post("/api/v1/assessments/{assessment_id}/answer")
def answer_assessment_question(
    assessment_id: str,
    payload: AnswerSubmit,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    ensure_profile(user)
    selected = payload.selected_answer or payload.selected_option_id
    if not selected:
        raise HTTPException(status_code=400, detail="selected_answer is required")
    return submit_answer(db, assessment_id, user.id, payload.question_id, selected, payload.time_taken_seconds)


@app.post("/api/v1/assessments/{assessment_id}/answers")
def answer_assessment_batch(
    assessment_id: str,
    payload: BatchAnswerSubmit,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    results = []
    for item in payload.answers:
        question_id = str(item.get("question_id") or "")
        selected = str(item.get("selected_option_id") or item.get("selected_answer") or "")
        if question_id and selected:
            results.append(submit_answer(db, assessment_id, user.id, question_id, selected, item.get("time_taken_seconds")))
    return {"assessment_id": assessment_id, "answers_recorded": len(results), "results": results}


@app.post("/api/v1/assessments/{assessment_id}/complete")
async def complete_assessment_route(assessment_id: str, user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    ensure_profile(user)
    before_row = db.query_one("SELECT status FROM assessments WHERE id = ? AND user_id = ?", (assessment_id, user.id))
    readiness_before = readiness_snapshot(user.id)["readiness"]
    result = await complete_assessment(db, assessment_id, user.id, force=True)
    if before_row and before_row["status"] != "completed":
        record_readiness_event(
            user.id,
            "assessment",
            assessment_id,
            float(result.get("score", 0)),
            readiness_before,
            {
                "correct_answers": result.get("correct_answers"),
                "total_questions": result.get("total_questions"),
                "status": result.get("status"),
            },
        )
    snapshot = readiness_snapshot(user.id)
    result["readiness_score"] = snapshot["readiness"]
    result["readiness_components"] = snapshot.get("readiness_components", [])
    result["readiness_formula"] = snapshot.get("readiness_formula")
    return result


@app.get("/api/v1/assessments/log")
def assessment_log(user: CurrentUser = Depends(get_current_user)) -> list[dict[str, Any]]:
    profile = ensure_profile(user)
    snapshot = readiness_snapshot(user.id)
    live_readiness = snapshot["readiness"]
    live_role_name = profile.get("focus_role") or "Unassigned"
    breakdown = snapshot.get("domain_breakdown") if isinstance(snapshot.get("domain_breakdown"), dict) else {}
    current_gaps = [
        dimension
        for dimension, _score in sorted(
            (
                (dimension, float(score))
                for dimension, score in breakdown.items()
                if isinstance(score, (int, float))
            ),
            key=lambda item: item[1],
        )[:3]
    ] or ["Practice consistency across the attempted subject"]
    rows = db.query_all(
        "SELECT * FROM assessments WHERE user_id = ? ORDER BY created_at DESC LIMIT 20",
        (user.id,),
    )

    def parse_log(row):
        meta = from_json(row.get("metadata") or "{}", {})
        inf = meta.get("inference", {})
        analytics = meta.get("analytics", {})
        capability_profile = from_json(row.get("capability_profile") or "{}", {})
        capability_strengths = list(capability_profile.keys())[:3] if isinstance(capability_profile, dict) else []
        return {
            "id": row["id"],
            "type": row["assessment_type"],
            "subject": row["category"],
            "score": row["score"],
            "status": row["status"],
            "completed_at": row["completed_at"],
            "insight": inf.get("insight", "Deterministic capability score generated by CELTMap Phase 1."),
            "feedback": None,
            "strengths": inf.get("strengths") or capability_strengths,
            "risks": inf.get("risks", current_gaps),
            "recommendations": inf.get("recommendations", ["Complete the next assessment block", "Upload stronger evidence", "Review the weakest dimension"]),
            "readiness_score": live_readiness,
            "role_name": live_role_name,
            "readiness_components": snapshot.get("readiness_components", []),
            "hidden_skills": inf.get("hidden_skills", []),
            "areas_of_betterment": inf.get("areas_of_betterment", []),
            "analytics": analytics,
        }

    logs = [parse_log(row) for row in rows]
    written_rows = db.query_all(
        "SELECT * FROM written_assessments WHERE user_id = ? ORDER BY updated_at DESC LIMIT 20",
        (user.id,),
    )
    for row in written_rows:
        item = written_assessment_row(row, readiness_score=live_readiness)
        logs.append(
            {
                "id": item["id"],
                "type": "written",
                "subject": item.get("metadata", {}).get("dimension") or item.get("skill_id") or "written",
                "score": item["score"],
                "status": item["status"],
                "completed_at": item["updated_at"] if item["status"] == "completed" else None,
                "insight": item["feedback"] or "Written assessment draft saved.",
                "feedback": item["feedback"],
                "strengths": item["insights"],
                "risks": item["loopholes"],
                "recommendations": item["recommendations"],
                "readiness_score": live_readiness,
                "role_name": item["role_name"] or live_role_name,
                "readiness_components": snapshot.get("readiness_components", []),
                "plagiarism": item["plagiarism"],
            }
        )
    return sorted(logs, key=lambda row: row.get("completed_at") or "", reverse=True)[:30]


@app.get("/api/v1/assessments/subject-progress")
def assessment_subject_progress(user: CurrentUser = Depends(get_current_user)) -> list[dict[str, Any]]:
    ensure_profile(user)
    return subject_progress_rows(user.id)


@app.get("/api/v1/mcq/questions")
def legacy_questions(
    limit: int = Query(default=15, ge=1, le=30),
    category: str = "capability-profile",
    question_type: str = "MCQ",
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    ensure_profile(user)
    live_question_rows = _live_question_rows_or_503()
    qtype = question_type.upper()
    if qtype not in {"MCQ", "SITUATIONAL"}:
        qtype = "MCQ"
    field, value = _category_match_field(category, live_question_rows)
    rows = [
        row
        for row in live_question_rows
        if row.get("question_type") == qtype
        and _question_matches_category(row, field, value)
        and str(row.get("options") or "[]") != "[]"
    ][:limit]
    return {"questions": [public_question(row) for row in rows], "count": len(rows)}


@app.get("/api/v1/written-assessments")
def written_assessments(user: CurrentUser = Depends(get_current_user)) -> list[dict[str, Any]]:
    ensure_profile(user)
    rows = db.query_all(
        "SELECT * FROM written_assessments WHERE user_id = ? ORDER BY updated_at DESC LIMIT 20",
        (user.id,),
    )
    return [written_assessment_row(row) for row in rows]


@app.post("/api/v1/written-assessments")
def create_written_assessment(
    payload: WrittenAssessmentCreate,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    profile = ensure_profile(user)
    live_question_rows = _live_question_rows_or_503()
    assignment = None
    question = None
    skill_id = payload.skill_id
    if payload.assignment_id:
        existing = db.query_one(
            """
            SELECT * FROM written_assessments
            WHERE user_id = ? AND assignment_id = ?
            ORDER BY created_at DESC LIMIT 1
            """,
            (user.id, payload.assignment_id),
        )
        if existing and existing["status"] == "completed":
            return written_assessment_row(existing)
        assignment = _validate_assignment_for_student(payload.assignment_id, user.id, profile)
        if existing:
            return written_assessment_row(existing)
        if assignment["question_type"] != "DESCRIPTIVE":
            raise HTTPException(status_code=400, detail="Assigned written tests must use DESCRIPTIVE questions")
        assigned_ids = from_json(assignment.get("question_ids"), [])
        question = _select_written_question_from_pool_ids(live_question_rows, assigned_ids) if isinstance(assigned_ids, list) else None
        skill_id = skill_id or normalize_key(assignment["category"])
    requested_subject = skill_id or ""
    dimension = _dimension_from_skill(requested_subject)
    question = question or _select_written_question_from_pool(live_question_rows, requested_subject or dimension)
    if not question:
        raise HTTPException(status_code=404, detail="Subject not available at the moment")
    role_name = role_fit(user.id)["role_name"]
    assignment_title = assignment["title"] if assignment else None
    prompt, prompt_normalized = _written_prompt_from_question(question, role_name, assignment_title)
    session_id = new_id("written")
    metadata = {
        "evaluator_mode": CENTRAL_WRITTEN_EVALUATOR_MODE,
        "role_name": role_name,
        "source": "supabase_questions",
        "dimension": question["dimension"] if question else (dimension or "Communication"),
        "subject": _subject_name_from_question(question) if question else (requested_subject or dimension or "Written"),
        "source_question_id": question["id"] if question else None,
        "raw_question_text": question["question_text"] if question else None,
        "prompt_normalized": prompt_normalized,
        "assignment_id": payload.assignment_id,
        "assignment_title": assignment_title,
    }
    rubric = {
        "question_relevance": 30,
        "reasoning_correctness": 25,
        "evidence": 20,
        "risk_tradeoff": 15,
        "clarity": 10,
    }
    db.execute(
        """
        INSERT INTO written_assessments (
            id, user_id, assignment_id, skill_id, skill_request_id, prompt, rubric, status, metadata, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?)
        """,
        (
            session_id,
            user.id,
            payload.assignment_id,
            skill_id,
            payload.skill_request_id,
            prompt,
            to_json(rubric),
            to_json(metadata),
            now_iso(),
            now_iso(),
        ),
    )
    return written_assessment_row(db.query_one("SELECT * FROM written_assessments WHERE id = ?", (session_id,)))


@app.get("/api/v1/written-assessments/{session_id}")
def get_written_assessment(session_id: str, user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    ensure_profile(user)
    row = db.query_one("SELECT * FROM written_assessments WHERE id = ? AND user_id = ?", (session_id, user.id))
    if not row:
        raise HTTPException(status_code=404, detail="Written assessment not found")
    return written_assessment_row(row)


@app.patch("/api/v1/written-assessments/{session_id}")
def update_written_assessment(
    session_id: str,
    payload: WrittenAssessmentPatch,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    ensure_profile(user)
    row = db.query_one("SELECT * FROM written_assessments WHERE id = ? AND user_id = ?", (session_id, user.id))
    if not row:
        raise HTTPException(status_code=404, detail="Written assessment not found")
    metadata = from_json(row["metadata"], {})
    metadata["evaluator_mode"] = CENTRAL_WRITTEN_EVALUATOR_MODE
    db.execute(
        """
        UPDATE written_assessments
        SET submission_text = COALESCE(?, submission_text),
            metadata = ?,
            status = CASE WHEN status = 'completed' THEN status ELSE 'draft' END,
            updated_at = ?
        WHERE id = ? AND user_id = ?
        """,
        (payload.submission_text, to_json(metadata), now_iso(), session_id, user.id),
    )
    return written_assessment_row(db.query_one("SELECT * FROM written_assessments WHERE id = ?", (session_id,)))


async def evaluate_written_assessment_session(session_id: str, user_id: str) -> None:
    row = db.query_one("SELECT * FROM written_assessments WHERE id = ? AND user_id = ?", (session_id, user_id))
    if not row:
        return
    submission = str(row["submission_text"] or "").strip()
    was_completed = row["status"] == "completed"
    try:
        readiness_before = readiness_snapshot(user_id)["readiness"]
        metadata = from_json(row["metadata"], {})
        role_name = metadata.get("role_name") or role_fit(user_id)["role_name"]
        evaluator_mode = CENTRAL_WRITTEN_EVALUATOR_MODE
        evaluation = await analyze_written_response(settings, row["prompt"], submission, evaluator_mode, role_name)
        metadata.update(
            {
                "role_name": role_name,
                "evaluator_mode": CENTRAL_WRITTEN_EVALUATOR_MODE,
                "insights": evaluation.get("insights", []),
                "loopholes": evaluation.get("loopholes", []),
                "recommendations": evaluation.get("recommendations", []),
                "plagiarism": evaluation.get("plagiarism"),
                "evaluation_score": evaluation.get("readiness_score", evaluation.get("score")),
                "processing_started_at": metadata.get("processing_started_at"),
                "processing_completed_at": now_iso(),
            }
        )
        score = float(evaluation.get("score", 0))
        db.execute(
            """
            UPDATE written_assessments
            SET score = ?,
                feedback = ?,
                status = 'completed',
                metadata = ?,
                updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (score, str(evaluation.get("feedback", "")), to_json(metadata), now_iso(), session_id, user_id),
        )

        profile = db.query_one("SELECT * FROM profiles WHERE user_id = ?", (user_id,))
        if profile:
            profile_metadata = from_json(profile["metadata"], {})
            profile_metadata["written_readiness"] = score
            profile_metadata["latest_written_assessment_id"] = session_id
            db.execute(
                "UPDATE profiles SET metadata = ?, updated_at = ? WHERE user_id = ?",
                (to_json(profile_metadata), now_iso(), user_id),
            )
        if not was_completed:
            record_readiness_event(
                user_id,
                "written_assessment",
                session_id,
                score,
                readiness_before,
                {
                    "role_name": role_name,
                    "dimension": metadata.get("dimension"),
                    "written_score": score,
                },
            )
        snapshot = readiness_snapshot(user_id)
        persist_readiness_snapshot(user_id, snapshot)
        sync_aspirations_readiness(user_id, snapshot)
        stored_metadata = from_json(db.query_one("SELECT metadata FROM written_assessments WHERE id = ?", (session_id,))["metadata"], {})
        stored_metadata.update(
            {
                "global_readiness_score": snapshot["readiness"],
                "readiness_score": snapshot["readiness"],
                "readiness_kind": "global",
                "readiness_components": snapshot.get("readiness_components", []),
                "readiness_formula": snapshot.get("readiness_formula"),
            }
        )
        db.execute(
            "UPDATE written_assessments SET metadata = ?, updated_at = ? WHERE id = ? AND user_id = ?",
            (to_json(stored_metadata), now_iso(), session_id, user_id),
        )
    except Exception as exc:
        failed = db.query_one("SELECT metadata FROM written_assessments WHERE id = ? AND user_id = ?", (session_id, user_id))
        metadata = from_json(failed["metadata"], {}) if failed else {}
        metadata["processing_error"] = str(exc)[:500]
        metadata["processing_failed_at"] = now_iso()
        db.execute(
            """
            UPDATE written_assessments
            SET status = 'failed',
                metadata = ?,
                updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (to_json(metadata), now_iso(), session_id, user_id),
        )


@app.post("/api/v1/written-assessments/{session_id}/complete")
async def complete_written_assessment(
    session_id: str,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    ensure_profile(user)
    row = db.query_one("SELECT * FROM written_assessments WHERE id = ? AND user_id = ?", (session_id, user.id))
    if not row:
        raise HTTPException(status_code=404, detail="Written assessment not found")
    submission = str(row["submission_text"] or "").strip()
    if len(submission) < 40:
        raise HTTPException(status_code=400, detail="Write a longer answer before submitting the assessment")
    if row["status"] == "completed":
        return written_assessment_row(row, readiness_score=readiness_snapshot(user.id)["readiness"])
    if row["status"] == "processing":
        return written_assessment_row(row)

    metadata = from_json(row["metadata"], {})
    metadata["processing_started_at"] = now_iso()
    metadata.pop("processing_error", None)
    metadata.pop("processing_failed_at", None)
    db.execute(
        """
        UPDATE written_assessments
        SET status = 'processing',
            metadata = ?,
            updated_at = ?
        WHERE id = ? AND user_id = ?
        """,
        (to_json(metadata), now_iso(), session_id, user.id),
    )
    background_tasks.add_task(evaluate_written_assessment_session, session_id, user.id)
    return written_assessment_row(db.query_one("SELECT * FROM written_assessments WHERE id = ? AND user_id = ?", (session_id, user.id)))


@app.get("/api/v1/learning/path")
def learning_path(user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    profile = ensure_profile(user)
    fit = role_fit(user.id, profile)
    modules = []
    for index, gap in enumerate(gap_rows(user.id)[:6], start=1):
        modules.append(
            {
                "title": f"Improve {gap['skill_name']}",
                "week": index,
                "skill_name": gap["skill_name"],
                "gap_severity": gap["gap_severity"],
                "is_available": True,
                "resources": [
                    {
                        "title": f"{gap['skill_name']} practice block",
                        "content": "Complete one assessment block, one project exercise, and one mentor review.",
                        "resource_type": "phase1_rule_based",
                        "skill_name": gap["skill_name"],
                        "resource_url": None,
                    }
                ],
            }
        )
    return {"role_name": fit["role_name"], "modules": modules}


@app.get("/api/v1/reports/me/latest")
def latest_report(user: CurrentUser = Depends(get_current_user)) -> dict[str, Any] | None:
    ensure_profile(user)
    resume = latest_resume(user.id)
    if not resume:
        return None
    return {"id": resume["id"], "user_id": user.id, "payload": resume["analysis"], "created_at": resume["created_at"]}


def _generate_passport_pdf_buffer(profile: dict, snapshot: dict, title: str = "CELTM Skill Passport") -> io.BytesIO:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.setTitle(title)

    # Header background
    pdf.setFillColor(colors.HexColor("#6B21A8")) # Purple-800
    pdf.rect(0, 700, 612, 100, stroke=0, fill=1)

    # CELTM Logo Text
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 36)
    pdf.drawString(50, 740, "CELTM")

    pdf.setFont("Helvetica", 14)
    pdf.drawString(50, 720, title)

    # Profile Info
    pdf.setFillColor(colors.black)
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, 660, f"Student: {profile.get('full_name') or 'CELTM Student'}")

    pdf.setFont("Helvetica", 12)
    pdf.setFillColor(colors.darkgray)
    pdf.drawString(50, 640, f"Email: {profile.get('email') or ''}")
    pdf.drawString(50, 620, f"Institution: {profile.get('institution_name') or 'Not set'}")
    pdf.drawString(50, 600, f"Department: {profile.get('department_name') or 'Not set'}")

    # Readiness Score Box
    pdf.setStrokeColor(colors.HexColor("#9333EA")) # Purple-600
    pdf.setFillColor(colors.HexColor("#FAF5FF")) # Purple-50
    pdf.roundRect(400, 600, 150, 80, 10, stroke=1, fill=1)
    pdf.setFillColor(colors.HexColor("#6B21A8")) # Purple-800
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(415, 655, "Readiness Score")
    pdf.setFont("Helvetica-Bold", 32)
    pdf.drawString(435, 620, f"{snapshot['readiness']}%")

    # Capability Profile Section
    y = 540
    pdf.setFillColor(colors.black)
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, y, "Capability Profile")
    pdf.setStrokeColor(colors.lightgrey)
    pdf.line(50, y-10, 562, y-10)

    y -= 40
    pdf.setFont("Helvetica", 12)
    for name, score in (snapshot["domain_breakdown"] or {}).items():
        # Draw label
        pdf.setFillColor(colors.darkgray)
        pdf.drawString(50, y, name)
        # Draw background bar
        pdf.setFillColor(colors.HexColor("#E5E7EB"))
        pdf.roundRect(250, y-2, 250, 12, 6, stroke=0, fill=1)
        # Fill bar
        pdf.setFillColor(colors.HexColor("#9333EA"))
        width = int((score / 100) * 250)
        if width > 0:
            pdf.roundRect(250, y-2, width, 12, 6, stroke=0, fill=1)
        # Draw score
        pdf.setFillColor(colors.black)
        pdf.drawString(515, y, f"{score}%")

        y -= 30

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer

def _generate_assessment_report_pdf(assessment_row: dict) -> io.BytesIO:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # Header
    pdf.setFillColor(colors.HexColor("#0A1128"))
    pdf.rect(0, height - 80, width, 80, fill=True, stroke=False)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 24)
    pdf.drawString(40, height - 50, "CELTM Assessment Report")

    pdf.setFillColor(colors.HexColor("#0A1128"))
    pdf.setFont("Helvetica-Bold", 18)
    subject = str(assessment_row.get("category") or assessment_row.get("subject") or "Unknown").replace("_", " ").title()
    pdf.drawString(40, height - 120, f"Subject: {subject}")

    pdf.setFont("Helvetica", 12)
    pdf.setFillColor(colors.gray)
    pdf.drawString(40, height - 140, f"Type: {str(assessment_row.get('assessment_type') or assessment_row.get('type') or 'Unknown').upper()}")
    pdf.drawString(40, height - 160, f"Status: {assessment_row.get('status', 'Unknown')}")
    pdf.drawString(200, height - 160, f"Score: {assessment_row.get('score', 0)}")

    y = height - 200
    meta = from_json(assessment_row.get("metadata", "{}"), {})
    analytics = meta.get("analytics", {})
    if analytics:
        pdf.setFillColor(colors.HexColor("#0A1128"))
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(40, y, "Analytics:")
        y -= 25
        pdf.setFont("Helvetica", 12)
        pdf.setFillColor(colors.black)
        pdf.drawString(40, y, f"Total Questions: {analytics.get('total', 0)}")
        pdf.drawString(200, y, f"Correct: {analytics.get('correct', 0)}")
        pdf.drawString(300, y, f"Wrong: {analytics.get('wrong', 0)}")
        y -= 35

    inference = meta.get("inference", {})
    if inference:
        pdf.setFillColor(colors.HexColor("#0A1128"))
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(40, y, "AI Inference:")
        y -= 25

        pdf.setFont("Helvetica", 12)
        pdf.setFillColor(colors.black)

        insight = inference.get("insight", "")
        if insight:
            pdf.drawString(40, y, "Insight:")
            y -= 20
            # Basic text wrap
            words = insight.split()
            line = ""
            for w in words:
                if pdf.stringWidth(line + w, "Helvetica", 12) < width - 80:
                    line += w + " "
                else:
                    pdf.drawString(60, y, line)
                    y -= 20
                    line = w + " "
            if line:
                pdf.drawString(60, y, line)
                y -= 25

        def draw_list(title, items):
            nonlocal y
            if not items: return
            if y < 100:
                pdf.showPage()
                y = height - 60
            pdf.setFont("Helvetica-Bold", 12)
            pdf.drawString(40, y, f"{title}:")
            y -= 20
            pdf.setFont("Helvetica", 11)
            for item in items:
                if isinstance(item, dict):
                    item_str = item.get("skill") or item.get("name") or item.get("area") or str(item)
                else:
                    item_str = str(item)
                pdf.drawString(60, y, f"- {item_str}")
                y -= 18
            y -= 10

        draw_list("Hidden Skills", inference.get("hidden_skills", []))
        draw_list("Areas of Betterment", inference.get("areas_of_betterment", []))
        draw_list("Strengths", inference.get("strengths", []))
        draw_list("Risks", inference.get("risks", []))
        draw_list("Recommendations", inference.get("recommendations", []))

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer


def _generate_written_assessment_report_pdf(row: dict[str, Any]) -> io.BytesIO:
    item = written_assessment_row(row)
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    pdf.setTitle("CELTM Written Assessment Report")

    pdf.setFillColor(colors.HexColor("#0A1128"))
    pdf.rect(0, height - 80, width, 80, fill=True, stroke=False)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawString(40, height - 50, "CELTM Written Assessment Report")

    y = height - 120
    pdf.setFillColor(colors.HexColor("#0A1128"))
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(40, y, f"Subject: {str(item.get('metadata', {}).get('dimension') or item.get('skill_id') or 'Written').replace('_', ' ').title()}")
    y -= 24
    pdf.setFont("Helvetica", 12)
    pdf.setFillColor(colors.gray)
    pdf.drawString(40, y, f"Status: {item['status']}")
    pdf.drawString(180, y, f"Score: {item['score'] if item['score'] is not None else 'Pending'}")
    y -= 36

    def draw_wrapped(title: str, text: str, max_lines: int = 9) -> None:
        nonlocal y
        if y < 120:
            pdf.showPage()
            y = height - 60
        pdf.setFillColor(colors.HexColor("#0A1128"))
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(40, y, title)
        y -= 20
        pdf.setFillColor(colors.black)
        pdf.setFont("Helvetica", 10)
        words = str(text or "").split()
        line = ""
        line_count = 0
        for word in words:
            next_line = f"{line}{word} "
            if pdf.stringWidth(next_line, "Helvetica", 10) < width - 90:
                line = next_line
                continue
            pdf.drawString(50, y, line)
            y -= 15
            line = f"{word} "
            line_count += 1
            if line_count >= max_lines:
                pdf.drawString(50, y, "...")
                y -= 18
                return
        if line:
            pdf.drawString(50, y, line)
            y -= 18

    def draw_list(title: str, values: list[Any]) -> None:
        nonlocal y
        if not values:
            return
        if y < 120:
            pdf.showPage()
            y = height - 60
        pdf.setFillColor(colors.HexColor("#0A1128"))
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(40, y, title)
        y -= 18
        pdf.setFillColor(colors.black)
        pdf.setFont("Helvetica", 10)
        for value in values[:6]:
            pdf.drawString(55, y, f"- {value}")
            y -= 15
        y -= 6

    draw_wrapped("Prompt", item["prompt"], max_lines=7)
    draw_wrapped("Submitted answer", item.get("submission_text") or "No submission text stored.", max_lines=14)
    draw_wrapped("Evaluator feedback", item.get("feedback") or "No evaluator feedback stored yet.", max_lines=8)
    draw_list("Insights", item.get("insights", []))
    draw_list("Loopholes", item.get("loopholes", []))
    draw_list("Recommendations", item.get("recommendations", []))

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer


def _generate_admin_students_report_pdf(cards: list[dict[str, Any]], admin: AdminUser) -> io.BytesIO:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    pdf.setTitle("CELTM Admin Students Report")

    def new_page() -> float:
        pdf.showPage()
        pdf.setFillColor(colors.HexColor("#0A1128"))
        pdf.rect(0, height - 62, width, 62, fill=True, stroke=False)
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 18)
        pdf.drawString(40, height - 40, "CELTM Admin Students Report")
        return height - 92

    def clean(value: Any) -> str:
        if isinstance(value, list):
            return "; ".join(str(item) for item in value if str(item).strip())
        return str(value or "").strip()

    def draw_wrapped(text: Any, x: float, y: float, max_width: float, *, font: str = "Helvetica", size: int = 9, max_lines: int = 2) -> float:
        pdf.setFont(font, size)
        words = clean(text).split()
        if not words:
            pdf.drawString(x, y, "-")
            return y - 12
        line = ""
        lines: list[str] = []
        for word in words:
            candidate = f"{line}{word} "
            if pdf.stringWidth(candidate, font, size) <= max_width:
                line = candidate
            else:
                if line:
                    lines.append(line.strip())
                line = f"{word} "
                if len(lines) >= max_lines:
                    break
        if line and len(lines) < max_lines:
            lines.append(line.strip())
        if len(lines) == max_lines and len(" ".join(words)) > len(" ".join(lines)):
            lines[-1] = lines[-1][:80].rstrip() + "..."
        for line_value in lines:
            pdf.drawString(x, y, line_value)
            y -= 12
        return y

    pdf.setFillColor(colors.HexColor("#0A1128"))
    pdf.rect(0, height - 82, width, 82, fill=True, stroke=False)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 24)
    pdf.drawString(40, height - 48, "CELTM Admin Students Report")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(40, height - 66, f"Generated by {admin.email} ({admin.role})")

    y = height - 118
    pdf.setFillColor(colors.HexColor("#0A1128"))
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(40, y, f"Total students: {len(cards)}")
    pdf.drawString(220, y, f"Generated at: {now_iso()}")
    y -= 30

    if not cards:
        pdf.setFont("Helvetica", 11)
        pdf.drawString(40, y, "No students found for the selected admin scope.")
    for index, card in enumerate(cards, start=1):
        if y < 145:
            y = new_page()
        readiness = round(float(card.get("readiness_score") or 0), 2)
        resume = card.get("resume_score")
        assessment = card.get("assessment_score")
        written = card.get("written_score")
        credential = card.get("credential_score")

        pdf.setFillColor(colors.HexColor("#F3F4F6"))
        pdf.roundRect(36, y - 98, width - 72, 106, 10, stroke=False, fill=True)
        pdf.setFillColor(colors.HexColor("#0A1128"))
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(50, y - 10, f"{index}. {clean(card.get('name')) or 'Student'}")
        pdf.setFont("Helvetica", 9)
        pdf.setFillColor(colors.darkgray)
        pdf.drawString(50, y - 26, clean(card.get("email")))
        pdf.drawString(50, y - 42, f"{clean(card.get('institution_name')) or 'Not set'} / {clean(card.get('department_name')) or 'Not set'}")
        pdf.drawString(50, y - 58, f"Target: {clean(card.get('target_role')) or 'Pending'}")

        pdf.setFillColor(colors.HexColor("#2563EB"))
        pdf.setFont("Helvetica-Bold", 18)
        pdf.drawRightString(width - 50, y - 12, f"{readiness}%")
        pdf.setFillColor(colors.darkgray)
        pdf.setFont("Helvetica", 9)
        pdf.drawRightString(width - 50, y - 28, "Readiness")
        pdf.drawString(330, y - 46, f"Resume: {'Pending' if resume is None else str(round(float(resume), 2)) + '%'}")
        pdf.drawString(330, y - 60, f"Assessment: {'Pending' if assessment is None else str(round(float(assessment), 2)) + '%'}")
        pdf.drawString(330, y - 74, f"Written: {'Pending' if written is None else str(round(float(written), 2)) + '%'}")
        pdf.drawString(330, y - 88, f"Credential: {'Pending' if credential is None else str(round(float(credential), 2)) + '%'}")

        y -= 126
        if y < 95:
            y = new_page()
        pdf.setFillColor(colors.black)
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(50, y, "Strong points")
        pdf.drawString(230, y, "Weak points")
        pdf.drawString(410, y, "Institute help")
        y -= 14
        start_y = y
        y1 = draw_wrapped(card.get("strong_points"), 50, start_y, 155, max_lines=3)
        y2 = draw_wrapped(card.get("weak_points"), 230, start_y, 155, max_lines=3)
        y3 = draw_wrapped(card.get("institute_help"), 410, start_y, 155, max_lines=3)
        y = min(y1, y2, y3) - 14

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer


def _pdf_response(buffer: io.BytesIO, filename: str) -> Response:
    return Response(
        buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/v1/reports/assessment/{assessment_id}.pdf")
def assessment_pdf(assessment_id: str, user: CurrentUser = Depends(get_current_user)) -> Response:
    row = db.query_one("SELECT * FROM assessments WHERE id = ? AND user_id = ?", (assessment_id, user.id))
    if row:
        buffer = _generate_assessment_report_pdf(row)
        return _pdf_response(buffer, f"assessment-report-{assessment_id}.pdf")

    written = db.query_one("SELECT * FROM written_assessments WHERE id = ? AND user_id = ?", (assessment_id, user.id))
    if written:
        buffer = _generate_written_assessment_report_pdf(written)
        return _pdf_response(buffer, f"written-assessment-report-{assessment_id}.pdf")

    raise HTTPException(status_code=404, detail="Assessment not found.")

@app.get("/api/v1/reports/me/passport.pdf")
def passport_pdf(user: CurrentUser = Depends(get_current_user)) -> Response:
    profile = ensure_profile(user)
    snapshot = readiness_snapshot(user.id)
    buffer = _generate_passport_pdf_buffer(profile, snapshot)
    return _pdf_response(buffer, "celtm-skill-passport.pdf")


@app.get("/api/v1/admin/students/{target_user_id}/passport.pdf")
def admin_student_passport_pdf(
    target_user_id: str,
    admin: AdminUser = Depends(get_admin_user)
) -> Response:
    profile_row = db.query_one("SELECT * FROM profiles WHERE user_id = ?", (target_user_id,))
    if not profile_row:
        raise HTTPException(status_code=404, detail="Student not found.")

    if admin.role != "super_admin" and admin.institution_id != profile_row["institution_id"]:
        raise HTTPException(status_code=403, detail="Not authorized to access this student.")

    profile = row_to_profile(profile_row)
    snapshot = readiness_snapshot(target_user_id)
    buffer = _generate_passport_pdf_buffer(profile, snapshot)
    return _pdf_response(buffer, f"{target_user_id}-skill-passport.pdf")


@app.get("/api/v1/reports/me/dashboard.pdf")
def dashboard_pdf(user: CurrentUser = Depends(get_current_user)) -> Response:
    profile = ensure_profile(user)
    snapshot = readiness_snapshot(user.id)
    buffer = _generate_passport_pdf_buffer(profile, snapshot, title="CELTM Student Dashboard")
    return _pdf_response(buffer, "celtm-student-dashboard.pdf")


@app.get("/api/v1/reports/me/dashboard.csv")
def dashboard_csv(user: CurrentUser = Depends(get_current_user)) -> Response:
    ensure_profile(user)
    raise HTTPException(status_code=403, detail="CSV exports are available only from the admin console.")


@app.get("/api/v1/schedule/events")
def list_schedule_events(
    limit: int = Query(default=50, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    ensure_profile(user)
    rows = db.query_all(
        "SELECT * FROM schedule_events WHERE user_id = ? ORDER BY starts_at LIMIT ?",
        (user.id, limit),
    )
    return {
        "items": [
            {
                "id": row["id"],
                "title": row["title"],
                "starts_at": row["starts_at"],
                "ends_at": row["ends_at"],
                "event_type": row["event_type"],
                "metadata": from_json(row["metadata"], {}),
            }
            for row in rows
        ],
        "has_more": False,
        "next_cursor": None,
    }


@app.post("/api/v1/schedule/events")
def create_schedule_event(payload: SchedulePayload, user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    ensure_profile(user)
    event_id = new_id("event")
    db.execute(
        """
        INSERT INTO schedule_events (id, user_id, title, starts_at, ends_at, event_type, metadata, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (event_id, user.id, payload.title, payload.starts_at, payload.ends_at, payload.event_type, to_json(payload.metadata), now_iso()),
    )
    return list_schedule_events(user=user)["items"][0]


@app.patch("/api/v1/schedule/events/{event_id}")
def update_schedule_event(event_id: str, payload: SchedulePayload, user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    ensure_profile(user)
    db.execute(
        """
        UPDATE schedule_events SET title = ?, starts_at = ?, ends_at = ?, event_type = ?, metadata = ?
        WHERE id = ? AND user_id = ?
        """,
        (payload.title, payload.starts_at, payload.ends_at, payload.event_type, to_json(payload.metadata), event_id, user.id),
    )
    row = db.query_one("SELECT * FROM schedule_events WHERE id = ? AND user_id = ?", (event_id, user.id))
    if not row:
        raise HTTPException(status_code=404, detail="Schedule event not found")
    return {
        "id": row["id"],
        "title": row["title"],
        "starts_at": row["starts_at"],
        "ends_at": row["ends_at"],
        "event_type": row["event_type"],
        "metadata": from_json(row["metadata"], {}),
    }


@app.delete("/api/v1/schedule/events/{event_id}")
def delete_schedule_event(event_id: str, user: CurrentUser = Depends(get_current_user)) -> dict[str, str]:
    db.execute("DELETE FROM schedule_events WHERE id = ? AND user_id = ?", (event_id, user.id))
    return {"status": "deleted"}


def _role_profile_by_key(key: str | None) -> dict[str, Any]:
    return career_roles.profile_by_key(key)


def roadmap_phase_details(
    desired_role: str,
    role_fit_score: dict[str, Any],
    major_gaps: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    profile = _role_profile_by_key(role_fit_score.get("role_profile_key"))
    gap_names = [
        str(item.get("dimension"))
        for item in role_fit_score.get("required_dimension_gaps", [])
        if item.get("dimension")
    ]
    priority_gaps = [item for item in (major_gaps or []) if item] or gap_names[:3] or ["role foundation"]
    certificates = list(profile.get("certificates") or career_roles.DEFAULT_ROLE_PROFILE["certificates"])
    practice = list(profile.get("practice") or career_roles.DEFAULT_ROLE_PROFILE["practice"])
    role_label = desired_role.strip() or "the target role"
    return {
        "roadmap_30_days": {
            "title": "Foundation proof",
            "summary": f"Validate whether {role_label} is realistic from the current evidence and close the first visible gap.",
            "certificates": certificates[:2],
            "practice": [
                practice[0],
                f"Complete one assessment block for {priority_gaps[0]}",
                "Write a short reflection on mistakes and retake weak questions",
            ],
            "evidence": [
                "One verified certificate or lab completion",
                "One uploaded proof artifact mapped to the role",
                "Updated resume bullet showing measurable practice",
            ],
        },
        "roadmap_60_days": {
            "title": "Role-specific practice",
            "summary": f"Move from foundation work to practical tasks expected for {role_label}.",
            "certificates": certificates[1:] or certificates[:1],
            "practice": [
                practice[1] if len(practice) > 1 else practice[0],
                f"Mentor-reviewed practice in {priority_gaps[1] if len(priority_gaps) > 1 else priority_gaps[0]}",
                "Complete one written case and one objective assessment under timed conditions",
            ],
            "evidence": [
                "Before/after score comparison",
                "Mentor or department feedback note",
                "A portfolio artifact with role-specific outcome metrics",
            ],
        },
        "roadmap_90_days": {
            "title": "Selection readiness",
            "summary": f"Prepare for interviews, screening tests, or entry programs related to {role_label}.",
            "certificates": certificates,
            "practice": [
                practice[2] if len(practice) > 2 else practice[-1],
                "Mock interview or selection-test simulation",
                "Final gap retest with evidence upload",
            ],
            "evidence": [
                "Mock interview feedback",
                "Final resume and certificate set",
                "Short application plan for internships, training, or bridge courses",
            ],
        },
    }


def roadmap_from_phase_details(details: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    roadmap: dict[str, list[str]] = {}
    for phase_key, detail in details.items():
        items: list[str] = []
        summary = str(detail.get("summary") or "").strip()
        if summary:
            items.append(summary)
        for value in list(detail.get("practice") or [])[:2]:
            text = str(value or "").strip()
            if text and text not in items:
                items.append(text)
        for value in list(detail.get("evidence") or [])[:1]:
            text = str(value or "").strip()
            if text and text not in items:
                items.append(text)
        roadmap[phase_key] = items or ["Reassess after completing earlier steps."]
    return roadmap


def _list_or_default(value: Any, fallback: list[str]) -> list[str]:
    if isinstance(value, str):
        if value.strip():
            return [value.strip()]
    if isinstance(value, list):
        clean = [str(item) for item in value if str(item).strip()]
        if clean:
            return clean
    return fallback


async def build_aspiration_analysis(
    user_id: str,
    desired_role: str,
    resolution: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    desired_role = _canonical_career_role(desired_role) or desired_role
    snapshot = readiness_snapshot(user_id)
    role_fit_score = role_specific_readiness(desired_role, snapshot)
    analysis = await analyze_aspiration(
        settings,
        desired_role,
        role_fit_score["score"],
        role_fit_score.get("role_adjusted_domain_breakdown") or snapshot["domain_breakdown"],
        snapshot["resume"]["analysis"] if snapshot["resume"] else None,
    )
    if not isinstance(analysis, dict):
        analysis = {}

    derived_gaps = [
        str(item.get("dimension"))
        for item in role_fit_score.get("required_dimension_gaps", [])
        if item.get("dimension")
    ][:3]
    major_gaps = _list_or_default(analysis.get("major_gaps"), derived_gaps or ["Build role-specific evidence"])
    nested_analysis = analysis.get("analysis") if isinstance(analysis.get("analysis"), dict) else {}
    details = roadmap_phase_details(desired_role, role_fit_score, major_gaps)
    roadmap = roadmap_from_phase_details(details)
    analyzed_at = now_iso()
    analysis["current_readiness"] = role_fit_score["score"]
    analysis["major_gaps"] = major_gaps
    analysis["better_current_fit"] = adjacent_fits_for_role(role_fit_score, desired_role)
    analysis["roadmap"] = roadmap
    if not isinstance(analysis.get("infographics"), list) or not analysis["infographics"]:
        analysis["infographics"] = [
            {"label": "Role-fit score", "value": f"{round(role_fit_score['score'])}%", "helper": "Saved at analysis time"},
            {"label": "Role family", "value": role_fit_score.get("role_profile", "Custom role"), "helper": "Used for role weighting"},
            {"label": "Primary gap", "value": major_gaps[0], "helper": "Fix this first"},
        ]
    analysis["analysis"] = {
        **nested_analysis,
        "summary": nested_analysis.get("summary") or f"{desired_role} requires targeted proof, not only a general readiness score.",
        "role_specific_readiness": role_fit_score,
        "global_readiness_score": snapshot["readiness"],
        "analyzed_at": analyzed_at,
        "roadmap_details": details,
        "career_aim_resolution": resolution,
    }
    return role_fit_score, analysis


async def create_aspiration_for_role(user_id: str, desired_role: str) -> dict[str, Any]:
    role, resolution = await resolve_career_aim_for_user(user_id, desired_role)
    existing = db.query_one(
        """
        SELECT id FROM aspirations
        WHERE user_id = ? AND lower(desired_role) = lower(?)
        ORDER BY created_at DESC LIMIT 1
        """,
        (user_id, role),
    )
    if existing:
        return get_aspiration_by_id(existing["id"], user_id)
    role_fit_score, analysis = await build_aspiration_analysis(user_id, role, resolution)
    aspiration_id = new_id("asp")
    db.execute(
        """
        INSERT INTO aspirations (
            id, user_id, desired_role, current_readiness, major_gaps,
            better_current_fit, roadmap, infographics, analysis, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            aspiration_id,
            user_id,
            role,
            role_fit_score["score"],
            to_json(analysis.get("major_gaps", [])),
            to_json(analysis.get("better_current_fit", [])),
            to_json(analysis.get("roadmap", {})),
            to_json(analysis.get("infographics", [])),
            to_json(analysis.get("analysis", analysis)),
            now_iso(),
            now_iso(),
        ),
    )
    return get_aspiration_by_id(aspiration_id, user_id)


@app.get("/api/v1/career-roles")
def list_career_roles(user: CurrentUser = Depends(get_current_user)) -> list[dict[str, Any]]:
    ensure_profile(user)
    return career_role_options()


@app.post("/api/v1/career-roles/suggestions")
async def suggest_career_roles(payload: CareerRoleSuggestPayload, user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    ensure_profile(user)
    raw_role = career_roles.clean_role_label(payload.desired_role)
    if not raw_role:
        return {"input": "", "suggestions": []}
    suggestions = await suggest_career_aims(
        settings,
        raw_role,
        career_role_options(),
        career_aim_context_for_user(user.id),
        limit=payload.limit,
    )
    enriched: list[dict[str, Any]] = []
    for item in suggestions:
        role_label = str(item.get("value") or item.get("label") or "").strip()
        if not role_label:
            continue
        role_key, normalized_label, subjects = career_roles.subjects_for_role(role_label)
        enriched.append(
            {
                **item,
                "value": normalized_label,
                "label": normalized_label,
                "profile_key": str(item.get("profile_key") or role_key),
                "subjects": subjects,
            }
        )
    return {"input": raw_role, "suggestions": enriched[: payload.limit]}


@app.post("/api/v1/career-roles/resolve")
async def resolve_career_role(payload: CareerRoleResolvePayload, user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    ensure_profile(user)
    role, resolution = await resolve_career_aim_for_user(user.id, payload.desired_role)
    return {
        **resolution,
        "normalized_role": role,
        "subjects": career_roles.subjects_for_role(role)[2],
    }


@app.get("/api/v1/career-recommendations")
def career_recommendations(
    desired_role: str | None = Query(default=None),
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    ensure_profile(user)
    return build_career_recommendations(user.id, desired_role)


@app.post("/api/v1/career-recommendations/draft-personality")
def save_draft_personality(
    payload: CareerDraftPersonalityPayload,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    ensure_profile(user)
    draft = {
        "interests": payload.interests[:8],
        "strengths": payload.strengths[:8],
        "work_style": payload.work_style,
        "experience_level": payload.experience_level,
        "preferred_industries": payload.preferred_industries[:8],
        "notes": payload.notes,
        "updated_at": now_iso(),
    }
    profile_row = db.query_one("SELECT * FROM profiles WHERE user_id = ?", (user.id,))
    metadata = from_json(profile_row["metadata"], {})
    metadata["draft_personality"] = draft
    db.execute(
        "UPDATE profiles SET metadata = ?, updated_at = ? WHERE user_id = ?",
        (to_json(metadata), now_iso(), user.id),
    )
    return build_career_recommendations(user.id, None, draft)


@app.post("/api/v1/career-aspirations")
async def create_aspiration(payload: AspirationCreate, user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    ensure_profile(user)
    return await create_aspiration_for_role(user.id, payload.desired_role)


@app.post("/api/v1/career-aspirations/recommended")
async def create_recommended_aspirations(
    payload: RecommendedAspirationsCreate,
    user: CurrentUser = Depends(get_current_user),
) -> list[dict[str, Any]]:
    ensure_profile(user)
    roles: list[str] = []
    for role in payload.desired_roles:
        clean = str(role or "").strip()
        if clean and normalize_key(clean) not in {normalize_key(item) for item in roles}:
            roles.append(clean)
        if len(roles) >= 3:
            break
    if not roles:
        recommendations = build_career_recommendations(user.id)["recommendations"]
        roles = [str(item["role"]) for item in recommendations[:3]]
    created: list[dict[str, Any]] = []
    for role in roles:
        created.append(await create_aspiration_for_role(user.id, role))
    return created


@app.post("/api/v1/career-aspirations/{aspiration_id}/reanalyze")
async def reanalyze_aspiration(aspiration_id: str, user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    ensure_profile(user)
    row = db.query_one("SELECT * FROM aspirations WHERE id = ? AND user_id = ?", (aspiration_id, user.id))
    if not row:
        raise HTTPException(status_code=404, detail="Aspiration not found")
    role_fit_score, analysis = await build_aspiration_analysis(user.id, row["desired_role"])
    db.execute(
        """
        UPDATE aspirations
        SET current_readiness = ?, major_gaps = ?, better_current_fit = ?,
            roadmap = ?, infographics = ?, analysis = ?, updated_at = ?
        WHERE id = ? AND user_id = ?
        """,
        (
            role_fit_score["score"],
            to_json(analysis.get("major_gaps", [])),
            to_json(analysis.get("better_current_fit", [])),
            to_json(analysis.get("roadmap", {})),
            to_json(analysis.get("infographics", [])),
            to_json(analysis.get("analysis", analysis)),
            now_iso(),
            aspiration_id,
            user.id,
        ),
    )
    return get_aspiration_by_id(aspiration_id, user.id)


def get_aspiration_by_id(aspiration_id: str, user_id: str, snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    row = db.query_one("SELECT * FROM aspirations WHERE id = ? AND user_id = ?", (aspiration_id, user_id))
    if not row:
        raise HTTPException(status_code=404, detail="Aspiration not found")
    if snapshot is None:
        snapshot = readiness_snapshot(user_id)
    analysis = from_json(row["analysis"], {})
    analysis["latest_readiness_score"] = snapshot["readiness"]
    analysis["latest_domain_breakdown"] = snapshot["domain_breakdown"]
    latest_role_fit = role_specific_readiness(row["desired_role"], snapshot)
    analysis["latest_role_specific_readiness"] = latest_role_fit
    analysis.setdefault("role_specific_readiness", latest_role_fit)
    analysis.setdefault(
        "roadmap_details",
        roadmap_phase_details(row["desired_role"], analysis["role_specific_readiness"], from_json(row["major_gaps"], [])),
    )
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "desired_role": row["desired_role"],
        "current_readiness": row["current_readiness"],
        "major_gaps": from_json(row["major_gaps"], []),
        "better_current_fit": from_json(row["better_current_fit"], []),
        "roadmap": from_json(row["roadmap"], {}),
        "infographics": from_json(row["infographics"], []),
        "analysis": analysis,
        "created_at": row["created_at"],
        "updated_at": row.get("updated_at") or row["created_at"],
    }


@app.get("/api/v1/career-aspirations")
def list_aspirations(user: CurrentUser = Depends(get_current_user)) -> list[dict[str, Any]]:
    ensure_profile(user)
    rows = db.query_all(
        "SELECT id FROM aspirations WHERE user_id = ? ORDER BY created_at DESC",
        (user.id,),
    )
    snapshot = readiness_snapshot(user.id)
    return [get_aspiration_by_id(row["id"], user.id, snapshot=snapshot) for row in rows]


def ensure_super_admin_account() -> dict[str, Any] | None:
    email = settings.admin_user.strip().lower()
    if not email or not settings.admin_pass:
        return None
    row = db.query_one("SELECT * FROM admin_accounts WHERE lower(email) = lower(?)", (email,))
    if row:
        metadata = _admin_metadata(row)
        changed_metadata = False
        if "token_version" not in metadata:
            metadata["token_version"] = 0
            changed_metadata = True
        if settings.admin_mfa_secret and not metadata.get("mfa_secret"):
            metadata["mfa_secret"] = settings.admin_mfa_secret
            changed_metadata = True
        if row["role"] != "super_admin":
            db.execute(
                """
                UPDATE admin_accounts
                SET role = 'super_admin', institution_id = NULL, department_id = NULL,
                    metadata = ?, updated_at = ?
                WHERE id = ?
                """,
                (to_json(metadata), now_iso(), row["id"]),
            )
            row = db.query_one("SELECT * FROM admin_accounts WHERE id = ?", (row["id"],))
        elif changed_metadata:
            db.execute(
                "UPDATE admin_accounts SET metadata = ?, updated_at = ? WHERE id = ?",
                (to_json(metadata), now_iso(), row["id"]),
            )
            row = db.query_one("SELECT * FROM admin_accounts WHERE id = ?", (row["id"],))
        return row
    account_id = "super_admin"
    existing_id = db.query_one("SELECT id FROM admin_accounts WHERE id = ?", (account_id,))
    if existing_id:
        account_id = new_id("admin")
    timestamp = now_iso()
    db.execute(
        """
        INSERT INTO admin_accounts (
            id, email, password_hash, role, institution_id, department_id,
            name, created_by, created_at, updated_at, metadata
        )
        VALUES (?, ?, ?, 'super_admin', NULL, NULL, 'Super Admin', 'env-bootstrap', ?, ?, ?)
        """,
        (
            account_id,
            email,
            hash_password(settings.admin_pass),
            timestamp,
            timestamp,
            to_json(
                {
                    "source": "environment_bootstrap",
                    "token_version": INITIAL_ADMIN_TOKEN_VERSION,
                    **({"mfa_secret": settings.admin_mfa_secret} if settings.admin_mfa_secret else {}),
                }
            ),
        ),
    )
    return db.query_one("SELECT * FROM admin_accounts WHERE id = ?", (account_id,))


def admin_account_public(row: dict[str, Any]) -> dict[str, Any]:
    metadata = from_json(row.get("metadata"), {})
    if isinstance(metadata, dict):
        metadata = {key: value for key, value in metadata.items() if key not in {"mfa_secret"}}
        metadata["mfa_enabled"] = bool(from_json(row.get("metadata"), {}).get("mfa_secret") or settings.admin_mfa_secret)
    else:
        metadata = {}
    return {
        "id": row["id"],
        "email": row["email"],
        "role": row["role"],
        "institution_id": row.get("institution_id"),
        "department_id": row.get("department_id"),
        "name": row.get("name") or row["email"],
        "created_by": row.get("created_by"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "last_password_reset_at": row.get("last_password_reset_at"),
        "metadata": metadata,
    }


def create_admin_session(account: dict[str, Any]) -> dict[str, Any]:
    token = create_admin_token(
        settings,
        {
            "sub": account["id"],
            "email": account["email"],
            "role": account["role"],
            "institution_id": account.get("institution_id"),
            "department_id": account.get("department_id"),
            "token_version": _admin_token_version(account),
        },
    )
    return {"access_token": token, "token_type": AUTH_SCHEME_LABEL, "role": account["role"]}


def admin_mfa_status_payload(account: dict[str, Any], admin: AdminUser) -> dict[str, Any]:
    metadata = _admin_metadata(account)
    return {
        "enabled": bool(metadata.get("mfa_secret") or settings.admin_mfa_secret),
        "required": settings.admin_mfa_required,
        "pending_enrollment": bool(metadata.get("pending_mfa_secret")),
        "issuer": "CELTM",
        "account": admin.email,
    }


@app.post("/api/v1/admin/login")
def admin_login(payload: AdminLoginRequest, request: Request) -> dict[str, Any]:
    ensure_super_admin_account()
    email = (payload.email or payload.username or "").strip().lower()
    account = db.query_one("SELECT * FROM admin_accounts WHERE lower(email) = lower(?)", (email,))
    if account and verify_password(payload.password, account["password_hash"]):
        try:
            _verify_admin_mfa(account, payload.mfa_code)
        except HTTPException:
            record_audit_event(
                "admin_login_mfa_failed",
                actor_type="admin",
                actor_id=account["id"],
                actor_email=account["email"],
                request=request,
            )
            raise
        record_audit_event(
            "admin_login_success",
            actor_type="admin",
            actor_id=account["id"],
            actor_email=account["email"],
            request=request,
        )
        return create_admin_session(account)

    record_audit_event(
        "admin_login_failed",
        actor_type="admin",
        actor_email=email,
        request=request,
    )
    raise HTTPException(status_code=401, detail="Invalid admin credentials")


@app.get("/api/v1/admin/me")
def read_admin_me(admin: AdminUser = Depends(get_admin_user)) -> dict[str, Any]:
    account = db.query_one("SELECT * FROM admin_accounts WHERE id = ?", (admin.id,))
    metadata = _admin_metadata(account or {})
    return {
        "id": admin.id,
        "email": admin.email,
        "role": admin.role,
        "institution_id": admin.institution_id,
        "department_id": admin.department_id,
        "mfa_enabled": bool(metadata.get("mfa_secret") or settings.admin_mfa_secret),
        "mfa_required": settings.admin_mfa_required,
    }


@app.get("/api/v1/admin/mfa")
def read_admin_mfa(admin: AdminUser = Depends(get_admin_user)) -> dict[str, Any]:
    account = db.query_one("SELECT * FROM admin_accounts WHERE id = ?", (admin.id,))
    if not account:
        raise HTTPException(status_code=404, detail="Admin account not found")
    return admin_mfa_status_payload(account, admin)


@app.post("/api/v1/admin/mfa/enroll")
def enroll_admin_mfa(admin: AdminUser = Depends(get_admin_user)) -> dict[str, Any]:
    account = db.query_one("SELECT * FROM admin_accounts WHERE id = ?", (admin.id,))
    if not account:
        raise HTTPException(status_code=404, detail="Admin account not found")
    metadata = _admin_metadata(account)
    secret = generate_totp_secret()
    metadata["pending_mfa_secret"] = secret
    metadata["pending_mfa_created_at"] = now_iso()
    db.execute(
        "UPDATE admin_accounts SET metadata = ?, updated_at = ? WHERE id = ?",
        (to_json(metadata), now_iso(), admin.id),
    )
    record_audit_event(
        "admin_mfa_enrollment_started",
        actor_type="admin",
        actor_id=admin.id,
        actor_email=admin.email,
        resource_type="admin_account",
        resource_id=admin.id,
    )
    return {
        "secret": secret,
        "otpauth_url": totp_uri(secret, admin.email),
        "issuer": "CELTM",
        "account": admin.email,
    }


@app.post("/api/v1/admin/mfa/verify")
def verify_admin_mfa_enrollment(payload: AdminMfaVerify, admin: AdminUser = Depends(get_admin_user)) -> dict[str, Any]:
    account = db.query_one("SELECT * FROM admin_accounts WHERE id = ?", (admin.id,))
    if not account:
        raise HTTPException(status_code=404, detail="Admin account not found")
    metadata = _admin_metadata(account)
    secret = str(payload.secret or metadata.get("pending_mfa_secret") or "").strip()
    if not secret or not verify_totp_code(secret, payload.code):
        record_audit_event(
            "admin_mfa_enrollment_failed",
            actor_type="admin",
            actor_id=admin.id,
            actor_email=admin.email,
            resource_type="admin_account",
            resource_id=admin.id,
        )
        raise HTTPException(status_code=400, detail="Invalid MFA verification code")
    metadata["mfa_secret"] = secret
    metadata["mfa_enabled_at"] = now_iso()
    metadata.pop("pending_mfa_secret", None)
    metadata.pop("pending_mfa_created_at", None)
    db.execute(
        "UPDATE admin_accounts SET metadata = ?, updated_at = ? WHERE id = ?",
        (to_json(metadata), now_iso(), admin.id),
    )
    record_audit_event(
        "admin_mfa_enabled",
        actor_type="admin",
        actor_id=admin.id,
        actor_email=admin.email,
        resource_type="admin_account",
        resource_id=admin.id,
    )
    updated = db.query_one("SELECT * FROM admin_accounts WHERE id = ?", (admin.id,))
    return admin_mfa_status_payload(updated, admin)


@app.delete("/api/v1/admin/mfa")
def disable_admin_mfa(payload: AdminMfaDisable, admin: AdminUser = Depends(get_admin_user)) -> dict[str, Any]:
    account = db.query_one("SELECT * FROM admin_accounts WHERE id = ?", (admin.id,))
    if not account:
        raise HTTPException(status_code=404, detail="Admin account not found")
    metadata = _admin_metadata(account)
    secret = str(metadata.get("mfa_secret") or "").strip()
    if settings.admin_mfa_required and not secret:
        raise HTTPException(status_code=400, detail="Environment-required MFA cannot be disabled from the UI")
    if secret and not verify_totp_code(secret, payload.code):
        raise HTTPException(status_code=400, detail="Valid MFA code is required to disable MFA")
    metadata.pop("mfa_secret", None)
    metadata.pop("pending_mfa_secret", None)
    metadata["mfa_disabled_at"] = now_iso()
    db.execute(
        "UPDATE admin_accounts SET metadata = ?, updated_at = ? WHERE id = ?",
        (to_json(metadata), now_iso(), admin.id),
    )
    _bump_admin_token_version(admin.id)
    record_audit_event(
        "admin_mfa_disabled",
        actor_type="admin",
        actor_id=admin.id,
        actor_email=admin.email,
        resource_type="admin_account",
        resource_id=admin.id,
    )
    updated = db.query_one("SELECT * FROM admin_accounts WHERE id = ?", (admin.id,))
    return admin_mfa_status_payload(updated, admin)


@app.post("/api/v1/admin/change-password")
def change_admin_password(
    payload: AdminChangePassword,
    admin: AdminUser = Depends(get_admin_user),
) -> dict[str, Any]:
    row = db.query_one("SELECT * FROM admin_accounts WHERE id = ?", (admin.id,))
    if not row or not verify_password(payload.current_password, row["password_hash"]):
        raise HTTPException(status_code=400, detail="Incorrect current password")

    timestamp = now_iso()
    password_hash = hash_password(payload.new_password)

    db.execute(
        """
        UPDATE admin_accounts
        SET password_hash = ?, updated_at = ?, last_password_reset_at = ?
        WHERE id = ?
        """,
        (password_hash, timestamp, timestamp, admin.id),
    )
    if row["role"] == "institution_admin":
        db.execute(
            "UPDATE institution_admins SET password_hash = ? WHERE id = ?",
            (password_hash, admin.id),
        )
    _bump_admin_token_version(admin.id)
    record_audit_event(
        "admin_password_changed",
        actor_type="admin",
        actor_id=admin.id,
        actor_email=admin.email,
        resource_type="admin_account",
        resource_id=admin.id,
    )
    return {"message": "Password changed successfully"}


@app.get("/api/v1/admin/institutions")
def admin_institutions(admin: AdminUser = Depends(get_admin_user)) -> list[dict[str, Any]]:
    if admin.role == "institution_admin" and admin.institution_id:
        return [item for item in public_institutions() if item["id"] == admin.institution_id]
    return public_institutions()


@app.post("/api/v1/admin/institutions")
def create_institution(payload: InstitutionCreate, admin: AdminUser = Depends(get_admin_user)) -> dict[str, Any]:
    require_super_admin(admin)
    institution_id = new_id("inst")
    db.execute(
        "INSERT INTO institutions (id, name, domain, created_at) VALUES (?, ?, ?, ?)",
        (institution_id, payload.name, payload.domain, now_iso()),
    )
    record_audit_event(
        "institution_created",
        actor_type="admin",
        actor_id=admin.id,
        actor_email=admin.email,
        resource_type="institution",
        resource_id=institution_id,
        metadata={"name": payload.name},
    )
    return db.query_one("SELECT * FROM institutions WHERE id = ?", (institution_id,))


@app.post("/api/v1/admin/departments")
def create_department(payload: DepartmentCreate, admin: AdminUser = Depends(get_admin_user)) -> dict[str, Any]:
    require_super_admin(admin)
    department_id = new_id("dept")
    db.execute(
        """
        INSERT INTO departments (id, institution_id, name, head_name, head_email, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (department_id, payload.institution_id, payload.name, payload.head_name, payload.head_email, now_iso()),
    )
    record_audit_event(
        "department_created",
        actor_type="admin",
        actor_id=admin.id,
        actor_email=admin.email,
        resource_type="department",
        resource_id=department_id,
        metadata={"institution_id": payload.institution_id, "name": payload.name},
    )
    return db.query_one("SELECT * FROM departments WHERE id = ?", (department_id,))


@app.post("/api/v1/admin/heads")
def create_head(payload: HeadCreate, admin: AdminUser = Depends(get_admin_user)) -> dict[str, Any]:
    require_super_admin(admin)
    existing = db.query_one("SELECT id FROM admin_accounts WHERE lower(email) = lower(?)", (payload.email.lower(),))
    legacy_existing = db.query_one("SELECT id FROM institution_admins WHERE lower(email) = lower(?)", (payload.email.lower(),))
    if existing or legacy_existing:
        raise HTTPException(status_code=409, detail="An admin account with this email already exists")
    head_id = new_id("head")
    timestamp = now_iso()
    password_hash = hash_password(payload.password)
    db.execute(
        """
        INSERT INTO institution_admins (
            id, institution_id, department_id, name, email, password_hash, created_by, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            head_id,
            payload.institution_id,
            payload.department_id,
            payload.name,
            payload.email.lower(),
            password_hash,
            admin.email,
            timestamp,
        ),
    )
    db.execute(
        """
        INSERT INTO admin_accounts (
            id, email, password_hash, role, institution_id, department_id,
            name, created_by, created_at, updated_at, metadata
        )
        VALUES (?, ?, ?, 'institution_admin', ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            head_id,
            payload.email.lower(),
            password_hash,
            payload.institution_id,
            payload.department_id,
            payload.name,
            admin.email,
            timestamp,
            timestamp,
            to_json(
                {
                    "source": "super_admin_create_head",
                    "token_version": INITIAL_ADMIN_TOKEN_VERSION,
                    **({"mfa_secret": payload.mfa_secret} if payload.mfa_secret else {}),
                }
            ),
        ),
    )
    record_audit_event(
        "admin_head_created",
        actor_type="admin",
        actor_id=admin.id,
        actor_email=admin.email,
        resource_type="admin_account",
        resource_id=head_id,
        metadata={"email": payload.email.lower(), "institution_id": payload.institution_id, "department_id": payload.department_id},
    )
    return {
        "id": head_id,
        "institution_id": payload.institution_id,
        "department_id": payload.department_id,
        "name": payload.name,
        "email": payload.email.lower(),
        "created_at": timestamp,
    }


@app.get("/api/v1/admin/admin-accounts")
def list_admin_accounts(admin: AdminUser = Depends(get_admin_user)) -> list[dict[str, Any]]:
    require_super_admin(admin)
    rows = db.query_all("SELECT * FROM admin_accounts ORDER BY role DESC, created_at DESC")
    return [admin_account_public(row) for row in rows]


@app.post("/api/v1/admin/admin-accounts/{account_id}/reset-password")
def reset_admin_password(
    account_id: str,
    payload: AdminPasswordReset,
    admin: AdminUser = Depends(get_admin_user),
) -> dict[str, Any]:
    require_super_admin(admin)
    account = db.query_one("SELECT * FROM admin_accounts WHERE id = ?", (account_id,))
    if not account:
        raise HTTPException(status_code=404, detail="Admin account not found")
    timestamp = now_iso()
    password_hash = hash_password(payload.password)
    db.execute(
        """
        UPDATE admin_accounts
        SET password_hash = ?, updated_at = ?, last_password_reset_at = ?
        WHERE id = ?
        """,
        (password_hash, timestamp, timestamp, account_id),
    )
    if account["role"] == "institution_admin":
        db.execute(
            "UPDATE institution_admins SET password_hash = ? WHERE id = ?",
            (password_hash, account_id),
        )
    _bump_admin_token_version(account_id)
    record_audit_event(
        "admin_password_reset",
        actor_type="admin",
        actor_id=admin.id,
        actor_email=admin.email,
        resource_type="admin_account",
        resource_id=account_id,
    )
    updated = db.query_one("SELECT * FROM admin_accounts WHERE id = ?", (account_id,))
    return admin_account_public(updated)


@app.get("/api/v1/admin/students")
def admin_students(
    search: str = "",
    admin: AdminUser = Depends(get_admin_user),
) -> list[dict[str, Any]]:
    params: list[Any] = []
    where = []
    if admin.role == "institution_admin" and admin.institution_id:
        where.append("institution_id = ?")
        params.append(admin.institution_id)
        if admin.department_id:
            where.append("department_id = ?")
            params.append(admin.department_id)
    if search:
        where.append("(lower(email) LIKE ? OR lower(full_name) LIKE ?)")
        needle = f"%{search.lower()}%"
        params.extend([needle, needle])
    sql = "SELECT user_id FROM profiles"
    if where:
        sql += " WHERE " + " AND ".join(where)
    rows = db.query_all(sql, tuple(params))
    cards = [progress_card(row["user_id"]) for row in rows]
    return sorted(cards, key=lambda item: item["readiness_score"], reverse=True)


@app.get("/api/v1/admin/students/export.csv")
def admin_students_export_csv(
    search: str = "",
    admin: AdminUser = Depends(get_admin_user)
) -> Response:
    cards = admin_students(search=search, admin=admin)
    record_audit_event(
        "admin_students_export_csv",
        actor_type="admin",
        actor_id=admin.id,
        actor_email=admin.email,
        resource_type="student_export",
        metadata={"search": search, "count": len(cards)},
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)

    writer.writerow(["CELTM Admin Students Export"])
    writer.writerow(["Generated by", admin.email, "Role", admin.role])
    writer.writerow([])

    writer.writerow([
        "Name",
        "Email",
        "Institution",
        "Department",
        "Focus Role",
        "Readiness Score",
        "Resume Score",
        "Assessment Score",
        "Written Score",
        "Credential Score",
        "Strong Points",
        "Weak Points",
        "Institute Help",
    ])

    for card in cards:
        writer.writerow([
            card.get("name", ""),
            card.get("email", ""),
            card.get("institution_name", ""),
            card.get("department_name", ""),
            card.get("target_role", ""),
            f"{card.get('readiness_score', 0)}%",
            "" if card.get("resume_score") is None else f"{card.get('resume_score')}%",
            "" if card.get("assessment_score") is None else f"{card.get('assessment_score')}%",
            "" if card.get("written_score") is None else f"{card.get('written_score')}%",
            "" if card.get("credential_score") is None else f"{card.get('credential_score')}%",
            "; ".join(str(item) for item in card.get("strong_points", [])),
            "; ".join(str(item) for item in card.get("weak_points", [])),
            "; ".join(str(item) for item in card.get("institute_help", [])),
        ])

    buffer.seek(0)
    return Response(
        buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="celtm-admin-students-report.csv"'},
    )


@app.get("/api/v1/admin/students/export.pdf")
def admin_students_export_pdf(
    search: str = "",
    admin: AdminUser = Depends(get_admin_user)
) -> Response:
    cards = admin_students(search=search, admin=admin)
    record_audit_event(
        "admin_students_export_pdf",
        actor_type="admin",
        actor_id=admin.id,
        actor_email=admin.email,
        resource_type="student_export",
        metadata={"search": search, "count": len(cards)},
    )
    buffer = _generate_admin_students_report_pdf(cards, admin)
    return _pdf_response(buffer, "celtm-admin-students-report.pdf")


@app.get("/api/v1/admin/students/{user_id}")
def admin_student_detail(user_id: str, admin: AdminUser = Depends(get_admin_user)) -> dict[str, Any]:
    profile = db.query_one("SELECT * FROM profiles WHERE user_id = ?", (user_id,))
    if not profile:
        raise HTTPException(status_code=404, detail="Student not found")
    if admin.role == "institution_admin" and profile["institution_id"] != admin.institution_id:
        raise HTTPException(status_code=403, detail="Student is outside your institution")
    record_audit_event(
        "admin_student_detail_viewed",
        actor_type="admin",
        actor_id=admin.id,
        actor_email=admin.email,
        resource_type="student_profile",
        resource_id=user_id,
    )
    return progress_card(user_id, include_subject_progress=True) | {
        "skills": skill_rows(user_id),
        "gaps": gap_rows(user_id),
        "aspirations": [get_aspiration_by_id(row["id"], user_id) for row in db.query_all("SELECT id FROM aspirations WHERE user_id = ? ORDER BY created_at DESC", (user_id,))],
    }


@app.get("/api/v1/admin/questions/sample.csv")
def admin_question_csv_template(admin: AdminUser = Depends(get_admin_user)) -> Response:
    require_super_admin(admin)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=QUESTION_CSV_HEADERS)
    writer.writeheader()
    writer.writerow(
        {
            "category": "AI Readiness",
            "difficulty": "easy",
            "question_type": "mcq",
            "question_text": "Which action best reduces hallucination risk in an AI workflow?",
            "scenario": "",
            "option_a": "Validate answers against trusted evidence before use",
            "option_b": "Use the longest generated answer",
            "option_c": "Avoid logging model outputs",
            "option_d": "Skip review when the answer sounds confident",
            "correct_answer": "A",
            "explanation": "Evidence checks keep the workflow deterministic and auditable.",
            "sample_answer": "",
        }
    )
    writer.writerow(
        {
            "category": "Problem Solving",
            "difficulty": "medium",
            "question_type": "situational",
            "question_text": "What is the strongest first response?",
            "scenario": "A team has a failing release and conflicting stakeholder requests.",
            "option_a": "List constraints, isolate the blocker, and agree on a measurable next step",
            "option_b": "Rewrite the entire plan immediately",
            "option_c": "Wait until every stakeholder agrees",
            "option_d": "Ignore the failing release until the next sprint",
            "correct_answer": "A",
            "explanation": "The best response narrows ambiguity and creates evidence quickly.",
            "sample_answer": "",
        }
    )
    writer.writerow(
        {
            "category": "Communication",
            "difficulty": "hard",
            "question_type": "descriptive",
            "question_text": "Write a stakeholder-ready explanation of an AI system failure, including evidence, risk, and remediation.",
            "scenario": "",
            "option_a": "",
            "option_b": "",
            "option_c": "",
            "option_d": "",
            "correct_answer": "",
            "explanation": "",
            "sample_answer": "A strong answer names the failure, explains evidence, states impact, and gives a remediation plan.",
        }
    )
    return Response(
        buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="celtm-question-template.csv"'},
    )


@app.post("/api/v1/admin/ingest-csv")
async def admin_ingest_questions_csv(
    file: UploadFile = File(...),
    assign_test: bool = Form(False),
    department_id: str | None = Form(None),
    test_title: str | None = Form(None),
    starts_at: str | None = Form(None),
    ends_at: str | None = Form(None),
    duration_minutes: int = Form(30),
    mode: str = Form("quick"),
    instructions: str | None = Form(None),
    admin: AdminUser = Depends(get_admin_user),
) -> dict[str, Any]:
    require_super_admin(admin)
    content = await read_validated_upload(file, "csv")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded") from exc

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV header row is required")
    rows = [row for row in reader if any(str(value or "").strip() for value in row.values())]

    inserted = 0
    inserted_ids: list[str] = []
    inserted_payloads: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for row_number, row in enumerate(rows, start=2):
        try:
            payload = _csv_question_payload(row)
            question_row = add_question_to_supabase(settings, payload)
            question_id = str(question_row.get("id") or "").strip()
            if question_id:
                inserted_ids.append(question_id)
            inserted_payloads.append(payload)
            inserted += 1
        except Exception as exc:
            errors.append({"row": row_number, "error": str(exc)})

    status = get_question_bank_status() if inserted else get_question_bank_status()
    question_set = None
    if inserted_ids:
        first_row = rows[0] if rows else {}
        type_counts = Counter(payload["question_type"] for payload in inserted_payloads)
        category_counts = Counter(payload["dimension"] for payload in inserted_payloads)
        set_title = _row_value(first_row, "set_title", "question_set", "set_name") or Path(file.filename or "questions.csv").stem
        dominant_category = category_counts.most_common(1)[0][0] if category_counts else "Imported questions"
        set_type = type_counts.most_common(1)[0][0] if len(type_counts) == 1 else "MIXED"
        question_set = _create_question_set(
            title=set_title,
            source="csv",
            category=dominant_category,
            question_type=set_type,
            question_ids=inserted_ids,
            admin=admin,
            metadata={
                "filename": file.filename,
                "type_counts": dict(type_counts),
                "category_counts": dict(category_counts),
                "errors": errors[:20],
            },
        )

    assignment = None
    assignment_error = None
    should_assign = assign_test or any(_truthy(_row_value(row, "assign_test", "assign")) for row in rows)
    if should_assign and question_set:
        first_row = rows[0] if rows else {}
        csv_starts_at = starts_at or _row_value(first_row, "starts_at", "date_time", "datetime")
        if not csv_starts_at:
            date_value = _row_value(first_row, "date", "test_date")
            time_value = _row_value(first_row, "time", "test_time")
            if date_value and time_value:
                csv_starts_at = f"{date_value}T{time_value}"
        csv_duration = _row_value(first_row, "duration_minutes", "duration")
        csv_ends_at = ends_at or _row_value(first_row, "ends_at", "end_time", "end_datetime")
        if not csv_ends_at:
            end_date_value = _row_value(first_row, "end_date", "test_end_date")
            end_time_value = _row_value(first_row, "end_time", "test_end_time")
            if end_date_value and end_time_value:
                csv_ends_at = f"{end_date_value}T{end_time_value}"
        try:
            assignment = admin_create_assessment_assignment(
                AssessmentAssignmentCreate(
                    title=test_title or _row_value(first_row, "test_title", "assignment_title") or question_set["title"],
                    department_id=department_id or _row_value(first_row, "department_id", "department"),
                    category=question_set["category"],
                    question_type="MIXED" if question_set["question_type"] == "MIXED" else question_set["question_type"],
                    mode=mode or _row_value(first_row, "mode") or "quick",
                    starts_at=csv_starts_at,
                    ends_at=csv_ends_at,
                    duration_minutes=int(csv_duration or duration_minutes or 30),
                    instructions=instructions or _row_value(first_row, "instructions"),
                    question_set_id=question_set["id"],
                ),
                admin=admin,
            )
        except Exception as exc:
            assignment_error = exc.detail if isinstance(exc, HTTPException) else str(exc)

    record_audit_event(
        "admin_questions_csv_ingested",
        actor_type="admin",
        actor_id=admin.id,
        actor_email=admin.email,
        resource_type="question_csv",
        resource_id=question_set["id"] if question_set else None,
        metadata={
            "filename": file.filename,
            "inserted": inserted,
            "error_count": len(errors),
            "assignment_id": assignment.get("id") if isinstance(assignment, dict) else None,
        },
    )
    return {
        "status": "ok",
        "inserted": inserted,
        "errors": errors[:20],
        "question_bank": status,
        "question_set": question_set,
        "assignment": assignment,
        "assignment_error": assignment_error,
        "admin": admin.email,
    }


@app.post("/api/v1/admin/sync-celtmind")
@app.post("/api/v1/admin/questions/sync")
def admin_sync_question_bank(admin: AdminUser = Depends(get_admin_user)) -> dict[str, Any]:
    require_super_admin(admin)
    return get_question_bank_status() | {"admin": admin.email}

class CreateCoursePayload(BaseModel):
    title: str
    description: str = ""
    institution_id: str | None = None

class CreateQuestionPayload(BaseModel):
    dimension: str
    difficulty: str
    question_type: str
    scenario: str | None = None
    question_text: str
    options: list[str]
    correct_answer: str
    explanation: str | None = None


class AssessmentAssignmentCreate(BaseModel):
    title: str
    department_id: str
    category: str = "Communication"
    question_type: str = "MCQ"
    assessment_type: str = "capability"
    mode: str = "quick"
    starts_at: str
    ends_at: str | None = None
    duration_minutes: int = Field(default=30, ge=5, le=240)
    instructions: str | None = None
    question_set_id: str | None = None
    question_ids: list[str] = Field(default_factory=list)


class AssessmentAssignmentTerminate(BaseModel):
    reason: str | None = None


@app.post("/api/v1/admin/courses")
def admin_create_course(payload: CreateCoursePayload, admin: AdminUser = Depends(get_admin_user)) -> dict[str, Any]:
    if admin.role != "super_admin" and admin.institution_id != payload.institution_id:
        raise HTTPException(status_code=403, detail="Cannot create course outside your institution")

    course_id = new_id("crs")
    db.execute(
        "INSERT INTO courses (id, title, description, institution_id, created_at) VALUES (?, ?, ?, ?, ?)",
        (course_id, payload.title, payload.description, payload.institution_id, now_iso())
    )
    return {"status": "ok", "id": course_id}

@app.post("/api/v1/admin/questions")
def admin_create_question(payload: CreateQuestionPayload, admin: AdminUser = Depends(get_admin_user)) -> dict[str, Any]:
    require_super_admin(admin)
    try:
        row = add_question_to_supabase(settings, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not write question to Supabase: {exc}") from exc
    status = get_question_bank_status()
    question_id = str(row.get("id") or "").strip()
    question_set = None
    if question_id:
        question_set = _create_question_set(
            title=f"Single question: {payload.question_text[:60]}",
            source="manual",
            category=payload.dimension,
            question_type=payload.question_type,
            question_ids=[question_id],
            admin=admin,
            metadata={"type_counts": {payload.question_type.upper(): 1}},
        )
    return {
        "status": "ok",
        "id": row.get("id"),
        "source": "supabase",
        "question_bank": status,
        "question_set": question_set,
        "admin": admin.email,
    }


@app.get("/api/v1/admin/question-sets")
def admin_question_sets(admin: AdminUser = Depends(get_admin_user)) -> list[dict[str, Any]]:
    rows = db.query_all("SELECT * FROM question_sets ORDER BY created_at DESC LIMIT 100")
    return [_question_set_row(row) for row in rows]


@app.get("/api/v1/admin/assessment-assignments")
def admin_list_assessment_assignments(admin: AdminUser = Depends(get_admin_user)) -> list[dict[str, Any]]:
    params: list[Any] = []
    where = []
    if admin.role == "institution_admin" and admin.institution_id:
        where.append("institution_id = ?")
        params.append(admin.institution_id)
    sql = "SELECT * FROM assessment_assignments"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY starts_at DESC"
    return [assignment_row(row) for row in db.query_all(sql, tuple(params))]


@app.post("/api/v1/admin/assessment-assignments")
def admin_create_assessment_assignment(
    payload: AssessmentAssignmentCreate,
    admin: AdminUser = Depends(get_admin_user),
) -> dict[str, Any]:
    live_question_rows = _live_question_rows_or_503()
    department = _validate_admin_department(admin, payload.department_id)
    qtype = payload.question_type.upper()
    if qtype not in {"MCQ", "SITUATIONAL", "MIXED", "DESCRIPTIVE"}:
        raise HTTPException(status_code=400, detail="Assigned tests support MCQ, SITUATIONAL, MIXED, or DESCRIPTIVE question types")

    question_set = _load_question_set(payload.question_set_id, admin) if payload.question_set_id else None
    requested_question_ids = payload.question_ids
    if question_set:
        requested_question_ids = [str(item) for item in question_set["question_ids"]]

    assignment_metadata: dict[str, Any] = {}
    fixed_question_ids: list[str] = []
    if requested_question_ids:
        fixed_question_ids, validation = _assignment_question_ids(requested_question_ids, qtype, live_question_rows)
        assignment_metadata["fixed_question_validation"] = validation
        if question_set:
            assignment_metadata["question_set_title"] = question_set["title"]
        if not fixed_question_ids:
            raise HTTPException(status_code=404, detail="No usable Supabase questions are available for this fixed assignment")
        fixed_id_set = set(fixed_question_ids)
        dimension_rows = [row for row in live_question_rows if row.get("id") in fixed_id_set]
        assignment_category = (
            question_set["category"]
            if question_set
            else (_subject_name_from_question(dimension_rows[0]) if dimension_rows else payload.category)
        )
    else:
        field, value = _category_match_field(payload.category, live_question_rows)
        if qtype == "MIXED":
            available_count = sum(
                1
                for row in live_question_rows
                if _question_matches_category(row, field, value)
                and row.get("question_type") in {"MCQ", "SITUATIONAL"}
                and str(row.get("options") or "[]") != "[]"
            )
        else:
            available_count = sum(
                1
                for row in live_question_rows
                if _question_matches_category(row, field, value)
                and row.get("question_type") == qtype
                and (qtype == "DESCRIPTIVE" or str(row.get("options") or "[]") != "[]")
            )
        if available_count == 0:
            raise HTTPException(status_code=404, detail="No Supabase questions are available for this assignment")
        assignment_category = value or payload.category

    starts_dt = _parse_datetime(payload.starts_at)
    if payload.ends_at:
        ends_dt = _parse_datetime(payload.ends_at)
        if ends_dt <= starts_dt:
            raise HTTPException(status_code=400, detail="ends_at must be after starts_at")
        duration_minutes = max(1, int((ends_dt - starts_dt).total_seconds() // 60))
    else:
        duration_minutes = payload.duration_minutes
        ends_dt = starts_dt + timedelta(minutes=duration_minutes)
    starts_at = starts_dt.isoformat()
    ends_at = ends_dt.isoformat()
    assignment_id = new_id("assign")
    db.execute(
        """
        INSERT INTO assessment_assignments (
            id, institution_id, department_id, title, category, assessment_type,
            question_type, question_set_id, question_ids, mode, starts_at, ends_at, duration_minutes,
            instructions, status, created_by_admin_id, created_by_email, metadata, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?)
        """,
        (
            assignment_id,
            department["institution_id"],
            payload.department_id,
            payload.title,
            assignment_category,
            payload.assessment_type,
            qtype,
            question_set["id"] if question_set else payload.question_set_id,
            to_json(fixed_question_ids),
            payload.mode,
            starts_at,
            ends_at,
            duration_minutes,
            payload.instructions,
            admin.id,
            admin.email,
            to_json(assignment_metadata),
            now_iso(),
        ),
    )
    return assignment_row(db.query_one("SELECT * FROM assessment_assignments WHERE id = ?", (assignment_id,)))


@app.post("/api/v1/admin/assessment-assignments/{assignment_id}/terminate")
def admin_terminate_assessment_assignment(
    assignment_id: str,
    payload: AssessmentAssignmentTerminate | None = None,
    admin: AdminUser = Depends(get_admin_user),
) -> dict[str, Any]:
    row = db.query_one("SELECT * FROM assessment_assignments WHERE id = ?", (assignment_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Assignment not found")
    _validate_admin_department(admin, row["department_id"])
    if row["status"] == "terminated":
        return assignment_row(row)
    metadata = from_json(row.get("metadata"), {})
    metadata["termination"] = {
        "reason": payload.reason if payload else None,
        "terminated_by": admin.email,
        "terminated_at": now_iso(),
    }
    terminated_at = metadata["termination"]["terminated_at"]
    db.execute(
        """
        UPDATE assessment_assignments
        SET status = 'terminated',
            terminated_at = ?,
            terminated_by_admin_id = ?,
            terminated_by_email = ?,
            metadata = ?
        WHERE id = ?
        """,
        (terminated_at, admin.id, admin.email, to_json(metadata), assignment_id),
    )
    db.execute(
        "UPDATE assessments SET status = 'terminated' WHERE assignment_id = ? AND status != 'completed'",
        (assignment_id,),
    )
    db.execute(
        "UPDATE written_assessments SET status = 'terminated', updated_at = ? WHERE assignment_id = ? AND status != 'completed'",
        (terminated_at, assignment_id),
    )
    return assignment_row(db.query_one("SELECT * FROM assessment_assignments WHERE id = ?", (assignment_id,)))


@app.post("/api/v1/chat")
async def chat_endpoint(payload: ChatRequest, user: CurrentUser = Depends(get_current_user)) -> dict[str, str]:
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")
    normalized_message = message.lower()

    # Rule based first
    if "where" in normalized_message and ("stats" in normalized_message or "analytics" in normalized_message):
        return {"response": "Your stats and exam analytics are available on your Dashboard. Look for the 'Exam Analytics History' section at the bottom."}
    if "resume" in normalized_message and "analyz" in normalized_message:
        return {"response": "Your resume is analyzed against the target role you provide, checking for keyword presence, score breakdown across dimensions, and identifying any recruiter-visible red flags."}
    if "how" in normalized_message and "assessment" in normalized_message:
        return {"response": "Navigate to the 'Assessments' page from the sidebar to take rule-based assessments and raise your readiness score."}
    if "career aim" in normalized_message:
        return {"response": "Career Aim helps you compare your current skills against your desired role to highlight major gaps and suggest a roadmap."}

    profile = ensure_profile(user)
    snapshot = readiness_snapshot(user.id)
    recent_history = [
        f"{item.get('role', 'user')}: {item.get('content', '')[:400]}"
        for item in payload.history[-8:]
        if isinstance(item, dict) and item.get("content")
    ]
    system_prompt = (
        "You are the CELTM platform assistant. You are a helpful, professional AI that helps users navigate their learning, resume analysis, "
        "and skill assessments. Keep your answers concise, practical, and directly address the user's question without making up unsupported features. "
        "Use the supplied user context only as context; never expose private implementation details."
    )
    user_prompt = (
        f"User: {profile.get('full_name') or user.email}\n"
        f"Target role: {profile.get('focus_role') or 'not set'}\n"
        f"Readiness: {snapshot.get('readiness', 0)}\n"
        f"Recent conversation:\n" + "\n".join(recent_history[-8:]) + "\n\n"
        f"Current question: {message}"
    )

    response = await call_ai_text(settings, system_prompt, user_prompt)
    if not response:
        return {"response": "The AI service is not responding in this environment. I can still answer common CELTM navigation questions from the quick prompts below."}

    return {"response": response.strip()}
