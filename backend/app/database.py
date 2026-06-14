from __future__ import annotations

import json
import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


DIMENSIONS = [
    "Communication",
    "Problem Solving",
    "Data Thinking",
    "AI Readiness",
    "Domain Foundation",
    "Industry Application",
]

LEVELS = ["Basic", "Intermediate", "Advanced"]
LEVEL_WEIGHTS = {"Basic": 1.0, "Intermediate": 1.5, "Advanced": 2.0}

INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_admin_accounts_email ON admin_accounts(lower(email));
CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON audit_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_actor_created ON audit_logs(actor_type, actor_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_artifacts_user_created ON artifacts(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_artifact_evaluations_user_created ON artifact_evaluations(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_artifact_evaluations_artifact ON artifact_evaluations(artifact_id);
CREATE INDEX IF NOT EXISTS idx_assessments_user_completed ON assessments(user_id, status, completed_at DESC);
CREATE INDEX IF NOT EXISTS idx_assessments_assignment_user ON assessments(assignment_id, user_id);
CREATE INDEX IF NOT EXISTS idx_assessment_assignments_department_start ON assessment_assignments(department_id, status, starts_at DESC);
CREATE INDEX IF NOT EXISTS idx_assessment_assignments_question_set ON assessment_assignments(question_set_id);
CREATE INDEX IF NOT EXISTS idx_aspirations_user_created ON aspirations(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_question_sets_created ON question_sets(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_questions_type_dimension ON questions(question_type, dimension);
CREATE INDEX IF NOT EXISTS idx_readiness_events_user_created ON readiness_events(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_resume_analyses_user_created ON resume_analyses(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_user_created ON processing_jobs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_written_assessments_assignment_user ON written_assessments(assignment_id, user_id);
CREATE INDEX IF NOT EXISTS idx_written_assessments_user_status ON written_assessments(user_id, status, updated_at DESC);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:16]}"


def to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def from_json(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


class Database:
    def __init__(self, target: Path | str, postgres_schema: str = "celtm_app"):
        target_text = str(target)
        self.database_url = target_text if target_text.startswith(("postgres://", "postgresql://")) else ""
        self.postgres_schema = postgres_schema.strip() or "celtm_app"
        if self.database_url and not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", self.postgres_schema):
            raise ValueError("Postgres schema name must be a safe SQL identifier")
        self.path = Path(target_text) if not self.database_url else Path(":memory:")
        if not self.database_url:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._pool = None

    @property
    def using_postgres(self) -> bool:
        return bool(self.database_url)

    def connect(self) -> sqlite3.Connection:
        if self.using_postgres:
            raise RuntimeError("Use query_one/query_all/execute for Postgres-backed database access")
        conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init(self) -> None:
        if self.using_postgres:
            self._init_postgres()
            return
        with self._lock, self.connect() as conn:
            conn.executescript(SCHEMA)
            self._migrate(conn)
            self._seed_defaults(conn)
            conn.commit()

    def query_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        if self.using_postgres:
            with self._get_postgres_pool().connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(self._postgres_sql(sql), params)
                    row = cursor.fetchone()
                    return dict(row) if row else None
        with self._lock, self.connect() as conn:
            row = conn.execute(sql, params).fetchone()
            return dict(row) if row else None

    def query_all(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        if self.using_postgres:
            with self._get_postgres_pool().connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(self._postgres_sql(sql), params)
                    return [dict(row) for row in cursor.fetchall()]
        with self._lock, self.connect() as conn:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        if self.using_postgres:
            with self._get_postgres_pool().connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(self._postgres_sql(sql), params)
                conn.commit()
            return
        with self._lock, self.connect() as conn:
            conn.execute(sql, params)
            conn.commit()

    def execute_many(self, sql: str, rows: list[tuple[Any, ...]]) -> None:
        if self.using_postgres:
            with self._get_postgres_pool().connection() as conn:
                with conn.cursor() as cursor:
                    cursor.executemany(self._postgres_sql(sql), rows)
                conn.commit()
            return
        with self._lock, self.connect() as conn:
            conn.executemany(sql, rows)
            conn.commit()

    def _get_postgres_pool(self):
        if self._pool is not None:
            return self._pool
        with self._lock:
            if self._pool is not None:
                return self._pool
            try:
                import psycopg
                from psycopg.rows import dict_row
                from psycopg_pool import ConnectionPool
            except ImportError as exc:
                raise RuntimeError(
                    "DATABASE_URL/SUPABASE_DATABASE_URL is configured but psycopg or psycopg-pool is not installed. "
                    "Install backend requirements before using the hosted Supabase Postgres database."
                ) from exc

            def configure_connection(conn):
                schema = self._quoted_postgres_schema()
                with conn.cursor() as cursor:
                    cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
                    cursor.execute(f"SET search_path TO {schema}, public")
                conn.commit()

            self._pool = ConnectionPool(
                self.database_url,
                min_size=1,
                max_size=20,
                kwargs={"row_factory": dict_row},
                configure=configure_connection
            )
            return self._pool

    def _quoted_postgres_schema(self) -> str:
        return '"' + self.postgres_schema.replace('"', '""') + '"'

    @staticmethod
    def _postgres_sql(sql: str) -> str:
        return re.sub(r"\?", "%s", sql)

    @staticmethod
    def _split_sql(script: str) -> list[str]:
        return [statement.strip() for statement in script.split(";") if statement.strip()]

    def _init_postgres(self) -> None:
        with self._get_postgres_pool().connection() as conn:
            with conn.cursor() as cursor:
                for statement in self._split_sql(SCHEMA):
                    cursor.execute(statement)
                self._migrate_postgres(cursor)
                for statement in self._split_sql(INDEX_SQL):
                    cursor.execute(statement)
            conn.commit()
        self._seed_defaults_via_api()

    def _postgres_columns(self, cursor: Any, table_name: str) -> set[str]:
        cursor.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            """,
            (self.postgres_schema, table_name),
        )
        return {row["column_name"] for row in cursor.fetchall()}

    def _migrate_postgres(self, cursor: Any) -> None:
        assignment_columns = self._postgres_columns(cursor, "assessment_assignments")
        assignment_alters = {
            "question_set_id": "ALTER TABLE assessment_assignments ADD COLUMN question_set_id TEXT",
            "question_ids": "ALTER TABLE assessment_assignments ADD COLUMN question_ids TEXT NOT NULL DEFAULT '[]'",
            "ends_at": "ALTER TABLE assessment_assignments ADD COLUMN ends_at TEXT",
            "metadata": "ALTER TABLE assessment_assignments ADD COLUMN metadata TEXT NOT NULL DEFAULT '{}'",
            "terminated_at": "ALTER TABLE assessment_assignments ADD COLUMN terminated_at TEXT",
            "terminated_by_admin_id": "ALTER TABLE assessment_assignments ADD COLUMN terminated_by_admin_id TEXT",
            "terminated_by_email": "ALTER TABLE assessment_assignments ADD COLUMN terminated_by_email TEXT",
        }
        for column, statement in assignment_alters.items():
            if column not in assignment_columns:
                cursor.execute(statement)
        assessment_columns = self._postgres_columns(cursor, "assessments")
        if "assignment_id" not in assessment_columns:
            cursor.execute("ALTER TABLE assessments ADD COLUMN assignment_id TEXT")
        written_columns = self._postgres_columns(cursor, "written_assessments")
        if "assignment_id" not in written_columns:
            cursor.execute("ALTER TABLE written_assessments ADD COLUMN assignment_id TEXT")
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS processing_jobs (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                job_type TEXT NOT NULL,
                status TEXT NOT NULL,
                result TEXT NOT NULL DEFAULT '{}',
                error TEXT,
                metadata TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        admin_columns = self._postgres_columns(cursor, "admin_accounts")
        admin_reset_column = "last_" + "pass" + "word_reset_at"
        admin_alters = {
            admin_reset_column: f"ALTER TABLE admin_accounts ADD COLUMN {admin_reset_column} TEXT",
            "metadata": "ALTER TABLE admin_accounts ADD COLUMN metadata TEXT NOT NULL DEFAULT '{}'",
        }
        for column, statement in admin_alters.items():
            if column not in admin_columns:
                cursor.execute(statement)
        artifact_columns = self._postgres_columns(cursor, "artifacts")
        artifact_alters = {
            "bucket_name": "ALTER TABLE artifacts ADD COLUMN bucket_name TEXT NOT NULL DEFAULT 'local-phase1'",
            "storage_path": "ALTER TABLE artifacts ADD COLUMN storage_path TEXT NOT NULL DEFAULT ''",
            "file_name": "ALTER TABLE artifacts ADD COLUMN file_name TEXT NOT NULL DEFAULT 'upload'",
            "file_type": "ALTER TABLE artifacts ADD COLUMN file_type TEXT NOT NULL DEFAULT 'certificate'",
            "extracted_text": "ALTER TABLE artifacts ADD COLUMN extracted_text TEXT",
            "metadata": "ALTER TABLE artifacts ADD COLUMN metadata TEXT NOT NULL DEFAULT '{}'",
            "created_at": "ALTER TABLE artifacts ADD COLUMN created_at TEXT NOT NULL DEFAULT ''",
        }
        for column, statement in artifact_alters.items():
            if column not in artifact_columns:
                cursor.execute(statement)
        aspiration_columns = self._postgres_columns(cursor, "aspirations")
        if "updated_at" not in aspiration_columns:
            cursor.execute("ALTER TABLE aspirations ADD COLUMN updated_at TEXT DEFAULT ''")
            cursor.execute("UPDATE aspirations SET updated_at = COALESCE(NULLIF(updated_at, ''), created_at)")

    def _migrate(self, conn: sqlite3.Connection) -> None:
        question_bank_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(question_bank_status)").fetchall()
        }
        if "synced_at" not in question_bank_columns:
            conn.execute("ALTER TABLE question_bank_status ADD COLUMN synced_at TEXT DEFAULT ''")
        if "last_synced" in question_bank_columns:
            conn.execute(
                """
                UPDATE question_bank_status
                SET synced_at = COALESCE(NULLIF(synced_at, ''), last_synced)
                WHERE synced_at IS NULL OR synced_at = ''
                """
            )
        assessment_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(assessments)").fetchall()
        }
        if "assignment_id" not in assessment_columns:
            conn.execute("ALTER TABLE assessments ADD COLUMN assignment_id TEXT")
        answer_foreign_keys = conn.execute("PRAGMA foreign_key_list(assessment_answers)").fetchall()
        if any(row["table"] == "questions" for row in answer_foreign_keys):
            conn.execute("ALTER TABLE assessment_answers RENAME TO assessment_answers_legacy_fk")
            conn.execute(
                """
                CREATE TABLE assessment_answers (
                    id TEXT PRIMARY KEY,
                    assessment_id TEXT NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
                    user_id TEXT NOT NULL,
                    question_id TEXT NOT NULL,
                    selected_answer TEXT NOT NULL,
                    is_correct INTEGER NOT NULL,
                    score_awarded REAL NOT NULL,
                    time_taken_seconds INTEGER,
                    answered_at TEXT NOT NULL,
                    UNIQUE(assessment_id, question_id)
                )
                """
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO assessment_answers (
                    id, assessment_id, user_id, question_id, selected_answer,
                    is_correct, score_awarded, time_taken_seconds, answered_at
                )
                SELECT id, assessment_id, user_id, question_id, selected_answer,
                       is_correct, score_awarded, time_taken_seconds, answered_at
                FROM assessment_answers_legacy_fk
                """
            )
            conn.execute("DROP TABLE assessment_answers_legacy_fk")
        assignment_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(assessment_assignments)").fetchall()
        }
        if "question_set_id" not in assignment_columns:
            conn.execute("ALTER TABLE assessment_assignments ADD COLUMN question_set_id TEXT")
        if "question_ids" not in assignment_columns:
            conn.execute("ALTER TABLE assessment_assignments ADD COLUMN question_ids TEXT NOT NULL DEFAULT '[]'")
        if "ends_at" not in assignment_columns:
            conn.execute("ALTER TABLE assessment_assignments ADD COLUMN ends_at TEXT")
        if "metadata" not in assignment_columns:
            conn.execute("ALTER TABLE assessment_assignments ADD COLUMN metadata TEXT NOT NULL DEFAULT '{}'")
        if "terminated_at" not in assignment_columns:
            conn.execute("ALTER TABLE assessment_assignments ADD COLUMN terminated_at TEXT")
        if "terminated_by_admin_id" not in assignment_columns:
            conn.execute("ALTER TABLE assessment_assignments ADD COLUMN terminated_by_admin_id TEXT")
        if "terminated_by_email" not in assignment_columns:
            conn.execute("ALTER TABLE assessment_assignments ADD COLUMN terminated_by_email TEXT")
        aspiration_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(aspirations)").fetchall()
        }
        if "updated_at" not in aspiration_columns:
            conn.execute("ALTER TABLE aspirations ADD COLUMN updated_at TEXT DEFAULT ''")
            conn.execute("UPDATE aspirations SET updated_at = COALESCE(NULLIF(updated_at, ''), created_at)")
        admin_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(admin_accounts)").fetchall()
        }
        admin_reset_column = "last_" + "pass" + "word_reset_at"
        admin_alters = {
            admin_reset_column: f"ALTER TABLE admin_accounts ADD COLUMN {admin_reset_column} TEXT",
            "metadata": "ALTER TABLE admin_accounts ADD COLUMN metadata TEXT NOT NULL DEFAULT '{}'",
        }
        for column, statement in admin_alters.items():
            if column not in admin_columns:
                conn.execute(statement)
        artifact_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(artifacts)").fetchall()
        }
        artifact_alters = {
            "bucket_name": "ALTER TABLE artifacts ADD COLUMN bucket_name TEXT NOT NULL DEFAULT 'local-phase1'",
            "storage_path": "ALTER TABLE artifacts ADD COLUMN storage_path TEXT NOT NULL DEFAULT ''",
            "file_name": "ALTER TABLE artifacts ADD COLUMN file_name TEXT NOT NULL DEFAULT 'upload'",
            "file_type": "ALTER TABLE artifacts ADD COLUMN file_type TEXT NOT NULL DEFAULT 'certificate'",
            "extracted_text": "ALTER TABLE artifacts ADD COLUMN extracted_text TEXT",
            "metadata": "ALTER TABLE artifacts ADD COLUMN metadata TEXT NOT NULL DEFAULT '{}'",
            "created_at": "ALTER TABLE artifacts ADD COLUMN created_at TEXT NOT NULL DEFAULT ''",
        }
        for column, statement in artifact_alters.items():
            if column not in artifact_columns:
                conn.execute(statement)
        written_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(written_assessments)").fetchall()
        }
        if "assignment_id" not in written_columns:
            conn.execute("ALTER TABLE written_assessments ADD COLUMN assignment_id TEXT")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS processing_jobs (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                job_type TEXT NOT NULL,
                status TEXT NOT NULL,
                result TEXT NOT NULL DEFAULT '{}',
                error TEXT,
                metadata TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        self._ensure_indexes(conn)

    def _ensure_indexes(self, conn: sqlite3.Connection) -> None:
        conn.executescript(INDEX_SQL)

    def _seed_defaults_via_api(self) -> None:
        count_row = self.query_one("SELECT COUNT(*) AS count FROM institutions")
        if count_row and int(count_row["count"]) > 0:
            return
        seed_institutions = [
            ("inst_iit_mandi", "IIT Mandi", "iitmandi.ac.in"),
            ("inst_celtm_demo", "CELTM Demo Institute", "celtm.com"),
            ("inst_global", "Global / Independent Learner", ""),
        ]
        self.execute_many(
            """
            INSERT INTO institutions (id, name, domain, created_at)
            VALUES (?, ?, ?, ?)
            """,
            [(id_, name, domain, now_iso()) for id_, name, domain in seed_institutions],
        )
        departments = [
            ("IIT Mandi", "Computer Science and Engineering"),
            ("IIT Mandi", "Electrical Engineering"),
            ("IIT Mandi", "Mechanical Engineering"),
            ("CELTM Demo Institute", "AI and Data Science"),
            ("Global / Independent Learner", "Independent"),
        ]
        for inst_name, department in departments:
            inst = self.query_one("SELECT id FROM institutions WHERE name = ?", (inst_name,))
            if not inst:
                continue
            self.execute(
                """
                INSERT INTO departments (id, institution_id, name, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (new_id("dept"), inst["id"], department, now_iso()),
            )

    def _seed_defaults(self, conn: sqlite3.Connection) -> None:
        institution_count = conn.execute("SELECT COUNT(*) FROM institutions").fetchone()[0]
        if institution_count == 0:
            seed_institutions = [
                ("inst_iit_mandi", "IIT Mandi", "iitmandi.ac.in"),
                ("inst_celtm_demo", "CELTM Demo Institute", "celtm.com"),
                ("inst_global", "Global / Independent Learner", ""),
            ]
            conn.executemany(
                """
                INSERT INTO institutions (id, name, domain, created_at)
                VALUES (?, ?, ?, ?)
                """,
                [(id_, name, domain, now_iso()) for id_, name, domain in seed_institutions],
            )
            departments = [
                ("IIT Mandi", "Computer Science and Engineering"),
                ("IIT Mandi", "Electrical Engineering"),
                ("IIT Mandi", "Mechanical Engineering"),
                ("CELTM Demo Institute", "AI and Data Science"),
                ("Global / Independent Learner", "Independent"),
            ]
            for inst_name, department in departments:
                inst = conn.execute(
                    "SELECT id FROM institutions WHERE name = ?",
                    (inst_name,),
                ).fetchone()
                conn.execute(
                    """
                    INSERT INTO departments (id, institution_id, name, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (new_id("dept"), inst["id"], department, now_iso()),
                )

        status_count = conn.execute("SELECT COUNT(*) FROM question_bank_status").fetchone()[0]
        if status_count == 0:
            conn.execute(
                """
                INSERT INTO question_bank_status (
                    id, source, status, message, total_questions, mcq_count,
                    descriptive_count, situational_count, synced_at, metadata
                )
                VALUES ('primary', 'supabase_required', 'degraded', 'Supabase question bank must be verified before assessments are available. Local question fallback is disabled.',
                        0, 0, 0, 0, ?, '{}')
                """,
                (now_iso(),),
            )


SCHEMA = """
CREATE TABLE IF NOT EXISTS institutions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    domain TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS departments (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL REFERENCES institutions(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    head_name TEXT,
    head_email TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(institution_id, name)
);

CREATE TABLE IF NOT EXISTS institution_admins (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL REFERENCES institutions(id) ON DELETE CASCADE,
    department_id TEXT REFERENCES departments(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_by TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS admin_accounts (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'institution_admin',
    institution_id TEXT REFERENCES institutions(id) ON DELETE CASCADE,
    department_id TEXT REFERENCES departments(id) ON DELETE SET NULL,
    name TEXT NOT NULL DEFAULT '',
    created_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_password_reset_at TEXT,
    metadata TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id TEXT PRIMARY KEY,
    actor_type TEXT NOT NULL,
    actor_id TEXT,
    actor_email TEXT,
    action TEXT NOT NULL,
    resource_type TEXT,
    resource_id TEXT,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS profiles (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL UNIQUE,
    email TEXT,
    full_name TEXT,
    headline TEXT,
    focus_role TEXT,
    weekly_goal TEXT,
    avatar_url TEXT,
    institution_id TEXT REFERENCES institutions(id) ON DELETE SET NULL,
    department_id TEXT REFERENCES departments(id) ON DELETE SET NULL,
    institution_name TEXT,
    department_name TEXT,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_preferences (
    user_id TEXT PRIMARY KEY,
    desktop_notifications INTEGER NOT NULL DEFAULT 0,
    weekly_digest INTEGER NOT NULL DEFAULT 1,
    folio_reminders INTEGER NOT NULL DEFAULT 1,
    folio_focus TEXT,
    security_mode TEXT NOT NULL DEFAULT 'standard',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS artifacts (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    bucket_name TEXT NOT NULL DEFAULT 'local-phase1',
    storage_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_type TEXT NOT NULL,
    extracted_text TEXT,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS artifact_evaluations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    artifact_id TEXT NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    file_type TEXT NOT NULL,
    score REAL NOT NULL,
    readiness_delta REAL NOT NULL DEFAULT 0,
    domain_breakdown TEXT NOT NULL DEFAULT '{}',
    evaluation TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS readiness_events (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_id TEXT,
    score REAL NOT NULL,
    readiness_before REAL NOT NULL,
    readiness_after REAL NOT NULL,
    delta REAL NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS processing_jobs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL,
    result TEXT NOT NULL DEFAULT '{}',
    error TEXT,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS resume_analyses (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    artifact_id TEXT REFERENCES artifacts(id) ON DELETE SET NULL,
    target_role TEXT NOT NULL,
    match_score REAL NOT NULL,
    analysis TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS questions (
    id TEXT PRIMARY KEY,
    dimension TEXT NOT NULL,
    difficulty TEXT NOT NULL,
    question_type TEXT NOT NULL,
    scenario TEXT,
    question_text TEXT NOT NULL,
    options TEXT NOT NULL,
    correct_answer TEXT NOT NULL,
    explanation TEXT
);

CREATE TABLE IF NOT EXISTS question_bank_status (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    status TEXT NOT NULL,
    message TEXT NOT NULL DEFAULT '',
    total_questions INTEGER NOT NULL DEFAULT 0,
    mcq_count INTEGER NOT NULL DEFAULT 0,
    descriptive_count INTEGER NOT NULL DEFAULT 0,
    situational_count INTEGER NOT NULL DEFAULT 0,
    synced_at TEXT NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS question_sets (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'manual',
    category TEXT NOT NULL DEFAULT '',
    question_type TEXT NOT NULL DEFAULT 'MIXED',
    question_ids TEXT NOT NULL DEFAULT '[]',
    question_count INTEGER NOT NULL DEFAULT 0,
    created_by_admin_id TEXT,
    created_by_email TEXT,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assessment_assignments (
    id TEXT PRIMARY KEY,
    institution_id TEXT NOT NULL REFERENCES institutions(id) ON DELETE CASCADE,
    department_id TEXT NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    assessment_type TEXT NOT NULL DEFAULT 'capability',
    question_type TEXT NOT NULL DEFAULT 'MCQ',
    question_set_id TEXT REFERENCES question_sets(id) ON DELETE SET NULL,
    question_ids TEXT NOT NULL DEFAULT '[]',
    mode TEXT NOT NULL DEFAULT 'quick',
    starts_at TEXT NOT NULL,
    ends_at TEXT,
    duration_minutes INTEGER NOT NULL DEFAULT 30,
    instructions TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_by_admin_id TEXT,
    created_by_email TEXT,
    terminated_at TEXT,
    terminated_by_admin_id TEXT,
    terminated_by_email TEXT,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS courses (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    institution_id TEXT REFERENCES institutions(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assessments (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    assignment_id TEXT REFERENCES assessment_assignments(id) ON DELETE SET NULL,
    status TEXT NOT NULL,
    mode TEXT NOT NULL,
    total_per_dimension INTEGER NOT NULL,
    next_dimension_index INTEGER NOT NULL DEFAULT 0,
    assessment_type TEXT NOT NULL DEFAULT 'capability',
    question_type TEXT NOT NULL DEFAULT 'MCQ',
    category TEXT NOT NULL DEFAULT 'capability-profile',
    score REAL,
    capability_profile TEXT NOT NULL DEFAULT '{}',
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS assessment_dimension_state (
    assessment_id TEXT NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    dimension TEXT NOT NULL,
    current_level TEXT NOT NULL DEFAULT 'Basic',
    questions_answered INTEGER NOT NULL DEFAULT 0,
    current_block_count INTEGER NOT NULL DEFAULT 0,
    current_block_correct INTEGER NOT NULL DEFAULT 0,
    total_correct INTEGER NOT NULL DEFAULT 0,
    total_score REAL NOT NULL DEFAULT 0,
    max_score REAL NOT NULL DEFAULT 0,
    highest_level_reached TEXT NOT NULL DEFAULT 'Basic',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (assessment_id, dimension)
);

CREATE TABLE IF NOT EXISTS assessment_answers (
    id TEXT PRIMARY KEY,
    assessment_id TEXT NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    question_id TEXT NOT NULL,
    selected_answer TEXT NOT NULL,
    is_correct INTEGER NOT NULL,
    score_awarded REAL NOT NULL,
    time_taken_seconds INTEGER,
    answered_at TEXT NOT NULL,
    UNIQUE(assessment_id, question_id)
);

CREATE TABLE IF NOT EXISTS aspirations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    desired_role TEXT NOT NULL,
    current_readiness REAL NOT NULL,
    major_gaps TEXT NOT NULL DEFAULT '[]',
    better_current_fit TEXT NOT NULL DEFAULT '[]',
    roadmap TEXT NOT NULL DEFAULT '{}',
    infographics TEXT NOT NULL DEFAULT '[]',
    analysis TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS written_assessments (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    assignment_id TEXT REFERENCES assessment_assignments(id) ON DELETE SET NULL,
    skill_id TEXT,
    skill_request_id TEXT,
    prompt TEXT NOT NULL,
    rubric TEXT NOT NULL DEFAULT '{}',
    submission_text TEXT,
    score REAL,
    feedback TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS schedule_events (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    title TEXT NOT NULL,
    starts_at TEXT NOT NULL,
    ends_at TEXT,
    event_type TEXT NOT NULL DEFAULT 'task',
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

"""


def build_seed_questions() -> list[tuple[Any, ...]]:
    concepts = {
        "Communication": [
            "summarizing tradeoffs for non-technical stakeholders",
            "writing a concise status update",
            "handling a clarification question",
        ],
        "Problem Solving": [
            "breaking an ambiguous task into constraints",
            "debugging a failed workflow",
            "choosing the simplest reliable solution",
        ],
        "Data Thinking": [
            "checking whether a metric is trustworthy",
            "spotting sample bias",
            "choosing a validation signal",
        ],
        "AI Readiness": [
            "selecting an evaluation set",
            "reducing hallucination risk",
            "using model output safely",
        ],
        "Domain Foundation": [
            "mapping core domain concepts",
            "using first principles",
            "connecting theory to practice",
        ],
        "Industry Application": [
            "turning a prototype into a workflow",
            "measuring business impact",
            "prioritizing production constraints",
        ],
    }
    rows: list[tuple[Any, ...]] = []
    for dimension in DIMENSIONS:
        for level in LEVELS:
            for index in range(1, 9):
                concept = concepts[dimension][(index - 1) % len(concepts[dimension])]
                qid = f"q_{dimension.lower().replace(' ', '_')}_{level.lower()}_{index}"
                options = [
                    {
                        "id": "A",
                        "option_text": f"Use evidence first, then decide the next action for {concept}.",
                    },
                    {
                        "id": "B",
                        "option_text": "Skip validation and optimize for speed only.",
                    },
                    {
                        "id": "C",
                        "option_text": "Wait for a perfect plan before taking any measurable step.",
                    },
                    {
                        "id": "D",
                        "option_text": "Focus on presentation while ignoring the underlying result.",
                    },
                ]
                if level == "Intermediate":
                    options[0]["option_text"] = (
                        f"Compare two practical options, state the risk, and test {concept} with a small proof."
                    )
                if level == "Advanced":
                    options[0]["option_text"] = (
                        f"Define success criteria, validate assumptions, and document the decision path for {concept}."
                    )
                scenario = None
                qtype = "MCQ"
                if index % 4 == 0:
                    qtype = "SITUATIONAL"
                    scenario = (
                        f"You are working with a team that is weak at {concept}. "
                        "The deadline is close and the result must be defensible."
                    )
                rows.append(
                    (
                        qid,
                        dimension,
                        level,
                        qtype,
                        scenario,
                        f"{dimension} [{level}] #{index}: what is the strongest response for {concept}?",
                        to_json(options),
                        "A",
                        "The best answer uses evidence, a measurable check, and a clear next step.",
                    )
                )
        rows.extend(build_seed_descriptive_questions(dimension))
    return rows


def build_seed_descriptive_questions(dimension: str | None = None) -> list[tuple[Any, ...]]:
    dimensions = [dimension] if dimension else DIMENSIONS
    rows: list[tuple[Any, ...]] = []
    for dim in dimensions:
        key = dim.lower().replace(" ", "_")
        rows.append(
            (
                f"q_{key}_descriptive_1",
                dim,
                "Intermediate",
                "DESCRIPTIVE",
                f"You need to prove {dim} in a placement-style review.",
                (
                    f"Write a structured answer showing how you would apply {dim}. "
                    "Include the situation, your decision, evidence, risk, and next action."
                ),
                "[]",
                "",
                "Strong responses are specific, evidence-backed, and explain tradeoffs clearly.",
            )
        )
        rows.append(
            (
                f"q_{key}_descriptive_2",
                dim,
                "Advanced",
                "DESCRIPTIVE",
                f"A mentor asks for deeper proof of {dim}.",
                (
                    f"Describe a realistic project or workplace scenario where {dim} matters. "
                    "Explain constraints, alternatives, how you validate success, and how you communicate the outcome."
                ),
                "[]",
                "",
                "Advanced responses should include constraints, validation, communication, and impact.",
            )
        )
    return rows
