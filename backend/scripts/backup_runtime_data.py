from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import Database, now_iso  # noqa: E402
from app.settings import get_settings  # noqa: E402


TABLES = [
    "institutions",
    "schema_migrations",
    "departments",
    "institution_admins",
    "admin_accounts",
    "profiles",
    "user_preferences",
    "artifacts",
    "artifact_evaluations",
    "readiness_events",
    "processing_jobs",
    "resume_analyses",
    "questions",
    "question_bank_status",
    "question_sets",
    "assessment_assignments",
    "courses",
    "assessments",
    "assessment_dimension_state",
    "assessment_answers",
    "aspirations",
    "written_assessments",
    "schedule_events",
    "audit_logs",
]


def _database() -> Database:
    settings = get_settings()
    database = Database(settings.database_target, postgres_schema=settings.postgres_schema)
    database.init()
    return database


def backup(output_path: Path) -> None:
    database = _database()
    payload: dict[str, Any] = {
        "format": "celtm-phase1-runtime-backup",
        "created_at": now_iso(),
        "tables": {},
    }
    for table in TABLES:
        try:
            payload["tables"][table] = database.query_all(f"SELECT * FROM {table}")
        except Exception as exc:
            payload["tables"][table] = {"error": str(exc)}

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote backup to {output_path}")


def restore(input_path: Path, replace: bool) -> None:
    database = _database()
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if payload.get("format") != "celtm-phase1-runtime-backup":
        raise SystemExit("Input is not a CELTM Phase 1 runtime backup")

    if replace:
        for table in reversed(TABLES):
            try:
                database.execute(f"DELETE FROM {table}")
            except Exception:
                pass

    for table in TABLES:
        rows = payload.get("tables", {}).get(table, [])
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict) or not row:
                continue
            columns = list(row.keys())
            placeholders = ", ".join("?" for _ in columns)
            column_sql = ", ".join(columns)
            values = tuple(row[column] for column in columns)
            if database.using_postgres:
                database.execute(
                    f"INSERT INTO {table} ({column_sql}) VALUES ({placeholders}) ON CONFLICT DO NOTHING",
                    values,
                )
            else:
                database.execute(
                    f"INSERT OR REPLACE INTO {table} ({column_sql}) VALUES ({placeholders})",
                    values,
                )
    print(f"Restored backup from {input_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Back up or restore CELTM Phase 1 runtime tables.")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "backups" / "celtm-runtime-backup.json")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--restore", action="store_true")
    parser.add_argument("--replace", action="store_true", help="Delete existing table rows before restore.")
    args = parser.parse_args()

    if args.restore:
        if not args.input:
            raise SystemExit("--restore requires --input")
        restore(args.input, replace=args.replace)
        return
    backup(args.output)


if __name__ == "__main__":
    main()
