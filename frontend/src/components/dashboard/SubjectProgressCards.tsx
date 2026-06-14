"use client";

import { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import type { SubjectProgress } from "@/lib/celtm";
import { formatDate, formatPercent } from "@/lib/celtm";

function trendTone(trend: string) {
  const normalized = trend.toLowerCase();
  if (normalized.includes("improving")) return "text-emerald-600 bg-emerald-500/10";
  if (normalized.includes("declining")) return "text-red-600 bg-red-500/10";
  if (normalized.includes("stable")) return "text-amber-600 bg-amber-500/10";
  return "text-primary bg-primary/10";
}

function signedPercent(value: number) {
  const rounded = Math.round(value);
  return `${rounded > 0 ? "+" : ""}${rounded}%`;
}

export function SubjectProgressCards({
  subjects,
  title = "Assessment improvement",
  description = "Subject-wise progress from repeated objective and written attempts.",
}: {
  subjects: SubjectProgress[];
  title?: string;
  description?: string;
}) {
  const [selected, setSelected] = useState<SubjectProgress | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!subjects.length) {
    return null;
  }

  return (
    <section className="clay-card rounded-[32px] p-7">
      <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
        <div>
          <h2 className="text-sm font-black uppercase tracking-[0.2em] text-on-surface-variant">{title}</h2>
          <p className="mt-2 text-sm leading-6 text-on-surface-variant">{description}</p>
        </div>
        <span className="rounded-full bg-primary/10 px-3 py-1 text-[10px] font-black uppercase tracking-[0.18em] text-primary">
          {subjects.length} subjects
        </span>
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {subjects.map((subject) => (
          <button
            key={subject.subject_key}
            type="button"
            onClick={() => setSelected(subject)}
            className="rounded-[28px] border border-outline-variant/15 bg-surface p-5 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-lg"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-lg font-black text-on-surface">{subject.subject}</p>
                <p className="mt-1 text-xs font-bold text-on-surface-variant">
                  {subject.attempt_count} attempts - last {formatDate(subject.last_completed_at)}
                </p>
              </div>
              <span className={`rounded-full px-3 py-1 text-[10px] font-black uppercase tracking-widest ${trendTone(subject.trend)}`}>
                {subject.trend}
              </span>
            </div>

            <div className="mt-5 grid grid-cols-3 gap-3">
              <Metric label="Latest" value={formatPercent(subject.latest_score)} />
              <Metric label="Best" value={formatPercent(subject.best_score)} />
              <Metric
                label="Change"
                value={signedPercent(subject.improvement)}
                tone={subject.improvement >= 0 ? "text-emerald-600" : "text-red-600"}
              />
            </div>

            <div className="mt-4 h-2 overflow-hidden rounded-full bg-surface-container-high">
              <div className="h-full rounded-full bg-primary" style={{ width: `${Math.min(100, Math.max(0, subject.latest_score))}%` }} />
            </div>
            <p className="mt-3 line-clamp-2 text-xs font-semibold leading-5 text-on-surface-variant">
              {subject.next_action || "Open for detailed attempt history and next action."}
            </p>
          </button>
        ))}
      </div>

      {selected && mounted ? createPortal(
        <div className="fixed inset-0 z-[120] flex bg-surface">
          <div className="h-full w-full overflow-y-auto p-8 md:p-12 lg:p-16">
            <div className="mx-auto max-w-7xl">
              <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                <div>
                  <p className="text-[10px] font-black uppercase tracking-[0.22em] text-primary">Subject progress</p>
                  <h3 className="mt-2 text-4xl font-black text-on-surface">{selected.subject}</h3>
                  <p className="mt-3 text-base font-semibold leading-7 text-on-surface-variant max-w-2xl">
                    {selected.next_action}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setSelected(null)}
                  className="rounded-full bg-surface-container-high px-6 py-3 text-sm font-bold text-on-surface transition-colors hover:bg-surface-container-highest flex-shrink-0"
                >
                  Close Report
                </button>
              </div>

            <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
              <Metric label="First" value={formatPercent(selected.first_score)} />
              <Metric label="Latest" value={formatPercent(selected.latest_score)} />
              <Metric label="Average" value={formatPercent(selected.average_score)} />
              <Metric label="Best" value={formatPercent(selected.best_score)} />
              <Metric
                label="Growth"
                value={signedPercent(selected.improvement)}
                tone={selected.improvement >= 0 ? "text-emerald-600" : "text-red-600"}
              />
            </div>

            <div className="mt-6 grid gap-5 lg:grid-cols-[1.4fr_1fr]">
              <div className="rounded-3xl bg-surface p-5">
                <h4 className="text-xs font-black uppercase tracking-widest text-on-surface-variant">Recent attempts</h4>
                <div className="mt-4 space-y-3">
                  {selected.recent_attempts.map((attempt) => (
                    <div key={attempt.id} className="rounded-2xl bg-surface-container-low px-4 py-3">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <p className="text-sm font-black uppercase tracking-wide text-on-surface">{attempt.type}</p>
                          <p className="text-xs font-semibold text-on-surface-variant">{formatDate(attempt.completed_at)}</p>
                        </div>
                        <div className="flex items-center gap-3">
                          {attempt.delta_from_previous != null ? (
                            <span className={`text-xs font-black ${attempt.delta_from_previous >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                              {signedPercent(attempt.delta_from_previous)}
                            </span>
                          ) : null}
                          <span className="text-2xl font-black text-primary">{formatPercent(attempt.score)}</span>
                        </div>
                      </div>
                      {attempt.total != null ? (
                        <p className="mt-2 text-xs font-semibold text-on-surface-variant">
                          {attempt.correct ?? 0} correct, {attempt.wrong ?? 0} wrong, {attempt.total} total
                        </p>
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>

              <div className="space-y-4">
                <InsightList title="Strong subject evidence" items={selected.strong_dimensions} fallback="No strong subject evidence recorded yet." />
                <InsightList title="Subject repair focus" items={selected.weak_dimensions} fallback="No subject repair focus recorded yet." />
                <div className="rounded-3xl bg-primary/5 p-5">
                  <p className="text-xs font-black uppercase tracking-widest text-primary">Attempt mix</p>
                  <p className="mt-3 text-sm font-semibold leading-6 text-on-surface-variant">
                    {selected.objective_attempt_count} objective attempts and {selected.written_attempt_count} written attempts are included in this subject trend.
                  </p>
                </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      , document.body) : null}
    </section>
  );
}

function Metric({ label, value, tone = "text-on-surface" }: { label: string; value: string; tone?: string }) {
  return (
    <div className="rounded-2xl bg-surface-container-low px-4 py-3">
      <p className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant">{label}</p>
      <p className={`mt-1 text-lg font-black ${tone}`}>{value}</p>
    </div>
  );
}

function InsightList({ title, items, fallback }: { title: string; items?: string[]; fallback: string }) {
  const values = items?.length ? items : [fallback];
  return (
    <div className="rounded-3xl bg-surface p-5">
      <p className="text-xs font-black uppercase tracking-widest text-on-surface-variant">{title}</p>
      <ul className="mt-3 space-y-2">
        {values.map((item) => (
          <li key={item} className="text-sm font-semibold leading-6 text-on-surface-variant">
            - {item}
          </li>
        ))}
      </ul>
    </div>
  );
}
