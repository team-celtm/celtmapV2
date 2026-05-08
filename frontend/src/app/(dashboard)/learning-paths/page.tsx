"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Info,
  TrendingUp,
  Target,
  CheckCircle2,
  ChevronRight,
  Zap,
  Star,
  BookOpen,
  MapPin,
  PlayCircle,
  AlertCircle,
} from "lucide-react";

import { apiFetch, getApiErrorMessage } from "@/lib/api";
import { buildAssessmentQuizHref, buildWrittenAssessmentHref } from "@/lib/assessmentLinks";
import type {
  DashboardSummary,
  LearningPathRead,
  ProfileRead,
  RoleFitRead,
  SkillGapRead,
  SkillRead,
} from "@/lib/celtm";
import { formatPercent } from "@/lib/celtm";
import { 
  DonutSkeleton, 
  StatCardSkeleton, 
  ListSkeleton,
  SkeletonPulse
} from "@/components/common/Skeletons";

/**
 * InfoPopup - A subtle interactive popup for hidden text.
 */
function InfoPopup({ content }: { content: string }) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="relative inline-block ml-1.5 align-middle">
      <button
        onMouseEnter={() => setIsOpen(true)}
        onMouseLeave={() => setIsOpen(false)}
        className="p-1 rounded-full bg-surface-container-high/50 text-on-surface-variant hover:text-primary transition-colors duration-200"
      >
        <Info size={14} strokeWidth={2.5} />
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 5, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 5, scale: 0.95 }}
            className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-3 rounded-2xl bg-surface-container-highest shadow-2xl border border-outline-variant/10 text-xs leading-relaxed text-on-surface pointer-events-none"
          >
            {content}
            <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-1 border-8 border-transparent border-t-surface-container-highest" />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/**
 * CircleProgress - Minimal circular progress indicator
 */
function CircleProgress({ value, color = "stroke-primary" }: { value: number; color?: string }) {
  const radius = 18;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (value / 100) * circumference;

  return (
    <div className="relative w-12 h-12 flex items-center justify-center">
      <svg className="w-full h-full transform -rotate-90">
        <circle
          cx="24"
          cy="24"
          r={radius}
          className="stroke-outline-variant/10 fill-none"
          strokeWidth="3.5"
        />
        <motion.circle
          cx="24"
          cy="24"
          r={radius}
          className={`${color} fill-none`}
          strokeWidth="3.5"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1.5, ease: "easeOut" }}
          strokeLinecap="round"
        />
      </svg>
      <span className="absolute text-[10px] font-black">{Math.round(value)}%</span>
    </div>
  );
}

interface LearningPathsState {
  summary: DashboardSummary | null;
  profile: ProfileRead | null;
  roleFit: RoleFitRead | null;
  skills: SkillRead[];
  gaps: SkillGapRead[];
  learningPath: LearningPathRead | null;
}

const initialState: LearningPathsState = {
  summary: null,
  profile: null,
  roleFit: null,
  skills: [],
  gaps: [],
  learningPath: null,
};

function buildLoadWarning(failedSections: Array<{ label: string; reason: unknown }>, fallback: string) {
  if (!failedSections.length) {
    return null;
  }

  const labels = failedSections.map((section) => section.label).join(", ");
  const detail = getApiErrorMessage(failedSections[0].reason, fallback);
  return `Some learning-path data is unavailable right now (${labels}). ${detail}`;
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

export default function LearningPathsPage() {
  const [data, setData] = useState<LearningPathsState>(initialState);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    const loadPaths = async () => {
      try {
        setIsLoading(true);
        setError(null);

        const [
          summaryResult,
          profileResult,
          roleFitResult,
          skillsResult,
          gapsResult,
          learningPathResult,
        ] = await Promise.allSettled([
          apiFetch<DashboardSummary>("/dashboard/summary"),
          apiFetch<ProfileRead>("/profile/me"),
          apiFetch<RoleFitRead>("/skills/me/role-fit"),
          apiFetch<SkillRead[]>("/skills/me"),
          apiFetch<SkillGapRead[]>("/skills/me/gaps"),
          apiFetch<LearningPathRead>("/learning/path"),
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
          { label: "learning path", result: learningPathResult },
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
          learningPath: learningPathResult.status === "fulfilled" ? learningPathResult.value : null,
        });
        setError(buildLoadWarning(failedSections, "Failed to load the live learning paths."));
      } catch (caught) {
        if (!isMounted) {
          return;
        }

        setError(getApiErrorMessage(caught, "Failed to load the live learning paths."));
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    void loadPaths();

    return () => {
      isMounted = false;
    };
  }, []);

  const topSkills = useMemo(
    () => [...data.skills].sort((left, right) => right.verified_score - left.verified_score).slice(0, 4),
    [data.skills],
  );
  const topGaps = useMemo(
    () => [...data.gaps].sort((left, right) => right.gap_severity - left.gap_severity).slice(0, 5),
    [data.gaps],
  );
  const modules = useMemo(() => data.learningPath?.modules ?? [], [data.learningPath?.modules]);
  const focusRole = data.profile?.focus_role || data.roleFit?.role_name || "Not set yet";
  const readiness = !isLoading && data.summary
    ? data.summary.readiness_score 
    : (data.roleFit ? data.roleFit.fit_score : null);
  const hasLiveTrajectory = Boolean(
    data.profile?.focus_role
    || data.roleFit?.role_name
    || data.skills.length
    || data.gaps.length
    || modules.length,
  );

  return (
    <div className="mx-auto w-full max-w-[1520px] space-y-8 animate-fade-in pb-10">
      {error ? (
        <div className="rounded-3xl border border-amber-500/20 bg-amber-500/10 px-6 py-5 text-sm text-amber-300">
          {error}
        </div>
      ) : null}

      <section>
        <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between px-2">
          <div>
            <h1 className="text-4xl md:text-5xl font-black tracking-tight text-on-surface">Learning Path</h1>
            <div className="mt-3 flex max-w-2xl items-start text-base leading-relaxed text-on-surface-variant">
              <span>
                Your personalized evolution strategy, automatically updated based on live performance and focus roles.
              </span>
              <InfoPopup content="This journey is recalculated every time you complete an assessment or change your focus role in settings." />
            </div>
          </div>
          <div className="flex items-center gap-3">
             <Link
              href="/settings"
              className="inline-flex rounded-full bg-primary/10 px-6 py-3 text-[11px] font-black uppercase tracking-widest text-primary transition hover:bg-primary/20 shadow-sm"
            >
              Update Focus Role
            </Link>
          </div>
        </div>

        <div className="mt-10 grid grid-cols-1 md:grid-cols-3 gap-6">
          {isLoading ? (
            <>
              <StatCardSkeleton />
              <StatCardSkeleton />
              <StatCardSkeleton />
            </>
          ) : (
            <>
              <div className="clay-card p-6 flex items-center gap-5 border-none bg-white shadow-xl shadow-primary/5">
                <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center text-primary">
                  <TrendingUp size={28} />
                </div>
                <div className="flex-1">
                  <p className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant/70">Readiness Score</p>
                  <div className="mt-1 flex items-center gap-3">
                    {readiness === null || isLoading ? (
                      <div className="h-8 w-16 animate-pulse bg-on-surface/10 rounded-lg" />
                    ) : (
                      <p className="text-2xl font-black text-on-surface">{Math.round(readiness)}%</p>
                    )}
                    <div className="flex-1 h-2 bg-outline-variant/10 rounded-full overflow-hidden">
                      <motion.div 
                        initial={{ width: 0 }}
                        animate={{ width: `${readiness || 0}%` }}
                        className="h-full bg-primary"
                      />
                    </div>
                  </div>
                </div>
              </div>

              <div className="clay-card p-6 flex items-center gap-5 border-none bg-white shadow-xl shadow-amber-500/5">
                <div className="w-14 h-14 rounded-2xl bg-amber-500/10 flex items-center justify-center text-amber-500">
                  <Target size={28} />
                </div>
                <div>
                  <p className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant/70">Critical Gaps</p>
                  <p className="text-2xl font-black text-on-surface">
                    {isLoading ? <span className="inline-block h-6 w-8 animate-pulse bg-on-surface/10 rounded" /> : data.gaps.length}
                  </p>
                </div>
              </div>

              <div className="clay-card p-6 flex items-center gap-5 border-none bg-white shadow-xl shadow-emerald-500/5">
                <div className="w-14 h-14 rounded-2xl bg-emerald-500/10 flex items-center justify-center text-emerald-500">
                  <CheckCircle2 size={28} />
                </div>
                <div>
                  <p className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant/70">Verified Assets</p>
                  <p className="text-2xl font-black text-on-surface">
                    {isLoading ? <span className="inline-block h-6 w-8 animate-pulse bg-on-surface/10 rounded" /> : data.skills.length}
                  </p>
                </div>
              </div>
            </>
          )}
        </div>
      </section>

      {!hasLiveTrajectory ? (
        <EmptyCard
          title="No learning path generated yet"
          body="There is no live role or assessment data to build a trajectory from. Set a focus role and complete your first assessments to generate a real path."
          href="/settings"
          action="Set focus role"
        />
      ) : (
        <div className="space-y-8">
          {/* Skill Distribution & Roadmap Section */}
          <section className="grid gap-8 xl:grid-cols-[1fr_1.1fr] items-stretch">
            <div className="clay-card rounded-[40px] p-8 border-none bg-white shadow-2xl shadow-primary/5 h-full flex flex-col">
              <div className="mb-10 flex items-center justify-between">
                <div>
                  <h2 className="text-2xl font-black tracking-tight text-on-surface">Skill Distribution</h2>
                  <p className="mt-1 text-sm text-on-surface-variant">
                    Your strongest verified assets vs critical pressure areas.
                  </p>
                </div>
                <div className="px-3 py-1 rounded-full bg-primary/10 text-[10px] font-bold text-primary tracking-widest uppercase">
                  {focusRole}
                </div>
              </div>

              <div className="space-y-12">
                <div>
                  <h3 className="text-[11px] font-black uppercase tracking-[0.2em] text-on-surface-variant/60 mb-6 flex items-center gap-2">
                    <Star size={14} className="text-emerald-500" />
                    Verified Strengths
                  </h3>
                  {topSkills.length ? (
                    <div className="grid grid-cols-2 gap-4">
                      {topSkills.map((skill) => (
                        <div key={skill.skill_id} className="p-4 rounded-3xl bg-surface-container-low flex items-center justify-between group hover:bg-emerald-500/5 transition-colors">
                          <span className="text-sm font-bold text-on-surface">{skill.skill_name}</span>
                          <CircleProgress value={skill.verified_score} color="stroke-emerald-500" />
                        </div>
                      ))}
                    </div>
                  ) : (
                    <EmptyCard
                      title="No strengths yet"
                      body="Complete assessments to verify your skills."
                      href="/assessments"
                      action="Start testing"
                    />
                  )}
                </div>

                <div>
                  <h3 className="text-[11px] font-black uppercase tracking-[0.2em] text-on-surface-variant/60 mb-6 flex items-center gap-2">
                    <AlertCircle size={14} className="text-amber-500" />
                    High Pressure Gaps
                  </h3>
                  {topGaps.length ? (
                    <div className="space-y-4">
                      {topGaps.slice(0, 3).map((gap) => (
                        <div key={gap.skill_name} className="p-5 rounded-3xl bg-surface-container-low group hover:bg-amber-500/5 transition-colors">
                          <div className="flex items-center justify-between mb-3">
                            <span className="text-sm font-bold text-on-surface">{gap.skill_name}</span>
                            <span className="text-[10px] font-black text-amber-500 bg-amber-500/10 px-2 py-0.5 rounded-full uppercase">
                              Severity {Math.round(gap.gap_severity * 100)}%
                            </span>
                          </div>
                          <div className="h-2 overflow-hidden rounded-full bg-outline-variant/15">
                            <motion.div
                              initial={{ width: 0 }}
                              animate={{ width: `${gap.gap_severity * 100}%` }}
                              className="h-full bg-gradient-to-r from-amber-400 to-amber-600"
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-on-surface-variant italic">No major gaps detected.</p>
                  )}
                </div>
              </div>
            </div>

            <div className="clay-card rounded-[40px] p-8 border-none bg-white relative overflow-hidden shadow-2xl shadow-primary/5 h-full flex flex-col">
              <div className="mb-10">
                <h2 className="text-2xl font-black tracking-tight text-on-surface">Suggested Sequence</h2>
                <p className="mt-1 text-sm text-on-surface-variant">
                  Vertical roadmap of recommended next steps.
                </p>
              </div>

              {modules.length ? (
                <div className="relative pl-12 space-y-12 flex-1">
                  <div className="absolute left-[23px] top-2 bottom-10 w-0.5 bg-gradient-to-b from-primary via-primary/30 to-transparent" />
                  
                  {modules.slice(0, 4).map((module, index) => (
                    <div key={module.skill_name} className="relative group">
                      <div className="absolute -left-[12px] top-1.5 w-6 h-6 rounded-full bg-white border-4 border-primary z-10 shadow-lg group-hover:scale-125 transition-transform" />
                      
                      <div className="p-5 rounded-3xl bg-surface-container-low lift-tile">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-[10px] font-black uppercase tracking-widest text-primary">Step {index + 1}</span>
                          <InfoPopup content={module.resources[0]?.content || "Focus on closing this gap to improve your role fit."} />
                        </div>
                        <h3 className="text-lg font-black text-on-surface mb-4">{module.skill_name}</h3>
                        
                        <div className="flex gap-3">
                          {module.is_available ? (
                            <>
                              <Link
                                href={buildAssessmentQuizHref({ title: module.skill_name })}
                                className="flex-1 flex items-center justify-center gap-2 rounded-2xl bg-primary text-white py-2.5 text-[10px] font-black uppercase tracking-widest transition hover:brightness-110 shadow-lg shadow-primary/20"
                              >
                                <PlayCircle size={14} /> MCQ
                              </Link>
                              <Link
                                href={buildWrittenAssessmentHref({ title: module.skill_name })}
                                className="flex-1 flex items-center justify-center gap-2 rounded-2xl bg-surface border border-outline-variant/20 text-on-surface py-2.5 text-[10px] font-black uppercase tracking-widest transition hover:bg-surface-container-high"
                              >
                                <BookOpen size={14} /> Written
                              </Link>
                            </>
                          ) : (
                            <div className="flex-1 text-center py-2.5 rounded-2xl bg-outline-variant/10 text-[10px] font-black uppercase tracking-widest text-on-surface-variant/50 border border-dashed border-outline-variant/30">
                              Assessment Coming Soon
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyCard
                  title="No roadmap yet"
                  body="As soon as live gap data appears, this page will rank the next best modules instead of showing canned tracks."
                  href="/assessments"
                  action="Open Assessments"
                />
              )}
            </div>
          </section>

          {/* Recommended Modules & Logic Section */}
          <section className="grid gap-8 xl:grid-cols-[1fr_400px] items-stretch">
            <div className="clay-card rounded-[40px] p-8 border-none bg-white shadow-2xl shadow-primary/5 h-full flex flex-col">
              <div className="mb-8 flex items-center justify-between">
                <div>
                  <h2 className="text-2xl font-black tracking-tight text-on-surface">Recommended Modules</h2>
                  <p className="mt-1 text-sm text-on-surface-variant">
                    Deep dive into specific domains from your actual learning path.
                  </p>
                </div>
              </div>

              {modules.length ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 flex-1">
                  {modules.map((module) => (
                    <div
                      key={module.title}
                      className="p-6 rounded-3xl bg-surface-container-low border border-transparent hover:border-primary/20 transition-all lift-tile flex flex-col h-full"
                    >
                      <div className="flex justify-between items-start mb-4 gap-4">
                        <h3 className="text-lg font-black text-on-surface line-clamp-1">{module.skill_name}</h3>
                        <div className="flex items-center gap-2 shrink-0">
                          {!module.is_available && (
                            <span className="rounded-full bg-amber-500/10 px-2 py-1 text-[9px] font-black uppercase tracking-widest text-amber-600 border border-amber-500/20 whitespace-nowrap">
                              Coming Soon
                            </span>
                          )}
                          <span className="rounded-full bg-primary/10 px-2 py-1 text-[9px] font-black uppercase tracking-widest text-primary whitespace-nowrap">
                            Week {module.week}
                          </span>
                        </div>
                      </div>
                      
                      <p className="text-sm text-on-surface-variant leading-relaxed mb-6 line-clamp-2">
                        {module.title}
                      </p>

                      <div className="mt-auto">
                        {module.resources.length ? (
                          <div className="flex flex-wrap gap-2 mb-4">
                            {module.resources.slice(0, 2).map((resource) => (
                              <a
                                key={`${module.title}-${resource.title}`}
                                href={resource.resource_url || "#"}
                                target="_blank"
                                rel="noreferrer"
                                className="inline-flex rounded-full bg-white px-3 py-1.5 text-[9px] font-black uppercase tracking-widest text-on-surface border border-outline-variant/20 hover:bg-surface-container-high transition-colors"
                              >
                                {resource.resource_type}
                              </a>
                            ))}
                          </div>
                        ) : null}

                        {module.is_available ? (
                          <Link
                            href={buildAssessmentQuizHref({ title: module.skill_name })}
                            className="flex items-center justify-center gap-2 w-full py-2.5 rounded-2xl bg-primary/10 text-primary text-[10px] font-black uppercase tracking-widest hover:bg-primary/15 transition-colors"
                          >
                            Explore Assessments <ChevronRight size={14} />
                          </Link>
                        ) : (
                          <div className="w-full py-2.5 rounded-2xl bg-outline-variant/5 text-on-surface-variant/40 text-[10px] font-black uppercase tracking-widest text-center border border-dashed border-outline-variant/20 cursor-not-allowed">
                            Content Upcoming
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-on-surface-variant italic">No modules scheduled yet.</p>
              )}
            </div>

            <div className="clay-card rounded-[40px] p-8 border-none bg-white shadow-2xl shadow-primary/5 h-full flex flex-col">
              <h2 className="text-2xl font-black tracking-tight text-on-surface mb-8">Logic Rules</h2>
              <div className="grid grid-cols-2 gap-4 flex-1 content-start">
                {[
                  { icon: <Target className="text-primary" />, title: "Precision", body: "Ranking missing skills for focus role first." },
                  { icon: <Zap className="text-amber-500" />, title: "Efficiency", body: "Prioritizing high gap density areas first." },
                  { icon: <Star className="text-emerald-500" />, title: "Stability", body: "Maintaining verified assets while growing." },
                  { icon: <MapPin className="text-secondary" />, title: "Progress", body: "Sequential building blocks for growth." },
                ].map((item) => (
                  <div key={item.title} className="p-4 rounded-3xl bg-surface-container-low group hover:bg-white hover:shadow-xl hover:shadow-primary/5 transition-all text-center">
                    <div className="mx-auto w-10 h-10 rounded-2xl bg-white flex items-center justify-center mb-3 group-hover:scale-110 transition-transform shadow-sm">
                      {item.icon}
                    </div>
                    <div className="flex items-center justify-center gap-1">
                      <h3 className="text-[10px] font-bold text-on-surface mb-1 uppercase tracking-tighter">{item.title}</h3>
                      <InfoPopup content={item.body} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
