-- CELTM DATABASE PATCH v2
-- This patch resolves PGRST204 (column not found) and PGRST205 (table not found) errors.

-- 1. Fix learning_modules table
ALTER TABLE public.learning_modules 
ADD COLUMN IF NOT EXISTS is_available BOOLEAN NOT NULL DEFAULT TRUE;

-- 2. Create uploaded_artifacts table
CREATE TABLE IF NOT EXISTS public.uploaded_artifacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    file_type TEXT NOT NULL,
    file_url TEXT NOT NULL,
    extracted_text TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Create job_failures table
CREATE TABLE IF NOT EXISTS public.job_failures (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_name TEXT NOT NULL,
    task_id TEXT,
    entity_type TEXT,
    entity_id TEXT,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT NOT NULL,
    traceback TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'failed',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. Grant Permissions
GRANT ALL ON public.uploaded_artifacts TO service_role;
GRANT ALL ON public.job_failures TO service_role;
GRANT ALL ON public.uploaded_artifacts TO anon, authenticated;
GRANT ALL ON public.job_failures TO anon, authenticated;

-- 5. Reload Schema Cache
NOTIFY pgrst, 'reload schema';
