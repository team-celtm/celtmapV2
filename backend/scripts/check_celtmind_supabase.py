from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _build_local_file_map(celtmind_path: Path) -> dict[str, dict[str, Any]]:
    csv_files = sorted(celtmind_path.glob("*.csv"))
    questions_dir = celtmind_path / "questions"
    if questions_dir.exists():
        csv_files.extend(sorted(questions_dir.glob("*.csv")))

    return {
        path.name: {
            "path": str(path),
            "checksum": _checksum(path),
        }
        for path in csv_files
    }


async def _table_count(client: Any, table_name: str, filters: dict[str, Any] | None = None) -> int:
    def operation() -> int:
        query = client.table(table_name).select("id", count="exact").limit(1)
        for key, value in (filters or {}).items():
            query = query.eq(key, value)
        response = query.execute()
        count = getattr(response, "count", None)
        if count is not None:
            return int(count)
        return len(response.data or [])

    return await asyncio.to_thread(operation)


async def _select_rows(
    client: Any,
    table_name: str,
    columns: str,
    *,
    order_by: str | None = None,
    descending: bool = True,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    def operation() -> list[dict[str, Any]]:
        query = client.table(table_name).select(columns)
        if order_by:
            query = query.order(order_by, desc=descending)
        if limit is not None:
            query = query.limit(limit)
        response = query.execute()
        return list(response.data or [])

    return await asyncio.to_thread(operation)


async def build_report() -> dict[str, Any]:
    from app.config.settings import get_settings
    from app.integrations.cache import CacheClient
    from app.integrations.supabase import get_supabase_client

    settings = get_settings()
    settings.require_supabase()

    client = get_supabase_client(settings)
    local_files = _build_local_file_map(settings.celtmind_path)
    schema_errors: dict[str, str] = {}

    async def safe_select_rows(
        table_name: str,
        columns: str,
        *,
        order_by: str | None = None,
        descending: bool = True,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        try:
            return await _select_rows(
                client,
                table_name,
                columns,
                order_by=order_by,
                descending=descending,
                limit=limit,
            )
        except Exception as exc:
            schema_errors[table_name] = str(exc)
            return []

    async def safe_table_count(
        table_name: str,
        *,
        filters: dict[str, Any] | None = None,
    ) -> int | None:
        try:
            return await _table_count(client, table_name, filters=filters)
        except Exception as exc:
            schema_errors[table_name] = str(exc)
            return None

    remote_registry = await safe_select_rows(
        "celtmind_file_registry",
        "file_name, checksum, category, last_ingested_at",
    )
    remote_by_name = {row["file_name"]: row for row in remote_registry}

    missing_in_supabase: list[str] = []
    checksum_mismatches: list[dict[str, str]] = []
    for file_name, metadata in local_files.items():
        remote_row = remote_by_name.get(file_name)
        if remote_row is None:
            missing_in_supabase.append(file_name)
            continue
        if remote_row.get("checksum") != metadata["checksum"]:
            checksum_mismatches.append(
                {
                    "file_name": file_name,
                    "local_checksum": metadata["checksum"],
                    "remote_checksum": str(remote_row.get("checksum") or ""),
                }
            )

    extra_remote_files = sorted(set(remote_by_name) - set(local_files))
    latest_runs = await safe_select_rows(
        "celtmind_ingestion_runs",
        "id, status, started_at, completed_at, summary, error",
        order_by="started_at",
        descending=True,
        limit=1,
    )

    table_names = [
        "subjects",
        "skills",
        "subskills",
        "roles",
        "questions",
        "options",
        "rag_documents",
        "celtmind_file_registry",
        "celtmind_ingestion_runs",
    ]
    counts = {
        table_name: await safe_table_count(table_name)
        for table_name in table_names
    }
    counts["rag_documents_global"] = await safe_table_count(
        "rag_documents", filters={"scope": "global"}
    )
    counts["rag_documents_catalog"] = await safe_table_count(
        "rag_documents", filters={"scope": "catalog"}
    )

    redis_ok = CacheClient(settings).ping()

    return {
        "redis": {
            "url_configured": bool(settings.redis_url),
            "reachable": redis_ok,
        },
        "supabase": {
            "url_configured": bool(settings.supabase_url),
            "service_key_configured": bool(settings.resolved_supabase_service_role_key),
        },
        "celtmind": {
            "path": str(settings.celtmind_path),
            "local_file_count": len(local_files),
            "local_files": sorted(local_files),
            "missing_in_supabase": sorted(missing_in_supabase),
            "checksum_mismatches": checksum_mismatches,
            "extra_remote_files": extra_remote_files,
        },
        "latest_ingestion_run": latest_runs[0] if latest_runs else None,
        "schema_errors": schema_errors,
        "table_counts": counts,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Verify CELTMIND ingestion and Redis/Supabase state.")
    parser.add_argument("--json", action="store_true", help="Print the report as JSON.")
    args = parser.parse_args()

    report = await build_report()
    if args.json:
        print(json.dumps(report, indent=2))
        return

    print("Redis:")
    print(f"  configured: {report['redis']['url_configured']}")
    print(f"  reachable: {report['redis']['reachable']}")
    print("Supabase:")
    print(f"  configured: {report['supabase']['url_configured']}")
    print(f"  service key configured: {report['supabase']['service_key_configured']}")
    print("CELTMIND:")
    print(f"  path: {report['celtmind']['path']}")
    print(f"  local files: {report['celtmind']['local_file_count']}")
    print(f"  missing in Supabase: {len(report['celtmind']['missing_in_supabase'])}")
    if report["celtmind"]["missing_in_supabase"]:
        print("    " + ", ".join(report["celtmind"]["missing_in_supabase"]))
    print(f"  checksum mismatches: {len(report['celtmind']['checksum_mismatches'])}")
    if report["celtmind"]["checksum_mismatches"]:
        for item in report["celtmind"]["checksum_mismatches"]:
            print(f"    {item['file_name']}")
    latest_run = report["latest_ingestion_run"]
    print("Latest ingestion run:")
    if latest_run is None:
        print("  none")
    else:
        print(f"  id: {latest_run['id']}")
        print(f"  status: {latest_run['status']}")
        print(f"  started_at: {latest_run['started_at']}")
        print(f"  completed_at: {latest_run['completed_at']}")
    if report["schema_errors"]:
        print("Schema errors:")
        for table_name, error in report["schema_errors"].items():
            print(f"  {table_name}: {error}")
    print("Table counts:")
    for table_name, count in report["table_counts"].items():
        label = count if count is not None else "unavailable"
        print(f"  {table_name}: {label}")


if __name__ == "__main__":
    asyncio.run(main())
