-- CELTM hosted Supabase/Postgres migration for admin credentials and scheduled assessments.
-- Run this in Supabase SQL editor if the hosted database already exists.
-- Fresh hosted deployments can instead set DATABASE_URL or SUPABASE_DATABASE_URL;
-- backend/app/database.py will create the full schema on startup.

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

ALTER TABLE assessment_assignments ADD COLUMN IF NOT EXISTS ends_at TEXT;
ALTER TABLE assessment_assignments ADD COLUMN IF NOT EXISTS terminated_at TEXT;
ALTER TABLE assessment_assignments ADD COLUMN IF NOT EXISTS terminated_by_admin_id TEXT;
ALTER TABLE assessment_assignments ADD COLUMN IF NOT EXISTS terminated_by_email TEXT;
ALTER TABLE assessment_assignments ADD COLUMN IF NOT EXISTS question_set_id TEXT;
ALTER TABLE assessment_assignments ADD COLUMN IF NOT EXISTS question_ids TEXT NOT NULL DEFAULT '[]';
ALTER TABLE assessment_assignments ADD COLUMN IF NOT EXISTS metadata TEXT NOT NULL DEFAULT '{}';

INSERT INTO admin_accounts (
    id, email, password_hash, role, institution_id, department_id,
    name, created_by, created_at, updated_at
)
SELECT id, email, password_hash, 'institution_admin', institution_id, department_id,
       name, created_by, created_at, created_at
FROM institution_admins
ON CONFLICT (id) DO NOTHING;

CREATE INDEX IF NOT EXISTS idx_admin_accounts_email ON admin_accounts(lower(email));
CREATE INDEX IF NOT EXISTS idx_assessment_assignments_department_start
    ON assessment_assignments(department_id, status, starts_at DESC);
CREATE INDEX IF NOT EXISTS idx_assessment_assignments_question_set
    ON assessment_assignments(question_set_id);
