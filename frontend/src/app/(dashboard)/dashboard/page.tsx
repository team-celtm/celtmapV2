"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { ApiError, apiFetch, apiFetchBlob } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import type {
  DashboardSummary,
  ProfileRead,
  SubjectProgress,
} from "@/lib/celtm";
import AppIcon from "@/components/AppIcon";
import CeltmProgressLoader from "@/components/CeltmProgressLoader";
import { SubjectProgressCards } from "@/components/dashboard/SubjectProgressCards";
import { motion as Motion, AnimatePresence } from "framer-motion";
import {
  breakdownProgressPercent,
  formatBreakdownScore,
  hasOnlyProfileLinksWithoutInsights,
  normalizeScoreBreakdown,
} from "@/lib/dashboardLogic.mjs";

interface ResumeAnalysis {
  id: string;
  target_role: string;
  match_score: number;
  created_at: string;
  analysis: {
    match_score?: number;
    verdict?: string;
    summary?: string;
    score_breakdown?: Array<{ label: string; score: number; max: number }>;
    top_keywords?: Array<{ rank: number; keyword: string; status: string; detail: string; badge: string }>;
    red_flags?: Array<{ title: string; reason: string; fix: string }>;
    full_breakdown?: string;
    strong_points?: string[];
    weak_points?: string[];
    institute_help?: string[];
  };
}

interface AssessmentLog {
  id: string;
  type: string;
  subject: string;
  score: number;
  status: string;
  completed_at: string | null;
  insight: string;
  feedback: string | null;
  strengths: string[];
  risks: string[];
  recommendations: string[];
  readiness_score: number;
  role_name: string;
  hidden_skills?: string[];
  areas_of_betterment?: string[];
  analytics?: {
    correct: number;
    wrong: number;
    total: number;
  };
}

type KeywordItem = { rank: number; keyword: string; status: string; detail: string; badge: string };
type RedFlagItem = { title: string; reason: string; fix: string };

async function fetchDashboardData<T>(path: string, timeoutMs = 8000): Promise<T> {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => {
    controller.abort(new DOMException(`Dashboard request timed out after ${timeoutMs}ms`, "TimeoutError"));
  }, timeoutMs);

  try {
    return await apiFetch<T>(path, {
      signal: controller.signal,
      cacheTtlMs: 60_000,
    });
  } finally {
    window.clearTimeout(timeoutId);
  }
}

function listFromUnknown(value: unknown): unknown[] {
  if (Array.isArray(value)) return value;
  if (value && typeof value === "object") return Object.values(value as Record<string, unknown>);
  if (typeof value === "string" && value.trim()) return [value.trim()];
  return [];
}

function normalizeKeywords(value: unknown): KeywordItem[] {
  return listFromUnknown(value)
    .map((item, index) => {
      if (item && typeof item === "object") {
        const raw = item as Record<string, unknown>;
        const keyword = String(raw.keyword ?? raw.term ?? raw.name ?? raw.label ?? raw.title ?? "").trim();
        if (!keyword) return null;
        return {
          rank: Number(raw.rank ?? index + 1) || index + 1,
          keyword,
          status: String(raw.status ?? raw.presence ?? "Review"),
          detail: String(raw.detail ?? raw.description ?? raw.reason ?? "Make this explicit with resume evidence."),
          badge: String(raw.badge ?? raw.status ?? "Keyword"),
        };
      }
      const keyword = String(item ?? "").trim();
      if (!keyword) return null;
      return {
        rank: index + 1,
        keyword,
        status: "Review",
        detail: "Add this keyword only when it is supported by visible resume evidence.",
        badge: "Keyword",
      };
    })
    .filter((item): item is KeywordItem => Boolean(item))
    .slice(0, 5);
}

function normalizeRedFlags(value: unknown): RedFlagItem[] {
  return listFromUnknown(value)
    .map((item) => {
      if (item && typeof item === "object") {
        const raw = item as Record<string, unknown>;
        const title = String(raw.title ?? raw.flag ?? raw.name ?? raw.label ?? "").trim();
        if (!title) return null;
        return {
          title,
          reason: String(raw.reason ?? raw.description ?? raw.detail ?? "This can weaken trust during a fast recruiter scan."),
          fix: String(raw.fix ?? raw.recommendation ?? raw.solution ?? "Add specific evidence and remove ambiguity."),
        };
      }
      const title = String(item ?? "").trim();
      if (!title) return null;
      return {
        title,
        reason: "A recruiter may notice this quickly during the first resume screen.",
        fix: "Rewrite the section with concrete evidence, dates, links, or measured impact.",
      };
    })
    .filter((item): item is RedFlagItem => Boolean(item))
    .slice(0, 3);
}

export default function DashboardPage() {
  const { user, refreshProfile } = useAuth();
  const [profile, setProfile] = useState<ProfileRead | null>(null);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [resume, setResume] = useState<ResumeAnalysis | null>(null);
  const [assessmentLogs, setAssessmentLogs] = useState<AssessmentLog[]>([]);
  const [subjectProgress, setSubjectProgress] = useState<SubjectProgress[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [isResumeComplete, setIsResumeComplete] = useState(false);
  const [error, setError] = useState("");
  const [insightStatus, setInsightStatus] = useState<string | null>(null);
  const resumeInputRef = useRef<HTMLInputElement | null>(null);

  const [isExportingPDF, setIsExportingPDF] = useState(false);

  const exportReport = async () => {
    try {
      setIsExportingPDF(true);
      const blob = await apiFetchBlob("/reports/me/dashboard.pdf");
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${profile?.full_name?.replace(/[^a-z0-9]/gi, "_").toLowerCase() || "student"}_dashboard.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      a.remove();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Failed to export PDF.");
    } finally {
      setIsExportingPDF(false);
    }
  };

  const load = async (showPageLoader = true) => {
    try {
      if (showPageLoader) setIsLoading(true);
      setError("");
      const [profilePayload, summaryPayload, resumePayload] = await Promise.all([
        apiFetch<ProfileRead>("/profile/me"),
        apiFetch<DashboardSummary>("/dashboard/summary"),
        apiFetch<ResumeAnalysis | null>("/resume/latest"),
      ]);
      setProfile(profilePayload);
      setSummary(summaryPayload);
      setResume(resumePayload);
      void (async () => {
        const [logsResult, subjectProgressResult] = await Promise.allSettled([
          fetchDashboardData<AssessmentLog[]>("/assessments/log"),
          fetchDashboardData<SubjectProgress[]>("/assessments/subject-progress"),
        ]);
        const failures: string[] = [];
        if (logsResult.status === "fulfilled") {
          setAssessmentLogs(logsResult.value);
        } else {
          failures.push("assessment insights");
        }
        if (subjectProgressResult.status === "fulfilled") {
          setSubjectProgress(subjectProgressResult.value);
        } else {
          failures.push("subject progress");
        }
        setInsightStatus(
          failures.length
            ? `${failures.join(" and ")} not available from the backend right now.`
            : null,
        );
      })();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Failed to load dashboard.");
    } finally {
      if (showPageLoader) setIsLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const analysis = resume?.analysis;
  const readinessScore = Math.round(summary?.readiness_score ?? 0);
  const resumeScore = Math.round(analysis?.match_score ?? resume?.match_score ?? 0);
  const score = readinessScore;
  const readinessComponents = summary?.readiness_components ?? [];
  const breakdown = normalizeScoreBreakdown(analysis?.score_breakdown);
  const keywords = normalizeKeywords(analysis?.top_keywords);
  const redFlags = normalizeRedFlags(analysis?.red_flags);
  const activeTargetRole = profile?.focus_role?.trim() ?? "";
  const showProfileOnlyInsightPrompt = hasOnlyProfileLinksWithoutInsights({
    resume,
    readinessComponents,
    assessmentLogs,
    subjectProgress,
    breakdown,
    keywords,
    redFlags,
  });

  const readinessText = useMemo(() => {
    if (readinessScore <= 0) return "Upload evidence or complete assessments to unlock CELTM readiness.";
    if (score >= 80) return "Strong candidate - a few fixable gaps";
    if (score >= 60) return "Good base - needs sharper proof";
    return "Developing profile - build evidence first";
  }, [readinessScore, score]);

  const submitResume = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!file) {
      setError("Select a resume PDF, DOCX, or TXT file.");
      return;
    }
    if (!activeTargetRole) {
      setError("Set your career aim in Settings before analyzing a resume.");
      return;
    }
    try {
      setIsUploading(true);
      setIsResumeComplete(false);
      setError("");
      const formData = new FormData();
      formData.append("file", file);
      formData.append("target_role", activeTargetRole);
      const payload = await apiFetch<ResumeAnalysis>("/resume/analyze", {
        method: "POST",
        body: formData,
      });
      setResume(payload);
      setFile(null);
      if (resumeInputRef.current) {
        resumeInputRef.current.value = "";
      }
      await refreshProfile();
      await load(false);
      setIsResumeComplete(true);
      await new Promise((resolve) => window.setTimeout(resolve, 650));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Resume analysis failed.");
    } finally {
      setIsUploading(false);
      setIsResumeComplete(false);
    }
  };

  if (isLoading) {
    return (
      <CeltmProgressLoader
        title="Loading dashboard"
        caption="Cooking your profile"
        minHeightClassName="min-h-[80vh]"
        stages={["Fetching your profile", "Reading latest resume analysis", "Syncing readiness score", "Preparing dashboard"]}
      />
    );
  }

  return (
    <div className="mx-auto w-full max-w-[1320px] space-y-8 pb-12">
      {error ? (
        <div className="rounded-3xl border border-red-500/20 bg-red-500/10 px-5 py-4 text-sm font-semibold text-red-500">
          {error}
        </div>
      ) : null}
      {insightStatus ? (
        <div className="rounded-3xl border border-amber-500/20 bg-amber-500/10 px-5 py-4 text-sm font-semibold text-amber-700 dark:text-amber-300">
          {insightStatus}
        </div>
      ) : null}

      <Motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="clay-card overflow-hidden rounded-[36px] p-7 md:p-9"
      >
        <div className="grid gap-8 lg:grid-cols-[1.1fr_0.9fr] lg:items-center">
          <div className="flex flex-col md:flex-row md:items-start md:justify-between col-span-1 lg:col-span-2 mb-4">
            <div>
              <p className="text-[11px] font-black uppercase tracking-[0.24em] text-primary">Student Dashboard</p>
              <h1 className="mt-3 text-4xl font-black tracking-tight text-on-surface md:text-5xl">
                {profile?.full_name || user?.name || "CELTM Student"}
              </h1>
            </div>
            <div className="mt-4 md:mt-0 flex items-center gap-3">
              <button
                onClick={() => void exportReport()}
                disabled={isExportingPDF}
                className="flex items-center gap-2 rounded-2xl bg-primary/10 hover:bg-primary/20 px-4 py-2 text-xs font-black uppercase tracking-widest text-primary transition-colors"
              >
                <AppIcon name="file_download" className="h-4 w-4" />
                {isExportingPDF ? "..." : "Export Full Report"}
              </button>
            </div>
          </div>
          <div>
            <p className="max-w-2xl text-lg leading-8 text-on-surface-variant">
              Phase 1 starts with resume analysis. Upload once, then use rule-based assessments to raise your readiness score.
            </p>
            <div className="mt-6 grid gap-3 sm:grid-cols-3">
              <Stat label="Institute" value={profile?.institution_name || user?.institutionName || "Not set"} />
              <Stat label="Department" value={profile?.department_name || user?.departmentName || "Not set"} />
              <Stat label="Target" value={activeTargetRole || "Set in settings"} />
            </div>
          </div>

          <form onSubmit={submitResume} className="rounded-[30px] bg-surface-container-low p-5">
            <h2 className="text-xl font-black tracking-tight text-on-surface">Upload resume to continue</h2>
            <p className="mt-2 text-sm leading-6 text-on-surface-variant">
              AI is used here only for resume checking. The target role is locked to the career aim saved in Settings.
            </p>
            <div className="mt-5 rounded-2xl border border-outline-variant/20 bg-surface px-4 py-3">
              <span className="block text-[10px] font-black uppercase tracking-widest text-on-surface-variant">Active career aim</span>
              <div className="mt-2 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-sm font-black text-on-surface">
                  {activeTargetRole || "Set your career aim in Settings first"}
                </p>
                <Link href="/settings" className="text-[10px] font-black uppercase tracking-[0.18em] text-primary">
                  Change in settings
                </Link>
              </div>
            </div>
            <label className="mt-4 flex cursor-pointer flex-col items-center justify-center rounded-3xl border-2 border-dashed border-outline-variant/25 bg-surface px-5 py-8 text-center transition hover:border-primary/40">
              <AppIcon name="upload_file" className="h-10 w-10 text-primary" />
              <span className="mt-3 text-sm font-bold text-on-surface">{file?.name || "Choose resume file"}</span>
              <span className="mt-1 text-xs text-on-surface-variant">PDF, DOCX, or TXT</span>
              <input ref={resumeInputRef} type="file" accept=".pdf,.docx,.txt" className="hidden" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
            </label>
            <button
              type="submit"
              disabled={isUploading || !activeTargetRole}
              className="mt-5 h-13 w-full rounded-2xl bg-primary px-5 py-4 text-[11px] font-black uppercase tracking-[0.18em] text-white transition hover:opacity-90 disabled:opacity-60"
            >
              {!activeTargetRole ? "Set career aim in settings" : isUploading ? "Analyzing..." : resume ? "Re-analyze resume" : "Analyze resume"}
            </button>
          </form>
        </div>
      </Motion.section>

      {!resume ? (
        <Motion.section
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-[34px] border border-outline-variant/15 bg-surface-container-low p-7"
        >
          <p className="text-[10px] font-black uppercase tracking-[0.22em] text-primary">No resume?</p>
          <h2 className="mt-2 text-2xl font-black tracking-tight text-on-surface">Update your career aim without a resume in Settings</h2>
          <p className="mt-2 max-w-3xl text-sm font-semibold leading-6 text-on-surface-variant">
            The draft digital CELTM personality now lives in Settings. Go there to add temporary interests, strengths, preferred industries, links, and career aim signals before uploading a resume.
          </p>
          <Link
            href="/settings?tab=career"
            className="mt-5 inline-flex rounded-2xl bg-primary px-5 py-3 text-[11px] font-black uppercase tracking-[0.18em] text-white transition hover:-translate-y-0.5 hover:shadow-lg hover:shadow-primary/20"
          >
            Go to settings
          </Link>
        </Motion.section>
      ) : null}

      {isUploading ? (
        <CeltmProgressLoader
          title="Resume analysis"
          caption="Cooking your resume"
          forceComplete={isResumeComplete}
          stages={["Extracting resume text", "Checking role keywords", "Scoring evidence strength", "Updating readiness"]}
        />
      ) : !resume && readinessScore <= 0 ? (
        <Motion.section
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.1 }}
          className="rounded-[36px] border border-dashed border-outline-variant/25 bg-surface-container-low p-10 text-center"
        >
          <h2 className="text-2xl font-black tracking-tight text-on-surface">No resume analysis yet</h2>
          <p className="mx-auto mt-3 max-w-xl text-sm leading-7 text-on-surface-variant">
            Your dashboard stays intentionally simple until the resume is uploaded. After analysis, assessments and career aim tracking become meaningful.
          </p>
        </Motion.section>
      ) : (
        <>
          <Motion.section
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="relative overflow-hidden rounded-[36px] bg-[#1f201e] p-6 text-white shadow-2xl"
          >
            <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/10 to-transparent pointer-events-none" />
            <div className="relative grid gap-8 md:grid-cols-[150px_1fr] md:items-center">
              <div className="relative mx-auto flex h-32 w-32 items-center justify-center">
                <svg className="absolute inset-0 h-full w-full -rotate-90 transform" viewBox="0 0 100 100">
                  <circle cx="50" cy="50" r="45" fill="none" stroke="rgba(16,185,129,0.2)" strokeWidth="8" />
                  <Motion.circle
                    cx="50" cy="50" r="45" fill="none"
                    stroke="#34d399" strokeWidth="8"
                    strokeDasharray="283" strokeDashoffset={283 - (283 * score) / 100}
                    strokeLinecap="round"
                    initial={{ strokeDashoffset: 283 }}
                    animate={{ strokeDashoffset: 283 - (283 * score) / 100 }}
                    transition={{ duration: 1.5, ease: "easeOut" }}
                  />
                </svg>
                <div className="text-3xl font-black text-emerald-400 drop-shadow-[0_0_10px_rgba(16,185,129,0.5)]">
                  {score}
                </div>
              </div>
              <div>
                <p className="text-sm font-bold text-white/60">Readiness score</p>
                <div className="mt-1 flex items-end gap-1">
                  <span className="text-5xl font-black text-emerald-400">{score}</span>
                  <span className="pb-2 text-2xl font-black text-white/70">/100</span>
                </div>
                <p className="mt-2 font-bold text-white/70">{analysis?.verdict || readinessText}</p>
                <p className="mt-4 max-w-3xl text-lg font-bold leading-8 text-white">
                  {showProfileOnlyInsightPrompt
                    ? "Your readiness currently comes only from validated profile links. Add more about yourself and explore assessments to unlock actual CELTM insights."
                    : analysis?.summary || "Your readiness is calculated from the active resume, assessments, written work, and credential evidence available for your profile."}
                </p>
              </div>
            </div>
          </Motion.section>

          {readinessComponents.length > 0 ? (
            <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              {readinessComponents.map((component) => (
                <div key={component.key} className="clay-card rounded-[28px] p-5">
                  <p className="text-[10px] font-black uppercase tracking-[0.2em] text-on-surface-variant">
                    {component.label}
                  </p>
                  <p className="mt-3 text-3xl font-black text-on-surface">{Math.round(component.score)}%</p>
                  <p className="mt-1 text-xs font-bold text-primary">
                    {Math.round(component.effective_weight * 100)}% of readiness
                  </p>
                </div>
              ))}
            </section>
          ) : null}

          {showProfileOnlyInsightPrompt ? (
            <ProfileOnlyInsightPrompt />
          ) : (
            <>
          <section className="grid gap-7 xl:grid-cols-2">
            <div className="relative overflow-hidden rounded-[32px] p-1 bg-gradient-to-br from-primary/30 via-transparent to-primary/10">
              <div className="clay-card rounded-[30px] p-7 h-full relative z-10 bg-surface/90 backdrop-blur-xl">
                <h2 className="text-sm font-black uppercase tracking-[0.2em] text-on-surface-variant flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-primary animate-pulse"></span>
                  Resume score breakdown
                </h2>
                <p className="mt-2 text-sm font-bold text-on-surface-variant">
                  Resume match: {resume ? `${resumeScore}%` : "Pending"}
                </p>
                <div className="mt-6 grid gap-4">
                  {breakdown.length ? breakdown.map((item, index) => (
                    <div key={`${item.label}-${index}`} className="group">
                      <div className="mb-2 flex items-center justify-between text-sm font-bold text-on-surface transition-colors group-hover:text-primary">
                        <span>{item.label}</span>
                        <span className="text-on-surface-variant">{formatBreakdownScore(item)}</span>
                      </div>
                      <div className="h-2.5 rounded-full bg-surface-container-highest overflow-hidden">
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-primary to-emerald-400 relative"
                          style={{ width: `${breakdownProgressPercent(item)}%` }}
                        >
                           <div className="absolute inset-0 bg-white/20 animate-[shimmer_2s_infinite]" />
                        </div>
                      </div>
                    </div>
                  )) : (
                    <p className="rounded-2xl bg-surface-container-low px-4 py-4 text-sm text-on-surface-variant">
                      Upload or analyze a resume to see recruiter-facing score details.
                    </p>
                  )}
                </div>
              </div>
            </div>

            <div className="relative overflow-hidden rounded-[32px] p-1 bg-gradient-to-br from-emerald-500/20 via-transparent to-amber-500/20">
              <div className="clay-card rounded-[30px] p-7 h-full relative z-10 bg-surface/90 backdrop-blur-xl">
                <h2 className="text-sm font-black uppercase tracking-[0.2em] text-on-surface-variant flex items-center gap-2">
                  <AppIcon name="stars" className="h-4 w-4 text-emerald-500" />
                  Top 5 Keywords
                </h2>
                <div className="mt-6 grid gap-4 sm:grid-cols-2">
                  {keywords.map((item, index) => (
                    <div key={`${item.rank}-${item.keyword}-${index}`} className="relative group overflow-hidden rounded-[24px] border border-outline-variant/15 bg-surface p-5 hover:shadow-[0_8px_30px_rgb(0,0,0,0.12)] hover:-translate-y-1 transition-all duration-300">
                      <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                      <div className="relative z-10">
                        <div className="flex justify-between items-start mb-2">
                          <p className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/10 text-[10px] font-black text-primary">#{item.rank}</p>
                          <span className="inline-flex rounded-full bg-emerald-500/10 px-3 py-1 text-[9px] font-black uppercase tracking-widest text-emerald-600">
                            {item.badge || item.status}
                          </span>
                        </div>
                        <h3 className="mt-2 text-lg font-black text-on-surface tracking-tight">{item.keyword}</h3>
                        <p className="mt-2 text-xs leading-5 text-on-surface-variant line-clamp-2">{item.detail}</p>
                      </div>
                    </div>
                  ))}
                  {!keywords.length ? (
                    <p className="rounded-2xl bg-surface-container-low px-4 py-4 text-sm font-semibold text-on-surface-variant">
                      Keyword insights are not available from the current evidence yet. Add a resume or complete assessments to generate them.
                    </p>
                  ) : null}
                </div>
              </div>
            </div>
          </section>

          <section className="relative overflow-hidden rounded-[32px] p-1 bg-gradient-to-r from-red-500/30 to-orange-500/20 mt-2">
            <div className="clay-card rounded-[30px] p-7 h-full relative z-10 bg-surface/95 backdrop-blur-xl">
              <div className="flex items-center gap-3 mb-6">
                <div className="h-10 w-10 rounded-2xl bg-red-500/10 flex items-center justify-center animate-pulse">
                  <AppIcon name="warning" className="h-5 w-5 text-red-500" />
                </div>
                <h2 className="text-sm font-black uppercase tracking-[0.2em] text-red-500">3 Red Flags - Spotted in under 10 seconds</h2>
              </div>
              <div className="grid gap-5 sm:grid-cols-3">
                {redFlags.map((flag, index) => (
                  <div key={`${flag.title}-${index}`} className="group relative overflow-hidden rounded-[24px] bg-surface-container-low p-6 transition-all duration-300 hover:shadow-lg border border-red-500/10 hover:border-red-500/40">
                    <div className="absolute -right-8 -top-8 h-32 w-32 rounded-full bg-red-500/5 transition-transform duration-700 group-hover:scale-[2]" />
                    <div className="relative z-10">
                      <h3 className="font-black text-on-surface text-lg leading-tight">{flag.title}</h3>
                      <p className="mt-3 text-xs leading-relaxed text-on-surface-variant">{flag.reason}</p>
                      <div className="mt-5 rounded-2xl bg-surface-container-high p-4 border border-outline-variant/10">
                        <p className="text-[9px] font-black uppercase tracking-widest text-emerald-500 mb-1.5 flex items-center gap-1">
                          <AppIcon name="build" className="h-3 w-3" />
                          Quick Fix
                        </p>
                        <p className="text-xs font-bold text-on-surface leading-tight">{flag.fix}</p>
                      </div>
                    </div>
                  </div>
                ))}
                {!redFlags.length ? (
                  <p className="sm:col-span-3 rounded-2xl bg-surface-container-low px-4 py-4 text-sm font-semibold text-on-surface-variant">
                    Red-flag insights are not available from the current evidence yet. Add more profile detail or upload a resume to run the recruiter screen.
                  </p>
                ) : null}
              </div>
            </div>
          </section>
            </>
          )}

          <section className="grid gap-4 sm:grid-cols-2">
            <Link href="/assessments" className="rounded-[28px] bg-primary px-6 py-5 text-sm font-black uppercase tracking-[0.18em] text-white">
              Take assessments to improve score
            </Link>
            <Link href="/career-aim" className="rounded-[28px] bg-surface-container-high px-6 py-5 text-sm font-black uppercase tracking-[0.18em] text-on-surface">
              Analyze career aim
            </Link>
          </section>

          <SubjectProgressCards subjects={subjectProgress} />

          {assessmentLogs.length > 0 && (
            <Motion.section
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
              className="clay-card rounded-[32px] p-7 mt-8"
            >
              <h2 className="text-sm font-black uppercase tracking-[0.2em] text-on-surface-variant mb-6">Exam Analytics History</h2>
              <div className="space-y-4">
                {assessmentLogs.map((log) => (
                  <AssessmentLogCard key={log.id} log={log} />
                ))}
              </div>
            </Motion.section>
          )}
        </>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-3xl bg-surface-container-low px-5 py-4 border border-outline-variant/10 shadow-sm transition hover:shadow-md">
      <p className="text-[10px] font-black uppercase tracking-[0.2em] text-on-surface-variant">{label}</p>
      <p className="mt-2 truncate text-sm font-black text-on-surface">{value}</p>
    </div>
  );
}

function ProfileOnlyInsightPrompt() {
  return (
    <section className="rounded-[34px] border border-dashed border-primary/25 bg-primary/5 p-7">
      <p className="text-[10px] font-black uppercase tracking-[0.22em] text-primary">Insights need more evidence</p>
      <h2 className="mt-2 text-2xl font-black tracking-tight text-on-surface">Add more about yourself and explore assessments to see insights</h2>
      <p className="mt-2 max-w-3xl text-sm font-semibold leading-6 text-on-surface-variant">
        CELTM has analyzed your profile links, but there is not enough resume, assessment, written, or credential evidence to generate trustworthy keyword, red-flag, and career-readiness insights yet.
      </p>
      <div className="mt-5 flex flex-col gap-3 sm:flex-row">
        <Link
          href="/settings"
          className="rounded-2xl bg-surface px-5 py-3 text-center text-[11px] font-black uppercase tracking-[0.18em] text-primary"
        >
          Add more about yourself
        </Link>
        <Link
          href="/assessments"
          className="rounded-2xl bg-primary px-5 py-3 text-center text-[11px] font-black uppercase tracking-[0.18em] text-white"
        >
          Explore assessments
        </Link>
      </div>
    </section>
  );
}

function AssessmentLogCard({ log }: { log: AssessmentLog }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-3xl border border-outline-variant/20 bg-surface shadow-sm transition hover:shadow-md overflow-hidden">
      <div
        className="p-5 cursor-pointer flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-surface-container-lowest transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div>
          <div className="flex items-center gap-3">
            <span className="inline-flex rounded-full bg-primary/10 px-3 py-1 text-[10px] font-black uppercase tracking-widest text-primary">
              {log.type}
            </span>
            <span className="text-xs font-bold text-on-surface-variant">
              {log.completed_at ? new Date(log.completed_at).toLocaleDateString() : "Pending"}
            </span>
          </div>
          <h3 className="mt-3 text-lg font-black text-on-surface capitalize">{log.subject.replace(/_/g, " ")}</h3>
          <p className="mt-1 text-sm text-on-surface-variant line-clamp-2">{log.insight}</p>
        </div>
        <div className="flex items-center gap-6">
          <div className="flex-shrink-0 text-right sm:text-center">
            <div className="inline-flex items-center justify-center h-16 w-16 rounded-full border-[4px] border-emerald-500/30">
              <span className="text-xl font-black text-emerald-600 dark:text-emerald-400">{Math.round(log.score)}</span>
            </div>
            <div className="mt-2 text-[10px] font-black uppercase tracking-widest text-on-surface-variant">Score</div>
          </div>
          <AppIcon name="expand_more" className={`h-5 w-5 transition-transform duration-300 ${expanded ? "rotate-180" : ""}`} />
        </div>
      </div>

      <AnimatePresence>
        {expanded && (
          <Motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="border-t border-outline-variant/15 bg-surface-container-lowest"
          >
            <div className="p-6 grid gap-6 md:grid-cols-2">
              <div className="space-y-4">
                {log.analytics && typeof log.analytics.total === "number" && log.analytics.total > 0 && (
                  <div className="grid grid-cols-3 gap-2">
                    <div className="rounded-2xl bg-emerald-500/10 p-3 text-center">
                      <span className="block text-2xl font-black text-emerald-600">{log.analytics.correct ?? 0}</span>
                      <span className="text-[10px] uppercase tracking-wider text-emerald-600/70 font-bold">Correct</span>
                    </div>
                    <div className="rounded-2xl bg-red-500/10 p-3 text-center">
                      <span className="block text-2xl font-black text-red-500">{log.analytics.wrong ?? 0}</span>
                      <span className="text-[10px] uppercase tracking-wider text-red-500/70 font-bold">Wrong</span>
                    </div>
                    <div className="rounded-2xl bg-surface-container-high p-3 text-center">
                      <span className="block text-2xl font-black text-on-surface">{log.analytics.total ?? 0}</span>
                      <span className="text-[10px] uppercase tracking-wider text-on-surface-variant font-bold">Total</span>
                    </div>
                  </div>
                )}

                {log.areas_of_betterment && log.areas_of_betterment.length > 0 && (
                  <div>
                    <h4 className="text-xs font-black uppercase tracking-widest text-red-400 mb-2">Areas for Betterment</h4>
                    <ul className="space-y-1">
                      {log.areas_of_betterment.map((area, i) => (
                        <li key={i} className="text-sm flex items-start gap-2 text-on-surface-variant">
                          <AppIcon name="warning" className="mt-0.5 h-4 w-4 shrink-0 text-red-400" />
                          {area}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>

              <div>
                {log.hidden_skills && log.hidden_skills.length > 0 && (
                  <div>
                    <h4 className="text-xs font-black uppercase tracking-widest text-primary mb-3">Hidden Skills Unlocked</h4>
                    <div className="flex flex-wrap gap-2">
                      {log.hidden_skills.map((skill, i) => (
                        <span key={i} className="inline-flex items-center gap-1 rounded-full bg-primary/10 border border-primary/20 px-3 py-1.5 text-xs font-bold text-primary">
                          <AppIcon name="psychology" className="h-3.5 w-3.5" />
                          {skill}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                <div className="mt-6">
                  <button
                    onClick={async (e) => {
                      e.stopPropagation();
                      try {
                        const blob = await apiFetchBlob(`/reports/assessment/${log.id}.pdf`);
                        const url = window.URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = `assessment-report-${log.id}.pdf`;
                        document.body.appendChild(a);
                        a.click();
                        window.URL.revokeObjectURL(url);
                        document.body.removeChild(a);
                      } catch {
                        alert("Failed to download assessment report.");
                      }
                    }}
                    className="inline-flex items-center gap-2 rounded-xl bg-primary px-5 py-2.5 text-xs font-black uppercase tracking-widest text-white transition hover:-translate-y-0.5 hover:shadow-lg"
                  >
                    <AppIcon name="download" className="h-4 w-4" />
                    Download Detailed Report
                  </button>
                </div>
              </div>
            </div>
          </Motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
