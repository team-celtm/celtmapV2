from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import Database, now_iso  # noqa: E402
from app.settings import get_settings  # noqa: E402


MIGRATION_VERSION = "2026-06-04-runtime-hardening"
MIGRATION_DESCRIPTION = "Phase 1 hosted hardening schema, audit logs, storage metadata, jobs, and indexes"


def main() -> None:
    settings = get_settings()
    database = Database(settings.database_target, postgres_schema=settings.postgres_schema)
    database.init()
    database.execute(
        """
        INSERT INTO schema_migrations (version, description, applied_at)
        VALUES (?, ?, ?)
        ON CONFLICT (version) DO NOTHING
        """,
        (MIGRATION_VERSION, MIGRATION_DESCRIPTION, now_iso()),
    ) if database.using_postgres else database.execute(
        """
        INSERT OR IGNORE INTO schema_migrations (version, description, applied_at)
        VALUES (?, ?, ?)
        """,
        (MIGRATION_VERSION, MIGRATION_DESCRIPTION, now_iso()),
    )
    target = "postgres" if database.using_postgres else settings.database_path
    print(f"CELTM runtime migration complete: {MIGRATION_VERSION} on {target}")


if __name__ == "__main__":
    main()
