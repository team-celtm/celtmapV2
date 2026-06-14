from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import Database, from_json  # noqa: E402
from app.settings import get_settings  # noqa: E402
from app.supabase_bank import (  # noqa: E402
    _build_question_rows,
    _fetch_table,
    _supabase_write_key,
    sync_supabase_question_bank,
)


def question_id(row: dict[str, Any]) -> str:
    return str(row.get("id") or "").strip()


def subject_name(row: dict[str, Any]) -> str:
    return str(row.get("subject_name") or row.get("category") or "Unknown").strip() or "Unknown"


def unusable_active_mcq_rows(
    questions: list[dict[str, Any]],
    options: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    option_ids = {str(row.get("question_id") or "") for row in options if row.get("question_id")}
    rows = [
        row
        for row in questions
        if row.get("is_active") is not False
        and str(row.get("question_type") or "").strip().lower() == "mcq"
        and question_id(row)
        and question_id(row) not in option_ids
    ]
    rows.sort(key=lambda row: (subject_name(row), str(row.get("difficulty") or ""), question_id(row)))
    return rows


def local_references(database: Database, ids: set[str]) -> list[dict[str, Any]]:
    references: list[dict[str, Any]] = []
    for table in ("question_sets", "assessment_assignments"):
        try:
            rows = database.query_all(f"SELECT id, title, question_ids FROM {table}")
        except Exception:
            continue
        for row in rows:
            question_ids = from_json(row.get("question_ids"), [])
            if not isinstance(question_ids, list):
                continue
            overlap = sorted(ids.intersection(str(item) for item in question_ids))
            if overlap:
                references.append(
                    {
                        "table": table,
                        "id": row.get("id"),
                        "title": row.get("title"),
                        "reference_count": len(overlap),
                        "sample_question_ids": overlap[:10],
                    }
                )
    return references


def print_bank_shape(label: str, questions: list[dict[str, Any]], options: list[dict[str, Any]]) -> None:
    rows, metadata = _build_question_rows(questions, options)
    source_counts = Counter(
        str(row.get("question_type") or "unknown").lower()
        for row in questions
        if row.get("is_active") is not False
    )
    usable_counts = Counter(row[3] for row in rows)
    print(
        label,
        {
            "source_question_rows": len(questions),
            "option_rows": len(options),
            "source_counts": dict(source_counts),
            "usable_counts": dict(usable_counts),
            "skipped": metadata.get("skipped", {}),
        },
    )


def delete_question_rows(client: httpx.Client, base_url: str, ids: list[str]) -> None:
    for start in range(0, len(ids), 100):
        chunk = ids[start : start + 100]
        response = client.delete(
            f"{base_url}/rest/v1/questions",
            params={"id": f"in.({','.join(chunk)})"},
            headers={"Prefer": "return=minimal"},
        )
        response.raise_for_status()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Delete active Supabase MCQ question rows that have no matching option row."
    )
    parser.add_argument("--dry-run", action="store_true", help="Print the delete set without writing.")
    parser.add_argument(
        "--allow-referenced",
        action="store_true",
        help="Allow deletion even if local question_sets or assessment_assignments reference a row.",
    )
    args = parser.parse_args()

    settings = get_settings()
    key = _supabase_write_key(settings)
    if not settings.supabase_url or not key:
        raise RuntimeError("Supabase URL and service key are required.")

    base_url = settings.supabase_url.rstrip("/")
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=30, headers=headers) as client:
        questions = _fetch_table(client, base_url, "questions")
        options = _fetch_table(client, base_url, "mcq_questions")
        print_bank_shape("before", questions, options)

        delete_rows = unusable_active_mcq_rows(questions, options)
        delete_ids = [question_id(row) for row in delete_rows]
        print("delete_count", len(delete_ids))
        print("delete_by_subject", dict(Counter(subject_name(row) for row in delete_rows).most_common()))
        print("sample_delete_ids", delete_ids[:10])

        database = Database(settings.database_target, postgres_schema=settings.postgres_schema)
        database.init()
        references = local_references(database, set(delete_ids))
        print("local_reference_rows", len(references))
        if references:
            print("references", references[:20])
            if not args.allow_referenced:
                raise RuntimeError("Refusing to delete rows referenced by local question sets or assignments.")

        if args.dry_run:
            return

        delete_question_rows(client, base_url, delete_ids)
        questions_after = _fetch_table(client, base_url, "questions")
        options_after = _fetch_table(client, base_url, "mcq_questions")
        print_bank_shape("after", questions_after, options_after)

    status = sync_supabase_question_bank(settings, database)
    print(
        "synced_status",
        {
            "total_questions": status.get("total_questions"),
            "mcq_count": status.get("mcq_count"),
            "descriptive_count": status.get("descriptive_count"),
            "situational_count": status.get("situational_count"),
            "status": status.get("status"),
            "skipped": status.get("metadata", {}).get("skipped"),
        },
    )


if __name__ == "__main__":
    main()
