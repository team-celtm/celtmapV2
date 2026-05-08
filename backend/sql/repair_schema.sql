-- REPAIR SCHEMA SCRIPT
-- Run this in your Supabase SQL Editor to resolve PGRST205 and other schema issues.

-- 1. Create public.users table (expected by legacy sync code)
CREATE TABLE IF NOT EXISTS public.users (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT UNIQUE NOT NULL,
    full_name TEXT,
    role TEXT DEFAULT 'student',
    target_role_id UUID,
    avatar_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. profiles (full sync)
DO $$ 
BEGIN 
    ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();
    ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();
    ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS headline TEXT;
    ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS focus_role TEXT;
    ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS weekly_goal TEXT;
    ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS avatar_url TEXT;
    ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;
END $$;

-- 3. subjects
CREATE TABLE IF NOT EXISTS public.subjects (id UUID PRIMARY KEY DEFAULT gen_random_uuid());
DO $$ 
BEGIN 
    ALTER TABLE public.subjects ADD COLUMN IF NOT EXISTS subject_id TEXT UNIQUE;
    ALTER TABLE public.subjects ADD COLUMN IF NOT EXISTS subject_name TEXT;
    ALTER TABLE public.subjects ADD COLUMN IF NOT EXISTS normalized_name TEXT UNIQUE;
    ALTER TABLE public.subjects ADD COLUMN IF NOT EXISTS track TEXT;
    ALTER TABLE public.subjects ADD COLUMN IF NOT EXISTS description TEXT;
    ALTER TABLE public.subjects ADD COLUMN IF NOT EXISTS domain_group TEXT;
    ALTER TABLE public.subjects ADD COLUMN IF NOT EXISTS industry_relevance TEXT;
    ALTER TABLE public.subjects ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
    ALTER TABLE public.subjects ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;
    ALTER TABLE public.subjects ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();
    ALTER TABLE public.subjects ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();
END $$;

-- 4. skills
CREATE TABLE IF NOT EXISTS public.skills (id UUID PRIMARY KEY DEFAULT gen_random_uuid());
DO $$ 
BEGIN 
    ALTER TABLE public.skills ADD COLUMN IF NOT EXISTS skill_id TEXT UNIQUE;
    ALTER TABLE public.skills ADD COLUMN IF NOT EXISTS subject_ref_id UUID REFERENCES public.subjects(id) ON DELETE SET NULL;
    ALTER TABLE public.skills ADD COLUMN IF NOT EXISTS skill_name TEXT UNIQUE;
    ALTER TABLE public.skills ADD COLUMN IF NOT EXISTS normalized_name TEXT UNIQUE;
    ALTER TABLE public.skills ADD COLUMN IF NOT EXISTS description TEXT;
    ALTER TABLE public.skills ADD COLUMN IF NOT EXISTS industry_usage TEXT;
    ALTER TABLE public.skills ADD COLUMN IF NOT EXISTS hidden_skills_supported TEXT[] DEFAULT '{}';
    ALTER TABLE public.skills ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active';
    ALTER TABLE public.skills ADD COLUMN IF NOT EXISTS is_generated BOOLEAN DEFAULT FALSE;
    ALTER TABLE public.skills ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
    ALTER TABLE public.skills ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;
    ALTER TABLE public.skills ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();
    ALTER TABLE public.skills ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();
END $$;

-- 5. subskills
CREATE TABLE IF NOT EXISTS public.subskills (id UUID PRIMARY KEY DEFAULT gen_random_uuid());
DO $$ 
BEGIN 
    ALTER TABLE public.subskills ADD COLUMN IF NOT EXISTS subskill_id TEXT UNIQUE;
    ALTER TABLE public.subskills ADD COLUMN IF NOT EXISTS skill_ref_id UUID REFERENCES public.skills(id) ON DELETE CASCADE;
    ALTER TABLE public.subskills ADD COLUMN IF NOT EXISTS subskill_name TEXT;
    ALTER TABLE public.subskills ADD COLUMN IF NOT EXISTS normalized_name TEXT;
    ALTER TABLE public.subskills ADD COLUMN IF NOT EXISTS description TEXT;
    ALTER TABLE public.subskills ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
    ALTER TABLE public.subskills ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;
    ALTER TABLE public.subskills ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();
    ALTER TABLE public.subskills ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();
END $$;

-- 5. questions (ensure all production columns exist and have correct types)
DO $$ 
BEGIN 
    -- Ensure columns exist first
    ALTER TABLE public.questions ADD COLUMN IF NOT EXISTS source_question_id TEXT;
    ALTER TABLE public.questions ADD COLUMN IF NOT EXISTS subject_id TEXT DEFAULT '';
    ALTER TABLE public.questions ADD COLUMN IF NOT EXISTS subject_name TEXT;
    
    -- Auxiliary columns for ingestion mapping (to avoid UUID type conflicts)
    ALTER TABLE public.questions ADD COLUMN IF NOT EXISTS source_skill_id TEXT;
    ALTER TABLE public.questions ADD COLUMN IF NOT EXISTS source_subskill_id TEXT;
    
    -- Legacy columns (ensure they exist as UUIDs - or whatever they currently are)
    ALTER TABLE public.questions ADD COLUMN IF NOT EXISTS skill_id UUID;
    ALTER TABLE public.questions ADD COLUMN IF NOT EXISTS subskill_id UUID;
    ALTER TABLE public.questions ADD COLUMN IF NOT EXISTS skill_name TEXT;
    ALTER TABLE public.questions ADD COLUMN IF NOT EXISTS subskill_name TEXT;
    
    ALTER TABLE public.questions ADD COLUMN IF NOT EXISTS role_ids TEXT[] DEFAULT '{}';
    ALTER TABLE public.questions ADD COLUMN IF NOT EXISTS question_text_normalized TEXT;
    ALTER TABLE public.questions ADD COLUMN IF NOT EXISTS category TEXT;
    ALTER TABLE public.questions ADD COLUMN IF NOT EXISTS difficulty TEXT DEFAULT 'unassigned';
    ALTER TABLE public.questions ADD COLUMN IF NOT EXISTS sample_answer TEXT;
    ALTER TABLE public.questions ADD COLUMN IF NOT EXISTS explanation TEXT;
    ALTER TABLE public.questions ADD COLUMN IF NOT EXISTS expected_concepts TEXT[] DEFAULT '{}';
    ALTER TABLE public.questions ADD COLUMN IF NOT EXISTS hidden_skills_targeted TEXT[] DEFAULT '{}';
    ALTER TABLE public.questions ADD COLUMN IF NOT EXISTS evaluation_mode TEXT;
    ALTER TABLE public.questions ADD COLUMN IF NOT EXISTS rag_tags TEXT[] DEFAULT '{}';
    ALTER TABLE public.questions ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;
    ALTER TABLE public.questions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();
END $$;

-- Add unique constraint on source_question_id for upserts
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'questions_source_question_id_key' 
        AND conrelid = 'public.questions'::regclass
    ) THEN
        ALTER TABLE public.questions ADD CONSTRAINT questions_source_question_id_key UNIQUE (source_question_id);
    END IF;
END $$;

-- 7a. roles (patch missing production columns)
DO $$
BEGIN
    ALTER TABLE public.roles ADD COLUMN IF NOT EXISTS role_id TEXT UNIQUE;
    ALTER TABLE public.roles ADD COLUMN IF NOT EXISTS normalized_name TEXT UNIQUE;
    ALTER TABLE public.roles ADD COLUMN IF NOT EXISTS role_category TEXT;
    ALTER TABLE public.roles ADD COLUMN IF NOT EXISTS description TEXT;
    ALTER TABLE public.roles ADD COLUMN IF NOT EXISTS target_industries TEXT[] DEFAULT '{}';
    ALTER TABLE public.roles ADD COLUMN IF NOT EXISTS required_subjects TEXT[] DEFAULT '{}';
    ALTER TABLE public.roles ADD COLUMN IF NOT EXISTS core_skills TEXT[] DEFAULT '{}';
    ALTER TABLE public.roles ADD COLUMN IF NOT EXISTS required_skills TEXT[] DEFAULT '{}';
    ALTER TABLE public.roles ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;
    ALTER TABLE public.roles ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
    ALTER TABLE public.roles ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();
    ALTER TABLE public.roles ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();
END $$;

-- 7b. role_requirements (patch missing production columns)
DO $$
BEGIN
    ALTER TABLE public.role_requirements ADD COLUMN IF NOT EXISTS weight NUMERIC DEFAULT 1.0;
    ALTER TABLE public.role_requirements ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;
    ALTER TABLE public.role_requirements ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();
    ALTER TABLE public.role_requirements ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();
    ALTER TABLE public.role_requirements ADD COLUMN IF NOT EXISTS role_name TEXT;
    ALTER TABLE public.role_requirements ADD COLUMN IF NOT EXISTS skill_name TEXT;
END $$;
-- Add unique constraint on (role_name, skill_name) if not present
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'role_requirements_role_name_skill_name_key'
        AND conrelid = 'public.role_requirements'::regclass
    ) THEN
        ALTER TABLE public.role_requirements
            ADD CONSTRAINT role_requirements_role_name_skill_name_key
            UNIQUE (role_name, skill_name);
    END IF;
END $$;

-- 7b. user_skills
CREATE TABLE IF NOT EXISTS public.user_skills (id UUID PRIMARY KEY DEFAULT gen_random_uuid());
DO $$ 
BEGIN 
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'user_skills' AND column_name = 'verified_score') THEN
        ALTER TABLE public.user_skills RENAME COLUMN verified_score TO proficiency_score;
    END IF;
    ALTER TABLE public.user_skills ADD COLUMN IF NOT EXISTS proficiency_score NUMERIC(5,2) DEFAULT 0;
    ALTER TABLE public.user_skills ADD COLUMN IF NOT EXISTS assessment_score NUMERIC(5,2);
    ALTER TABLE public.user_skills ADD COLUMN IF NOT EXISTS written_score NUMERIC(5,2);
    ALTER TABLE public.user_skills ADD COLUMN IF NOT EXISTS interview_score NUMERIC(5,2);
    ALTER TABLE public.user_skills ADD COLUMN IF NOT EXISTS artifact_score NUMERIC(5,2);
    ALTER TABLE public.user_skills ADD COLUMN IF NOT EXISTS source TEXT;
    ALTER TABLE public.user_skills ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;
    ALTER TABLE public.user_skills ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();
    ALTER TABLE public.user_skills ADD COLUMN IF NOT EXISTS user_id UUID;
    ALTER TABLE public.user_skills ADD COLUMN IF NOT EXISTS skill_id TEXT;
END $$;

-- 7. hidden_skill_candidates
CREATE TABLE IF NOT EXISTS public.hidden_skill_candidates (id UUID PRIMARY KEY DEFAULT gen_random_uuid());
DO $$ 
BEGIN 
    ALTER TABLE public.hidden_skill_candidates ADD COLUMN IF NOT EXISTS user_id UUID;
    ALTER TABLE public.hidden_skill_candidates ADD COLUMN IF NOT EXISTS skill_name TEXT;
    ALTER TABLE public.hidden_skill_candidates ADD COLUMN IF NOT EXISTS skill_id TEXT;
    ALTER TABLE public.hidden_skill_candidates ADD COLUMN IF NOT EXISTS confidence_score NUMERIC(5,2);
    ALTER TABLE public.hidden_skill_candidates ADD COLUMN IF NOT EXISTS source TEXT;
    ALTER TABLE public.hidden_skill_candidates ADD COLUMN IF NOT EXISTS evidence TEXT;
    ALTER TABLE public.hidden_skill_candidates ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'pending';
    ALTER TABLE public.hidden_skill_candidates ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;
    ALTER TABLE public.hidden_skill_candidates ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ;
END $$;

-- 8. domain_events
CREATE TABLE IF NOT EXISTS public.domain_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type TEXT NOT NULL,
    aggregate_type TEXT NOT NULL,
    aggregate_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    retry_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    processing_started_at TIMESTAMPTZ,
    processed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 9. celtmind_ingestion_runs
CREATE TABLE IF NOT EXISTS public.celtmind_ingestion_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    summary JSONB NOT NULL DEFAULT '[]'::jsonb,
    error TEXT
);

-- 10. celtmind_file_registry
CREATE TABLE IF NOT EXISTS public.celtmind_file_registry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_name TEXT NOT NULL UNIQUE,
    checksum TEXT NOT NULL,
    category TEXT NOT NULL,
    last_ingested_at TIMESTAMPTZ NOT NULL
);

-- 11. question_options (production schema)
CREATE TABLE IF NOT EXISTS public.question_options (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question_id UUID REFERENCES public.questions(id) ON DELETE CASCADE,
    option_key TEXT NOT NULL,
    option_text TEXT NOT NULL,
    is_correct BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(question_id, option_key)
);

-- 12. rag_documents (ensure it matches RagService expectations)
CREATE TABLE IF NOT EXISTS public.rag_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope TEXT DEFAULT 'global',
    user_id UUID,
    artifact_id UUID,
    source_type TEXT DEFAULT 'knowledge',
    source_ref TEXT,
    skill_id TEXT,
    subskill_id TEXT,
    title TEXT,
    content_chunk TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding vector(1536),
    dedupe_hash TEXT NOT NULL UNIQUE,
    access_count INTEGER NOT NULL DEFAULT 0,
    last_accessed_at TIMESTAMPTZ,
    archived_at TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- Patch existing rag_documents if columns are missing (table may already exist)
DO $$
BEGIN
    ALTER TABLE public.rag_documents ADD COLUMN IF NOT EXISTS artifact_id UUID;
    ALTER TABLE public.rag_documents ADD COLUMN IF NOT EXISTS content_chunk TEXT;
    ALTER TABLE public.rag_documents ADD COLUMN IF NOT EXISTS scope TEXT DEFAULT 'global';
    ALTER TABLE public.rag_documents ADD COLUMN IF NOT EXISTS source_type TEXT DEFAULT 'knowledge';
    ALTER TABLE public.rag_documents ADD COLUMN IF NOT EXISTS source_ref TEXT;
    ALTER TABLE public.rag_documents ADD COLUMN IF NOT EXISTS skill_id TEXT;
    ALTER TABLE public.rag_documents ADD COLUMN IF NOT EXISTS subskill_id TEXT;
    ALTER TABLE public.rag_documents ADD COLUMN IF NOT EXISTS title TEXT;
    ALTER TABLE public.rag_documents ADD COLUMN IF NOT EXISTS access_count INTEGER DEFAULT 0;
    ALTER TABLE public.rag_documents ADD COLUMN IF NOT EXISTS last_accessed_at TIMESTAMPTZ;
    ALTER TABLE public.rag_documents ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ;
    ALTER TABLE public.rag_documents ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
    ALTER TABLE public.rag_documents ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();
    -- Ensure dedupe_hash column and unique constraint exist
    ALTER TABLE public.rag_documents ADD COLUMN IF NOT EXISTS dedupe_hash TEXT;
END $$;

-- 13. ai_call_logs (for ops logging during ingestion)
CREATE TABLE IF NOT EXISTS public.ai_call_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    operation TEXT NOT NULL,
    prompt_hash TEXT,
    cache_hit BOOLEAN NOT NULL DEFAULT FALSE,
    latency_ms INTEGER,
    input_tokens INTEGER,
    output_tokens INTEGER,
    status TEXT NOT NULL,
    source_entity_type TEXT,
    source_entity_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 15. user_answers (for MCQ responses)
CREATE TABLE IF NOT EXISTS public.user_answers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assessment_id UUID REFERENCES public.assessments(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    question_id UUID REFERENCES public.questions(id) ON DELETE CASCADE,
    selected_option_id UUID REFERENCES public.question_options(id) ON DELETE SET NULL,
    is_correct BOOLEAN,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 14. Unified uploaded_artifacts schema
CREATE TABLE IF NOT EXISTS public.uploaded_artifacts (id UUID PRIMARY KEY DEFAULT gen_random_uuid());
DO $$
BEGIN
    ALTER TABLE public.uploaded_artifacts ADD COLUMN IF NOT EXISTS user_id UUID;
    -- Try to add FK if user_id was just created or exists
    BEGIN
        ALTER TABLE public.uploaded_artifacts ADD CONSTRAINT uploaded_artifacts_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;
    EXCEPTION WHEN duplicate_object or dependent_objects_still_exist THEN
        -- Already exists or other issue
    END;

    ALTER TABLE public.uploaded_artifacts ADD COLUMN IF NOT EXISTS bucket_name TEXT;
    ALTER TABLE public.uploaded_artifacts ADD COLUMN IF NOT EXISTS storage_path TEXT;
    ALTER TABLE public.uploaded_artifacts ADD COLUMN IF NOT EXISTS file_name TEXT NOT NULL DEFAULT 'untitled';
    ALTER TABLE public.uploaded_artifacts ADD COLUMN IF NOT EXISTS file_type TEXT NOT NULL DEFAULT 'document';
    ALTER TABLE public.uploaded_artifacts ADD COLUMN IF NOT EXISTS file_url TEXT;
    ALTER TABLE public.uploaded_artifacts ADD COLUMN IF NOT EXISTS extracted_text TEXT;
    ALTER TABLE public.uploaded_artifacts ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb;
    ALTER TABLE public.uploaded_artifacts ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
    ALTER TABLE public.uploaded_artifacts ADD COLUMN IF NOT EXISTS processed_at TIMESTAMPTZ;
    
    -- Ensure storage_path unique if it exists and is not null
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'uploaded_artifacts_storage_path_key' 
        AND conrelid = 'public.uploaded_artifacts'::regclass
    ) THEN
        BEGIN
            ALTER TABLE public.uploaded_artifacts ADD CONSTRAINT uploaded_artifacts_storage_path_key UNIQUE (storage_path);
        EXCEPTION WHEN others THEN
            -- Might fail if null values or existing duplicates
        END;
    END IF;
END $$;

-- 15. Grant Permissions
GRANT ALL ON public.user_preferences TO service_role;
GRANT ALL ON public.uploaded_artifacts TO service_role;
GRANT ALL ON public.user_answers TO service_role;
GRANT ALL ON public.user_skills TO service_role;
GRANT ALL ON public.hidden_skill_candidates TO service_role;
GRANT ALL ON public.domain_events TO service_role;
GRANT ALL ON public.celtmind_ingestion_runs TO service_role;
GRANT ALL ON public.celtmind_file_registry TO service_role;
GRANT ALL ON public.rag_documents TO service_role;
GRANT ALL ON public.ai_call_logs TO service_role;

-- 14. RELOAD SCHEMA CACHE
NOTIFY pgrst, 'reload schema';
