from __future__ import annotations

import re
from collections import Counter
from typing import Any

import httpx

from app.database import DIMENSIONS, Database, now_iso, to_json
from app.settings import Settings


PAGE_SIZE = 1000
SUBJECT_DIMENSION_HINTS = {
    "Communication": [
        "english",
        "communication",
        "presentation",
        "writing",
        "speaking",
        "stakeholder",
    ],
    "Problem Solving": [
        "algorithm",
        "data structure",
        "aptitude",
        "math",
        "mathematics",
        "reasoning",
        "logic",
    ],
    "Data Thinking": [
        "database",
        "dbms",
        "sql",
        "data analytics",
        "analytics",
        "statistics",
        "metric",
    ],
    "AI Readiness": [
        "machine learning",
        "artificial intelligence",
        " ai ",
        " ml ",
        "model",
        "neural",
        "llm",
    ],
    "Domain Foundation": [
        "programming",
        "object-oriented",
        "oop",
        "operating system",
        "computer network",
        "physics",
        "chemistry",
    ],
    "Industry Application": [
        "software engineering",
        "web development",
        "cloud",
        "cyber",
        "devops",
        "deployment",
        "production",
    ],
}
SUBJECT_NAME_HINTS = {
    "ML Systems": [
        "ml systems",
        "model serving",
        "deployed model",
        "model deployment",
        "deployment of a new model",
        "production model",
        "model performance after deployment",
        "scaling a deployed model",
    ],
    "Python Fundamentals for ML": [
        "python fundamentals for ml",
        "python script",
        "debug it",
    ],
    "Database Management Systems": [
        "sql",
        "acid",
        "foreign key",
        "database",
        "transaction",
        "order by",
        "table",
        "schema",
    ],
    "Machine Learning": [
        "machine learning",
        "overfitting",
        "classification",
        "model evaluation",
        "roc",
        "high bias",
        "training error",
        "loss function",
        "feature",
        "time series forecasting",
        "regression model",
        "confusion matrix",
        "model's performance",
    ],
    "Artificial Intelligence": [
        "artificial intelligence",
        " ai ",
        "chatbot",
        "sequential decision",
        "probabilistic",
        "heuristic",
    ],
    "Data Analytics": [
        "missing data",
        "visualization",
        "outlier",
        "correlation",
        "analytics",
        "dataset",
        "distribution",
        "business insights",
    ],
    "Data Structures": [
        "data structures",
        "linked list",
        "tree",
        "stack",
        "queue",
        "heap",
        "graph",
        "bfs",
        "dfs",
    ],
    "Algorithms": [
        "algorithm",
        "greedy",
        "sorting",
        "shortest path",
        "binary search",
        "dynamic programming",
        "cycle",
        "recursion",
        "subproblems",
    ],
    "DevOps": [
        "devops",
        "release",
        "logging",
        "deployment pipeline",
        "ci/cd",
        "monitoring",
        "container",
        "version control",
        "git",
        "continuous integration",
        "deployment steps",
        "development and operations",
    ],
    "Cloud Computing": [
        "cloud",
        "virtualization",
        "serverless",
        "auto scaling",
        "cdn",
        "private cloud",
        "hybrid architecture",
    ],
    "Cyber Security": [
        "security",
        "phishing",
        "xss",
        "vulnerability",
        "password",
        "encryption",
        "data integrity",
    ],
    "Computer Networks": [
        "network",
        "dns",
        "browser",
        "packet",
        "routing",
        "tcp",
        "ip address",
        "router",
        "switch",
        "transport",
        "video calls",
        "file downloads",
    ],
    "Operating Systems": [
        "operating system",
        "page fault",
        "process",
        "deadlock",
        "memory management",
        "scheduling",
    ],
    "Object-Oriented Programming": [
        "object-oriented",
        "oop",
        "abstraction",
        "encapsulation",
        "inheritance",
        "polymorphism",
        "class",
        "object",
    ],
    "Programming Fundamentals": [
        "programming",
        "function",
        "loop",
        "variable",
        "array",
        "condition",
    ],
    "Software Engineering": [
        "software design",
        "software engineering",
        "requirements",
        "testing",
        "architecture",
    ],
    "Web Development": [
        "react",
        "javascript",
        "frontend",
        "website",
        "html",
        "css",
        "ui",
        "virtual dom",
        "padding",
        "margin",
        "rest",
        "web services",
    ],
    "Mathematics": [
        "quadratic",
        "slope",
        "limit",
        "logarithm",
        "triangle",
        "trigonometric",
        "probability",
        "vector",
        "distance",
        "rate of change",
        "integral",
        "derivative",
        "pi",
        "algebra",
        "equation",
        "percentage",
    ],
    "Aptitude": [
        "time-speed-distance",
        "blood relation",
        "aptitude",
        "reasoning accuracy",
    ],
    "Logical Reasoning": [
        "logical reasoning",
        "blood relation",
        "pattern",
        "sequence",
    ],
    "Physics": [
        "force",
        "motion",
        "energy",
        "electricity",
        "structural stability",
        "subatomic",
        "charge",
        "planet",
        "atmosphere",
        "refraction",
        "bent",
    ],
    "Chemistry": [
        "reaction",
        "acid",
        "base",
        "entropy",
        "oxidation",
        "ideal gas",
        "exothermic",
        "chemical symbol",
        "atomic radius",
        "gold",
        "natural substance",
    ],
    "English Communication": [
        "communication",
        "stakeholder-ready",
        "formal email",
        "professional email",
        "grammar",
        "spelling",
        "writing clarity",
        "vocabulary",
        "adjective",
        "punctuation",
        "sentence",
    ],
    "Biology": [
        "photosynthesis",
        "cell",
        "plants make their food",
        "powerhouse",
    ],
    "Social Science": [
        "social science",
    ],
    "General Knowledge": [
        "red planet",
        "earth's atmosphere",
    ],
}
SUBJECT_ALIASES = {
    "Database Management": "Database Management Systems",
    "Object Oriented Programming": "Object-Oriented Programming",
}


def sync_supabase_question_bank(settings: Settings, db: Database) -> dict[str, Any]:
    key = _supabase_write_key(settings)
    if not settings.supabase_url or not key:
        status = _status_payload(
            source="supabase_required",
            status="degraded",
            message="Supabase credentials are missing; local question-bank fallback is disabled for hosted mode.",
            rows=[],
        )
        _save_status(db, status)
        return status

    try:
        base_url = settings.supabase_url.rstrip("/")
        headers = {"apikey": key, "Authorization": f"Bearer {key}"}
        with httpx.Client(timeout=25, headers=headers) as client:
            questions = _fetch_table(client, base_url, "questions")
            mcq_options = _fetch_table(client, base_url, "mcq_questions")
        rows, metadata = _build_question_rows(questions, mcq_options)
        if not rows:
            status = _status_payload(
                source="supabase_required",
                status="degraded",
                message="Supabase returned no usable question rows; local question-bank fallback is disabled.",
                rows=[],
                metadata=metadata,
            )
            _save_status(db, status)
            return status

        status = _status_payload(
            source="supabase",
            status="ready",
            message="Question bank verified from Supabase REST tables. Local question fallback is disabled.",
            rows=[{"question_type": row[3], "dimension": row[1], "difficulty": row[2]} for row in rows],
            metadata=metadata,
        )
        _save_status(db, status)
        return status
    except Exception as exc:
        status = _status_payload(
            source="supabase_required",
            status="degraded",
            message=f"Supabase sync failed and local question-bank fallback is disabled. {type(exc).__name__}: {exc}",
            rows=[],
        )
        _save_status(db, status)
        return status


def supabase_question_bank_available(db: Database) -> bool:
    status = question_bank_status(db)
    return status["source"] == "supabase" and status["status"] == "ready" and status["total_questions"] > 0


def fetch_supabase_question_rows(settings: Settings) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    key = _supabase_write_key(settings)
    if not settings.supabase_url or not key:
        raise RuntimeError("Supabase service credentials are required to read assessment questions.")

    base_url = settings.supabase_url.rstrip("/")
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    with httpx.Client(timeout=25, headers=headers) as client:
        questions = _fetch_table(client, base_url, "questions")
        mcq_options = _fetch_table(client, base_url, "mcq_questions")
    rows, metadata = _build_question_rows(questions, mcq_options)
    return [_tuple_to_question_dict(row) for row in rows], metadata


def _map_difficulty_for_supabase(val: Any) -> str:
    text = str(val or "").strip().lower()
    if text in {"advanced", "hard"}:
        return "hard"
    if text in {"intermediate", "medium"}:
        return "medium"
    return "easy"


def add_question_to_supabase(settings: Settings, payload: dict[str, Any]) -> dict[str, Any]:
    key = _supabase_write_key(settings)
    if not settings.supabase_url or not key:
        raise RuntimeError("Supabase service credentials are required to add questions.")

    question_type = str(payload.get("question_type") or "MCQ").strip().lower()
    if question_type not in {"mcq", "situational", "descriptive"}:
        question_type = "mcq"

    option_rows: list[dict[str, str]] = []
    correct_option = ""
    if question_type in {"mcq", "situational"}:
        option_rows = _normalize_payload_options(payload)
        correct_option = _normalize_correct_option(payload.get("correct_answer") or payload.get("correct_option"))
        if len(option_rows) < 2 or not correct_option:
            raise ValueError("At least two options and a correct answer are required for MCQ/situational questions.")

    scenario = str(payload.get("scenario") or "").strip()
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    if scenario:
        metadata = {**metadata, "scenario": scenario}
    explanation = str(payload.get("explanation") or "").strip() or None
    sample_answer = str(payload.get("sample_answer") or "").strip() or None
    if question_type == "descriptive" and not sample_answer:
        sample_answer = explanation

    question_payload = {
        "question_text": str(payload.get("question_text") or "").strip(),
        "question_type": "situational_mcq" if question_type == "situational" else question_type,
        "difficulty": _map_difficulty_for_supabase(payload.get("difficulty")),
        "category": str(payload.get("dimension") or payload.get("category") or "").strip(),
        "subject_name": str(payload.get("dimension") or payload.get("subject_name") or "").strip(),
        "skill_name": str(payload.get("skill_name") or payload.get("dimension") or "").strip(),
        "explanation": explanation,
        "sample_answer": sample_answer,
        "metadata": metadata,
        "is_active": True,
    }
    if not question_payload["question_text"]:
        raise ValueError("question_text is required")

    base_url = settings.supabase_url.rstrip("/")
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    with httpx.Client(timeout=25, headers=headers) as client:
        response = client.post(f"{base_url}/rest/v1/questions", json=question_payload)
        response.raise_for_status()
        returned = response.json()
        question_row = returned[0] if isinstance(returned, list) and returned else returned
        question_id = str(question_row.get("id") or "")
        if question_type in {"mcq", "situational"}:
            option_payload = {"question_id": question_id, "correct_option": correct_option}
            for option in option_rows:
                option_payload[f"option_{option['id'].lower()}"] = option["option_text"]
            option_response = client.post(f"{base_url}/rest/v1/mcq_questions", json=option_payload)
            option_response.raise_for_status()
    return question_row


def question_bank_status(db: Database) -> dict[str, Any]:
    row = db.query_one("SELECT * FROM question_bank_status WHERE id = 'primary'")
    if not row:
        status = _status_payload(
            source="supabase_required",
            status="degraded",
            message="Supabase question bank has not been verified yet. Local question-bank fallback is disabled.",
            rows=[],
        )
        _save_status(db, status)
        return status
    metadata = _safe_json(row["metadata"])
    return {
        "source": row["source"],
        "status": row["status"],
        "message": row["message"],
        "total_questions": row["total_questions"],
        "mcq_count": row["mcq_count"],
        "descriptive_count": row["descriptive_count"],
        "situational_count": row["situational_count"],
        "synced_at": row["synced_at"],
        "metadata": metadata,
    }


def _fetch_table(client: httpx.Client, base_url: str, table: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0
    while True:
        end = start + PAGE_SIZE - 1
        response = client.get(
            f"{base_url}/rest/v1/{table}",
            params={"select": "*"},
            headers={"Range": f"{start}-{end}"},
        )
        if response.status_code == 404:
            return []
        response.raise_for_status()
        page = response.json()
        if not isinstance(page, list) or not page:
            break
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            break
        start += PAGE_SIZE
    return rows


def _supabase_write_key(settings: Settings) -> str:
    return (
        settings.supabase_service_role_key
        or settings.supabase_secret_key
        or settings.supabase_legacy_key
        or settings.supabase_api_key
    )


def _normalize_payload_options(payload: dict[str, Any]) -> list[dict[str, str]]:
    raw_options = payload.get("options")
    if isinstance(raw_options, list):
        options = []
        for index, value in enumerate(raw_options[:4]):
            if isinstance(value, dict):
                text = str(value.get("option_text") or value.get("text") or "").strip()
                option_id = str(value.get("id") or "ABCD"[index]).strip().upper()[:1]
            else:
                text = str(value or "").strip()
                option_id = "ABCD"[index]
            if text and option_id in {"A", "B", "C", "D"}:
                options.append({"id": option_id, "option_text": text})
        return options

    options = []
    for letter in ("A", "B", "C", "D"):
        text = str(payload.get(f"option_{letter.lower()}") or payload.get(f"option_{letter}") or "").strip()
        if text:
            options.append({"id": letter, "option_text": text})
    return options


def _build_question_rows(
    questions: list[dict[str, Any]],
    mcq_options: list[dict[str, Any]],
) -> tuple[list[tuple[Any, ...]], dict[str, Any]]:
    options_by_question = {str(row.get("question_id") or ""): row for row in mcq_options if row.get("question_id")}
    rows: list[tuple[Any, ...]] = []
    skipped = Counter()
    source_types = Counter(str(row.get("question_type") or "unknown").lower() for row in questions)

    for question in questions:
        if question.get("is_active") is False:
            skipped["inactive"] += 1
            continue
        question_id = str(question.get("id") or "").strip()
        question_text = str(question.get("question_text") or "").strip()
        if not question_id or not question_text:
            skipped["missing_question_text"] += 1
            continue

        source_type = str(question.get("question_type") or "").strip().lower()
        dimension = _resolve_dimension(question)
        subject = _resolve_subject_name(question, dimension)
        difficulty = _resolve_difficulty(str(question.get("difficulty") or ""))
        metadata = question.get("metadata") if isinstance(question.get("metadata"), dict) else {}
        scenario = str(metadata.get("scenario") or "").strip() or None
        explanation = str(question.get("explanation") or question.get("sample_answer") or "").strip()

        if source_type == "descriptive":
            rows.append(
                (
                    question_id,
                    dimension,
                    difficulty,
                    "DESCRIPTIVE",
                    scenario,
                    question_text,
                    "[]",
                    "",
                    explanation,
                    subject,
                )
            )
            continue

        option_row = options_by_question.get(question_id)
        if not option_row:
            skipped["missing_options"] += 1
            continue
        options = _options_from_row(option_row)
        correct = _normalize_correct_option(option_row.get("correct_option"))
        if len(options) < 2 or not correct:
            skipped["invalid_options"] += 1
            continue

        qtype = "SITUATIONAL" if "situational" in source_type else "MCQ"
        rows.append(
            (
                question_id,
                dimension,
                difficulty,
                qtype,
                scenario,
                question_text,
                to_json(options),
                correct,
                explanation,
                subject,
            )
        )

    metadata = {
        "supabase_question_rows": len(questions),
        "supabase_mcq_option_rows": len(mcq_options),
        "source_question_types": dict(source_types),
        "skipped": dict(skipped),
        "dimension_counts": dict(Counter(row[1] for row in rows)),
        "subject_counts": dict(Counter(row[9] for row in rows)),
        "subject_type_counts": {
            subject: dict(Counter(row[3] for row in rows if row[9] == subject))
            for subject in sorted({row[9] for row in rows})
        },
        "difficulty_counts": dict(Counter(row[2] for row in rows)),
    }
    rows.sort(key=lambda row: (row[9], row[1], row[2], row[3], row[0]))
    return rows, metadata


def _options_from_row(row: dict[str, Any]) -> list[dict[str, str]]:
    options: list[dict[str, str]] = []
    for letter in ("A", "B", "C", "D"):
        text = str(row.get(f"option_{letter.lower()}") or "").strip()
        if not text:
            continue
        text = re.sub(rf"^\s*{letter}\s*[\).:\-]\s*", "", text, flags=re.IGNORECASE)
        options.append({"id": letter, "option_text": text})
    return options


def _normalize_correct_option(value: Any) -> str:
    text = str(value or "").strip().upper()
    if text in {"A", "B", "C", "D"}:
        return text
    match = re.search(r"\b([A-D])\b", text)
    return match.group(1) if match else ""


def _resolve_difficulty(value: str) -> str:
    text = value.strip().lower()
    if text in {"advanced", "hard"}:
        return "Advanced"
    if text in {"intermediate", "medium"}:
        return "Intermediate"
    return "Basic"


def _resolve_dimension(row: dict[str, Any]) -> str:
    parts = [
        row.get("subject_name"),
        row.get("category"),
        row.get("skill_name"),
        row.get("subskill_name"),
        row.get("question_text"),
    ]
    haystack = " " + " ".join(str(part or "").lower() for part in parts) + " "
    for dimension, hints in SUBJECT_DIMENSION_HINTS.items():
        if any(hint in haystack for hint in hints):
            return dimension
    return "Domain Foundation"


def _resolve_subject_name(row: dict[str, Any], fallback: str) -> str:
    for key in ("subject_name", "category", "skill_name", "subskill_name"):
        value = str(row.get(key) or "").strip()
        if value and value.lower() not in {"questions", "question", "unknown", "none", "null"} and value not in DIMENSIONS:
            return SUBJECT_ALIASES.get(value, value)
    haystack = " " + " ".join(
        str(row.get(key) or "").lower()
        for key in ("subject_name", "category", "skill_name", "subskill_name", "question_text", "sample_answer", "explanation")
    ) + " "
    for subject, hints in SUBJECT_NAME_HINTS.items():
        if any(hint in haystack for hint in hints):
            return SUBJECT_ALIASES.get(subject, subject)
    if fallback in DIMENSIONS:
        return "General Knowledge"
    return fallback


def _tuple_to_question_dict(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "id": row[0],
        "dimension": row[1],
        "difficulty": row[2],
        "question_type": row[3],
        "scenario": row[4],
        "question_text": row[5],
        "options": row[6],
        "correct_answer": row[7],
        "explanation": row[8],
        "subject_name": row[9],
        "subject_key": re.sub(r"[^a-z0-9]+", "-", str(row[9]).lower()).strip("-"),
    }


def _status_payload(
    source: str,
    status: str,
    message: str,
    rows: list[dict[str, Any]],
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    counts = Counter(str(row.get("question_type") or "").upper() for row in rows)
    return {
        "source": source,
        "status": status,
        "message": message,
        "total_questions": len(rows),
        "mcq_count": counts.get("MCQ", 0),
        "descriptive_count": counts.get("DESCRIPTIVE", 0),
        "situational_count": counts.get("SITUATIONAL", 0),
        "synced_at": now_iso(),
        "metadata": metadata or {},
    }


def _save_status(db: Database, status: dict[str, Any]) -> None:
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
            to_json(status.get("metadata", {})),
        ),
    )


def _safe_json(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        import json

        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}
