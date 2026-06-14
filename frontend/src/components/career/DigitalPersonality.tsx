"use client";

import Link from "next/link";

import type { CareerRecommendation, CareerRecommendationResponse } from "@/lib/celtm";
import ThemedSelect from "@/components/ThemedSelect";

export type DraftPersonalityKey = "interests" | "strengths" | "preferred_industries";

export type DraftPersonalityState = {
  interests: string[];
  strengths: string[];
  preferred_industries: string[];
  work_style: string;
  experience_level: string;
  notes: string;
};

export const initialDraftPersonality: DraftPersonalityState = {
  interests: [],
  strengths: [],
  preferred_industries: [],
  work_style: "",
  experience_level: "",
  notes: "",
};

const DRAFT_PERSONALITY_OPTIONS: Record<DraftPersonalityKey, string[]> = {
  interests: ["AI", "Data", "Cyber security", "Business", "Aviation", "Design", "Education", "Hospitality"],
  strengths: ["Problem solving", "Communication", "Discipline", "Creativity", "Technical curiosity", "Leadership"],
  preferred_industries: ["Technology", "Finance", "Healthcare", "Aviation", "Education", "Retail", "Manufacturing"],
};

const WORK_STYLE_OPTIONS = ["Structured", "Creative", "Hands-on", "Research-led"];
const EXPERIENCE_LEVEL_OPTIONS = ["Beginner", "Intermediate", "Project-ready"];

function stringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item)).filter(Boolean) : [];
}

export function normalizeDraftPersonality(value: unknown): DraftPersonalityState {
  const source = value && typeof value === "object" ? (value as Record<string, unknown>) : {};
  return {
    interests: stringArray(source.interests),
    strengths: stringArray(source.strengths),
    preferred_industries: stringArray(source.preferred_industries),
    work_style: String(source.work_style ?? ""),
    experience_level: String(source.experience_level ?? ""),
    notes: String(source.notes ?? ""),
  };
}

export function DraftPersonalityPanel({
  draft,
  isSaving,
  needsAssessment,
  recommendations,
  onToggle,
  onChange,
  onSave,
}: {
  draft: DraftPersonalityState;
  isSaving: boolean;
  needsAssessment: boolean;
  recommendations: CareerRecommendation[];
  onToggle: (key: DraftPersonalityKey, value: string) => void;
  onChange: (patch: Partial<DraftPersonalityState>) => void;
  onSave: () => void;
}) {
  const suggestedSkills = recommendations.flatMap((item) => item.suggested_skills).filter(Boolean).slice(0, 3);

  return (
    <section className="rounded-[34px] border border-outline-variant/15 bg-surface-container-low p-7">
      <div className="grid gap-7 lg:grid-cols-[1.1fr_0.9fr]">
        <div>
          <p className="text-[10px] font-black uppercase tracking-[0.22em] text-primary">No resume?</p>
          <h2 className="mt-2 text-2xl font-black tracking-tight text-on-surface">Create a draft digital CELTM personality</h2>
          <p className="mt-2 text-sm font-semibold leading-6 text-on-surface-variant">
            Select available signals for now. CELTM will use them only as a temporary personality draft until resume, links, credentials, and assessments replace it with stronger evidence.
          </p>
          <div className="mt-6 space-y-5">
            {(Object.keys(DRAFT_PERSONALITY_OPTIONS) as DraftPersonalityKey[]).map((key) => (
              <div key={key}>
                <p className="mb-2 text-[10px] font-black uppercase tracking-widest text-on-surface-variant">
                  {key.replace(/_/g, " ")}
                </p>
                <div className="flex flex-wrap gap-2">
                  {DRAFT_PERSONALITY_OPTIONS[key].map((option) => {
                    const selected = draft[key].includes(option);
                    return (
                      <button
                        key={option}
                        type="button"
                        onClick={() => onToggle(key, option)}
                        className={`rounded-full px-4 py-2 text-xs font-black transition-all duration-200 hover:-translate-y-0.5 ${
                          selected ? "bg-primary text-white shadow-sm shadow-primary/25" : "bg-surface text-on-surface-variant hover:bg-primary/10 hover:text-primary"
                        }`}
                      >
                        {option}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
            <div className="grid gap-4 sm:grid-cols-2">
              <ThemedSelect
                value={draft.work_style}
                onChange={(value) => onChange({ work_style: value })}
                placeholder="Work style"
                options={WORK_STYLE_OPTIONS.map((option) => ({ value: option, label: option }))}
              />
              <ThemedSelect
                value={draft.experience_level}
                onChange={(value) => onChange({ experience_level: value })}
                placeholder="Experience level"
                options={EXPERIENCE_LEVEL_OPTIONS.map((option) => ({ value: option, label: option }))}
              />
            </div>
            <textarea
              value={draft.notes}
              onChange={(event) => onChange({ notes: event.target.value })}
              rows={3}
              placeholder="Optional context: projects, certificates, constraints, or roles you are considering."
              className="w-full resize-none rounded-2xl border border-outline-variant/15 bg-surface px-4 py-3 text-sm font-semibold text-on-surface outline-none transition focus:border-primary/40 focus:ring-4 focus:ring-primary/10"
            />
            <button
              type="button"
              onClick={onSave}
              disabled={isSaving}
              className="rounded-2xl bg-primary px-5 py-3 text-[11px] font-black uppercase tracking-[0.18em] text-white transition hover:-translate-y-0.5 hover:shadow-lg hover:shadow-primary/20 disabled:opacity-60"
            >
              {isSaving ? "Building..." : "Build draft personality"}
            </button>
          </div>
        </div>
        <div className="rounded-[28px] bg-surface p-5">
          <p className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant">Assessment-gated skill suggestions</p>
          {needsAssessment ? (
            <div className="mt-4 rounded-2xl bg-amber-500/10 p-4 text-sm font-bold leading-6 text-amber-700 dark:text-amber-300">
              Complete at least one assessment before CELTM generates the top 3 suggested skills from your measured capability profile.
              <Link href="/assessments" className="mt-3 block text-[10px] font-black uppercase tracking-[0.18em] text-primary">
                Take assessment
              </Link>
            </div>
          ) : (
            <div className="mt-4 flex flex-wrap gap-2">
              {(suggestedSkills.length ? suggestedSkills : ["No skill gaps found yet"]).map((skill) => (
                <span key={skill} className="rounded-full bg-primary/10 px-3 py-1.5 text-xs font-black text-primary">
                  {skill}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

export function CareerRecommendationPanel({
  payload,
  activeTargetRole,
  actionRole,
  isAnalyzingAll,
  activeRoleAction,
  onSelectPath,
  onAnalyzeAll,
  onSetActiveRole,
}: {
  payload: CareerRecommendationResponse | null;
  activeTargetRole: string;
  actionRole: string | null;
  isAnalyzingAll: boolean;
  activeRoleAction?: string | null;
  onSelectPath: (role: string) => void;
  onAnalyzeAll: () => void;
  onSetActiveRole?: (role: string) => void;
}) {
  const recommendations = payload?.recommendations ?? [];

  return (
    <section className="clay-card rounded-[34px] p-7">
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-[10px] font-black uppercase tracking-[0.22em] text-primary">AI predicted career path</p>
          <h2 className="mt-2 text-2xl font-black tracking-tight text-on-surface">Top 3 fits CELTM can analyze</h2>
          <p className="mt-2 max-w-3xl text-sm font-semibold leading-6 text-on-surface-variant">
            {activeTargetRole
              ? `Your saved aim is included in the prediction set: ${activeTargetRole}.`
              : "No career aim is saved yet. These are the strongest starting paths from your current CELTM evidence."}
          </p>
        </div>
        <button
          type="button"
          onClick={onAnalyzeAll}
          disabled={!recommendations.length || isAnalyzingAll}
          className="rounded-2xl bg-primary px-5 py-3 text-[11px] font-black uppercase tracking-[0.18em] text-white transition hover:-translate-y-0.5 hover:shadow-lg hover:shadow-primary/20 disabled:opacity-60"
        >
          {isAnalyzingAll ? "Analyzing..." : "Analyze all 3 in career aim"}
        </button>
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        {recommendations.length ? recommendations.map((item) => (
          <div
            key={`${item.rank}-${item.role}`}
            className={`rounded-[28px] border p-5 text-left transition hover:-translate-y-0.5 hover:shadow-lg ${
              item.is_primary
                ? "border-primary/30 bg-primary/10"
                : "border-outline-variant/15 bg-surface-container-low"
            }`}
          >
            <div className="flex items-start justify-between gap-4">
              <span className="rounded-full bg-surface px-3 py-1 text-[10px] font-black uppercase tracking-widest text-primary">
                Rank {item.rank}
              </span>
              <span className="text-2xl font-black text-on-surface">{Math.round(item.fit_score)}%</span>
            </div>
            <h3 className="mt-4 text-xl font-black text-on-surface">{item.role}</h3>
            <p className="mt-2 text-sm font-semibold leading-6 text-on-surface-variant">{item.reason}</p>
            <div className="mt-4 rounded-2xl bg-surface px-4 py-3">
              <p className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant">
                {item.is_primary ? "Main DB readiness" : "Role readiness"}
              </p>
              <p className="mt-1 text-sm font-black text-on-surface">{Math.round(item.readiness_score)}%</p>
              <p className="mt-1 text-[11px] font-semibold leading-5 text-on-surface-variant">{item.readiness_note}</p>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              {(item.evidence?.primary_gaps ?? []).slice(0, 3).map((gap) => (
                <span key={gap} className="rounded-full bg-surface px-3 py-1 text-[10px] font-black text-on-surface-variant">
                  {gap}
                </span>
              ))}
            </div>
            <p className="mt-5 text-[10px] font-black uppercase tracking-[0.18em] text-primary">
              {normalizeRole(activeTargetRole) === normalizeRole(item.role) ? "Active focus role" : "Suggested career aim"}
            </p>
            <div className="mt-4 grid gap-2">
              {onSetActiveRole ? (
                <button
                  type="button"
                  onClick={() => onSetActiveRole(item.role)}
                  disabled={activeRoleAction === item.role || normalizeRole(activeTargetRole) === normalizeRole(item.role)}
                  className="rounded-2xl bg-primary px-4 py-3 text-[10px] font-black uppercase tracking-[0.16em] text-white transition hover:-translate-y-0.5 disabled:opacity-60"
                >
                  {normalizeRole(activeTargetRole) === normalizeRole(item.role)
                    ? "Active career aim"
                    : activeRoleAction === item.role
                      ? "Setting active..."
                      : "Set as active career aim"}
                </button>
              ) : null}
              <button
                type="button"
                onClick={() => onSelectPath(item.role)}
                disabled={Boolean(actionRole)}
                className="rounded-2xl bg-surface px-4 py-3 text-[10px] font-black uppercase tracking-[0.16em] text-primary transition hover:-translate-y-0.5 disabled:opacity-60"
              >
                {actionRole === item.role ? "Opening..." : "Analyze career path"}
              </button>
            </div>
          </div>
        )) : (
          <div className="col-span-full rounded-[28px] border border-dashed border-outline-variant/25 bg-surface-container-low p-6 text-sm font-semibold text-on-surface-variant">
            Career predictions are loading from your live profile.
          </div>
        )}
      </div>
    </section>
  );
}

function normalizeRole(value: string) {
  return value.trim().toLowerCase();
}
