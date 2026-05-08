"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";

import { apiFetch, getApiErrorMessage } from "@/lib/api";
const SchedulePlanner = dynamic(() => import("@/components/schedule/SchedulePlanner").then(mod => mod.SchedulePlanner), {
  ssr: false,
  loading: () => <div className="h-96 w-full animate-pulse rounded-3xl bg-surface-container-low" />
});

const SkillDonutChart = dynamic(() => import("@/components/skills/SkillDonutChart").then(mod => mod.SkillDonutChart), {
  ssr: false,
  loading: () => <div className="h-64 w-64 animate-pulse rounded-full bg-surface-container-low" />
});

const SkillInsightModal = dynamic(() => import("@/components/skills/SkillInsightModal").then(mod => mod.SkillInsightModal), {
  ssr: false
});

const ExamLog = dynamic(() => import("@/components/dashboard/ExamLog").then(mod => mod.ExamLog), {
  ssr: false,
  loading: () => <div className="grid gap-4 sm:grid-cols-2">
    {[1, 2, 3, 4].map((i) => (
      <div key={i} className="h-40 animate-pulse rounded-3xl bg-surface-container-low" />
    ))}
  </div>
});

import { ExamInsightModal } from "@/components/dashboard/ExamInsightModal";
import { ResumeReminderPopup } from "@/components/dashboard/ResumeReminderPopup";
import { useAuth } from "@/contexts/AuthContext";
import { supabase } from "@/lib/supabase";
import { ListSkeleton, SectionSkeleton, StatCardSkeleton } from "@/components/common/Skeletons";
import type {
  ArtifactRead,
  AssessmentLogEntry,
  CursorPage,
  DashboardSummary,
  ProfileRead,
  ReportRead,
  RoleFitRead,
  ScheduleEventPayload,
  ScheduleEvent,
  SkillGapRead,
  SkillRead,
} from "@/lib/celtm";
import { formatDate, formatPercent, formatRelativeTime } from "@/lib/celtm";

interface DashboardState {
  summary: DashboardSummary;
  roleFit: RoleFitRead;
  skills: SkillRead[];
  gaps: SkillGapRead[];
  profile: ProfileRead;
  artifacts: ArtifactRead[];
  events: ScheduleEvent[];
  latestReport: ReportRead | null;
}

const emptySummary: DashboardSummary = {
  user_id: "",
  readiness_score: 0,
  role_fit: 0,
  top_skills: [],
  domain_breakdown: {},
  pending_hidden_skills: 0,
  next_event: null,
  latest_report_id: null,
  latest_report_created_at: null,
};

const emptyRoleFit: RoleFitRead = {
  role_name: "Unassigned",
  fit_score: 0,
  matched_skills: [],
  missing_skills: [],
};

const emptyProfile: ProfileRead = {
  id: "",
  email: null,
  full_name: null,
  headline: null,
  focus_role: null,
  weekly_goal: null,
  avatar_url: null,
  metadata: {},
  created_at: null,
  updated_at: null,
};

const emptyState: DashboardState = {
  summary: emptySummary,
  roleFit: emptyRoleFit,
  skills: [],
  gaps: [],
  profile: emptyProfile,
  artifacts: [],
  events: [],
  latestReport: null,
};

function EmptyPanel({
  title,
  body,
  actionHref,
  actionLabel,
}: {
  title: string;
  body: string;
  actionHref: string;
  actionLabel: string;
}) {
  return (
    <div className="rounded-3xl border border-dashed border-outline-variant/20 dark:border-transparent bg-surface-container-low px-5 py-6">
      <h4 className="text-sm font-bold text-on-surface">{title}</h4>
      <p className="mt-2 text-sm leading-6 text-on-surface-variant">{body}</p>
      <Link
        href={actionHref}
        className="mt-4 inline-flex rounded-full bg-primary/10 px-4 py-2 text-[11px] font-black uppercase tracking-[0.18em] text-primary transition hover:bg-primary/15"
      >
        {actionLabel}
      </Link>
    </div>
  );
}

function buildLoadWarning(failedSections: Array<{ label: string; reason: unknown }>, fallback: string) {
  if (!failedSections.length) {
    return null;
  }

  const labels = failedSections.map((section) => section.label).join(", ");
  const detail = getApiErrorMessage(failedSections[0].reason, fallback);
  return `Some live dashboard data is unavailable right now (${labels}). ${detail}`;
}

export default function DashboardPage() {
  const { user, isLoading: isAuthLoading } = useAuth();
  
  // Split state into granular pieces to prevent full-page re-renders
  const [summary, setSummary] = useState<DashboardSummary>(emptySummary);
  const [roleFit, setRoleFit] = useState<RoleFitRead>(emptyRoleFit);
  const [skills, setSkills] = useState<SkillRead[]>([]);
  const [gaps, setGaps] = useState<SkillGapRead[]>([]);
  const [profile, setProfile] = useState<ProfileRead>(emptyProfile);
  const [artifacts, setArtifacts] = useState<ArtifactRead[]>([]);
  const [events, setEvents] = useState<ScheduleEvent[]>([]);
  const [latestReport, setLatestReport] = useState<ReportRead | null>(null);

  const [isSummaryLoading, setIsSummaryLoading] = useState(true);
  const [isPathLoading, setIsPathLoading] = useState(true);
  const [isLoading, setIsLoading] = useState(true); // Global fallback 
  const [error, setError] = useState<string | null>(null);
  const [selectedSkillId, setSelectedSkillId] = useState<string | null>(null);
  const [selectedLogEntry, setSelectedLogEntry] = useState<AssessmentLogEntry | null>(null);

  const isSummaryLoaded = summary.user_id !== "" && !isSummaryLoading;
  const isProfileLoaded = profile.id !== "";

  useEffect(() => {
    if (isAuthLoading || !user?.id) {
      return;
    }

    let isMounted = true;

    const fetchSummary = async (options = {}) => {
        try {
            const res = await apiFetch<DashboardSummary>("/dashboard/summary", options);
            if (isMounted) setSummary(res);
        } catch (e) { console.error("Summary fetch failed", e); }
    };

    const fetchSkills = async (options = {}) => {
        try {
            const [sk, gp, rf] = await Promise.all([
                apiFetch<SkillRead[]>("/skills/me", options),
                apiFetch<SkillGapRead[]>("/skills/me/gaps", options),
                apiFetch<RoleFitRead>("/skills/me/role-fit", options)
            ]);
            if (isMounted) {
                setSkills(sk);
                setGaps(gp);
                setRoleFit(rf);
            }
        } catch (e) { console.error("Skills fetch failed", e); }
    };

    const fetchProfileData = async (options = {}) => {
        try {
            const [pr, ar, rep] = await Promise.all([
                apiFetch<ProfileRead>("/profile/me", options),
                apiFetch<ArtifactRead[]>("/profile/me/artifacts", options),
                apiFetch<ReportRead | null>("/reports/me/latest", options)
            ]);
            if (isMounted) {
                setProfile(pr);
                setArtifacts(ar);
                setLatestReport(rep);
            }
        } catch (e) { console.error("Profile data fetch failed", e); }
    };

    const fetchSchedule = async (options = {}) => {
        try {
            const res = await apiFetch<CursorPage<ScheduleEvent>>("/schedule/events?limit=50", options);
            if (isMounted) setEvents(res.items);
        } catch (e) { console.error("Schedule fetch failed", e); }
    };

    const loadDashboard = async (revalidate = false) => {
      try {
        if (!revalidate) {
          setIsLoading(true);
          setIsSummaryLoading(true);
        }
        setError(null);

        const fetchOptions = { revalidate };
        
        // Execute fetches and update their specific loading states
        const summaryTask = fetchSummary(fetchOptions).finally(() => {
          if (isMounted) setIsSummaryLoading(false);
        });
        
        const otherTasks = Promise.allSettled([
            fetchSkills(fetchOptions),
            fetchProfileData(fetchOptions),
            fetchSchedule(fetchOptions)
        ]);

        // Global isLoading stays until summary is at least attempted
        await Promise.allSettled([summaryTask, otherTasks]);

      } catch (caught) {
        if (isMounted) setError(getApiErrorMessage(caught, "Failed to load dashboard."));
      } finally {
        if (isMounted) {
          setIsLoading(false);
          setIsSummaryLoading(false); 
        }
      }
    };

    // Initial load: Fetch once. If revalidate is true, apiFetch handles background refresh.
    void loadDashboard(false);
    
    // Subscribe to real-time updates via Supabase
    const summaryChannel = supabase
      .channel("dashboard-realtime-summary")
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "assessments" },
        () => void fetchSummary({ revalidate: true }),
      )
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "written_assessments" },
        () => void fetchSummary({ revalidate: true }),
      )
      .subscribe();

    const reportChannel = supabase
      .channel("dashboard-realtime-reports")
      .on(
        "postgres_changes",
        { event: "INSERT", schema: "public", table: "reports" },
        () => void fetchProfileData({ revalidate: true }),
      )
      .subscribe();

    return () => {
      isMounted = false;
      void supabase.removeChannel(summaryChannel);
      void supabase.removeChannel(reportChannel);
    };
  }, [user?.id, isAuthLoading]);


  const topSkills = useMemo(
    () => [...skills].sort((left, right) => right.verified_score - left.verified_score).slice(0, 5),
    [skills],
  );
  
  const topGaps = useMemo(() => gaps.slice(0, 5), [gaps]);
  
  const displayName =
    profile.full_name || profile.email?.split("@")[0] || "New candidate";
    
  const focusRole = profile.focus_role || roleFit.role_name || "Choose a focus role";
  
  const readiness = isSummaryLoaded
    ? summary.readiness_score
    : null;

  const selectedSkill = topSkills.find((skill) => skill.skill_id === selectedSkillId) ?? null;
  const chartFocusSkill = selectedSkill ?? topSkills[0] ?? null;
  
  const skillChartItems = useMemo(() => {
    if (topSkills.length > 0) {
      return topSkills.map((skill, index) => ({
        id: skill.skill_id,
        label: skill.skill_name,
        value: Math.max(skill.verified_score, 1),
        color: ["#6366F1", "#8B5CF6", "#14B8A6", "#F59E0B", "#EC4899"][index % 5],
      }));
    }
    
    // Fallback to domain breakdown if no verified skills yet
    if (summary.domain_breakdown && Object.keys(summary.domain_breakdown).length > 0) {
      return Object.entries(summary.domain_breakdown).map(([domain, score], index) => ({
        id: domain,
        label: domain,
        value: Math.max(score, 1),
        color: ["#6366F1", "#8B5CF6", "#14B8A6", "#F59E0B", "#EC4899"][index % 5],
      }));
    }
    
    return [];
  }, [topSkills, summary.domain_breakdown]);

  const refreshScheduleOnly = async () => {
    try {
      const payload = await apiFetch<CursorPage<ScheduleEvent>>("/schedule/events?limit=50");
      setEvents(payload.items);
    } catch (e) {
      console.error("Schedule refresh failed", e);
    }
  };

  const handleCreateScheduleEvent = async (payload: ScheduleEventPayload) => {
    try {
      await apiFetch<ScheduleEvent>("/schedule/events", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      await refreshScheduleOnly();
    } catch (caught) {
      throw new Error(getApiErrorMessage(caught, "Failed to create the schedule event."));
    }
  };

  const handleUpdateScheduleEvent = async (eventId: string, payload: ScheduleEventPayload) => {
    try {
      await apiFetch<ScheduleEvent>(`/schedule/events/${eventId}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      await refreshScheduleOnly();
    } catch (caught) {
      throw new Error(getApiErrorMessage(caught, "Failed to update the schedule event."));
    }
  };

  const handleDeleteScheduleEvent = async (eventId: string) => {
    try {
      await apiFetch<void>(`/schedule/events/${eventId}`, {
        method: "DELETE",
      });
      await refreshScheduleOnly();
    } catch (caught) {
      throw new Error(getApiErrorMessage(caught, "Failed to delete the schedule event."));
    }
  };

  return (
    <div className="mx-auto w-full max-w-[1520px] space-y-6 animate-fade-in pb-10">
      {error ? (
        <div className="rounded-3xl border border-amber-500/20 bg-amber-500/10 px-6 py-5 text-sm text-amber-300">
          {error}
        </div>
      ) : null}

      <section className="clay-card relative overflow-hidden rounded-[32px] p-6 md:p-8 min-h-[400px]">
        <div className="absolute right-0 top-0 h-64 w-64 rounded-full bg-primary/10 blur-3xl" />
        {isProfileLoaded ? (
          <div className="relative z-10 flex flex-col gap-8 lg:flex-row lg:items-center lg:justify-between">
            <div className="max-w-2xl space-y-5">
              <p className="text-[11px] font-black uppercase tracking-[0.24em] text-primary">
                Live dashboard
              </p>
              <div>
                <h1 className="text-4xl font-extrabold tracking-tight text-on-surface md:text-5xl">
                  {displayName}
                </h1>
                <p className="mt-3 text-lg leading-8 text-on-surface-variant">
                  {profile.headline
                    ? `${profile.headline} preparing for ${focusRole}.`
                    : `You are currently tracking toward ${focusRole}.`}
                </p>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="rounded-3xl bg-surface-container-low px-5 py-4">
                  <p className="text-[10px] font-black uppercase tracking-[0.2em] text-on-surface-variant">
                    Focus role
                  </p>
                  <p className="mt-2 text-lg font-bold text-on-surface">{focusRole}</p>
                </div>
                <div className="rounded-3xl bg-surface-container-low px-5 py-4">
                  <p className="text-[10px] font-black uppercase tracking-[0.2em] text-on-surface-variant">
                    Weekly goal
                  </p>
                  <p className="mt-2 text-lg font-bold text-on-surface">
                    {profile.weekly_goal || "Set your first weekly goal in settings."}
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap gap-3">
                <Link
                  href="/assessments"
                  className="inline-flex rounded-full bg-gradient-to-r from-primary to-secondary px-6 py-3 text-[11px] font-black uppercase tracking-[0.18em] text-white shadow-[0_0_20px_rgba(99,102,241,0.25)]"
                >
                  Start assessments
                </Link>
                <Link
                  href="/settings"
                  className="inline-flex rounded-full bg-surface-container-high px-6 py-3 text-[11px] font-black uppercase tracking-[0.18em] text-on-surface"
                >
                  Update profile
                </Link>
              </div>
            </div>

            <div className="flex w-full max-w-sm shrink-0 flex-col items-center rounded-[32px] bg-surface-container-low px-8 py-10 text-center">
              <p className="text-[10px] font-black uppercase tracking-[0.2em] text-on-surface-variant">
                Overall readiness score
              </p>
              <div className="mt-5 flex h-40 w-40 items-center justify-center rounded-full border-[12px] border-primary/15 bg-primary/5">
                <div>
                  <p className="text-5xl font-extrabold tracking-tight text-on-surface">
                    {isLoading ? (
                      <span className="inline-block h-12 w-20 animate-pulse bg-on-surface/10 rounded-lg" />
                    ) : (
                      formatPercent(readiness)
                    )}
                  </p>
                  <p className="mt-1 text-[11px] font-black uppercase tracking-[0.22em] text-primary">
                    {isLoading ? (
                      <span className="inline-block h-3 w-24 animate-pulse bg-primary/20 rounded-full" />
                    ) : (
                      roleFit.role_name || "Unassigned"
                    )}
                  </p>
                </div>
              </div>
              <p className="mt-5 text-sm leading-6 text-on-surface-variant">
                {topSkills.length
                  ? `${topSkills.length} verified skills are feeding this score.`
                  : "No verified skills yet. Your score will update as you complete assessments and upload evidence."}
              </p>
            </div>
          </div>
        ) : (
          <div className="relative z-10 flex flex-col gap-8 lg:flex-row lg:items-center lg:justify-between py-4">
            <div className="max-w-2xl w-full space-y-5">
              <div className="h-4 w-32 animate-pulse bg-primary/10 rounded-full" />
              <div className="h-12 w-64 animate-pulse bg-on-surface/10 rounded-3xl" />
              <div className="h-6 w-full animate-pulse bg-on-surface/5 rounded-2xl" />
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="h-24 animate-pulse bg-surface-container-low rounded-3xl" />
                <div className="h-24 animate-pulse bg-surface-container-low rounded-3xl" />
              </div>
            </div>
            <div className="h-64 w-64 animate-pulse bg-surface-container-high rounded-full mx-auto" />
          </div>
        )}
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {isSummaryLoaded ? [
          {
            label: "Verified skills",
            value: isSummaryLoaded ? String(skills.length) : "--",
            detail: isSummaryLoaded && topSkills.length ? `${topSkills[0].skill_name} is currently strongest.` : "No skills recorded yet.",
          },
          {
            label: "Role match",
            value: isSummaryLoaded ? formatPercent(roleFit.fit_score) : "--",
            detail: (isSummaryLoaded && roleFit.role_name) || "No active role match yet.",
          },
          {
            label: "Hidden skill queue",
            value: isSummaryLoaded ? String(summary.pending_hidden_skills) : "--",
            detail: isSummaryLoaded && summary.pending_hidden_skills
              ? "Pending discoveries need review."
              : "No pending hidden skills right now.",
          },
          {
            label: "Uploaded evidence",
            value: isSummaryLoaded ? String(artifacts.length) : "--",
            detail: isSummaryLoaded && artifacts.length
              ? `${artifacts.length} artifact${artifacts.length === 1 ? "" : "s"} stored.`
              : "No portfolio evidence uploaded yet.",
          },
        ].map((item) => (
          <div key={item.label} className="clay-card lift-card rounded-[28px] p-6">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-on-surface-variant">
              {item.label}
            </p>
            <p className="mt-4 text-4xl font-extrabold tracking-tight text-on-surface">{item.value}</p>
            <p className="mt-3 text-sm leading-6 text-on-surface-variant">{item.detail}</p>
          </div>
        )) : (
          Array.from({ length: 4 }).map((_, i) => (
            <StatCardSkeleton key={i} />
          ))
        )}
      </section>

      <section className="grid gap-8 xl:grid-cols-[1.05fr_0.95fr]">
        <div className="clay-card rounded-[32px] p-8">
          <div className="mb-6 flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-bold tracking-tight text-on-surface">Top verified skills</h2>
              <p className="mt-1 text-sm text-on-surface-variant">
                Live scores from your persisted skill records. Click a skill to inspect the verification breakdown.
              </p>
            </div>
            <Link
              href="/skill-profile"
              className="text-[11px] font-black uppercase tracking-[0.18em] text-primary"
            >
              Open profile
            </Link>
          </div>

          {isSummaryLoading ? (
            <div className="grid gap-6 lg:grid-cols-[0.8fr_1.2fr]">
              <div className="flex flex-col items-center justify-center rounded-3xl bg-surface-container-low px-4 py-6">
                <div className="h-48 w-48 rounded-full border-[12px] border-surface-container animate-pulse" />
                <div className="mt-6 h-4 w-32 rounded-full bg-surface-container animate-pulse" />
              </div>
              <div className="space-y-4">
                {[1, 2, 3, 4, 5].map((i) => (
                  <div key={i} className="h-20 w-full rounded-3xl bg-surface-container-low animate-pulse" />
                ))}
              </div>
            </div>
          ) : skillChartItems.length ? (
            <div className="grid gap-6 lg:grid-cols-[0.8fr_1.2fr]">
              <div className="flex flex-col items-center justify-center rounded-3xl bg-surface-container-low px-4 py-6">
                <SkillDonutChart
                  items={skillChartItems}
                  selectedId={selectedSkillId ?? topSkills[0]?.skill_id ?? null}
                  onSelect={(item) => setSelectedSkillId(item.id)}
                  centerLabel={
                    selectedSkill ? "Selected skill" : chartFocusSkill ? "Top skill" : "Verified mix"
                  }
                  centerValue={formatPercent(chartFocusSkill?.verified_score ?? readiness)}
                />
                <p className="mt-4 text-center text-sm leading-6 text-on-surface-variant">
                  {topSkills.length > 0 ? "The donut reflects which verified skills are carrying the current dashboard readiness." : "The donut reflects your current domain readiness based on initial placement results."}
                </p>
              </div>

              <div className="space-y-4">
                {(topSkills.length > 0 ? topSkills : skillChartItems).map((item, index) => {
                  const isSkill = 'skill_id' in item;
                  const label = isSkill ? item.skill_name : item.label;
                  const id = isSkill ? item.skill_id : item.id;
                  const score = isSkill ? item.verified_score : item.value;
                  const updatedAt = isSkill ? item.updated_at : null;

                  return (
                    <button
                      key={id}
                      type="button"
                      onClick={() => isSkill && setSelectedSkillId(id)}
                      className={`lift-tile block w-full rounded-3xl border px-5 py-4 text-left transition ${
                        selectedSkillId === id
                          ? "border-primary/35 bg-primary/10"
                          : "border-outline-variant/12 dark:border-transparent bg-surface-container-low hover:border-primary/20"
                      } ${!isSkill ? "cursor-default" : ""}`}
                    >
                      <div className="flex items-center justify-between gap-4">
                        <div className="flex items-center gap-4">
                          <span
                            className="h-4 w-4 rounded-full"
                            style={{ backgroundColor: skillChartItems[index]?.color ?? "#6366F1" }}
                          />
                          <div>
                            <h3 className="text-base font-bold text-on-surface">{label}</h3>
                            <p className="mt-1 text-xs font-bold uppercase tracking-[0.16em] text-on-surface-variant">
                              {updatedAt ? `Updated ${formatRelativeTime(updatedAt)}` : "Initial Projection"}
                            </p>
                          </div>
                        </div>
                        <div className="text-right">
                          <p className="text-2xl font-extrabold tracking-tight text-on-surface">
                            {formatPercent(score)}
                          </p>
                          <p className="text-[10px] font-black uppercase tracking-[0.16em] text-primary">
                            {isSkill ? "Verified" : "Readiness"}
                          </p>
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          ) : (

            <EmptyPanel
              title="No verified skills yet"
              body="Your dashboard is now reading live data, so new accounts stay empty until you actually create assessments or import evidence."
              actionHref="/assessments"
              actionLabel="Create first assessment"
            />
          )}
        </div>

        <div className="clay-card rounded-[32px] p-8">
          <div className="mb-6 flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-bold tracking-tight text-on-surface">Priority gaps</h2>
              <p className="mt-1 text-sm text-on-surface-variant">
                Highest-severity gaps for your current target role.
              </p>
            </div>
            <span className="rounded-full bg-primary/10 px-3 py-1 text-[10px] font-black uppercase tracking-[0.18em] text-primary">
              {roleFit.role_name || "Unassigned"}
            </span>
          </div>

          {topGaps.length ? (
            <div className="space-y-4">
              {topGaps.map((gap) => (
                <div
                  key={gap.skill_name}
                  className="lift-tile rounded-3xl border border-outline-variant/12 dark:border-transparent bg-surface-container-low px-5 py-4"
                >
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <h3 className="text-base font-bold text-on-surface">{gap.skill_name}</h3>
                      <p className="mt-1 text-sm text-on-surface-variant">
                        Current score: {formatPercent(gap.user_score)}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-lg font-extrabold tracking-tight text-on-surface">
                        {(gap.gap_severity * 100).toFixed(1)}
                      </p>
                      <p className="text-[10px] font-black uppercase tracking-[0.16em] text-primary">
                        Gap severity
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyPanel
              title="No gap analysis yet"
              body="Once a focus role has requirements and your first live skill scores arrive, the dashboard will rank your missing areas here."
              actionHref="/settings"
              actionLabel="Set focus role"
            />
          )}
        </div>
      </section>

      <section className="grid gap-8 xl:grid-cols-3">
        {/* Left column: Schedule & Exam Log */}
        <div className="flex flex-col gap-8 xl:col-span-2">
          <div className="clay-card rounded-[32px] p-6 md:p-8">
            <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="text-2xl font-bold tracking-tight text-on-surface">Upcoming schedule</h2>
                <p className="mt-1 text-sm text-on-surface-variant">
                  Live schedule records from your account in editable calendar form.
                </p>
              </div>
            </div>

            <SchedulePlanner
              events={events}
              onCreate={handleCreateScheduleEvent}
              onUpdate={handleUpdateScheduleEvent}
              onDelete={handleDeleteScheduleEvent}
            />
          </div>

          <div className="clay-card rounded-[32px] p-6 md:p-8">
            <div className="mb-6 flex items-center justify-between">
              <div>
                <h2 className="text-2xl font-bold tracking-tight text-on-surface">Exam log</h2>
                <p className="mt-1 text-sm text-on-surface-variant">
                  Detailed results from your MCQ, situational, and written assessments.
                </p>
              </div>
              <Link
                href="/assessments"
                className="text-[11px] font-black uppercase tracking-[0.18em] text-primary"
              >
                New Assessment
              </Link>
            </div>

            <ExamLog onEntryClick={setSelectedLogEntry} />
          </div>
        </div>

        {/* Right column: Latest Report & Account Snapshot */}
        <div className="flex flex-col gap-8 xl:col-span-1">
          <div className="clay-card flex flex-col rounded-[32px] p-6 md:p-8">
            <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between xl:flex-col xl:items-start">
              <div>
                <h2 className="text-2xl font-bold tracking-tight text-on-surface">Latest report</h2>
                <p className="mt-1 text-sm text-on-surface-variant">
                  Most recent generated profile summary.
                </p>
              </div>
              <span className="rounded-full bg-surface-container-high px-3 py-1 text-[10px] font-black uppercase tracking-[0.18em] text-on-surface-variant shrink-0">
                {latestReport?.created_at ? formatDate(latestReport.created_at) : "No report"}
              </span>
            </div>

            {latestReport ? (
              <div className="space-y-4">
                <div className="lift-tile rounded-3xl border border-outline-variant/12 dark:border-transparent bg-surface-container-low px-4 py-3">
                  <p className="text-[10px] font-black uppercase tracking-[0.2em] text-on-surface-variant">
                    Report id
                  </p>
                  <p className="mt-1 break-all text-xs font-bold text-on-surface">{latestReport.id}</p>
                </div>
                <div className="lift-tile flex-1 rounded-3xl border border-outline-variant/12 dark:border-transparent bg-surface-container-low px-4 py-3">
                  <p className="text-[10px] font-black uppercase tracking-[0.2em] text-on-surface-variant">
                    Summary snapshot
                  </p>
                  <p className="mt-1 text-sm leading-6 text-on-surface-variant">
                    The report payload is stored live. Latest generation ran{" "}
                    {formatRelativeTime(latestReport.created_at)}.
                  </p>
                </div>
              </div>
            ) : (
              <EmptyPanel
                title="No report generated"
                body="This section stays empty until a report is generated."
                actionHref="/assessments"
                actionLabel="Build report"
              />
            )}
          </div>

          <div className="clay-card rounded-[32px] p-6 md:p-8">
            <div className="mb-6">
              <h2 className="text-2xl font-bold tracking-tight text-on-surface">Account snapshot</h2>
              <p className="mt-1 text-sm text-on-surface-variant">
                Persisted identity data.
              </p>
            </div>

            <div className="space-y-3">
              {[
                { label: "Email", value: profile.email || "Not available" },
                { label: "Current role", value: profile.headline || "Not set yet" },
                { label: "Focus role", value: profile.focus_role || "Not set yet" },
                { label: "Weekly goal", value: profile.weekly_goal || "Not set yet" },
              ].map((item) => (
                <div
                  key={item.label}
                  className="lift-tile rounded-[20px] border border-outline-variant/12 dark:border-transparent bg-surface-container-low px-4 py-3"
                >
                  <p className="text-[10px] font-black uppercase tracking-[0.2em] text-on-surface-variant">
                    {item.label}
                  </p>
                  <p className="mt-1 text-sm font-bold text-on-surface">{item.value}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <SkillInsightModal
        skill={selectedSkill}
        onClose={() => setSelectedSkillId(null)}
      />

      <ExamInsightModal
        entry={selectedLogEntry}
        onClose={() => setSelectedLogEntry(null)}
      />

      <ResumeReminderPopup />
    </div>
  );
}
