"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import type { AssessmentAssignmentRead, AssessmentLogEntry, DashboardSummary, SubjectDetail } from "@/lib/celtm";
import { formatDateTime } from "@/lib/celtm";
import { buildAssessmentQuizHref, buildWrittenAssessmentHref } from "@/lib/assessmentLinks";
import AppIcon from "@/components/AppIcon";
import CeltmProgressLoader from "@/components/CeltmProgressLoader";
import { motion as Motion, AnimatePresence } from "framer-motion";

export default function AssessmentsHubPage() {
  const [subjects, setSubjects] = useState<SubjectDetail[]>([]);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [logs, setLogs] = useState<AssessmentLogEntry[]>([]);
  const [assignments, setAssignments] = useState<AssessmentAssignmentRead[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all([
      apiFetch<SubjectDetail[]>("/assessments/subjects"),
      apiFetch<DashboardSummary>("/dashboard/summary"),
      apiFetch<AssessmentLogEntry[]>("/assessments/log"),
      apiFetch<AssessmentAssignmentRead[]>("/assessments/assignments").catch(() => []),
    ])
      .then(([subjectPayload, summaryPayload, logPayload, assignmentPayload]) => {
        if (!active) return;
        setSubjects(subjectPayload);
        setSummary(summaryPayload);
        setLogs(logPayload);
        setAssignments(assignmentPayload);
      })
      .catch((caught) => {
        if (active) setError(caught instanceof Error ? caught.message : "Failed to load assessments.");
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  if (isLoading) {
    return (
      <CeltmProgressLoader
        title="Loading assessments"
        caption="Cooking your assessment map"
        minHeightClassName="min-h-[70vh]"
        stages={["Fetching subjects", "Checking assigned tests", "Reading recent attempts", "Preparing assessment cards"]}
      />
    );
  }

  return (
    <div className="mx-auto w-full max-w-[1320px] space-y-8 pb-12">
      {error ? <div className="rounded-3xl bg-red-500/10 px-5 py-4 text-sm font-bold text-red-500">{error}</div> : null}

      <section className="clay-card rounded-[36px] p-8 md:p-10">
        <div className="grid gap-8 lg:grid-cols-[1fr_360px] lg:items-center">
          <div>
            <p className="text-[11px] font-black uppercase tracking-[0.24em] text-primary">CELTMap Assessment Engine</p>
            <h1 className="mt-3 text-4xl font-black tracking-tight text-on-surface md:text-5xl">Subject-specific assessment practice</h1>
            <p className="mt-4 max-w-3xl text-lg leading-8 text-on-surface-variant">
              Pick the exact subject you want to improve. MCQ, situational, and written tracks now use the live subject bank directly, so progress stays pinpoint instead of broad.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link href="/assessments/quiz?mode=quick" className="rounded-full bg-primary px-6 py-3 text-[11px] font-black uppercase tracking-[0.18em] text-white">
                Start quick assessment
              </Link>
              <Link href="/assessments/quiz?mode=standard" className="rounded-full bg-surface-container-high px-6 py-3 text-[11px] font-black uppercase tracking-[0.18em] text-on-surface">
                Standard
              </Link>
              <Link href="/assessments/quiz?mode=deep" className="rounded-full bg-surface-container-high px-6 py-3 text-[11px] font-black uppercase tracking-[0.18em] text-on-surface">
                Deep
              </Link>
            </div>
          </div>
          <div className="rounded-[32px] bg-surface-container-low p-7 text-center">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-on-surface-variant">Current readiness</p>
            <p className="mt-4 text-5xl font-black text-primary sm:text-6xl">{Math.round(summary?.readiness_score ?? 0)}%</p>
            <p className="mt-3 text-sm leading-6 text-on-surface-variant">
              Resume analysis, objective assessments, written work, and credentials. New completed evidence updates this score immediately.
            </p>
          </div>
        </div>
      </section>

      <section className="clay-card rounded-[32px] p-7">
        <div className="mb-5 flex items-center justify-between gap-4">
          <div>
            <h2 className="text-2xl font-black tracking-tight text-on-surface">Assigned tests</h2>
            <p className="mt-1 text-sm text-on-surface-variant">
              Department-scheduled assessments with fixed date, time, and duration.
            </p>
          </div>
          <span className="rounded-full bg-primary/10 px-3 py-1 text-[10px] font-black uppercase tracking-[0.18em] text-primary">
            {assignments.length} scheduled
          </span>
        </div>
        {assignments.length ? (
          <div className="grid gap-4 lg:grid-cols-2">
            {assignments.map((assignment) => {
              const params = new URLSearchParams({
                assignmentId: assignment.id,
                title: assignment.title,
                duration: String(assignment.duration_minutes),
              });
              const isCompleted = assignment.attempt_status === "completed";
              const isTerminated = Boolean(assignment.terminated || assignment.status === "terminated");
              const isMissed = Boolean(assignment.missed);
              const assignmentHref = assignment.question_type === "DESCRIPTIVE"
                ? `/assessments/written-protocol?${params.toString()}`
                : `/assessments/quiz?${params.toString()}`;
              const statusText = isCompleted
                ? `Completed ${Math.round(assignment.attempt_score ?? 0)}%`
                : isTerminated
                  ? "Terminated"
                  : isMissed
                    ? "Not attended"
                    : assignment.is_upcoming
                      ? "Upcoming"
                      : assignment.is_expired
                        ? "Closed"
                        : "Open now";
              return (
                <article key={assignment.id} className="rounded-[28px] border border-outline-variant/15 bg-surface-container-low p-5">
                  <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                    <div>
                      <p className="text-[10px] font-black uppercase tracking-[0.18em] text-primary">
                        {assignment.question_type} - {assignment.mode}
                      </p>
                      <h3 className="mt-2 text-xl font-black text-on-surface">{assignment.title}</h3>
                      <p className="mt-2 text-sm leading-6 text-on-surface-variant">
                        {assignment.category} - {formatDateTime(assignment.starts_at)} to {formatDateTime(assignment.ends_at)} - {assignment.duration_minutes} minutes
                      </p>
                      {assignment.question_count ? (
                        <p className="mt-1 text-xs font-bold text-on-surface-variant">
                          {assignment.question_count} fixed questions
                        </p>
                      ) : null}
                      {assignment.instructions ? (
                        <p className="mt-2 text-sm leading-6 text-on-surface-variant">{assignment.instructions}</p>
                      ) : null}
                    </div>
                    <div className="text-left md:text-right">
                      <p className={`text-xs font-bold ${
                        isTerminated || isMissed ? "text-error" : "text-on-surface-variant"
                      }`}>
                        {statusText}
                      </p>
                      <Link
                        href={assignmentHref}
                        aria-disabled={(!assignment.can_start && !assignment.attempt_id) || (!isCompleted && (isTerminated || isMissed))}
                        className={`mt-3 inline-flex rounded-full px-5 py-3 text-[10px] font-black uppercase tracking-[0.18em] transition ${
                          (assignment.can_start || assignment.attempt_id) && (isCompleted || (!isTerminated && !isMissed))
                            ? "bg-primary text-white hover:opacity-90"
                            : "pointer-events-none bg-surface-container-high text-on-surface-variant opacity-60"
                        }`}
                      >
                        {isCompleted ? "View result" : assignment.attempt_id ? "Resume" : "Begin test"}
                      </Link>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        ) : (
          <p className="rounded-3xl bg-surface-container-low px-5 py-5 text-sm text-on-surface-variant">
            No department tests have been assigned yet.
          </p>
        )}
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {subjects.map((subject) => {
          const subjectLink = `/assessments/${subject.key}`;
          const canMcq = subject.availability?.mcq ?? subject.is_available;
          const canSituational = subject.availability?.situational ?? false;
          const canWritten = subject.availability?.written ?? false;
          const linkSubject = {
            title: subject.title,
            skillId: subject.skill_id,
            skillRequestId: subject.skill_request_id,
          };

          return (
          <article key={subject.key} className="clay-card flex min-h-[21rem] flex-col rounded-[30px] p-6 transition hover:-translate-y-1 hover:border-primary/20">
            <div className="flex items-start justify-between gap-4">
              <div>
                <Link href={subjectLink} className="text-xl font-black tracking-tight text-on-surface transition hover:text-primary">
                  {subject.title}
                </Link>
                <p className="mt-2 text-sm leading-6 text-on-surface-variant">{subject.description}</p>
              </div>
              <span className="rounded-full bg-primary/10 px-3 py-1 text-[10px] font-black text-primary">
                {subject.current_score == null ? "New" : `${Math.round(subject.current_score)}%`}
              </span>
            </div>
            <div className="mt-5 h-2 rounded-full bg-surface-container-high">
              <div className="h-2 rounded-full bg-primary" style={{ width: `${Math.min(100, subject.current_score ?? 0)}%` }} />
            </div>
            <div className="mt-5 grid grid-cols-3 gap-2 text-center text-[10px] font-black uppercase tracking-[0.14em] text-on-surface-variant">
              <span className="rounded-2xl bg-surface-container-low px-2 py-2">MCQ {subject.mcq_count ?? 0}</span>
              <span className="rounded-2xl bg-surface-container-low px-2 py-2">SIT {subject.situational_count ?? 0}</span>
              <span className="rounded-2xl bg-surface-container-low px-2 py-2">WR {subject.written_count ?? 0}</span>
            </div>
            {subject.is_available ? (
              <div className="mt-auto grid gap-2 pt-5">
                <Link
                  href={buildAssessmentQuizHref(linkSubject, "MCQ")}
                  aria-disabled={!canMcq}
                  className={`rounded-2xl px-4 py-3 text-center text-[10px] font-black uppercase tracking-[0.18em] transition ${
                    canMcq ? "bg-primary text-white hover:opacity-90" : "pointer-events-none bg-surface-container-high text-on-surface-variant opacity-50"
                  }`}
                >
                  Attempt MCQ
                </Link>
                <div className="grid grid-cols-2 gap-2">
                  <Link
                    href={buildAssessmentQuizHref(linkSubject, "SITUATIONAL")}
                    aria-disabled={!canSituational}
                    className={`rounded-2xl px-3 py-3 text-center text-[10px] font-black uppercase tracking-[0.14em] transition ${
                      canSituational ? "bg-surface-container-high text-on-surface hover:bg-surface-container-highest" : "pointer-events-none bg-surface-container-high text-on-surface-variant opacity-50"
                    }`}
                  >
                    Situational
                  </Link>
                  <Link
                    href={buildWrittenAssessmentHref(linkSubject)}
                    aria-disabled={!canWritten}
                    className={`rounded-2xl px-3 py-3 text-center text-[10px] font-black uppercase tracking-[0.14em] transition ${
                      canWritten ? "bg-surface-container-high text-on-surface hover:bg-surface-container-highest" : "pointer-events-none bg-surface-container-high text-on-surface-variant opacity-50"
                    }`}
                  >
                    Written
                  </Link>
                </div>
                <Link href={subjectLink} className="text-center text-[10px] font-black uppercase tracking-[0.18em] text-primary">
                  View subject details
                </Link>
              </div>
            ) : (
              <div className="mt-auto rounded-3xl border border-dashed border-outline-variant/20 bg-surface-container-low px-4 py-4 text-sm font-semibold text-on-surface-variant">
                Subject not available at the moment.
              </div>
            )}
          </article>
        )})}
      </section>

      <Motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="clay-card rounded-[32px] p-7"
      >
        <h2 className="text-2xl font-black tracking-tight text-on-surface">Recent attempts</h2>
        <div className="mt-5 space-y-4">
          {logs.length ? logs.map((entry) => (
            <AssessmentLogCard key={entry.id} log={entry} />
          )) : (
            <p className="rounded-3xl bg-surface-container-low px-5 py-5 text-sm text-on-surface-variant">
              No assessment attempt yet.
            </p>
          )}
        </div>
      </Motion.section>
    </div>
  );
}

function AssessmentLogCard({ log }: { log: AssessmentLogEntry }) {
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
              <span className="text-xl font-black text-emerald-600 dark:text-emerald-400">{Math.round(log.score ?? 0)}</span>
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
              </div>
            </div>
          </Motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
