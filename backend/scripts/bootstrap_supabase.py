from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import psycopg

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load_env() -> dict[str, str]:
    env_path = PROJECT_ROOT / ".env"
    env: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


def _connect():
    env = _load_env()
    raw = env.get("SUPABASE_DB_CONNECTION_STRING")
    if not raw:
        raise RuntimeError("SUPABASE_DB_CONNECTION_STRING is missing from backend/.env")

    parsed = urlparse(raw)
    params = {
        "host": parsed.hostname,
        "port": parsed.port or 5432,
        "dbname": (parsed.path or "/postgres").lstrip("/"),
        "user": unquote(parsed.username or ""),
        "password": unquote(parsed.password or ""),
        "sslmode": parse_qs(parsed.query).get("sslmode", ["require"])[0],
        "connect_timeout": 10,
    }
    return psycopg.connect(**params)


def apply_schema(schema_path: Path) -> None:
    sql = schema_path.read_text(encoding="utf-8")
    with _connect() as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(sql)


def run_ingest() -> None:
    subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "ingest_mcq.py")],
        check=True,
        cwd=str(PROJECT_ROOT),
    )


def run_verify() -> None:
    subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "check_celtmind_supabase.py")],
        check=True,
        cwd=str(PROJECT_ROOT),
    )


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply the Supabase schema and optionally ingest CELTMIND content."
    )
    parser.add_argument(
        "--schema",
        default=str(PROJECT_ROOT / "sql" / "supabase_schema.sql"),
        help="Path to the SQL schema file.",
    )
    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        help="Apply schema only.",
    )
    parser.add_argument(
        "--skip-verify",
        action="store_true",
        help="Skip the final verification step.",
    )
    args = parser.parse_args()

    schema_path = Path(args.schema)
    print(f"Applying schema: {schema_path}")
    try:
        apply_schema(schema_path)
    except Exception as exc:
        print("Failed to apply schema.")
        print(str(exc))
        print(
            "If the error is password or hostname related, update "
            "SUPABASE_DB_CONNECTION_STRING in backend/.env or run the SQL file "
            "manually in the Supabase SQL editor."
        )
        raise

    print("Schema applied.")
    if not args.skip_ingest:
        print("Running CELTMIND ingest...")
        run_ingest()

    if not args.skip_verify:
        print("Running verification...")
        run_verify()


if __name__ == "__main__":
    asyncio.run(main())
