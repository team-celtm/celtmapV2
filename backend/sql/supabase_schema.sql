create extension if not exists pgcrypto;
create extension if not exists vector;
create extension if not exists pg_trgm;

create or replace function public.celtm_normalize_text(input text)
returns text
language sql
immutable
as $$
    select nullif(lower(trim(regexp_replace(coalesce(input, ''), '\s+', ' ', 'g'))), '');
$$;

create table if not exists public.profiles (
    id uuid primary key,
    email text,
    full_name text,
    headline text,
    focus_role text,
    weekly_goal text,
    avatar_url text,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.user_preferences (
    user_id uuid primary key,
    desktop_notifications boolean not null default true,
    weekly_digest boolean not null default true,
    folio_reminders boolean not null default true,
    folio_focus text,
    security_mode text not null default 'standard',
    updated_at timestamptz not null default now()
);

create table if not exists public.uploaded_artifacts (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null,
    bucket_name text not null,
    storage_path text not null unique,
    file_name text not null,
    file_type text not null,
    extracted_text text,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    processed_at timestamptz
);

create table if not exists public.subjects (
    id uuid primary key default gen_random_uuid(),
    subject_id text not null unique,
    subject_name text not null,
    normalized_name text not null unique,
    track text,
    description text,
    domain_group text,
    industry_relevance text,
    metadata jsonb not null default '{}'::jsonb,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.skills (
    id uuid primary key default gen_random_uuid(),
    skill_id text not null unique,
    subject_ref_id uuid references public.subjects(id) on delete set null,
    skill_name text not null,
    normalized_name text not null unique,
    description text,
    industry_usage text,
    hidden_skills_supported text[] not null default '{}',
    metadata jsonb not null default '{}'::jsonb,
    status text not null default 'active',
    is_generated boolean not null default false,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (skill_name)
);

create table if not exists public.subskills (
    id uuid primary key default gen_random_uuid(),
    subskill_id text not null unique,
    skill_ref_id uuid references public.skills(id) on delete cascade,
    subskill_name text not null,
    normalized_name text not null,
    description text,
    metadata jsonb not null default '{}'::jsonb,
    is_generated boolean not null default false,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (skill_ref_id, normalized_name)
);

create table if not exists public.roles (
    id uuid primary key default gen_random_uuid(),
    role_id text unique,
    role_name text not null,
    normalized_name text not null unique,
    role_category text,
    description text,
    target_industries text[] not null default '{}',
    required_subjects text[] not null default '{}',
    core_skills text[] not null default '{}',
    metadata jsonb not null default '{}'::jsonb,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (role_name)
);

create table if not exists public.role_skill_requirements (
    id uuid primary key default gen_random_uuid(),
    role_name text not null,
    skill_name text not null,
    weight numeric(6,2) not null default 1,
    prerequisite_skill_name text,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    unique (role_name, skill_name)
);

create table if not exists public.skill_requests (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null,
    requested_name text not null,
    normalized_name text not null,
    requested_type text not null default 'skill',
    matched_skill_id text,
    status text not null default 'pending_validation',
    generation_status text not null default 'queued',
    generated_payload jsonb not null default '{}'::jsonb,
    mcq_score numeric(5,2),
    written_score numeric(5,2),
    interview_score numeric(5,2),
    overall_score numeric(5,2),
    promoted_skill_id text,
    promoted_at timestamptz,
    rejected_at timestamptz,
    admin_override_status text,
    admin_override_reason text,
    metadata jsonb not null default '{}'::jsonb,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (user_id, normalized_name)
);

create table if not exists public.questions (
    id uuid primary key default gen_random_uuid(),
    source_question_id text,
    subject_id text default '',
    subject_name text,
    skill_id text not null default '',
    skill_name text,
    subskill_id text not null default '',
    subskill_name text,
    role_ids text[] not null default '{}',
    question_text text not null,
    question_text_normalized text not null,
    category text not null,
    difficulty text not null default 'unassigned',
    question_type text not null default 'MCQ',
    sample_answer text,
    explanation text,
    expected_concepts text[] not null default '{}',
    hidden_skills_targeted text[] not null default '{}',
    evaluation_mode text,
    rag_tags text[] not null default '{}',
    skill_request_id uuid references public.skill_requests(id) on delete set null,
    metadata jsonb not null default '{}'::jsonb,
    is_generated boolean not null default false,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (question_text_normalized, question_type, skill_id, subskill_id)
);

create table if not exists public.options (
    id uuid primary key default gen_random_uuid(),
    question_id uuid not null references public.questions(id) on delete cascade,
    option_key text,
    option_text text not null,
    explanation text,
    is_correct boolean not null default false,
    unique (question_id, option_text)
);

create table if not exists public.assessments (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null,
    category text not null,
    assessment_type text not null default 'mcq',
    question_type text not null default 'MCQ',
    skill_id text,
    subskill_id text,
    skill_request_id uuid references public.skill_requests(id) on delete set null,
    score numeric(5,2),
    status text not null default 'pending',
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    completed_at timestamptz
);

create table if not exists public.user_answers (
    id uuid primary key default gen_random_uuid(),
    assessment_id uuid not null references public.assessments(id) on delete cascade,
    user_id uuid not null,
    question_id uuid not null references public.questions(id) on delete cascade,
    selected_option_id uuid references public.options(id) on delete set null,
    answer_text text,
    is_correct boolean not null default false,
    created_at timestamptz not null default now(),
    unique (user_id, question_id, assessment_id)
);

create table if not exists public.written_assessment_sessions (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null,
    skill_id text,
    skill_request_id uuid references public.skill_requests(id) on delete set null,
    prompt text not null,
    rubric jsonb not null default '{}'::jsonb,
    submission_text text,
    score numeric(5,2),
    feedback text,
    status text not null default 'draft',
    metadata jsonb not null default '{}'::jsonb,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    completed_at timestamptz
);

create table if not exists public.user_skills (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null,
    skill_id text not null,
    skill_name text not null,
    verified_score numeric(5,2) not null default 0,
    assessment_score numeric(5,2),
    written_score numeric(5,2),
    interview_score numeric(5,2),
    artifact_score numeric(5,2),
    source text,
    skill_request_id uuid references public.skill_requests(id) on delete set null,
    metadata jsonb not null default '{}'::jsonb,
    updated_at timestamptz not null default now(),
    unique (user_id, skill_id)
);

create table if not exists public.hidden_skill_candidates (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null,
    skill_name text not null,
    skill_id text,
    confidence_score numeric(5,2) not null,
    source text not null,
    evidence text,
    status text not null default 'pending',
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    approved_at timestamptz,
    rejected_at timestamptz,
    unique (user_id, skill_name, status)
);

create table if not exists public.interview_sessions (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null,
    role_name text,
    skill_request_id uuid references public.skill_requests(id) on delete set null,
    interview_type text not null default 'role',
    status text not null default 'draft',
    transcript text,
    media_reference text,
    duration_seconds integer,
    metadata jsonb not null default '{}'::jsonb,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.interview_questions (
    id uuid primary key default gen_random_uuid(),
    session_id uuid not null references public.interview_sessions(id) on delete cascade,
    question_text text not null,
    source_document jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.interview_answers (
    id uuid primary key default gen_random_uuid(),
    session_id uuid not null references public.interview_sessions(id) on delete cascade,
    question_id uuid references public.interview_questions(id) on delete set null,
    answer_text text,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.interview_evaluations (
    id uuid primary key default gen_random_uuid(),
    session_id uuid not null references public.interview_sessions(id) on delete cascade,
    score numeric(5,2) not null,
    feedback text not null,
    detected_skills jsonb not null default '[]'::jsonb,
    hidden_skills jsonb not null default '[]'::jsonb,
    metrics jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.learning_paths (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null,
    role_name text not null,
    source text not null default 'system',
    skill_request_id uuid references public.skill_requests(id) on delete set null,
    created_at timestamptz not null default now()
);

create table if not exists public.learning_modules (
    id uuid primary key default gen_random_uuid(),
    path_id uuid not null references public.learning_paths(id) on delete cascade,
    title text not null,
    week integer not null,
    skill_name text not null,
    gap_severity numeric(8,4) not null,
    resources jsonb not null default '[]'::jsonb,
    unique (path_id, title)
);

create table if not exists public.trajectory_roles (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null,
    role_name text not null,
    fit_score numeric(5,2),
    payload jsonb not null default '{}'::jsonb,
    updated_at timestamptz not null default now(),
    unique (user_id, role_name)
);

create table if not exists public.schedule_events (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null,
    title text not null,
    starts_at timestamptz not null,
    ends_at timestamptz,
    event_type text not null,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.reports (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null,
    report_type text not null default 'summary',
    payload jsonb not null,
    is_active boolean not null default true,
    created_at timestamptz not null default now()
);

create table if not exists public.dashboard_projections (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null unique,
    payload jsonb not null,
    updated_at timestamptz not null default now()
);

create table if not exists public.rag_documents (
    id uuid primary key default gen_random_uuid(),
    scope text not null,
    user_id uuid,
    source_type text not null,
    source_ref text,
    skill_id text,
    subskill_id text,
    title text,
    content text not null,
    metadata jsonb not null default '{}'::jsonb,
    embedding vector(1536),
    dedupe_hash text not null unique,
    access_count integer not null default 0,
    last_accessed_at timestamptz,
    archived_at timestamptz,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.ai_call_logs (
    id uuid primary key default gen_random_uuid(),
    user_id uuid,
    provider text not null,
    model text not null,
    operation text not null,
    prompt_hash text,
    cache_hit boolean not null default false,
    latency_ms integer,
    input_tokens integer,
    output_tokens integer,
    status text not null,
    source_entity_type text,
    source_entity_id text,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.job_failures (
    id uuid primary key default gen_random_uuid(),
    task_name text not null,
    task_id text,
    entity_type text,
    entity_id text,
    payload jsonb not null default '{}'::jsonb,
    error_message text not null,
    traceback text,
    retry_count integer not null default 0,
    status text not null default 'failed',
    created_at timestamptz not null default now()
);

create table if not exists public.domain_events (
    id uuid primary key default gen_random_uuid(),
    event_type text not null,
    aggregate_type text not null,
    aggregate_id text not null,
    status text not null default 'pending',
    payload jsonb not null default '{}'::jsonb,
    retry_count integer not null default 0,
    last_error text,
    processing_started_at timestamptz,
    processed_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.celtmind_ingestion_runs (
    id uuid primary key default gen_random_uuid(),
    status text not null,
    started_at timestamptz not null default now(),
    completed_at timestamptz,
    summary jsonb not null default '[]'::jsonb,
    error text
);

create table if not exists public.celtmind_file_registry (
    id uuid primary key default gen_random_uuid(),
    file_name text not null unique,
    checksum text not null,
    category text not null,
    last_ingested_at timestamptz not null
);

alter table if exists public.skills
    add column if not exists skill_id text,
    add column if not exists subject_ref_id uuid references public.subjects(id) on delete set null,
    add column if not exists skill_name text,
    add column if not exists normalized_name text,
    add column if not exists industry_usage text,
    add column if not exists hidden_skills_supported text[] not null default '{}',
    add column if not exists metadata jsonb not null default '{}'::jsonb,
    add column if not exists status text not null default 'active',
    add column if not exists is_generated boolean not null default false,
    add column if not exists is_active boolean not null default true,
    add column if not exists updated_at timestamptz not null default now();

update public.skills
set
    skill_id = coalesce(skill_id, id::text),
    skill_name = coalesce(skill_name, name),
    normalized_name = coalesce(normalized_name, public.celtm_normalize_text(coalesce(skill_name, name))),
    metadata = coalesce(metadata, '{}'::jsonb),
    status = coalesce(status, 'active'),
    is_generated = coalesce(is_generated, false),
    is_active = coalesce(is_active, true),
    updated_at = coalesce(updated_at, created_at, now())
where skill_id is null
   or skill_name is null
   or normalized_name is null
   or updated_at is null;

insert into public.subjects (
    subject_id,
    subject_name,
    normalized_name,
    track,
    metadata,
    is_active,
    created_at,
    updated_at
)
select distinct
    'legacy-subject:' || public.celtm_normalize_text(s.category),
    s.category,
    public.celtm_normalize_text(s.category),
    'legacy',
    jsonb_build_object('source', 'legacy.skills.category'),
    true,
    now(),
    now()
from public.skills s
where public.celtm_normalize_text(s.category) is not null
on conflict (normalized_name) do nothing;

update public.skills s
set subject_ref_id = subj.id
from public.subjects subj
where s.subject_ref_id is null
  and public.celtm_normalize_text(s.category) = subj.normalized_name;

alter table if exists public.roles
    add column if not exists role_id text,
    add column if not exists role_name text,
    add column if not exists normalized_name text,
    add column if not exists role_category text,
    add column if not exists target_industries text[] not null default '{}',
    add column if not exists required_subjects text[] not null default '{}',
    add column if not exists core_skills text[] not null default '{}',
    add column if not exists metadata jsonb not null default '{}'::jsonb,
    add column if not exists is_active boolean not null default true,
    add column if not exists updated_at timestamptz not null default now();

update public.roles
set
    role_id = coalesce(role_id, id::text),
    role_name = coalesce(role_name, name),
    normalized_name = coalesce(normalized_name, public.celtm_normalize_text(coalesce(role_name, name))),
    metadata = coalesce(metadata, '{}'::jsonb),
    is_active = coalesce(is_active, true),
    updated_at = coalesce(updated_at, created_at, now())
where role_id is null
   or role_name is null
   or normalized_name is null
   or updated_at is null;

alter table if exists public.user_skills
    drop constraint if exists user_skills_skill_id_fkey;

alter table if exists public.user_skills
    drop constraint if exists user_skills_skill_fkey;

alter table if exists public.user_skills
    alter column skill_id type text using skill_id::text;

alter table if exists public.user_skills
    add column if not exists skill_name text,
    add column if not exists verified_score numeric(5,2) not null default 0,
    add column if not exists assessment_score numeric(5,2),
    add column if not exists written_score numeric(5,2),
    add column if not exists interview_score numeric(5,2),
    add column if not exists artifact_score numeric(5,2),
    add column if not exists skill_request_id uuid references public.skill_requests(id) on delete set null,
    add column if not exists metadata jsonb not null default '{}'::jsonb,
    add column if not exists updated_at timestamptz not null default now();

update public.user_skills us
set
    verified_score = coalesce(
        verified_score,
        proficiency_score,
        case
            when confidence_score is not null then round((confidence_score * 100)::numeric, 2)
            else 0
        end
    ),
    updated_at = coalesce(updated_at, last_updated, now()),
    metadata = coalesce(metadata, '{}'::jsonb)
where verified_score is null
   or updated_at is null;

update public.user_skills us
set skill_name = coalesce(us.skill_name, s.skill_name, s.name)
from public.skills s
where us.skill_name is null
  and (us.skill_id = s.skill_id or us.skill_id = s.id::text);

alter table if exists public.reports
    add column if not exists payload jsonb,
    add column if not exists is_active boolean not null default true;

alter table if exists public.interview_answers
    add column if not exists metadata jsonb not null default '{}'::jsonb;

alter table if exists public.interview_evaluations
    add column if not exists metrics jsonb not null default '{}'::jsonb;

alter table if exists public.reports
    alter column report_type set default 'summary';

update public.reports
set payload = coalesce(payload, content, '{}'::jsonb)
where payload is null;

insert into public.profiles (
    id,
    email,
    full_name,
    headline,
    focus_role,
    avatar_url,
    metadata,
    created_at,
    updated_at
)
select
    u.id,
    u.email,
    u.full_name,
    u.role,
    r.name,
    u.avatar_url,
    jsonb_build_object('source', 'legacy.users'),
    coalesce(u.created_at::timestamptz, now()),
    coalesce(u.updated_at::timestamptz, u.created_at::timestamptz, now())
from public.users u
left join public.roles r on r.id = u.target_role_id
on conflict (id) do update
set
    email = coalesce(excluded.email, public.profiles.email),
    full_name = coalesce(excluded.full_name, public.profiles.full_name),
    headline = coalesce(excluded.headline, public.profiles.headline),
    focus_role = coalesce(excluded.focus_role, public.profiles.focus_role),
    avatar_url = coalesce(excluded.avatar_url, public.profiles.avatar_url),
    metadata = public.profiles.metadata || excluded.metadata,
    updated_at = now();

insert into public.role_skill_requirements (
    role_name,
    skill_name,
    weight,
    metadata,
    created_at
)
select
    r.role_name,
    coalesce(s.skill_name, s.name),
    coalesce(rs.weight::numeric, 1),
    jsonb_build_object('source', 'legacy.role_skills'),
    now()
from public.role_skills rs
join public.roles r on r.id = rs.role_id
join public.skills s on s.id = rs.skill_id
where r.role_name is not null
  and coalesce(s.skill_name, s.name) is not null
on conflict (role_name, skill_name) do nothing;

insert into public.questions (
    source_question_id,
    subject_name,
    skill_id,
    skill_name,
    question_text,
    question_text_normalized,
    category,
    difficulty,
    question_type,
    metadata,
    is_active,
    created_at,
    updated_at
)
select
    mq.id::text,
    nullif(mq.subject, ''),
    coalesce(s.skill_id, mq.skill_id::text, ''),
    coalesce(s.skill_name, s.name),
    mq.question,
    public.celtm_normalize_text(mq.question),
    coalesce(nullif(mq.subject, ''), 'legacy'),
    coalesce(nullif(lower(mq.difficulty), ''), 'unassigned'),
    'MCQ',
    jsonb_build_object('source', 'legacy.mcq_questions'),
    true,
    coalesce(mq.created_at::timestamptz, now()),
    coalesce(mq.created_at::timestamptz, now())
from public.mcq_questions mq
left join public.skills s on s.id = mq.skill_id
where public.celtm_normalize_text(mq.question) is not null
on conflict (question_text_normalized, question_type, skill_id, subskill_id) do nothing;

insert into public.options (question_id, option_key, option_text, is_correct)
select q.id, option_key, option_text, is_correct
from (
    select
        mq.id::text as source_question_id,
        'A'::text as option_key,
        mq.option_a as option_text,
        upper(coalesce(mq.correct_answer, '')) = 'A' as is_correct
    from public.mcq_questions mq
    union all
    select mq.id::text, 'B', mq.option_b, upper(coalesce(mq.correct_answer, '')) = 'B'
    from public.mcq_questions mq
    union all
    select mq.id::text, 'C', mq.option_c, upper(coalesce(mq.correct_answer, '')) = 'C'
    from public.mcq_questions mq
    union all
    select mq.id::text, 'D', mq.option_d, upper(coalesce(mq.correct_answer, '')) = 'D'
    from public.mcq_questions mq
    union all
    select mq.id::text, 'E', mq.option_e, upper(coalesce(mq.correct_answer, '')) = 'E'
    from public.mcq_questions mq
) legacy_options
join public.questions q on q.source_question_id = legacy_options.source_question_id
where nullif(trim(legacy_options.option_text), '') is not null
on conflict (question_id, option_text) do nothing;

insert into public.interview_sessions (
    id,
    user_id,
    role_name,
    interview_type,
    status,
    transcript,
    media_reference,
    metadata,
    is_active,
    created_at,
    updated_at
)
select
    i.id,
    i.user_id,
    r.role_name,
    'role',
    coalesce(i.status, 'completed'),
    i.transcript,
    i.video_url,
    jsonb_build_object('source', 'legacy.interviews'),
    true,
    coalesce(i.created_at::timestamptz, now()),
    coalesce(i.created_at::timestamptz, now())
from public.interviews i
left join public.roles r on r.id = i.role_id
on conflict (id) do nothing;

insert into public.interview_evaluations (
    session_id,
    score,
    feedback,
    detected_skills,
    hidden_skills,
    created_at
)
select
    ir.interview_id,
    coalesce(ir.score::numeric, 0),
    coalesce(ir.feedback, ''),
    jsonb_build_object('confidence', ir.confidence),
    '[]'::jsonb,
    coalesce(ir.created_at::timestamptz, now())
from public.interview_results ir
on conflict do nothing;

insert into public.hidden_skill_candidates (
    user_id,
    skill_name,
    skill_id,
    confidence_score,
    source,
    evidence,
    status,
    metadata,
    created_at,
    approved_at
)
select
    hs.user_id,
    coalesce(s.skill_name, s.name, hs.skill_id::text),
    coalesce(s.skill_id, hs.skill_id::text),
    round(coalesce(hs.confidence, 0)::numeric, 2),
    coalesce(hs.source, 'legacy.hidden_skills'),
    null,
    case when hs.approved then 'approved' else 'pending' end,
    jsonb_build_object('source', 'legacy.hidden_skills'),
    coalesce(hs.created_at::timestamptz, now()),
    case when hs.approved then coalesce(hs.created_at::timestamptz, now()) else null end
from public.hidden_skills hs
left join public.skills s on s.id::text = hs.skill_id::text
on conflict (user_id, skill_name, status) do nothing;

insert into public.uploaded_artifacts (
    user_id,
    bucket_name,
    storage_path,
    file_name,
    file_type,
    extracted_text,
    metadata,
    created_at,
    processed_at
)
select
    c.user_id,
    'legacy-certifications',
    c.file_url,
    split_part(c.file_url, '/', array_length(string_to_array(c.file_url, '/'), 1)),
    'certification',
    c.extracted_text,
    jsonb_build_object('source', 'legacy.certifications'),
    coalesce(c.created_at::timestamptz, now()),
    coalesce(c.created_at::timestamptz, now())
from public.certifications c
where nullif(trim(coalesce(c.file_url, '')), '') is not null
on conflict (storage_path) do nothing;

insert into public.schedule_events (
    user_id,
    title,
    starts_at,
    ends_at,
    event_type,
    metadata,
    created_at
)
select
    s.user_id,
    s.title,
    s.scheduled_at::timestamptz,
    null,
    coalesce(s.type, 'legacy'),
    jsonb_build_object(
        'source', 'legacy.schedules',
        'legacy_reference_id', s.reference_id,
        'legacy_status', s.status
    ),
    coalesce(s.created_at::timestamptz, now())
from public.schedules s
on conflict do nothing;

create index if not exists idx_subjects_active_name
    on public.subjects (is_active, normalized_name);
create unique index if not exists uq_subjects_subject_id
    on public.subjects (subject_id);
create index if not exists idx_skills_active_name
    on public.skills (is_active, normalized_name);
create unique index if not exists uq_skills_skill_id
    on public.skills (skill_id);
create unique index if not exists uq_skills_normalized_name
    on public.skills (normalized_name);
create index if not exists idx_subskills_active_skill_name
    on public.subskills (is_active, skill_ref_id, normalized_name);
create unique index if not exists uq_subskills_source_id
    on public.subskills (subskill_id);
create index if not exists idx_roles_active_name
    on public.roles (is_active, normalized_name);
create unique index if not exists uq_roles_normalized_name
    on public.roles (normalized_name);
create index if not exists idx_questions_active_type_skill
    on public.questions (is_active, question_type, skill_id, category, difficulty);
create unique index if not exists uq_questions_lookup
    on public.questions (question_text_normalized, question_type, skill_id, subskill_id);
create index if not exists idx_options_question_id
    on public.options (question_id);
create index if not exists idx_assessments_user_created_at
    on public.assessments (user_id, created_at desc);
create index if not exists idx_user_answers_user_question
    on public.user_answers (user_id, question_id);
create index if not exists idx_written_assessment_user_created
    on public.written_assessment_sessions (user_id, created_at desc);
create index if not exists idx_user_skills_user_skill
    on public.user_skills (user_id, skill_id);
create index if not exists idx_user_skills_user_verified
    on public.user_skills (user_id, verified_score desc, updated_at desc);
create index if not exists idx_hidden_skill_candidates_user_status_created
    on public.hidden_skill_candidates (user_id, status, created_at desc);
create index if not exists idx_interview_sessions_user_status_created
    on public.interview_sessions (user_id, status, created_at desc);
create index if not exists idx_interview_evaluations_session_created
    on public.interview_evaluations (session_id, created_at desc);
create index if not exists idx_learning_paths_user_role_created
    on public.learning_paths (user_id, role_name, created_at desc);
create index if not exists idx_learning_modules_path_week
    on public.learning_modules (path_id, week);
create index if not exists idx_schedule_events_user_starts_at
    on public.schedule_events (user_id, starts_at);
create index if not exists idx_uploaded_artifacts_user_created
    on public.uploaded_artifacts (user_id, created_at desc);
create index if not exists idx_reports_user_created
    on public.reports (user_id, created_at desc) where is_active = true;
create index if not exists idx_profiles_email
    on public.profiles (email);
create index if not exists idx_dashboard_projections_user_updated
    on public.dashboard_projections (user_id, updated_at desc);
create index if not exists idx_rag_documents_scope_user_active
    on public.rag_documents (scope, user_id, is_active, archived_at);
create index if not exists idx_rag_documents_skill_source
    on public.rag_documents (skill_id, subskill_id, source_type);
create index if not exists idx_rag_documents_last_accessed
    on public.rag_documents (last_accessed_at desc nulls last);
create index if not exists idx_rag_documents_embedding
    on public.rag_documents using ivfflat (embedding vector_cosine_ops) with (lists = 100);
create index if not exists idx_ai_call_logs_created
    on public.ai_call_logs (created_at desc);
create index if not exists idx_job_failures_created
    on public.job_failures (created_at desc);
create index if not exists idx_domain_events_status_created
    on public.domain_events (status, created_at desc);
create index if not exists idx_skill_requests_user_status_created
    on public.skill_requests (user_id, status, created_at desc);
create index if not exists idx_skill_requests_normalized_name
    on public.skill_requests (normalized_name);

create or replace function public.search_rag_documents(
    query_embedding float8[],
    p_user_id uuid default null,
    p_limit integer default 6
)
returns table (
    id uuid,
    scope text,
    user_id uuid,
    source_type text,
    source_ref text,
    skill_id text,
    subskill_id text,
    title text,
    content text,
    metadata jsonb,
    distance double precision
)
language plpgsql
as $$
declare
    query_vector vector(1536);
    desired_user_docs integer;
begin
    query_vector := query_embedding::vector(1536);
    desired_user_docs := greatest(2, least(coalesce(p_limit, 6), 6));

    return query
    with user_docs as (
        select
            d.id,
            d.scope,
            d.user_id,
            d.source_type,
            d.source_ref,
            d.skill_id,
            d.subskill_id,
            d.title,
            d.content,
            d.metadata,
            (d.embedding <=> query_vector) as distance,
            0 as scope_rank
        from public.rag_documents d
        where d.is_active = true
          and d.archived_at is null
          and d.embedding is not null
          and d.scope = 'user'
          and p_user_id is not null
          and d.user_id = p_user_id
        order by d.embedding <=> query_vector
        limit desired_user_docs
    ),
    global_docs as (
        select
            d.id,
            d.scope,
            d.user_id,
            d.source_type,
            d.source_ref,
            d.skill_id,
            d.subskill_id,
            d.title,
            d.content,
            d.metadata,
            (d.embedding <=> query_vector) as distance,
            1 as scope_rank
        from public.rag_documents d
        where d.is_active = true
          and d.archived_at is null
          and d.embedding is not null
          and d.scope in ('global', 'catalog')
        order by d.embedding <=> query_vector
        limit greatest(coalesce(p_limit, 6), 6)
    ),
    combined as (
        select * from user_docs
        union all
        select g.*
        from global_docs g
        where not exists (
            select 1 from user_docs u where u.id = g.id
        )
    )
    select
        c.id,
        c.scope,
        c.user_id,
        c.source_type,
        c.source_ref,
        c.skill_id,
        c.subskill_id,
        c.title,
        c.content,
        c.metadata,
        c.distance
    from combined c
    order by c.scope_rank asc, c.distance asc
    limit least(coalesce(p_limit, 6), 6);
end;
$$;

create or replace function public.archive_stale_user_rag_documents(
    p_user_id uuid,
    p_keep_count integer default 120
)
returns integer
language plpgsql
as $$
declare
    archived_count integer;
begin
    with ranked as (
        select
            id,
            row_number() over (
                order by coalesce(last_accessed_at, created_at) desc, created_at desc
            ) as row_num
        from public.rag_documents
        where is_active = true
          and archived_at is null
          and scope = 'user'
          and user_id = p_user_id
    ),
    archived as (
        update public.rag_documents d
        set archived_at = now(),
            updated_at = now()
        from ranked r
        where d.id = r.id
          and r.row_num > greatest(p_keep_count, 0)
        returning d.id
    )
    select count(*) into archived_count from archived;

    return coalesce(archived_count, 0);
end;
$$;
