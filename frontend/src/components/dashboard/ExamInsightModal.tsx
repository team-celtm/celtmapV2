"use client";

import { useState } from "react";
import type { AssessmentLogEntry, MCQDetailedFeedback } from "@/lib/celtm";
import { formatDate, formatPercent } from "@/lib/celtm";

interface ExamInsightModalProps {
  entry: AssessmentLogEntry | null;
  onClose: () => void;
}

function hasItems(items: string[] | undefined): items is string[] {
  return Array.isArray(items) && items.length > 0;
}

type Tab = "overview" | "questions";

export function ExamInsightModal({ entry, onClose }: ExamInsightModalProps) {
  const [tab, setTab] = useState<Tab>("overview");

  if (!entry) return null;

  const feedback = entry.feedback || entry.insight || "Evaluation details are still being prepared.";
  const strengths = hasItems(entry.strengths) ? entry.strengths : [];
  const risks = hasItems(entry.risks) ? entry.risks : [];
  const recommendations = hasItems(entry.recommendations) ? entry.recommendations : [];
  const plagiarism = entry.plagiarism;
  const questions: MCQDetailedFeedback[] = entry.detailed_feedback ?? [];
  const hasQuestions = questions.length > 0;

  const correctCount = questions.filter((q) => q.is_correct).length;
  const wrongCount = questions.length - correctCount;
  const correctPct = questions.length ? Math.round((correctCount / questions.length) * 100) : 0;

  const tabs: { key: Tab; label: string; show: boolean }[] = [
    { key: "overview", label: "Overview", show: true },
    { key: "questions", label: `Question Analysis (${questions.length})`, show: hasQuestions },
  ];

  return (
    <div className="fixed inset-0 z-[75] flex items-center justify-center bg-black/60 px-4 backdrop-blur-sm">
      <div className="max-h-[90vh] w-full max-w-4xl overflow-y-auto rounded-[40px] border border-outline-variant/12 dark:border-transparent bg-surface-container p-8 shadow-3xl md:p-10">
        {/* Header */}
        <div className="flex items-start justify-between gap-6">
          <div className="flex-1">
            <div className="flex flex-wrap items-center gap-3">
              <span
                className={`rounded-full px-3 py-1 text-[10px] font-black uppercase tracking-widest ${
                  entry.type === "mcq"
                    ? "bg-blue-500/10 text-blue-500"
                    : entry.type === "situational"
                      ? "bg-teal-500/10 text-teal-500"
                      : entry.type === "written"
                        ? "bg-purple-500/10 text-purple-500"
                        : "bg-amber-500/10 text-amber-500"
                }`}
              >
                {entry.type} evaluation
              </span>
              <span className="text-[11px] font-medium text-on-surface-variant">
                {formatDate(entry.completed_at)}
              </span>
            </div>
            <h3 className="mt-4 text-3xl font-extrabold leading-tight tracking-tight text-on-surface">
              {entry.subject}
            </h3>
            {entry.role_name ? (
              <p className="mt-2 text-sm text-on-surface-variant">
                Role-fit snapshot: {entry.role_name}
              </p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="flex h-10 w-10 items-center justify-center rounded-full border border-outline-variant/20 bg-surface-container-high transition hover:bg-surface-container-highest"
            aria-label="Close exam insight modal"
          >
            <span className="text-xl">&times;</span>
          </button>
        </div>

        {/* Score strip */}
        <div className="mt-8 grid gap-4 md:grid-cols-3">
          <div className="rounded-3xl bg-surface p-5 shadow-inner ring-1 ring-outline-variant/5">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-on-surface-variant">Performance</p>
            <div className="mt-3 flex items-baseline gap-2">
              <span className="text-5xl font-extrabold tracking-tighter text-on-surface">
                {entry.score !== null ? formatPercent(entry.score) : "--"}
              </span>
              <span className="text-xs font-black uppercase tracking-widest text-primary">Score</span>
            </div>
          </div>
          <div className="rounded-3xl bg-surface p-5 shadow-inner ring-1 ring-outline-variant/5">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-on-surface-variant">Status</p>
            <div className="mt-3 flex items-center gap-3">
              <span className={`h-3 w-3 rounded-full ${entry.status === "completed" ? "bg-green-500" : "bg-amber-500"}`} />
              <p className="text-lg font-bold uppercase tracking-tight text-on-surface">{entry.status}</p>
            </div>
          </div>
          <div className="rounded-3xl bg-surface p-5 shadow-inner ring-1 ring-outline-variant/5">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-on-surface-variant">Readiness</p>
            <div className="mt-3 flex items-baseline gap-2">
              <span className="text-5xl font-extrabold tracking-tighter text-on-surface">
                {entry.readiness_score != null ? formatPercent(entry.readiness_score) : "--"}
              </span>
              <span className="text-xs font-black uppercase tracking-widest text-primary">Live</span>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="mt-8 flex gap-2 border-b border-outline-variant/10 pb-0">
          {tabs.filter((t) => t.show).map((t) => (
            <button
              key={t.key}
              type="button"
              onClick={() => setTab(t.key)}
              className={`px-5 py-2.5 text-[11px] font-black uppercase tracking-[0.18em] rounded-t-2xl transition-all ${
                tab === t.key
                  ? "bg-primary text-white"
                  : "text-on-surface-variant hover:text-on-surface"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* ── Overview Tab ──────────────────────────────────────────────────── */}
        {tab === "overview" && (
          <div className="mt-8 space-y-6">
            <div className="rounded-3xl bg-primary/5 p-6 md:p-8">
              <h4 className="text-[11px] font-black uppercase tracking-[0.2em] text-primary">
                Evaluator feedback
              </h4>
              <p className="mt-4 text-base leading-relaxed text-on-surface-variant font-medium">{feedback}</p>
            </div>

            <div className="grid gap-6 md:grid-cols-3">
              <div className="rounded-[32px] bg-green-500/[0.03] p-6 ring-1 ring-green-500/10">
                <h5 className="flex items-center gap-2 text-[10px] font-black uppercase tracking-widest text-green-600">
                  <span className="h-1.5 w-1.5 rounded-full bg-green-500" />
                  Key Strengths
                </h5>
                <ul className="mt-4 space-y-2.5">
                  {(strengths.length > 0 ? strengths : ["Demonstrated core competency"]).map((s, i) => (
                    <li key={i} className="text-xs font-semibold leading-relaxed text-on-surface-variant flex items-start gap-2">
                      <span className="mt-1 text-green-500">•</span>
                      {s}
                    </li>
                  ))}
                </ul>
              </div>

              <div className="rounded-[32px] bg-rose-500/[0.03] p-6 ring-1 ring-rose-500/10">
                <h5 className="flex items-center gap-2 text-[10px] font-black uppercase tracking-widest text-rose-600">
                  <span className="h-1.5 w-1.5 rounded-full bg-rose-500" />
                  Knowledge Gaps
                </h5>
                <ul className="mt-4 space-y-2.5">
                  {(risks.length > 0 ? risks : ["Minor concept refinement needed"]).map((r, i) => (
                    <li key={i} className="text-xs font-semibold leading-relaxed text-on-surface-variant flex items-start gap-2">
                      <span className="mt-1 text-rose-500">•</span>
                      {r}
                    </li>
                  ))}
                </ul>
              </div>

              <div className="rounded-[32px] bg-primary/[0.03] p-6 ring-1 ring-primary/10">
                <h5 className="flex items-center gap-2 text-[10px] font-black uppercase tracking-widest text-primary">
                  <span className="h-1.5 w-1.5 rounded-full bg-primary" />
                  Next Optimization
                </h5>
                <ul className="mt-4 space-y-2.5">
                  {(recommendations.length > 0 ? recommendations : ["Continue standard path"]).map((rec, i) => (
                    <li key={i} className="text-xs font-semibold leading-relaxed text-on-surface-variant flex items-start gap-2">
                      <span className="mt-1 text-primary">•</span>
                      {rec}
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            {plagiarism ? (
              <div className="rounded-3xl border border-rose-500/15 bg-rose-500/5 p-6">
                <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                  <div>
                    <p className="text-[10px] font-black uppercase tracking-[0.2em] text-rose-500">Plagiarism risk</p>
                    <p className="mt-3 text-base leading-7 text-on-surface-variant">{plagiarism.summary}</p>
                  </div>
                  <div className="rounded-2xl bg-surface px-4 py-3 text-center shadow-inner ring-1 ring-outline-variant/5">
                    <p className="text-[10px] font-black uppercase tracking-[0.2em] text-on-surface-variant">Risk level</p>
                    <p className="mt-2 text-lg font-extrabold uppercase tracking-tight text-on-surface">{plagiarism.risk_level}</p>
                    <p className="mt-1 text-sm font-semibold text-rose-500">{formatPercent(plagiarism.risk_score)}</p>
                  </div>
                </div>
                {plagiarism.signals.length > 0 ? (
                  <ul className="mt-4 space-y-2 text-sm leading-6 text-on-surface-variant">
                    {plagiarism.signals.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                ) : null}
              </div>
            ) : null}
          </div>
        )}

        {/* ── Question Analysis Tab ─────────────────────────────────────────── */}
        {tab === "questions" && hasQuestions && (
          <div className="mt-8 space-y-6">
            {/* Summary bar */}
            <div className="rounded-3xl bg-surface-container-low p-5">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div className="flex items-center gap-6">
                  <div className="text-center">
                    <p className="text-3xl font-extrabold text-green-500">{correctCount}</p>
                    <p className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant">Correct</p>
                  </div>
                  <div className="h-10 w-px bg-outline-variant/20" />
                  <div className="text-center">
                    <p className="text-3xl font-extrabold text-rose-500">{wrongCount}</p>
                    <p className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant">Incorrect</p>
                  </div>
                  <div className="h-10 w-px bg-outline-variant/20" />
                  <div className="text-center">
                    <p className="text-3xl font-extrabold text-on-surface">{questions.length}</p>
                    <p className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant">Total</p>
                  </div>
                </div>

                {/* Accuracy bar */}
                <div className="flex-1 min-w-[180px]">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant">Accuracy</span>
                    <span className="text-sm font-extrabold text-on-surface">{correctPct}%</span>
                  </div>
                  <div className="h-2.5 rounded-full bg-surface-container-highest overflow-hidden">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-green-500 to-primary transition-all duration-700"
                      style={{ width: `${correctPct}%` }}
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* Per-question cards */}
            <div className="space-y-4">
              {questions.map((item, idx) => (
                <div
                  key={item.question_id || idx}
                  className={`rounded-3xl border p-5 transition-all md:p-6 ${
                    item.is_correct
                      ? "border-green-500/15 bg-green-500/[0.03]"
                      : "border-rose-500/15 bg-rose-500/[0.03]"
                  }`}
                >
                  {/* Question header */}
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-center gap-3">
                      <div
                        className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-extrabold ${
                          item.is_correct
                            ? "bg-green-500/15 text-green-600"
                            : "bg-rose-500/15 text-rose-600"
                        }`}
                      >
                        {idx + 1}
                      </div>
                      <span
                        className={`rounded-full px-2.5 py-0.5 text-[9px] font-black uppercase tracking-widest ${
                          item.is_correct
                            ? "bg-green-500/10 text-green-600"
                            : "bg-rose-500/10 text-rose-600"
                        }`}
                      >
                        {item.is_correct ? "✓ Correct" : "✗ Incorrect"}
                      </span>
                      <span className="rounded-full bg-surface-container-highest px-2 py-0.5 text-[9px] font-black uppercase tracking-wider text-on-surface-variant">
                        {item.category}
                      </span>
                    </div>
                  </div>

                  {/* Question text */}
                  <p className="mt-3 text-sm font-bold leading-snug text-on-surface">
                    {item.question_text}
                  </p>

                  {/* Answer comparison */}
                  <div className="mt-4 grid grid-cols-1 gap-3 rounded-2xl bg-surface-container-low p-4 md:grid-cols-2">
                    <div>
                      <p className="text-[9px] font-black uppercase tracking-widest text-on-surface-variant">Your Answer</p>
                      <p className={`mt-1.5 text-sm font-semibold ${item.is_correct ? "text-green-600" : "text-rose-600"}`}>
                        {item.selected_option}
                      </p>
                    </div>
                    {!item.is_correct && (
                      <div>
                        <p className="text-[9px] font-black uppercase tracking-widest text-on-surface-variant">Correct Answer</p>
                        <p className="mt-1.5 text-sm font-semibold text-green-600">
                          {item.correct_option}
                        </p>
                      </div>
                    )}
                  </div>

                  {/* Personalised insight */}
                  <div className="mt-4 flex gap-3 rounded-2xl bg-primary/5 px-4 py-3">
                    <svg className="mt-0.5 h-4 w-4 shrink-0 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <p className="text-xs leading-relaxed text-on-surface-variant">
                      {item.personalized_insight}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="mt-10 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="rounded-full bg-surface-container-highest px-8 py-3 text-[11px] font-black uppercase tracking-[0.2em] text-on-surface transition hover:opacity-80"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
