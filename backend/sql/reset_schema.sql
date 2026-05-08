-- Drop all existing tables in public schema except basic ones if needed
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;

-- Restore default permissions
GRANT ALL ON SCHEMA public TO postgres;
GRANT ALL ON SCHEMA public TO public;

-- Profiles
CREATE TABLE public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name TEXT,
    email TEXT,
    role_focus TEXT,
    learning_goal TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public profiles are viewable by everyone." ON public.profiles FOR SELECT USING (true);
CREATE POLICY "Users can insert their own profile." ON public.profiles FOR INSERT WITH CHECK (auth.uid() = id);
CREATE POLICY "Users can update own profile." ON public.profiles FOR UPDATE USING (auth.uid() = id);

-- User Artifacts
CREATE TABLE public.user_artifacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
    file_type TEXT,
    storage_path TEXT,
    extracted_text TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);
ALTER TABLE public.user_artifacts ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view their own artifacts." ON public.user_artifacts FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert their own artifacts." ON public.user_artifacts FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can delete their own artifacts." ON public.user_artifacts FOR DELETE USING (auth.uid() = user_id);

-- Skills
CREATE TABLE public.skills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Subskills
CREATE TABLE public.subskills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_id UUID REFERENCES public.skills(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- User Skills
CREATE TABLE public.user_skills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
    skill_id UUID REFERENCES public.skills(id) ON DELETE CASCADE,
    source TEXT CHECK (source IN ('resume', 'onboarding_assessment', 'inferred')),
    proficiency_score NUMERIC,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    UNIQUE(user_id, skill_id)
);

-- User Hidden Skills
CREATE TABLE public.user_hidden_skills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
    skill_name TEXT NOT NULL,
    confidence_score NUMERIC,
    evidence_text TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Roles
CREATE TABLE public.roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role_name TEXT NOT NULL UNIQUE,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Role Requirements
CREATE TABLE public.role_requirements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role_id UUID REFERENCES public.roles(id) ON DELETE CASCADE,
    skill_name TEXT NOT NULL,
    weight NUMERIC DEFAULT 1.0, -- Importance weight for fit calculation
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    UNIQUE(role_id, skill_name)
);

-- Questions Core Table
CREATE TABLE public.questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question_text TEXT NOT NULL,
    question_type TEXT NOT NULL CHECK (question_type IN ('mcq', 'situational_mcq', 'descriptive')),
    difficulty TEXT CHECK (difficulty IN ('easy','medium','hard')),
    subject_id TEXT, -- Might be related to skills or a subject text
    skill_id UUID REFERENCES public.skills(id) ON DELETE SET NULL,
    subskill_id UUID REFERENCES public.subskills(id) ON DELETE SET NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);
CREATE INDEX idx_questions_type ON public.questions(question_type);
CREATE INDEX idx_questions_skill ON public.questions(skill_id);
CREATE INDEX idx_questions_subskill ON public.questions(subskill_id);
CREATE INDEX idx_questions_difficulty ON public.questions(difficulty);

-- MCQ Questions
CREATE TABLE public.mcq_questions (
    question_id UUID PRIMARY KEY REFERENCES public.questions(id) ON DELETE CASCADE,
    option_a TEXT NOT NULL,
    option_b TEXT NOT NULL,
    option_c TEXT NOT NULL,
    option_d TEXT NOT NULL,
    correct_option TEXT NOT NULL CHECK (correct_option IN ('A','B','C','D'))
);

-- Situational MCQ Questions
CREATE TABLE public.situational_mcq_questions (
    question_id UUID PRIMARY KEY REFERENCES public.questions(id) ON DELETE CASCADE,
    scenario TEXT NOT NULL,
    option_a TEXT NOT NULL,
    option_b TEXT NOT NULL,
    option_c TEXT NOT NULL,
    option_d TEXT NOT NULL,
    correct_option TEXT NOT NULL CHECK (correct_option IN ('A','B','C','D'))
);

-- Descriptive Questions
CREATE TABLE public.descriptive_questions (
    question_id UUID PRIMARY KEY REFERENCES public.questions(id) ON DELETE CASCADE,
    expected_answer TEXT,
    evaluation_rubric JSONB
);

-- Assessments
CREATE TABLE public.assessments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
    assessment_type TEXT,
    overall_score NUMERIC,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Descriptive Answers
CREATE TABLE public.descriptive_answers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assessment_id UUID REFERENCES public.assessments(id) ON DELETE CASCADE,
    question_id UUID REFERENCES public.descriptive_questions(question_id) ON DELETE CASCADE,
    user_answer TEXT,
    ai_feedback TEXT,
    score NUMERIC,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Skill Requests
CREATE TABLE public.skill_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
    requested_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    requested_type TEXT DEFAULT 'skill',
    matched_skill_id UUID REFERENCES public.skills(id) ON DELETE SET NULL,
    promoted_skill_id UUID REFERENCES public.skills(id) ON DELETE SET NULL,
    status TEXT DEFAULT 'pending', -- pending, generated, validated, promoted, rejected
    generation_status TEXT, -- none, fast, full, reused
    generated_payload JSONB, -- The entire blueprint
    mcq_score NUMERIC,
    written_score NUMERIC,
    interview_score NUMERIC,
    overall_score NUMERIC,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    promoted_at TIMESTAMP WITH TIME ZONE,
    rejected_at TIMESTAMP WITH TIME ZONE,
    admin_override_status TEXT,
    admin_override_reason TEXT
);
CREATE INDEX idx_skill_requests_user ON public.skill_requests(user_id);
CREATE INDEX idx_skill_requests_status ON public.skill_requests(status);
CREATE INDEX idx_skill_requests_name ON public.skill_requests(normalized_name);

-- RAG Knowledge
-- Assuming pgvector is enabled, wait I need to enable vector extension if it's not enabled by default
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE public.rag_knowledge (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
    artifact_id UUID REFERENCES public.user_artifacts(id) ON DELETE CASCADE,
    content_chunk TEXT,
    embedding vector(1536),
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);
CREATE INDEX ON public.rag_knowledge USING hnsw (embedding vector_cosine_ops);

-- RAG RPC Functions
CREATE OR REPLACE FUNCTION public.search_rag_knowledge(
    query_embedding vector(1536),
    match_threshold FLOAT DEFAULT 0.5,
    match_count INT DEFAULT 10,
    p_user_id UUID DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    content_chunk TEXT,
    metadata JSONB,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        rk.id,
        rk.content_chunk,
        rk.metadata,
        1 - (rk.embedding <=> query_embedding) AS similarity
    FROM public.rag_knowledge rk
    WHERE (p_user_id IS NULL OR rk.user_id = p_user_id)
      AND 1 - (rk.embedding <=> query_embedding) > match_threshold
    ORDER BY rk.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

CREATE OR REPLACE FUNCTION public.archive_stale_user_rag_knowledge(
    p_user_id UUID,
    p_keep_count INT
)
RETURNS INT
LANGUAGE plpgsql
AS $$
DECLARE
    deleted_count INT;
BEGIN
    DELETE FROM public.rag_knowledge
    WHERE id IN (
        SELECT id
        FROM public.rag_knowledge
        WHERE user_id = p_user_id
        ORDER BY created_at DESC
        OFFSET p_keep_count
    );
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$;
