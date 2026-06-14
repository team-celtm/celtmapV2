export interface ReadinessComponent {
  key: string;
  label: string;
  score: number;
  weight: number;
  effective_weight: number;
}

export interface DashboardSummary {
  user_id: string;
  readiness_score: number;
  role_fit: number;
  top_skills: string[];
  domain_breakdown?: Record<string, number>;
  readiness_components?: ReadinessComponent[];
  component_scores?: Record<string, number>;
  component_weights?: Record<string, number>;
  readiness_formula?: string | null;
  pending_hidden_skills: number;
  next_event: ScheduleEvent | null;
  latest_report_id?: string | null;
  latest_report_created_at?: string | null;
}

export interface CareerRecommendation {
  rank: number;
  role: string;
  fit_score: number;
  readiness_score: number;
  global_readiness: number;
  role_profile?: string | null;
  reason: string;
  path_summary: string;
  suggested_skills: string[];
  needs_assessment: boolean;
  is_primary: boolean;
  readiness_note?: string;
  evidence?: {
    matched_keywords?: string[];
    context_overlap?: number;
    evidence_confidence?: number;
    primary_gaps?: string[];
  };
}

export interface CareerRecommendationResponse {
  recommendations: CareerRecommendation[];
  source: string;
  analyzed_at: string;
  needs_assessment_for_skills: boolean;
  readiness_score: number;
  draft_personality?: Record<string, unknown> | null;
}

export interface CareerRoleOption {
  value: string;
  label: string;
  profile_key: string;
  aliases: string[];
  description?: string;
  is_catalog?: boolean;
}

export interface CareerRoleSuggestion extends CareerRoleOption {
  matched_catalog_role?: string | null;
  is_supported_catalog?: boolean;
  confidence?: number;
  source?: string;
  interpretation?: string;
  subjects?: string[];
}

export interface CareerAspirationRead {
  id: string;
  desired_role: string;
  current_readiness: number;
  major_gaps: string[];
  better_current_fit: string[];
  roadmap: Record<string, string[]>;
  infographics: Array<{ label: string; value: string; helper: string }>;
  analysis: Record<string, unknown>;
  created_at: string;
  updated_at?: string | null;
}

export interface CareerLink {
  label: string;
  url: string;
  type: string;
}

export interface ProfileLinkEvidence {
  score: number;
  domain_breakdown: Record<string, number>;
  skills: string[];
  links: Array<CareerLink & {
    reachable?: boolean;
    status_code?: number | null;
    summary?: string;
    error?: string;
    score?: number;
  }>;
  validated_at: string;
}

export interface ProfileLinkValidationResponse {
  profile: ProfileRead;
  evidence: ProfileLinkEvidence;
  readiness_event?: Record<string, unknown>;
  readiness?: Record<string, unknown>;
}


export interface ReportRead {
  id: string;
  user_id: string;
  payload: Record<string, unknown>;
  created_at?: string | null;
}

export interface SkillRead {
  skill_id: string;
  skill_name: string;
  verified_score: number;
  assessment_score?: number | null;
  written_score?: number | null;
  interview_score?: number | null;
  artifact_score?: number | null;
  updated_at?: string | null;
}

export interface SkillGapRead {
  skill_name: string;
  target_weight: number;
  user_score: number;
  gap_severity: number;
}

export interface RoleFitRead {
  role_name: string;
  fit_score: number;
  matched_skills: string[];
  missing_skills: string[];
}

export interface HiddenSkillCandidateRead {
  id: string;
  skill_name: string;
  confidence_score: number;
  source: string;
  evidence: string;
  artifact_id?: string | null;
  status: string;
  created_at?: string | null;
}

export interface MCQOptionPublic {
  id: string;
  option_text: string;
}

export interface MCQQuestionPublic {
  id: string;
  question_text: string;
  category: string;
  difficulty: string;
  skill_id?: string | null;
  skill_request_id?: string | null;
  question_type: string;
  scenario?: string | null;
  options: MCQOptionPublic[];
}

export interface MCQQuestionBatchResponse {
  questions: MCQQuestionPublic[];
  count: number;
}

export interface AssessmentRead {
  id: string;
  user_id: string;
  category: string;
  assessment_type: string;
  question_type: string;
  skill_id?: string | null;
  skill_request_id?: string | null;
  score?: number | null;
  status: string;
  created_at?: string | null;
  completed_at?: string | null;
}

export interface MCQDetailedFeedback {
  question_id: string;
  question_text: string;
  category: string;
  selected_option: string;
  correct_option: string;
  is_correct: boolean;
  personalized_insight: string;
}

export interface AssessmentCompletionResponse {
  assessment_id: string;
  score: number;
  correct_answers: number;
  total_questions: number;
  status: string;
  detailed_feedback?: MCQDetailedFeedback[];
}

export interface PlagiarismReportRead {
  risk_score: number;
  risk_level: string;
  summary: string;
  signals: string[];
}

export interface AssessmentLogEntry {
  id: string;
  type: "mcq" | "situational" | "written" | "interview" | string;
  subject: string;
  score: number | null;
  status: string;
  completed_at: string | null;
  insight?: string | null;
  feedback?: string | null;
  strengths?: string[];
  risks?: string[];
  recommendations?: string[];
  plagiarism?: PlagiarismReportRead | null;
  readiness_score?: number | null;
  readiness_components?: ReadinessComponent[];
  role_name?: string | null;
  detailed_feedback?: MCQDetailedFeedback[];
  hidden_skills?: string[];
  areas_of_betterment?: string[];
  analytics?: {
    correct: number;
    wrong: number;
    total: number;
  };
}

export interface SubjectProgressAttempt {
  id: string;
  type: "mcq" | "situational" | "written" | string;
  score: number;
  completed_at?: string | null;
  question_type?: string | null;
  assessment_type?: string | null;
  correct?: number | null;
  wrong?: number | null;
  total?: number | null;
  delta_from_previous?: number | null;
  capability_profile?: Record<string, number>;
}

export interface SubjectProgress {
  subject_key: string;
  subject: string;
  attempt_count: number;
  objective_attempt_count: number;
  written_attempt_count: number;
  first_score: number;
  latest_score: number;
  best_score: number;
  average_score: number;
  improvement: number;
  trend: "improving" | "declining" | "stable" | "single attempt" | string;
  last_completed_at?: string | null;
  best_attempt_id?: string | null;
  latest_attempt_id?: string | null;
  latest_type?: string | null;
  strong_dimensions?: string[];
  weak_dimensions?: string[];
  next_action?: string;
  recent_attempts: SubjectProgressAttempt[];
}

export interface SubjectDetail {
  key: string;
  title: string;
  description: string;
  source: string;
  dimension?: string | null;
  severity: number;
  current_score: number | null;
  skill_id: string | null;
  skill_request_id: string | null;
  resource_count: number;
  is_available: boolean;
  mcq_count?: number;
  situational_count?: number;
  written_count?: number;
  availability?: {
    mcq?: boolean;
    situational?: boolean;
    written?: boolean;
  };
}

export interface AssessmentAssignmentRead {
  id: string;
  institution_id: string;
  department_id: string;
  title: string;
  category: string;
  assessment_type: string;
  question_type: string;
  question_set_id?: string | null;
  question_count?: number;
  mode: string;
  starts_at: string;
  ends_at: string;
  duration_minutes: number;
  instructions?: string | null;
  status: string;
  can_start: boolean;
  is_upcoming: boolean;
  is_expired: boolean;
  missed?: boolean;
  terminated?: boolean;
  terminated_at?: string | null;
  terminated_by_email?: string | null;
  attempt_id?: string | null;
  attempt_status?: string | null;
  attempt_score?: number | null;
  completed_at?: string | null;
}


export interface WrittenAssessmentRead {
  id: string;
  user_id: string;
  assignment_id?: string | null;
  skill_id?: string | null;
  skill_request_id?: string | null;
  prompt: string;
  rubric?: Record<string, unknown>;
  submission_text?: string | null;
  score?: number | null;
  readiness_score?: number | null;
  written_score?: number | null;
  evaluation_score?: number | null;
  feedback?: string | null;
  status: string;
  metadata?: Record<string, unknown>;
  readiness_components?: ReadinessComponent[];
  readiness_formula?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface InterviewSessionRead {
  id: string;
  user_id: string;
  role_name?: string | null;
  skill_request_id?: string | null;
  interview_type: string;
  status: string;
  transcript?: string | null;
  created_at?: string | null;
}

export interface TranscriptTurnRead {
  question_id?: string | null;
  question_text?: string | null;
  answer_id?: string | null;
  answer_text?: string | null;
  evaluation_metrics: Record<string, number>;
  evidence?: string | null;
  created_at?: string | null;
}

export interface InterviewResultRead {
  session_id: string;
  score: number;
  feedback: string;
  detected_skills: Array<Record<string, string | number>>;
  hidden_skills: Array<Record<string, string | number>>;
  evaluation_metrics: Record<string, number>;
  transcript_turns: TranscriptTurnRead[];
}

export interface SkillRequestRead {
  id: string;
  user_id: string;
  requested_name: string;
  normalized_name: string;
  requested_type: string;
  matched_skill_id?: string | null;
  status: string;
  generation_status: string;
  generated_payload: Record<string, unknown>;
  mcq_score?: number | null;
  written_score?: number | null;
  interview_score?: number | null;
  overall_score?: number | null;
  promoted_skill_id?: string | null;
  promoted_at?: string | null;
  rejected_at?: string | null;
  admin_override_status?: string | null;
  admin_override_reason?: string | null;
  metadata: Record<string, unknown>;
  is_active: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface UserPreferenceRead {
  user_id: string;
  desktop_notifications: boolean;
  weekly_digest: boolean;
  folio_reminders: boolean;
  folio_focus?: string | null;
  security_mode: string;
  updated_at?: string | null;
}

export interface ProfileRead {
  id: string;
  email?: string | null;
  full_name?: string | null;
  headline?: string | null;
  focus_role?: string | null;
  weekly_goal?: string | null;
  avatar_url?: string | null;
  institution_id?: string | null;
  department_id?: string | null;
  institution_name?: string | null;
  department_name?: string | null;
  metadata: Record<string, unknown>;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ArtifactRead {
  id: string;
  user_id: string;
  bucket_name: string;
  storage_path: string;
  signed_url?: string | null;
  file_url?: string | null;
  file_name: string;
  file_type: string;
  extracted_text?: string | null;
  metadata: Record<string, unknown>;
  created_at?: string | null;
}

export interface ScheduleEvent {
  id: string;
  title: string;
  starts_at: string;
  ends_at?: string | null;
  event_type: string;
  metadata: Record<string, string>;
}

export interface ScheduleEventPayload {
  title: string;
  starts_at: string;
  ends_at?: string | null;
  event_type: string;
  metadata: Record<string, string>;
}

export interface LearningResource {
  title: string;
  content: string;
  resource_type: string;
  skill_name?: string | null;
  resource_url?: string | null;
}

export interface LearningModule {
  title: string;
  week: number;
  skill_name: string;
  gap_severity: number;
  resources: LearningResource[];
  is_available: boolean;
}

export interface LearningPathRead {
  role_name: string;
  modules: LearningModule[];
}

export interface TrajectoryBootstrapRead {
  role_name: string;
  detected_skills: string[];
  seeded_skills: string[];
  skill_request_names: string[];
  modules: LearningModule[];
}

export interface CursorPage<T> {
  items: T[];
  has_more: boolean;
  next_cursor: string | null;
}

export function formatPercent(value: number | null | undefined): string {
  return `${Math.round(Number(value ?? 0))}%`;
}

export function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "Not available";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "Not scheduled";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function formatRelativeTime(value: string | null | undefined): string {
  if (!value) {
    return "Just now";
  }

  const parsed = new Date(value).getTime();
  if (Number.isNaN(parsed)) {
    return value;
  }

  const diffMs = parsed - Date.now();
  const absMs = Math.abs(diffMs);
  const minute = 60_000;
  const hour = 60 * minute;
  const day = 24 * hour;

  const formatter = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });

  if (absMs < hour) {
    return formatter.format(Math.round(diffMs / minute), "minute");
  }
  if (absMs < day) {
    return formatter.format(Math.round(diffMs / hour), "hour");
  }
  return formatter.format(Math.round(diffMs / day), "day");
}

export function toTitleCase(value: string): string {
  return value
    .replace(/[_-]+/g, " ")
    .split(" ")
    .filter(Boolean)
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1).toLowerCase())
    .join(" ");
}
