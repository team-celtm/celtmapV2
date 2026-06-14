"use client";

import { FormEvent, useEffect, useState } from "react";
import { ApiError, apiFetch } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import CeltmProgressLoader from "@/components/CeltmProgressLoader";
import CareerRoleInput from "@/components/career/CareerRoleInput";
import type { CareerRecommendation, CareerRecommendationResponse, CareerRoleOption } from "@/lib/celtm";

type RoadmapPhaseKey = "roadmap_30_days" | "roadmap_60_days" | "roadmap_90_days";

interface RoadmapPhaseDetail {
  title?: string;
  summary?: string;
  certificates?: string[];
  practice?: string[];
  evidence?: string[];
}

interface Aspiration {
  id: string;
  desired_role: string;
  current_readiness: number;
  major_gaps: string[];
  better_current_fit: string[];
  roadmap: {
    roadmap_30_days?: string[];
    roadmap_60_days?: string[];
    roadmap_90_days?: string[];
  };
  infographics: Array<{ label: string; value: string; helper: string }>;
  analysis: {
    summary?: string;
    strengths?: string[];
    gaps?: string[];
    latest_readiness_score?: number;
    analyzed_at?: string;
    roadmap_details?: Partial<Record<RoadmapPhaseKey, RoadmapPhaseDetail>>;
    role_specific_readiness?: {
      global_readiness?: number;
      role_profile?: string;
      required_dimension_gaps?: Array<{ dimension: string; score: number; gap_to_ready: number }>;
    };
    latest_role_specific_readiness?: {
      score?: number;
      role_profile?: string;
    };
  };
  created_at: string;
  updated_at?: string;
}

export default function CareerAimPage() {
  const [items, setItems] = useState<Aspiration[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [desiredRole, setDesiredRole] = useState("");
  const [roleOptions, setRoleOptions] = useState<CareerRoleOption[]>([]);
  const [recommendations, setRecommendations] = useState<CareerRecommendationResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [isReanalyzing, setIsReanalyzing] = useState(false);
  const [recommendationRole, setRecommendationRole] = useState<string | null>(null);
  const [isAnalyzingAllRecommendations, setIsAnalyzingAllRecommendations] = useState(false);
  const [isCreateComplete, setIsCreateComplete] = useState(false);
  const [activePhase, setActivePhase] = useState<RoadmapPhaseKey>("roadmap_30_days");
  const [error, setError] = useState("");
  const { refreshProfile } = useAuth();

  const load = async () => {
    try {
      setIsLoading(true);
      setError("");
      const [aspirations, recommendationPayload, rolePayload] = await Promise.all([
        apiFetch<Aspiration[]>("/career-aspirations"),
        apiFetch<CareerRecommendationResponse>("/career-recommendations").catch(() => null),
        apiFetch<CareerRoleOption[]>("/career-roles"),
      ]);
      setItems(aspirations);
      setRecommendations(recommendationPayload);
      setRoleOptions(rolePayload);
      if (typeof window !== "undefined") {
        const selected = new URLSearchParams(window.location.search).get("selected");
        if (selected) {
          setSelectedId(selected);
        }
      }
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Failed to load career aims.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  useEffect(() => {
    if (items.length > 0 && !selectedId) {
      setSelectedId(items[0].id);
    }
  }, [items, selectedId]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!desiredRole.trim()) return;
    try {
      setIsCreating(true);
      setIsCreateComplete(false);
      setError("");
      const created = await apiFetch<Aspiration>("/career-aspirations", {
        method: "POST",
        body: JSON.stringify({ desired_role: desiredRole.trim() }),
      });
      setIsCreateComplete(true);
      await new Promise((resolve) => window.setTimeout(resolve, 650));
      setItems((current) => [created, ...current]);
      setSelectedId(created.id);
      setDesiredRole("");
      await refreshProfile();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Career inference failed.");
    } finally {
      setIsCreating(false);
      setIsCreateComplete(false);
    }
  };

  const latest = (items.find(i => i.id === selectedId) || items[0]) ?? null;
  const latestGlobalReadiness =
    typeof latest?.analysis?.latest_readiness_score === "number"
      ? latest.analysis.latest_readiness_score
      : latest?.analysis?.role_specific_readiness?.global_readiness;
  const analysisDate = latest?.analysis?.analyzed_at || latest?.created_at || null;
  const analysisAgeDays = daysSince(analysisDate);
  const staleLevel = analysisAgeDays >= 5 ? "red" : analysisAgeDays >= 2 ? "amber" : null;
  const activePhaseDetail = latest
    ? latest.analysis?.roadmap_details?.[activePhase] ?? fallbackPhaseDetail(latest, activePhase)
    : null;

  useEffect(() => {
    setActivePhase("roadmap_30_days");
  }, [selectedId]);

  const reanalyzeSelected = async () => {
    if (!latest) return;
    try {
      setIsReanalyzing(true);
      setError("");
      const updated = await apiFetch<Aspiration>(`/career-aspirations/${latest.id}/reanalyze`, {
        method: "POST",
      });
      setItems((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setSelectedId(updated.id);
      await refreshProfile();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Career reanalysis failed.");
    } finally {
      setIsReanalyzing(false);
    }
  };

  const analyzeRecommendation = async (role: string) => {
    try {
      setRecommendationRole(role);
      setError("");
      const created = await apiFetch<Aspiration>("/career-aspirations", {
        method: "POST",
        body: JSON.stringify({ desired_role: role }),
      });
      setItems((current) => {
        const withoutDuplicate = current.filter((item) => item.id !== created.id);
        return [created, ...withoutDuplicate];
      });
      setSelectedId(created.id);
      window.history.replaceState(null, "", `/career-aim?selected=${encodeURIComponent(created.id)}`);
      await refreshProfile();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Career recommendation analysis failed.");
    } finally {
      setRecommendationRole(null);
    }
  };

  const analyzeAllRecommendations = async () => {
    const roles = (recommendations?.recommendations ?? []).map((item) => item.role).slice(0, 3);
    if (!roles.length) return;
    try {
      setIsAnalyzingAllRecommendations(true);
      setError("");
      const created = await apiFetch<Aspiration[]>("/career-aspirations/recommended", {
        method: "POST",
        body: JSON.stringify({ desired_roles: roles }),
      });
      setItems((current) => {
        const createdIds = new Set(created.map((item) => item.id));
        return [...created, ...current.filter((item) => !createdIds.has(item.id))];
      });
      if (created[0]) {
        setSelectedId(created[0].id);
        window.history.replaceState(null, "", `/career-aim?selected=${encodeURIComponent(created[0].id)}`);
      }
      await refreshProfile();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not analyze the recommended career paths.");
    } finally {
      setIsAnalyzingAllRecommendations(false);
    }
  };

  return (
    <div className="mx-auto w-full max-w-[1320px] space-y-8 pb-12">
      {error ? <div className="rounded-3xl bg-red-500/10 px-5 py-4 text-sm font-bold text-red-500">{error}</div> : null}

      <section className="clay-card rounded-[36px] p-8 md:p-10">
        <div className="grid gap-8 lg:grid-cols-[1fr_420px] lg:items-center">
          <div>
            <p className="text-[11px] font-black uppercase tracking-[0.24em] text-primary">What You Want To Be</p>
            <h1 className="mt-3 text-4xl font-black tracking-tight text-on-surface md:text-5xl">Career aim tracker</h1>
            <p className="mt-4 max-w-3xl text-lg leading-8 text-on-surface-variant">
              Choose what you want to become. CELTM compares your global readiness with role-specific gaps and saves a dated plan you can revisit.
            </p>
          </div>
          <form onSubmit={submit} className="rounded-[30px] bg-surface-container-low p-5">
            <CareerRoleInput
              required
              label="Desired role"
              value={desiredRole}
              onChange={setDesiredRole}
              placeholder="Type any aim, e.g. CA, IAS, UX designer"
              options={roleOptions}
            />
            <p className="mt-3 text-xs font-semibold leading-5 text-on-surface-variant">
              Type freely. CELTM will normalize abbreviations and custom aims before generating the roadmap.
            </p>
            <button
              type="submit"
              disabled={isCreating || !desiredRole.trim()}
              className="mt-4 w-full rounded-2xl bg-primary px-5 py-4 text-[11px] font-black uppercase tracking-[0.18em] text-white disabled:opacity-60"
            >
              {isCreating ? "Analyzing..." : "Analyze my path"}
            </button>
          </form>
        </div>
      </section>

      <CareerRecommendationRail
        recommendations={recommendations?.recommendations ?? []}
        activeRole={recommendationRole}
        isAnalyzingAll={isAnalyzingAllRecommendations}
        onSelect={(role) => void analyzeRecommendation(role)}
        onAnalyzeAll={() => void analyzeAllRecommendations()}
      />

      {isLoading ? (
        <CeltmProgressLoader
          title="Loading career aim"
          caption="Cooking your goal"
          stages={["Fetching saved ambitions", "Rechecking latest readiness", "Preparing your roadmap view", "Opening the analysis"]}
        />
      ) : isCreating ? (
        <CeltmProgressLoader
          title="Career aim analysis"
          caption="Cooking your goal"
          forceComplete={isCreateComplete}
          stages={["Understanding the role", "Comparing your readiness", "Finding priority gaps", "Writing your action plan"]}
        />
      ) : isReanalyzing ? (
        <CeltmProgressLoader
          title="Refreshing career match"
          caption="Rechecking this ambition"
          stages={["Reading latest evidence", "Reweighting role skills", "Rebuilding the match score", "Updating roadmap details"]}
        />
      ) : latest ? (
        <>
          <section className="grid gap-6 lg:grid-cols-[1fr_2fr]">
            {/* Infographic Hero */}
            <div className="clay-card rounded-[36px] flex flex-col items-center justify-center p-10 text-center relative overflow-hidden bg-gradient-to-b from-primary/5 to-transparent">
              <div className="relative flex items-center justify-center mb-6">
                <svg className="w-48 h-48 -rotate-90 transform" viewBox="0 0 160 160">
                  <circle cx="80" cy="80" r="70" stroke="currentColor" strokeWidth="12" fill="transparent" className="text-surface-container-high" />
                  <circle
                    cx="80" cy="80" r="70" stroke="currentColor" strokeWidth="12" fill="transparent"
                    strokeDasharray={2 * Math.PI * 70}
                    strokeDashoffset={2 * Math.PI * 70 * (1 - Math.max(0, Math.min(100, latest.current_readiness)) / 100)}
                    strokeLinecap="round"
                    className="text-primary transition-all duration-1000 ease-out"
                  />
                </svg>
                <div className="absolute flex flex-col items-center justify-center">
                  <span className="text-5xl font-black text-on-surface">{Math.round(latest.current_readiness)}<span className="text-2xl">%</span></span>
                </div>
              </div>
              <div className="mt-0 mb-4 flex justify-center">
                <span className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant">Saved match score</span>
              </div>
              <h2 className="text-2xl font-black text-on-surface">{latest.desired_role}</h2>
              <p className="mt-2 text-sm font-bold text-on-surface-variant">
                {latest.analysis?.role_specific_readiness?.role_profile || "Role-specific ambition"}
              </p>
              {typeof latestGlobalReadiness === "number" ? (
                <p className="mt-4 rounded-full bg-surface-container-low px-4 py-2 text-xs font-black uppercase tracking-widest text-primary">
                  Global readiness {Math.round(latestGlobalReadiness)}%
                </p>
              ) : null}
            </div>

            {/* Gap Analysis */}
            <div className="grid gap-6 grid-rows-2">
              <div className="clay-card rounded-[30px] p-8 flex items-center gap-6">
                <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full bg-red-500/10 text-red-500">
                  <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5"><path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
                </div>
                <div>
                  <p className="text-[11px] font-black uppercase tracking-[0.2em] text-red-500">Top Priority Gap</p>
                  <p className="mt-2 text-xl font-black text-on-surface">{(Array.isArray(latest.major_gaps) && latest.major_gaps[0]) ? latest.major_gaps[0] : "Pending"}</p>
                  <p className="mt-1 text-sm text-on-surface-variant">Focus your efforts here first</p>
                </div>
              </div>

              <div className="clay-card rounded-[30px] p-8 flex items-center gap-6">
                <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-500">
                  <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5"><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>
                </div>
                <div>
                  <p className="text-[11px] font-black uppercase tracking-[0.2em] text-emerald-500">Better Fit Alternative</p>
                  <p className="mt-2 text-xl font-black text-on-surface">{(Array.isArray(latest.better_current_fit) && latest.better_current_fit[0]) ? latest.better_current_fit[0] : "None identified"}</p>
                  <p className="mt-1 text-sm text-on-surface-variant">Consider this role for immediate placement</p>
                </div>
              </div>
            </div>
          </section>

          {staleLevel ? (
            <section
              className={`rounded-[32px] border px-6 py-5 ${
                staleLevel === "red"
                  ? "border-red-500/25 bg-red-500/10 text-red-700 dark:text-red-300"
                  : "border-amber-500/25 bg-amber-500/10 text-amber-700 dark:text-amber-300"
              }`}
            >
              <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div>
                  <p className="text-[10px] font-black uppercase tracking-[0.22em]">
                    {staleLevel === "red" ? "Analysis is outdated" : "Analysis may be stale"}
                  </p>
                  <p className="mt-2 text-sm font-bold leading-6">
                    This match score was analyzed {analysisAgeDays} days ago. Re-analyze this ambition for a more precise role match using the latest resume, assessments, written score, and credentials.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={reanalyzeSelected}
                  disabled={isReanalyzing}
                  className={`shrink-0 rounded-2xl px-5 py-3 text-[11px] font-black uppercase tracking-[0.18em] text-white ${
                    staleLevel === "red" ? "bg-red-600" : "bg-amber-600"
                  } disabled:opacity-60`}
                >
                  Analyze again
                </button>
              </div>
            </section>
          ) : null}

          {/* Timeline Roadmap */}
          <section className="clay-card rounded-[36px] p-8 md:p-10">
            <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between border-b border-outline-variant/30 pb-6 mb-8">
              <div>
                <p className="text-[11px] font-black uppercase tracking-[0.24em] text-primary">Execution Plan</p>
                <h2 className="mt-2 text-3xl font-black text-on-surface">Your Roadmap to {latest.desired_role}</h2>
              </div>
              <p className="text-sm font-bold text-on-surface-variant">Saved {new Date(latest.created_at).toLocaleDateString()}</p>
            </div>

            <p className="max-w-4xl text-base leading-8 text-on-surface-variant mb-10">
              {latest.analysis?.summary || "Follow this staged plan and reassess after every major improvement."}
            </p>
            {activePhaseDetail ? (
              <div className="mb-8 rounded-[24px] bg-surface-container-low px-5 py-4">
                <p className="text-[10px] font-black uppercase tracking-[0.22em] text-primary">
                  Selected phase
                </p>
                <p className="mt-2 text-sm font-bold leading-6 text-on-surface-variant">
                  {activePhaseDetail.summary || activePhaseDetail.title || "Use this phase to convert practice into visible proof."}
                </p>
              </div>
            ) : null}

            <div className="relative border-l-4 border-surface-container-high ml-6 space-y-12 pb-4">
              <TimelinePhase
                phaseKey="roadmap_30_days"
                phase="30 Days"
                items={latest.roadmap?.roadmap_30_days || []}
                color="text-primary"
                bg="bg-primary"
                active={activePhase === "roadmap_30_days"}
                onSelect={setActivePhase}
                phaseDetail={latest.analysis?.roadmap_details?.roadmap_30_days ?? fallbackPhaseDetail(latest, "roadmap_30_days")}
              />
              <TimelinePhase
                phaseKey="roadmap_60_days"
                phase="60 Days"
                items={latest.roadmap?.roadmap_60_days || []}
                color="text-amber-500"
                bg="bg-amber-500"
                active={activePhase === "roadmap_60_days"}
                onSelect={setActivePhase}
                phaseDetail={latest.analysis?.roadmap_details?.roadmap_60_days ?? fallbackPhaseDetail(latest, "roadmap_60_days")}
              />
              <TimelinePhase
                phaseKey="roadmap_90_days"
                phase="90 Days"
                items={latest.roadmap?.roadmap_90_days || []}
                color="text-emerald-500"
                bg="bg-emerald-500"
                active={activePhase === "roadmap_90_days"}
                onSelect={setActivePhase}
                phaseDetail={latest.analysis?.roadmap_details?.roadmap_90_days ?? fallbackPhaseDetail(latest, "roadmap_90_days")}
              />
            </div>
          </section>

          <section className="clay-card rounded-[32px] p-7">
            <h2 className="text-2xl font-black tracking-tight text-on-surface">Saved history</h2>
            <div className="mt-5 grid gap-3 lg:grid-cols-2">
              {items.map((item) => (
                <div
                  key={item.id}
                  onClick={() => {
                    setSelectedId(item.id);
                    window.scrollTo({ top: 0, behavior: 'smooth' });
                  }}
                  className={`rounded-3xl bg-surface-container-low px-6 py-5 flex items-center justify-between border-2 transition-colors cursor-pointer ${selectedId === item.id ? 'border-primary' : 'border-transparent hover:border-primary/20'}`}
                >
                  <div>
                    <p className="font-black text-lg text-on-surface">{item.desired_role}</p>
                    <p className="text-xs font-bold text-on-surface-variant mt-1">{new Date(item.created_at).toLocaleDateString()}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="h-2 w-24 rounded-full bg-surface-container-high overflow-hidden hidden sm:block">
                      <div className="h-full bg-primary" style={{ width: `${Math.min(100, item.current_readiness)}%` }} />
                    </div>
                    <p className="text-sm font-black text-primary w-24 text-right">{Math.round(item.current_readiness)}% role fit</p>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </>
      ) : (
        <section className="rounded-[36px] border border-dashed border-outline-variant/25 bg-surface-container-low p-10 text-center">
          <h2 className="text-2xl font-black text-on-surface">No career aim saved yet</h2>
          <p className="mx-auto mt-3 max-w-xl text-sm leading-7 text-on-surface-variant">
            Add a desired role above. CELTM will save the result so you can compare improvement over time.
          </p>
        </section>
      )}
    </div>
  );
}

function CareerRecommendationRail({
  recommendations,
  activeRole,
  isAnalyzingAll,
  onSelect,
  onAnalyzeAll,
}: {
  recommendations: CareerRecommendation[];
  activeRole: string | null;
  isAnalyzingAll: boolean;
  onSelect: (role: string) => void;
  onAnalyzeAll: () => void;
}) {
  return (
    <section className="clay-card rounded-[32px] p-7">
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-[10px] font-black uppercase tracking-[0.22em] text-primary">AI recommendations</p>
          <h2 className="mt-2 text-2xl font-black tracking-tight text-on-surface">Analyze the predicted top 3 paths</h2>
          <p className="mt-2 max-w-3xl text-sm font-semibold leading-6 text-on-surface-variant">
            These are the same dashboard predictions. Selecting one saves it as a dated Career Aim analysis.
          </p>
        </div>
        <button
          type="button"
          onClick={onAnalyzeAll}
          disabled={!recommendations.length || isAnalyzingAll}
          className="rounded-2xl bg-primary px-5 py-3 text-[11px] font-black uppercase tracking-[0.18em] text-white disabled:opacity-60"
        >
          {isAnalyzingAll ? "Analyzing..." : "Analyze all 3"}
        </button>
      </div>
      <div className="mt-5 grid gap-3 lg:grid-cols-3">
        {recommendations.length ? recommendations.map((item) => (
          <button
            key={`${item.rank}-${item.role}`}
            type="button"
            onClick={() => onSelect(item.role)}
            disabled={Boolean(activeRole)}
            className="rounded-[24px] border border-outline-variant/15 bg-surface-container-low p-5 text-left transition hover:border-primary/30 disabled:opacity-60"
          >
            <div className="flex items-start justify-between gap-3">
              <p className="text-[10px] font-black uppercase tracking-widest text-primary">Rank {item.rank}</p>
              <p className="text-lg font-black text-on-surface">{Math.round(item.fit_score)}%</p>
            </div>
            <h3 className="mt-3 text-lg font-black text-on-surface">{item.role}</h3>
            <p className="mt-2 text-xs font-semibold leading-5 text-on-surface-variant">{item.path_summary}</p>
            <p className="mt-4 text-[10px] font-black uppercase tracking-[0.18em] text-primary">
              {activeRole === item.role ? "Saving..." : "Analyze this path"}
            </p>
          </button>
        )) : (
          <div className="col-span-full rounded-[24px] border border-dashed border-outline-variant/25 bg-surface-container-low p-5 text-sm font-semibold text-on-surface-variant">
            Recommendations will appear after CELTM reads your live profile.
          </div>
        )}
      </div>
    </section>
  );
}

function TimelinePhase({
  phaseKey,
  phase,
  items,
  color,
  bg,
  active,
  onSelect,
  phaseDetail,
}: {
  phaseKey: RoadmapPhaseKey;
  phase: string;
  items: string[];
  color: string;
  bg: string;
  active: boolean;
  onSelect: (phase: RoadmapPhaseKey) => void;
  phaseDetail?: RoadmapPhaseDetail | null;
}) {
  return (
    <div className="relative block w-full pl-10 text-left">
      <button
        type="button"
        onClick={() => onSelect(phaseKey)}
        className={`absolute -left-[14px] top-1.5 h-6 w-6 rounded-full border-4 border-white shadow-sm transition-transform hover:scale-110 focus:outline-none ${active ? bg : 'bg-surface-container-high'}`}
      />

      <button
        type="button"
        onClick={() => onSelect(phaseKey)}
        className="block w-full text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-primary rounded-xl"
      >
        <h3 className={`text-lg font-black uppercase tracking-wider ${active ? color : 'text-on-surface-variant transition-colors hover:text-on-surface'}`}>{phase}</h3>
      </button>

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        {(Array.isArray(items) && items.length ? items : ["Reassess after completing earlier steps."]).map((item, i) => (
          <div key={i} className={`rounded-2xl bg-surface-container-low p-5 border transition-colors ${active ? "border-primary/30 shadow-[0_4px_20px_rgb(0,0,0,0.03)]" : "border-outline-variant/10 opacity-70"}`}>
            <p className="text-sm font-bold leading-6 text-on-surface-variant">{item}</p>
          </div>
        ))}
      </div>

      {active && phaseDetail ? (
        <div className="mt-6 rounded-[24px] bg-surface/50 p-6 border border-primary/10 shadow-sm animate-in fade-in slide-in-from-top-4 duration-300">
          <p className="text-[10px] font-black uppercase tracking-[0.22em] text-primary">{phaseTitle(phaseKey)} details</p>
          <h3 className="mt-2 text-xl font-black text-on-surface">{phaseDetail.title || "Detailed path"}</h3>
          <p className="mt-2 max-w-3xl text-sm font-semibold leading-7 text-on-surface-variant">
            {phaseDetail.summary || "Use this phase to convert practice into visible proof."}
          </p>
          <div className="mt-6 grid gap-4 md:grid-cols-3">
            <PhaseDetailColumn title="Certificates to consider" items={phaseDetail.certificates} />
            <PhaseDetailColumn title="Practice to assign" items={phaseDetail.practice} />
            <PhaseDetailColumn title="Evidence to upload" items={phaseDetail.evidence} />
          </div>
        </div>
      ) : null}
    </div>
  );
}

function PhaseDetailColumn({ title, items }: { title: string; items?: string[] }) {
  const safeItems = Array.isArray(items) && items.length ? items : ["No specific item assigned yet."];
  return (
    <div className="rounded-2xl bg-surface px-5 py-4">
      <p className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant">{title}</p>
      <ul className="mt-3 space-y-2">
        {safeItems.map((item) => (
          <li key={item} className="text-sm font-semibold leading-6 text-on-surface">
            - {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

function daysSince(value: string | null | undefined) {
  if (!value) return 0;
  const timestamp = new Date(value).getTime();
  if (Number.isNaN(timestamp)) return 0;
  return Math.max(0, Math.floor((Date.now() - timestamp) / (1000 * 60 * 60 * 24)));
}

function phaseTitle(phase: RoadmapPhaseKey) {
  if (phase === "roadmap_60_days") return "60 day";
  if (phase === "roadmap_90_days") return "90 day";
  return "30 day";
}

function fallbackPhaseDetail(aspiration: Aspiration, phase: RoadmapPhaseKey): RoadmapPhaseDetail {
  const role = aspiration.desired_role || "the target role";
  const gaps = aspiration.major_gaps?.length ? aspiration.major_gaps : ["role foundation"];
  if (phase === "roadmap_60_days") {
    return {
      title: "Role-specific practice",
      summary: `Move from foundation work to practical tasks expected for ${role}.`,
      certificates: ["Intermediate role certificate", "Mentor-reviewed project proof"],
      practice: [`Practice ${gaps[1] || gaps[0]}`, "Complete one timed written case", "Compare before and after scores"],
      evidence: ["Mentor feedback note", "Improved assessment score", "Portfolio artifact"],
    };
  }
  if (phase === "roadmap_90_days") {
    return {
      title: "Selection readiness",
      summary: `Prepare for interviews, screening tests, or entry programs related to ${role}.`,
      certificates: ["Final certificate set", "Mock interview completion"],
      practice: ["Mock interview", "Final gap retest", "Application plan review"],
      evidence: ["Interview feedback", "Updated resume", "Final proof upload"],
    };
  }
  return {
    title: "Foundation proof",
    summary: `Validate whether ${role} is realistic from the current evidence and close the first visible gap.`,
    certificates: ["Foundation certificate", "Verified learning proof"],
    practice: [`Practice ${gaps[0]}`, "Complete one baseline assessment", "Upload one proof artifact"],
    evidence: ["Certificate upload", "Practice notes", "Resume bullet update"],
  };
}
