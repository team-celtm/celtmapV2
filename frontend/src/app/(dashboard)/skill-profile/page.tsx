"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { apiFetch, getApiErrorMessage } from "@/lib/api";
import { buildAssessmentQuizHref } from "@/lib/assessmentLinks";
import CeltmProgressLoader from "@/components/CeltmProgressLoader";
import { SkillDonutChart } from "@/components/skills/SkillDonutChart";
import { SkillInsightModal } from "@/components/skills/SkillInsightModal";
import type {
  DashboardSummary,
  HiddenSkillCandidateRead,
  ProfileRead,
  ReportRead,
  RoleFitRead,
  SkillGapRead,
  SkillRead,
} from "@/lib/celtm";
import { formatDate, formatPercent, formatRelativeTime, toTitleCase } from "@/lib/celtm";

type TabKey = "overview" | "gaps" | "discoveries";

interface SkillProfileState {
  summary: DashboardSummary | null;
  profile: ProfileRead | null;
  roleFit: RoleFitRead | null;
  skills: SkillRead[];
  gaps: SkillGapRead[];
  hiddenSkills: HiddenSkillCandidateRead[];
  latestReport: ReportRead | null;
}

const initialState: SkillProfileState = {
  summary: null,
  profile: null,
  roleFit: null,
  skills: [],
  gaps: [],
  hiddenSkills: [],
  latestReport: null,
};

function buildLoadWarning(failedSections: Array<{ label: string; reason: unknown }>, fallback: string) {
  if (!failedSections.length) {
    return null;
  }

  const labels = failedSections.map((section) => section.label).join(", ");
  const detail = getApiErrorMessage(failedSections[0].reason, fallback);
  return `Some skill profile data is unavailable right now (${labels}). ${detail}`;
}

function EmptyCard({
  title,
  body,
  href,
  action,
}: {
  title: string;
  body: string;
  href: string;
  action: string;
}) {
  return (
    <div className="rounded-3xl border border-dashed border-outline-variant/20 dark:border-transparent bg-surface-container-low px-5 py-6">
      <h3 className="text-base font-bold text-on-surface">{title}</h3>
      <p className="mt-2 text-sm leading-6 text-on-surface-variant">{body}</p>
      <Link
        href={href}
        className="mt-4 inline-flex rounded-full bg-primary/10 px-4 py-2 text-[11px] font-black uppercase tracking-[0.18em] text-primary transition hover:bg-primary/15"
      >
        {action}
      </Link>
    </div>
  );
}

function InitialBadge({ label }: { label: string }) {
  const initial = label.trim().charAt(0).toUpperCase() || "C";

  return (
    <div className="flex h-20 w-20 items-center justify-center rounded-[28px] bg-gradient-to-br from-primary to-secondary text-3xl font-extrabold text-white shadow-[0_0_24px_rgba(99,102,241,0.25)]">
      {initial}
    </div>
  );
}

function skillSourceLabel(skill: SkillRead) {
  const source = String(skill.source || "");
  if (source.includes("written_practice")) return "Written practice";
  if (source.includes("assessment_discovery")) return "Assessment discovery";
  if (source.includes("assessment_practice")) return "Assessment practice";
  if (source.includes("readiness_dimension")) return "Readiness dimension";
  return "Verified evidence";
}

export default function SkillProfilePage() {
  const [activeTab, setActiveTab] = useState<TabKey>("overview");
  const [data, setData] = useState<SkillProfileState>(initialState);
  const [isLoading, setIsLoading] = useState(true);
  const [isProfileComplete, setIsProfileComplete] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedSkillId, setSelectedSkillId] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    const loadProfile = async () => {
      try {
        setIsLoading(true);
        setIsProfileComplete(false);
        setError(null);

        const [
          summaryResult,
          profileResult,
          roleFitResult,
          skillsResult,
          gapsResult,
          hiddenSkillsResult,
          latestReportResult,
        ] = await Promise.allSettled([
          apiFetch<DashboardSummary>("/dashboard/summary"),
          apiFetch<ProfileRead>("/profile/me"),
          apiFetch<RoleFitRead>("/skills/me/role-fit"),
          apiFetch<SkillRead[]>("/skills/me"),
          apiFetch<SkillGapRead[]>("/skills/me/gaps"),
          apiFetch<HiddenSkillCandidateRead[]>("/skills/me/hidden"),
          apiFetch<ReportRead | null>("/reports/me/latest"),
        ]);

        if (!isMounted) {
          return;
        }

        const failedSections = [
          { label: "summary", result: summaryResult },
          { label: "profile", result: profileResult },
          { label: "role fit", result: roleFitResult },
          { label: "skills", result: skillsResult },
          { label: "gaps", result: gapsResult },
          { label: "hidden skills", result: hiddenSkillsResult },
          { label: "reports", result: latestReportResult },
        ]
          .filter(
            (
              section,
            ): section is { label: string; result: PromiseRejectedResult } =>
              section.result.status === "rejected",
          )
          .map((section) => ({ label: section.label, reason: section.result.reason }));

        setData({
          summary: summaryResult.status === "fulfilled" ? summaryResult.value : null,
          profile: profileResult.status === "fulfilled" ? profileResult.value : null,
          roleFit: roleFitResult.status === "fulfilled" ? roleFitResult.value : null,
          skills: skillsResult.status === "fulfilled" ? skillsResult.value : [],
          gaps: gapsResult.status === "fulfilled" ? gapsResult.value : [],
          hiddenSkills: hiddenSkillsResult.status === "fulfilled" ? hiddenSkillsResult.value : [],
          latestReport: latestReportResult.status === "fulfilled" ? latestReportResult.value : null,
        });
        setError(buildLoadWarning(failedSections, "Failed to load the live skill profile."));
        setIsProfileComplete(true);
        await new Promise((resolve) => window.setTimeout(resolve, 650));
      } catch (caught) {
        if (!isMounted) {
          return;
        }

        setError(getApiErrorMessage(caught, "Failed to load the live skill profile."));
      } finally {
        if (isMounted) {
          setIsLoading(false);
          setIsProfileComplete(false);
        }
      }
    };

    void loadProfile();

    return () => {
      isMounted = false;
    };
  }, []);

  const topSkills = useMemo(
    () => [...data.skills].sort((left, right) => right.verified_score - left.verified_score),
    [data.skills],
  );
  const practiceSkills = useMemo(
    () =>
      data.skills
        .filter((skill) => {
          const source = String(skill.source || "");
          return source.includes("assessment_practice") || source.includes("assessment_discovery") || source.includes("written_practice");
        })
        .sort((left, right) => {
          const rightTime = right.updated_at ? new Date(right.updated_at).getTime() : 0;
          const leftTime = left.updated_at ? new Date(left.updated_at).getTime() : 0;
          return rightTime - leftTime || right.verified_score - left.verified_score;
        }),
    [data.skills],
  );
  const criticalGaps = useMemo(
    () => [...data.gaps].sort((left, right) => right.gap_severity - left.gap_severity),
    [data.gaps],
  );
  const pendingDiscoveries = useMemo(
    () => data.hiddenSkills.filter((candidate) => candidate.status === "pending"),
    [data.hiddenSkills],
  );

  const displayName =
    data.profile?.full_name || data.profile?.email?.split("@")[0] || "CELTM user";
  const headline = data.profile?.headline || "No headline saved yet";
  const focusRole = data.profile?.focus_role || data.roleFit?.role_name || "Not set yet";
  const readinessScore = data.summary?.readiness_score ?? data.roleFit?.fit_score ?? 0;
  const matchedSkills = data.roleFit?.matched_skills ?? [];
  const missingSkills = data.roleFit?.missing_skills ?? [];
  const selectedSkill = topSkills.find((skill) => skill.skill_id === selectedSkillId) ?? null;
  const chartFocusSkill = selectedSkill ?? topSkills[0] ?? null;
  const skillChartItems = topSkills.slice(0, 6).map((skill, index) => ({
    id: skill.skill_id,
    label: skill.skill_name,
    value: Math.max(skill.verified_score, 1),
    color: ["#6366F1", "#8B5CF6", "#14B8A6", "#F59E0B", "#EC4899", "#22C55E"][index % 6],
  }));

  if (isLoading) {
    return (
      <div className="mx-auto w-full max-w-[1520px] page-fade-in pb-10">
        <CeltmProgressLoader
          title="Loading skill profile"
          caption="Cooking your skill profile"
          forceComplete={isProfileComplete}
          minHeightClassName="min-h-[78vh]"
          stages={["Fetching readiness", "Mapping verified skills", "Checking hidden skills", "Building profile view"]}
        />
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-[1520px] space-y-6 page-fade-in pb-10">
      {error ? (
        <div className="rounded-3xl border border-amber-500/20 bg-amber-500/10 px-6 py-5 text-sm text-amber-300">
          {error}
        </div>
      ) : null}

      <section className="clay-card rounded-[32px] p-8 md:p-10">
        <div className="flex flex-col gap-8 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex items-start gap-5">
              <InitialBadge label={displayName} />
              <div className="space-y-3">
                <p className="text-[11px] font-black uppercase tracking-[0.24em] text-primary">
                  Live skill profile
                </p>
                <div>
                  <h1 className="text-4xl font-extrabold tracking-tight text-on-surface md:text-5xl">
                    {displayName}
                  </h1>
                  <p className="mt-2 text-sm font-bold uppercase tracking-[0.18em] text-primary">
                    {focusRole}
                  </p>
                </div>
                <p className="max-w-2xl text-sm leading-7 text-on-surface-variant">{headline}</p>
                <div className="flex flex-wrap gap-3">
                  <Link
                    href="/settings"
                    className="inline-flex rounded-full bg-primary px-5 py-3 text-[11px] font-black uppercase tracking-[0.18em] text-white"
                  >
                    Update profile
                  </Link>
                  <Link
                    href="/assessments"
                    className="inline-flex rounded-full bg-surface-container-high px-5 py-3 text-[11px] font-black uppercase tracking-[0.18em] text-on-surface"
                  >
                    Run assessments
                  </Link>
                </div>
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-3 lg:w-[28rem]">
              {[
                {
                  label: "Readiness",
                  value: formatPercent(readinessScore),
                  detail: data.roleFit?.role_name || "Waiting for role fit",
                },
                {
                  label: "Verified skills",
                  value: String(data.skills.length),
                  detail: topSkills[0]?.skill_name || "No verified skills yet",
                },
                {
                  label: "Hidden queue",
                  value: String(pendingDiscoveries.length),
                  detail: pendingDiscoveries.length ? "Needs review" : "No pending discoveries",
                },
              ].map((item) => (
                <div key={item.label} className="lift-card rounded-3xl border border-outline-variant/12 dark:border-transparent bg-surface-container-low px-5 py-4">
                  <p className="text-[10px] font-black uppercase tracking-[0.2em] text-on-surface-variant">
                    {item.label}
                  </p>
                  <p className="mt-3 text-3xl font-extrabold tracking-tight text-on-surface">{item.value}</p>
                  <p className="mt-2 text-xs font-semibold leading-5 text-primary">
                    {item.detail}
                  </p>
                </div>
              ))}
            </div>
        </div>
      </section>

      <section className="flex flex-wrap gap-2 rounded-[28px] bg-surface-container-low p-2">
        {[
          { key: "overview" as const, label: "Overview" },
          { key: "gaps" as const, label: "Gap Analysis" },
          { key: "discoveries" as const, label: "Discovery Queue" },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`rounded-full px-4 py-2 text-[11px] font-black uppercase tracking-[0.18em] transition ${
              activeTab === tab.key
                ? "bg-surface text-primary shadow-sm"
                : "text-on-surface-variant hover:text-on-surface"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </section>

      {activeTab === "overview" ? (
        <section className="grid gap-8 xl:grid-cols-[1.05fr_0.95fr]">
          <div className="space-y-8">
            <div className="clay-card rounded-[32px] p-8">
              <div className="mb-6 flex items-center justify-between">
                <div>
                  <h2 className="text-2xl font-bold tracking-tight text-on-surface">Verified capability map</h2>
                  <p className="mt-1 text-sm text-on-surface-variant">
                    Stored scores from assessments, writing, interviews, and artifact review. Click a skill for the detailed log.
                  </p>
                </div>
                <span className="rounded-full bg-primary/10 px-3 py-1 text-[10px] font-black uppercase tracking-[0.18em] text-primary">
                  {data.skills.length} skills
                </span>
              </div>

              {topSkills.length ? (
                <div className="grid gap-6 lg:grid-cols-[0.85fr_1.15fr]">
                  <div className="flex flex-col items-center justify-center rounded-3xl bg-surface-container-low px-4 py-6">
                    <SkillDonutChart
                      items={skillChartItems}
                      selectedId={selectedSkillId ?? topSkills[0]?.skill_id ?? null}
                      onSelect={(item) => setSelectedSkillId(item.id)}
                      centerLabel={
                        selectedSkill ? "Selected skill" : chartFocusSkill ? "Top skill" : "Role fit"
                      }
                      centerValue={formatPercent(chartFocusSkill?.verified_score ?? readinessScore)}
                    />
                    <p className="mt-4 text-center text-sm leading-6 text-on-surface-variant">
                      This chart shows how your strongest verified skills are contributing to the current profile.
                    </p>
                  </div>

                  <div className="space-y-4">
                    {topSkills.slice(0, 6).map((skill, index) => (
                      <button
                        key={skill.skill_id}
                        type="button"
                        onClick={() => setSelectedSkillId(skill.skill_id)}
                        className={`lift-tile block w-full rounded-3xl border px-5 py-4 text-left transition ${
                          selectedSkillId === skill.skill_id
                            ? "border-primary/35 bg-primary/10"
                            : "border-outline-variant/12 dark:border-transparent bg-surface-container-low hover:border-primary/20"
                        }`}
                      >
                        <div className="flex items-center justify-between gap-4">
                          <div className="flex items-center gap-4">
                            <span
                              className="h-4 w-4 rounded-full"
                              style={{ backgroundColor: skillChartItems[index]?.color ?? "#6366F1" }}
                            />
                            <div>
                              <h3 className="text-base font-bold text-on-surface">{skill.skill_name}</h3>
                              <p className="mt-1 text-xs font-bold uppercase tracking-[0.16em] text-on-surface-variant">
                                Updated {formatRelativeTime(skill.updated_at)}
                              </p>
                            </div>
                          </div>
                          <div className="text-right">
                            <p className="text-2xl font-extrabold tracking-tight text-on-surface">
                              {formatPercent(skill.verified_score)}
                            </p>
                            <p className="text-[10px] font-black uppercase tracking-[0.16em] text-primary">
                              Verified
                            </p>
                          </div>
                        </div>
                        <div className="mt-4 h-2 overflow-hidden rounded-full bg-outline-variant/15">
                          <div
                            className="h-full rounded-full bg-gradient-to-r from-primary to-secondary"
                            style={{ width: `${Math.max(0, Math.min(100, Math.round(skill.verified_score)))}%` }}
                          />
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                <EmptyCard
                  title="No verified skills yet"
                  body="This page now only shows saved skill records. Complete your first assessment or approve a hidden skill to populate the profile."
                  href="/assessments"
                  action="Start assessment"
                />
              )}
            </div>

            {practiceSkills.length ? (
              <div className="clay-card rounded-[32px] p-8">
                <div className="mb-6 flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
                  <div>
                    <h2 className="text-2xl font-bold tracking-tight text-on-surface">
                      Practice-discovered skills
                    </h2>
                    <p className="mt-1 text-sm text-on-surface-variant">
                      Skills found from completed assessments and written practice, similar to topic tags after a practice session.
                    </p>
                  </div>
                  <span className="rounded-full bg-secondary/10 px-3 py-1 text-[10px] font-black uppercase tracking-[0.18em] text-secondary">
                    {practiceSkills.length} found
                  </span>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  {practiceSkills.slice(0, 8).map((skill) => (
                    <button
                      key={skill.skill_id}
                      type="button"
                      onClick={() => setSelectedSkillId(skill.skill_id)}
                      className={`lift-tile rounded-3xl border px-5 py-5 text-left transition ${
                        selectedSkillId === skill.skill_id
                          ? "border-secondary/40 bg-secondary/10"
                          : "border-outline-variant/12 dark:border-transparent bg-surface-container-low hover:border-secondary/30"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <p className="text-[10px] font-black uppercase tracking-[0.18em] text-secondary">
                            {skillSourceLabel(skill)}
                          </p>
                          <h3 className="mt-2 text-lg font-bold text-on-surface">{skill.skill_name}</h3>
                          <p className="mt-2 text-xs font-semibold leading-5 text-on-surface-variant">
                            {skill.evidence_label || "Completed practice"} - {Math.max(1, Number(skill.attempt_count || 1))} signal
                          </p>
                        </div>
                        <span className="rounded-2xl bg-surface px-3 py-2 text-lg font-extrabold tracking-tight text-on-surface shadow-inner">
                          {formatPercent(skill.verified_score)}
                        </span>
                      </div>
                      <div className="mt-4 h-2 overflow-hidden rounded-full bg-outline-variant/15">
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-secondary to-primary"
                          style={{ width: `${Math.max(0, Math.min(100, Math.round(skill.verified_score)))}%` }}
                        />
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            ) : null}

            <div className="clay-card rounded-[32px] p-8">
              <div className="mb-6">
                <h2 className="text-2xl font-bold tracking-tight text-on-surface">Role fit snapshot</h2>
                <p className="mt-1 text-sm text-on-surface-variant">
                  What currently aligns with your strongest fit role, and what is still missing.
                </p>
              </div>

              <div className="grid gap-6 md:grid-cols-2">
                <div className="rounded-3xl bg-surface-container-low px-5 py-5">
                  <p className="text-[10px] font-black uppercase tracking-[0.2em] text-on-surface-variant">
                    Matched skills
                  </p>
                  {matchedSkills.length ? (
                    <div className="mt-4 flex flex-wrap gap-2">
                      {matchedSkills.map((skill) => (
                        <span
                          key={skill}
                          className="rounded-full bg-emerald-500/10 px-3 py-2 text-[10px] font-black uppercase tracking-[0.16em] text-emerald-400"
                        >
                          {skill}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-4 text-sm leading-6 text-on-surface-variant">
                      No confirmed role matches yet.
                    </p>
                  )}
                </div>

                <div className="rounded-3xl bg-surface-container-low px-5 py-5">
                  <p className="text-[10px] font-black uppercase tracking-[0.2em] text-on-surface-variant">
                    Missing skills
                  </p>
                  {missingSkills.length ? (
                    <div className="mt-4 flex flex-wrap gap-2">
                      {missingSkills.map((skill) => (
                        <span
                          key={skill}
                          className="rounded-full bg-amber-500/10 px-3 py-2 text-[10px] font-black uppercase tracking-[0.16em] text-amber-300"
                        >
                          {skill}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-4 text-sm leading-6 text-on-surface-variant">
                      No missing role requirements recorded yet.
                    </p>
                  )}
                </div>
              </div>
            </div>
          </div>

          <div className="space-y-8">
            <div className="clay-card rounded-[32px] p-8">
              <div className="mb-6">
                <h2 className="text-2xl font-bold tracking-tight text-on-surface">Stored report</h2>
                <p className="mt-1 text-sm text-on-surface-variant">
                  Latest generated profile summary attached to this user account.
                </p>
              </div>

              {data.latestReport ? (
                <div className="space-y-4">
                  <div className="rounded-3xl bg-surface-container-low px-5 py-4">
                    <p className="text-[10px] font-black uppercase tracking-[0.2em] text-on-surface-variant">
                      Generated
                    </p>
                    <p className="mt-2 text-lg font-bold text-on-surface">
                      {formatDate(data.latestReport.created_at)}
                    </p>
                  </div>
                  <div className="rounded-3xl bg-surface-container-low px-5 py-4">
                    <p className="text-[10px] font-black uppercase tracking-[0.2em] text-on-surface-variant">
                      Report id
                    </p>
                    <p className="mt-2 break-all text-sm font-bold text-on-surface">
                      {data.latestReport.id}
                    </p>
                  </div>
                  <Link
                    href="/assessments"
                    className="inline-flex rounded-full bg-primary/10 px-4 py-2 text-[11px] font-black uppercase tracking-[0.18em] text-primary transition hover:bg-primary/15"
                  >
                    Refresh inputs
                  </Link>
                </div>
              ) : (
                <EmptyCard
                  title="No report generated yet"
                  body="Reports are no longer mocked here. Generate real assessment inputs first, then create a report from the backend."
                  href="/assessments"
                  action="Build report inputs"
                />
              )}
            </div>

            <div className="clay-card rounded-[32px] p-8">
              <div className="mb-6">
                <h2 className="text-2xl font-bold tracking-tight text-on-surface">Account metadata</h2>
                <p className="mt-1 text-sm text-on-surface-variant">
                  Saved profile values currently driving this workspace.
                </p>
              </div>

              <div className="space-y-4">
                {[
                  { label: "Email", value: data.profile?.email || "Not available" },
                  { label: "Current headline", value: headline },
                  { label: "Focus role", value: focusRole },
                  { label: "Weekly goal", value: data.profile?.weekly_goal || "Not set yet" },
                ].map((item) => (
                  <div
                    key={item.label}
                    className="lift-tile rounded-3xl border border-outline-variant/12 dark:border-transparent bg-surface-container-low px-5 py-4"
                  >
                    <p className="text-[10px] font-black uppercase tracking-[0.2em] text-on-surface-variant">
                      {item.label}
                    </p>
                    <p className="mt-2 text-base font-bold text-on-surface">{item.value}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>
      ) : null}

      {activeTab === "gaps" ? (
        <section className="grid gap-8 xl:grid-cols-[1.05fr_0.95fr]">
          <div className="clay-card rounded-[32px] p-8">
            <div className="mb-6 flex items-center justify-between">
              <div>
                <h2 className="text-2xl font-bold tracking-tight text-on-surface">Priority gaps</h2>
                <p className="mt-1 text-sm text-on-surface-variant">
                  Ranked by live role-fit severity.
                </p>
              </div>
              <span className="rounded-full bg-amber-500/10 px-3 py-1 text-[10px] font-black uppercase tracking-[0.18em] text-amber-300">
                {criticalGaps.length} gaps
              </span>
            </div>

            {criticalGaps.length ? (
              <div className="space-y-4">
                {criticalGaps.slice(0, 8).map((gap) => (
                  <div
                    key={gap.skill_name}
                    className="lift-tile rounded-3xl border border-outline-variant/12 dark:border-transparent bg-surface-container-low px-5 py-5"
                  >
                    <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                      <div>
                        <h3 className="text-lg font-bold text-on-surface">{gap.skill_name}</h3>
                        <p className="mt-2 text-sm leading-6 text-on-surface-variant">
                          Current score {formatPercent(gap.user_score)} against a target weight of{" "}
                          {Math.round(gap.target_weight * 100)}%.
                        </p>
                      </div>
                      <div className="min-w-[10rem] rounded-3xl bg-surface px-4 py-3 text-right shadow-inner">
                        <p className="text-[10px] font-black uppercase tracking-[0.18em] text-on-surface-variant">
                          Gap severity
                        </p>
                        <p className="mt-2 text-2xl font-extrabold tracking-tight text-amber-300">
                          {(gap.gap_severity * 100).toFixed(1)}
                        </p>
                      </div>
                    </div>
                    <div className="mt-4 h-2 overflow-hidden rounded-full bg-outline-variant/15">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-amber-400 to-red-500"
                        style={{ width: `${Math.max(0, Math.min(100, Math.round(gap.gap_severity * 100)))}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyCard
                title="No gap analysis available"
                body="Gap ranking appears here only after role-fit requirements and verified skill scores exist for your account."
                href="/settings"
                action="Set focus role"
              />
            )}
          </div>

          <div className="space-y-8">
            <div className="clay-card rounded-[32px] p-8">
              <div className="mb-6">
                <h2 className="text-2xl font-bold tracking-tight text-on-surface">Recommended next steps</h2>
                <p className="mt-1 text-sm text-on-surface-variant">
                  Straight from the current live gap queue.
                </p>
              </div>

              {criticalGaps.length ? (
                <div className="space-y-4">
                  {criticalGaps.slice(0, 3).map((gap, index) => (
                    <div
                      key={gap.skill_name}
                      className="lift-tile rounded-3xl border border-outline-variant/12 dark:border-transparent bg-surface-container-low px-5 py-4"
                    >
                      <p className="text-[10px] font-black uppercase tracking-[0.2em] text-primary">
                        Step {index + 1}
                      </p>
                      <h3 className="mt-3 text-lg font-bold text-on-surface">{gap.skill_name}</h3>
                      <p className="mt-2 text-sm leading-6 text-on-surface-variant">
                        Reassess this domain first to reduce one of your highest-severity role-fit gaps.
                      </p>
                      <Link
                        href={buildAssessmentQuizHref({ title: gap.skill_name })}
                        className="mt-4 inline-flex rounded-full bg-primary/10 px-4 py-2 text-[11px] font-black uppercase tracking-[0.18em] text-primary transition hover:bg-primary/15"
                      >
                        Reassess skill
                      </Link>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyCard
                  title="No next steps yet"
                  body="Once gap data exists, this panel will recommend the next assessment sequence instead of showing a generic roadmap."
                  href="/assessments"
                  action="Open assessments"
                />
              )}
            </div>

            <div className="clay-card rounded-[32px] p-8">
              <div className="mb-6">
                <h2 className="text-2xl font-bold tracking-tight text-on-surface">Strongest verified areas</h2>
                <p className="mt-1 text-sm text-on-surface-variant">
                  Your best-performing live skills.
                </p>
              </div>

              {topSkills.length ? (
                <div className="space-y-4">
                  {topSkills.slice(0, 4).map((skill) => (
                    <div
                      key={skill.skill_id}
                      className="lift-tile rounded-3xl border border-outline-variant/12 dark:border-transparent bg-surface-container-low px-5 py-4"
                    >
                      <div className="flex items-center justify-between gap-4">
                        <h3 className="text-base font-bold text-on-surface">{skill.skill_name}</h3>
                        <span className="text-lg font-extrabold tracking-tight text-emerald-400">
                          {formatPercent(skill.verified_score)}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm leading-6 text-on-surface-variant">
                  No verified scores yet.
                </p>
              )}
            </div>
          </div>
        </section>
      ) : null}

      {activeTab === "discoveries" ? (
        <section className="grid gap-8 xl:grid-cols-[0.9fr_1.1fr]">
          <div className="clay-card rounded-[32px] p-8">
            <div className="mb-6">
              <h2 className="text-2xl font-bold tracking-tight text-on-surface">Discovery summary</h2>
              <p className="mt-1 text-sm text-on-surface-variant">
                Hidden-skill detection results saved for this account.
              </p>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              {[
                {
                  label: "Pending",
                  value: String(pendingDiscoveries.length),
                },
                {
                  label: "Approved",
                  value: String(data.hiddenSkills.filter((candidate) => candidate.status === "approved").length),
                },
                {
                  label: "Rejected",
                  value: String(data.hiddenSkills.filter((candidate) => candidate.status === "rejected").length),
                },
                {
                  label: "Total candidates",
                  value: String(data.hiddenSkills.length),
                },
              ].map((item) => (
                <div key={item.label} className="rounded-3xl bg-surface-container-low px-5 py-5">
                  <p className="text-[10px] font-black uppercase tracking-[0.2em] text-on-surface-variant">
                    {item.label}
                  </p>
                  <p className="mt-3 text-3xl font-extrabold tracking-tight text-on-surface">{item.value}</p>
                </div>
              ))}
            </div>

            <Link
              href="/hidden-skills"
              className="mt-6 inline-flex rounded-full bg-primary px-5 py-3 text-[11px] font-black uppercase tracking-[0.18em] text-white"
            >
              Review hidden skills
            </Link>
          </div>

          <div className="clay-card rounded-[32px] p-8">
            <div className="mb-6 flex items-center justify-between">
              <div>
                <h2 className="text-2xl font-bold tracking-tight text-on-surface">Candidate queue</h2>
                <p className="mt-1 text-sm text-on-surface-variant">
                  Evidence-driven discoveries. No placeholder traits are shown anymore.
                </p>
              </div>
            </div>

            {isLoading ? (
              <div className="space-y-4">
                {[1, 2, 3].map(i => (
                  <div key={i} className="h-32 rounded-3xl bg-on-surface-variant/5 animate-pulse" />
                ))}
              </div>
            ) : data.hiddenSkills.length ? (
              <div className="max-h-[52rem] space-y-4 overflow-y-auto pr-2 custom-scrollbar">
                {data.hiddenSkills.map((candidate) => (
                  <div
                    key={candidate.id}
                    className="lift-tile rounded-3xl border border-outline-variant/12 dark:border-transparent bg-surface-container-low px-5 py-5"
                  >
                    <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                      <div className="space-y-2">
                        <h3 className="text-lg font-bold text-on-surface">{candidate.skill_name}</h3>
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="text-[10px] font-black uppercase tracking-[0.18em] text-primary">
                            Source {candidate.source}
                          </p>
                          {candidate.artifact_id && (
                            <Link
                              href="/settings"
                              className="text-[10px] font-bold text-on-surface-variant underline hover:text-primary transition"
                            >
                              (View Artifact)
                            </Link>
                          )}
                        </div>
                        <p className="max-w-2xl text-sm leading-6 text-on-surface-variant">
                          {candidate.evidence}
                        </p>
                        <p className="text-[10px] font-black uppercase tracking-[0.18em] text-on-surface-variant">
                          {candidate.created_at
                            ? `Detected ${formatDate(candidate.created_at)}`
                            : "Recently detected"}
                        </p>
                      </div>

                      <div className="space-y-3 lg:min-w-[12rem]">
                        <div className="rounded-3xl bg-surface px-4 py-3 text-right shadow-inner">
                          <p className="text-[10px] font-black uppercase tracking-[0.18em] text-on-surface-variant">
                            Confidence
                          </p>
                          <p className="mt-2 text-2xl font-extrabold tracking-tight text-on-surface">
                            {Math.round(candidate.confidence_score * 100)}%
                          </p>
                        </div>
                        <span className="inline-flex rounded-full bg-primary/10 px-3 py-2 text-[10px] font-black uppercase tracking-[0.16em] text-primary">
                          {toTitleCase(candidate.status)}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyCard
                title="No hidden skill discoveries yet"
                body="This section now stays empty until the backend actually stores discovery candidates for your account."
                href="/assessments"
                action="Generate evidence"
              />
            )}
          </div>
        </section>
      ) : null}

      <SkillInsightModal skill={selectedSkill} onClose={() => setSelectedSkillId(null)} />
    </div>
  );
}
