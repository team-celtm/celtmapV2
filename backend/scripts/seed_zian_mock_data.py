from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config.settings import get_settings
from app.integrations.supabase import get_supabase_client
from app.repositories.assessment_repository import AssessmentRepository
from app.repositories.skill_repository import SkillRepository
from app.utils.text import normalize_name

SEED_TAG = "zian-mock-seed-v1"
DEFAULT_EMAIL = "zian.surani@gmail.com"
FOCUS_ROLE = "ML Engineer"
SKILL_REQUEST_NAME = "Python Fundamentals for ML"
SKILL_REQUEST_ID = "python-fundamentals-for-ml"

ROLE_SKILLS: list[tuple[str, float, float | None, float | None, float | None]] = [
    ("Programming - Variables and Data Types", 88.0, 86.0, 90.0, 87.0),
    ("Programming - Control Flow", 84.0, 83.0, 85.0, 80.0),
    ("Programming - Functions and Scope", 79.0, 78.0, 81.0, 76.0),
    ("Programming - Arrays Basics", 76.0, 74.0, 79.0, 73.0),
    ("Programming - Pseudocode Logic", 82.0, 80.0, 84.0, None),
    ("Data Structures - Arrays", 71.0, 70.0, 73.0, None),
    ("Machine Learning", 74.0, 72.0, 75.0, 78.0),
    ("Artificial Intelligence", 72.0, None, 74.0, 73.0),
    ("Cloud Computing", 61.0, None, 64.0, 58.0),
    ("ML Systems", 58.0, None, 61.0, 55.0),
    ("Optimization", 66.0, None, 68.0, 63.0),
    ("Deployment", 49.0, 45.0, 52.0, 47.0),
    ("Engineering Rigor", 64.0, None, 68.0, 60.0),
]

HIDDEN_SKILLS: list[dict[str, Any]] = [
    {
        "skill_name": "Research Synthesis",
        "confidence_score": 0.82,
        "source": "interview",
        "evidence": "Connected math, code, and model-evaluation ideas into one practical study plan.",
        "status": "pending",
    },
    {
        "skill_name": "Stakeholder Communication",
        "confidence_score": 0.68,
        "source": "artifact_review",
        "evidence": "Explained project tradeoffs and business impact in plain language inside uploaded evidence.",
        "status": "approved",
    },
]

ARTIFACTS: list[dict[str, Any]] = [
    {
        "bucket_name": "career-artifacts",
        "storage_path": "mock/resume-zian.pdf",
        "file_name": "Zian-ML-Resume.pdf",
        "file_type": "resume",
        "extracted_text": "Resume covering Python, data cleaning, model training, deployment notes, and project outcomes.",
    },
    {
        "bucket_name": "career-artifacts",
        "storage_path": "mock/ml-project-brief.pdf",
        "file_name": "Zian-CropYield-Pipeline.pdf",
        "file_type": "project",
        "extracted_text": "End-to-end ML pipeline brief with preprocessing, feature engineering, evaluation, and monitoring notes.",
    },
    {
        "bucket_name": "career-artifacts",
        "storage_path": "mock/python-certificate.pdf",
        "file_name": "Zian-Python-Certificate.pdf",
        "file_type": "certificate",
        "extracted_text": "Certificate of completion for Python foundations and applied data workflows.",
    },
]

REQUEST_MCQS: list[dict[str, Any]] = [
    {
        "question_text": "Which Python data type is best suited for storing an ordered, mutable collection of feature values?",
        "difficulty": "easy",
        "options": [
            ("A", "tuple", False),
            ("B", "list", True),
            ("C", "set", False),
            ("D", "str", False),
        ],
    },
    {
        "question_text": "What is the most reliable way to avoid data leakage when preparing train and test datasets?",
        "difficulty": "medium",
        "options": [
            ("A", "Fit preprocessing on all rows before splitting", False),
            ("B", "Split first, then fit preprocessing on the training set only", True),
            ("C", "Use only the test set for scaling", False),
            ("D", "Shuffle labels after preprocessing", False),
        ],
    },
    {
        "question_text": "Why are functions useful in a machine-learning codebase?",
        "difficulty": "easy",
        "options": [
            ("A", "They make code shorter by removing variables", False),
            ("B", "They improve reuse, testing, and readability", True),
            ("C", "They guarantee better model accuracy", False),
            ("D", "They replace the need for debugging", False),
        ],
    },
    {
        "question_text": "You need to iterate over rows in a dataset and compute a derived value. Which Python control-flow concept is most directly involved?",
        "difficulty": "easy",
        "options": [
            ("A", "looping", True),
            ("B", "inheritance", False),
            ("C", "serialization", False),
            ("D", "compilation", False),
        ],
    },
    {
        "question_text": "Which practice most improves debugging quality in an ML experiment script?",
        "difficulty": "medium",
        "options": [
            ("A", "Changing several parameters at once", False),
            ("B", "Logging intermediate shapes, metrics, and assumptions", True),
            ("C", "Skipping validation runs", False),
            ("D", "Hardcoding every path in the script", False),
        ],
    },
]

REQUEST_WRITTEN = {
    "question_text": (
        "You are given a small Python-based ML training pipeline with missing values, "
        "inconsistent feature names, and no validation split. Describe how you would "
        "structure the code, prevent leakage, validate the model, and communicate tradeoffs."
    ),
    "difficulty": "medium",
    "sample_answer": (
        "A strong answer should separate ingestion, cleaning, splitting, transformation, "
        "training, and evaluation into clear functions, fit preprocessing only on training "
        "data, and describe verification metrics plus deployment-safe logging."
    ),
    "expected_concepts": [
        "train test split",
        "fit preprocessing on training data only",
        "functions and modular code",
        "validation metrics",
        "logging and reproducibility",
    ],
}


async def _run(operation):
    return await asyncio.to_thread(operation)


async def _upsert_rows(client, table: str, payload: dict[str, Any] | list[dict[str, Any]], *, on_conflict: str):
    def operation():
        return client.table(table).upsert(payload, on_conflict=on_conflict).execute().data or []

    return await _run(operation)


async def _insert_row(client, table: str, payload: dict[str, Any]):
    def operation():
        return client.table(table).insert(payload).execute().data or []

    rows = await _run(operation)
    return rows[0] if rows else payload


async def _select_rows(client, table: str, columns: str = "*", *, filters: dict[str, Any] | None = None, limit: int = 100):
    def operation():
        query = client.table(table).select(columns).limit(limit)
        for key, value in (filters or {}).items():
            query = query.eq(key, value)
        return query.execute().data or []

    return await _run(operation)


async def _delete_rows_by_ids(client, table: str, ids: list[str]):
    if not ids:
        return []

    def operation():
        return client.table(table).delete().in_("id", ids).execute().data or []

    return await _run(operation)


async def _resolve_user(client, email: str) -> dict[str, Any]:
    direct = await _select_rows(client, "profiles", filters={"email": email}, limit=1)
    if direct:
        return direct[0]

    named = await _select_rows(client, "profiles", filters={"full_name": "Zian"}, limit=5)
    if named:
        return named[0]

    raise RuntimeError(f"Could not find a Supabase profile for {email!r} or full_name 'Zian'.")


async def _resolve_skill_ids(repository: SkillRepository, skill_names: list[str]) -> dict[str, str]:
    rows = await repository.skills.list_where_in(
        column="skill_name",
        values=skill_names,
        columns="skill_id,skill_name",
    )
    resolved = {row["skill_name"]: row["skill_id"] for row in rows}
    for skill_name in skill_names:
        resolved.setdefault(skill_name, normalize_name(skill_name))
    return resolved


async def _seed_schedule(client, user_id: str, now: datetime) -> int:
    existing = await _select_rows(client, "schedule_events", "id,title,metadata", filters={"user_id": user_id}, limit=100)
    stale_ids = [
        row["id"]
        for row in existing
        if str(row.get("title", "")).startswith("Mock ·")
        or (isinstance(row.get("metadata"), dict) and row["metadata"].get("seed") == SEED_TAG)
    ]
    await _delete_rows_by_ids(client, "schedule_events", stale_ids)

    payloads = [
        {
            "user_id": user_id,
            "title": "Mock · Python fundamentals review",
            "starts_at": (now + timedelta(days=1, hours=2)).isoformat(),
            "ends_at": (now + timedelta(days=1, hours=3, minutes=30)).isoformat(),
            "event_type": "study",
            "metadata": {"seed": SEED_TAG, "location": "Dashboard planner", "track": "Python Fundamentals"},
            "created_at": now.isoformat(),
        },
        {
            "user_id": user_id,
            "title": "Mock · MCQ validation sprint",
            "starts_at": (now + timedelta(days=3, hours=1)).isoformat(),
            "ends_at": (now + timedelta(days=3, hours=2)).isoformat(),
            "event_type": "assessment",
            "metadata": {"seed": SEED_TAG, "mode": "MCQ", "track": "ML Engineer"},
            "created_at": now.isoformat(),
        },
        {
            "user_id": user_id,
            "title": "Mock · Evidence refresh and folio pass",
            "starts_at": (now + timedelta(days=5, hours=4)).isoformat(),
            "ends_at": (now + timedelta(days=5, hours=5)).isoformat(),
            "event_type": "portfolio",
            "metadata": {"seed": SEED_TAG, "focus": "Artifacts", "track": "Readiness"},
            "created_at": now.isoformat(),
        },
    ]
    await _upsert_rows(client, "schedule_events", payloads, on_conflict="id")
    return len(payloads)


async def _seed_artifacts(client, user_id: str, now: datetime) -> int:
    payloads = [
        {
            "user_id": user_id,
            "bucket_name": item["bucket_name"],
            "storage_path": f"{user_id}/{item['storage_path']}",
            "file_name": item["file_name"],
            "file_type": item["file_type"],
            "extracted_text": item["extracted_text"],
            "metadata": {"seed": SEED_TAG},
            "created_at": now.isoformat(),
            "processed_at": now.isoformat(),
        }
        for item in ARTIFACTS
    ]
    await _upsert_rows(client, "uploaded_artifacts", payloads, on_conflict="storage_path")
    return len(payloads)


async def _seed_report(client, user_id: str, now: datetime) -> str:
    report = await _insert_row(
        client,
        "reports",
        {
            "user_id": user_id,
            "report_type": "summary",
            "payload": {
                "seed": SEED_TAG,
                "headline": "Mock readiness snapshot for Zian",
                "summary": [
                    "Programming basics are stable enough to start repeated validation loops.",
                    "Deployment and ML systems remain the highest-pressure gaps.",
                    "Artifacts and schedule evidence are now populated for dashboard verification.",
                ],
                "focus_role": FOCUS_ROLE,
            },
            "created_at": now.isoformat(),
        },
    )
    return str(report["id"])


async def _seed_skill_request(
    repository: SkillRepository,
    assessment_repository: AssessmentRepository,
    client,
    user_id: str,
    now: datetime,
) -> tuple[str, str]:
    skill_name = SKILL_REQUEST_NAME
    normalized_name = normalize_name(skill_name)

    await repository.upsert_skill_catalog(
        {
            "skill_id": SKILL_REQUEST_ID,
            "skill_name": skill_name,
            "normalized_name": normalized_name,
            "description": "Python foundations curated for ML workflows, data handling, debugging, and validation.",
            "industry_usage": "Used in data prep, model training, experimentation, and evaluation workflows.",
            "hidden_skills_supported": ["debugging", "structured_reasoning", "communication"],
            "metadata": {
                "seed": SEED_TAG,
                "written_prompt": REQUEST_WRITTEN["question_text"],
            },
            "status": "active",
            "is_generated": True,
            "is_active": True,
            "updated_at": now.isoformat(),
        }
    )

    request = await repository.upsert_skill_request(
        {
            "user_id": user_id,
            "requested_name": skill_name,
            "normalized_name": normalized_name,
            "requested_type": "skill",
            "matched_skill_id": SKILL_REQUEST_ID,
            "status": "pending_validation",
            "generation_status": "generated",
            "generated_payload": {
                "description": "Validate Python readiness for ML experimentation, data handling, and reproducible workflows.",
                "written_prompt": REQUEST_WRITTEN["question_text"],
                "interview_focus": [
                    "debugging habits",
                    "data leakage prevention",
                    "function decomposition",
                    "validation discipline",
                ],
                "subskills": ["variables", "control flow", "functions", "lists", "debugging"],
                "seed": SEED_TAG,
            },
            "metadata": {
                "seed": SEED_TAG,
                "validation_ready_at": (now + timedelta(minutes=5)).isoformat(),
                "target_role": FOCUS_ROLE,
            },
            "updated_at": now.isoformat(),
            "is_active": True,
        }
    )
    request_id = str(request["id"])

    for item in REQUEST_MCQS:
        question = await assessment_repository.upsert_question(
            {
                "skill_id": SKILL_REQUEST_ID,
                "skill_name": skill_name,
                "skill_request_id": request_id,
                "question_text": item["question_text"],
                "category": skill_name,
                "difficulty": item["difficulty"],
                "question_type": "MCQ",
                "metadata": {"seed": SEED_TAG},
                "is_generated": True,
                "updated_at": now.isoformat(),
            }
        )
        await assessment_repository.upsert_options(
            [
                {
                    "question_id": question["id"],
                    "option_key": option_key,
                    "option_text": option_text,
                    "is_correct": is_correct,
                    "explanation": "Seeded MCQ option",
                }
                for option_key, option_text, is_correct in item["options"]
            ]
        )

    await assessment_repository.upsert_question(
        {
            "skill_id": SKILL_REQUEST_ID,
            "skill_name": skill_name,
            "skill_request_id": request_id,
            "question_text": REQUEST_WRITTEN["question_text"],
            "category": skill_name,
            "difficulty": REQUEST_WRITTEN["difficulty"],
            "question_type": "WRITTEN",
            "sample_answer": REQUEST_WRITTEN["sample_answer"],
            "expected_concepts": REQUEST_WRITTEN["expected_concepts"],
            "metadata": {"seed": SEED_TAG},
            "is_generated": True,
            "updated_at": now.isoformat(),
        }
    )

    return request_id, SKILL_REQUEST_ID


async def seed(email: str) -> dict[str, Any]:
    settings = get_settings()
    settings.require_supabase()
    client = get_supabase_client(settings)
    skill_repository = SkillRepository(client)
    assessment_repository = AssessmentRepository(client)
    now = datetime.now(timezone.utc)

    user = await _resolve_user(client, email)
    user_id = str(user["id"])
    existing_metadata = user.get("metadata") if isinstance(user.get("metadata"), dict) else {}

    await _upsert_rows(
        client,
        "profiles",
        {
            "id": user_id,
            "email": user.get("email"),
            "full_name": user.get("full_name") or "Zian",
            "headline": "Aspiring ML Engineer",
            "focus_role": FOCUS_ROLE,
            "weekly_goal": "Complete two validation loops and one portfolio evidence refresh every week.",
            "avatar_url": user.get("avatar_url"),
            "metadata": {
                **existing_metadata,
                "seed": SEED_TAG,
                "goal": "ML Engineer readiness",
                "mock_ready": True,
            },
            "updated_at": now.isoformat(),
        },
        on_conflict="id",
    )

    await _upsert_rows(
        client,
        "users",
        {
            "id": user_id,
            "email": user.get("email"),
            "full_name": user.get("full_name") or "Zian",
            "role": "student",
            "target_role_id": None,
            "avatar_url": user.get("avatar_url"),
            "updated_at": now.isoformat(),
        },
        on_conflict="id",
    )

    await _upsert_rows(
        client,
        "user_preferences",
        {
            "user_id": user_id,
            "desktop_notifications": True,
            "weekly_digest": True,
            "folio_reminders": True,
            "folio_focus": "ML Engineer readiness",
            "security_mode": "standard",
            "updated_at": now.isoformat(),
        },
        on_conflict="user_id",
    )

    role_skill_names = [skill_name for skill_name, *_ in ROLE_SKILLS]
    resolved_skill_ids = await _resolve_skill_ids(skill_repository, role_skill_names)

    user_skill_payloads = [
        {
            "user_id": user_id,
            "skill_id": resolved_skill_ids[skill_name],
            "skill_name": skill_name,
            "proficiency_score": proficiency_score,
            "assessment_score": assessment_score,
            "interview_score": interview_score,
            "artifact_score": artifact_score,
            "source": "mock_seed",
            "metadata": {"seed": SEED_TAG, "focus_role": FOCUS_ROLE},
            "updated_at": now.isoformat(),
        }
        for skill_name, proficiency_score, assessment_score, interview_score, artifact_score in ROLE_SKILLS
    ]
    await _upsert_rows(client, "user_skills", user_skill_payloads, on_conflict="user_id,skill_id")

    hidden_payloads = []
    for item in HIDDEN_SKILLS:
        payload = {
            "user_id": user_id,
            "skill_name": item["skill_name"],
            "skill_id": normalize_name(item["skill_name"]),
            "confidence_score": item["confidence_score"],
            "source": item["source"],
            "evidence": item["evidence"],
            "status": item["status"],
            "metadata": {"seed": SEED_TAG},
        }
        if item["status"] == "approved":
            payload["approved_at"] = now.isoformat()
        hidden_payloads.append(payload)
    await _upsert_rows(
        client,
        "hidden_skill_candidates",
        hidden_payloads,
        on_conflict="user_id,skill_name,status",
    )

    request_id, custom_skill_id = await _seed_skill_request(
        skill_repository,
        assessment_repository,
        client,
        user_id,
        now,
    )
    artifact_count = await _seed_artifacts(client, user_id, now)
    schedule_count = await _seed_schedule(client, user_id, now)
    report_id = await _seed_report(client, user_id, now)

    return {
        "user_id": user_id,
        "email": user.get("email"),
        "focus_role": FOCUS_ROLE,
        "seed_tag": SEED_TAG,
        "user_skills": len(user_skill_payloads),
        "hidden_skill_candidates": len(hidden_payloads),
        "artifacts": artifact_count,
        "schedule_events": schedule_count,
        "skill_request_id": request_id,
        "custom_skill_id": custom_skill_id,
        "report_id": report_id,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Zian with mock CELTM workspace data.")
    parser.add_argument("--email", default=DEFAULT_EMAIL, help="Supabase profile email to seed.")
    args = parser.parse_args()

    result = await seed(args.email)
    print("Seeded mock data:")
    for key, value in result.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    asyncio.run(main())
