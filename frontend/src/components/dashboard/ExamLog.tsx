"use client";

import { useEffect, useEffectEvent, useState } from "react";
import Link from "next/link";
import { apiFetch, getApiErrorMessage } from "@/lib/api";
import { AssessmentLogEntry, formatDate, formatPercent } from "@/lib/celtm";

interface ExamLogProps {
  onEntryClick?: (entry: AssessmentLogEntry) => void;
}

export function ExamLog({ onEntryClick }: ExamLogProps) {
  const [entries, setEntries] = useState<AssessmentLogEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchLog = useEffectEvent(async (background = false) => {
    try {
      if (!background) {
        setIsLoading(true);
      }
      const data = await apiFetch<AssessmentLogEntry[]>("/assessments/log", {
        cache: "no-store",
        skipCache: true,
      });
      setEntries(data);
      setError(null);
    } catch (err) {
      setError(getApiErrorMessage(err, "Failed to load exam log."));
    } finally {
      if (!background) {
        setIsLoading(false);
      }
    }
  });

  useEffect(() => {
    void fetchLog();

    const handleRefresh = () => {
      void fetchLog(true);
    };

    window.addEventListener("celtm-assessment-log-refresh", handleRefresh);

    return () => {
      window.removeEventListener("celtm-assessment-log-refresh", handleRefresh);
    };
  }, []);

  if (isLoading) {
    return (
      <div className="grid gap-4 sm:grid-cols-2">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-40 animate-pulse rounded-3xl bg-surface-container-low" />
        ))}
      </div>
    );
  }

  if (!entries.length) {
    return (
      <div className="space-y-3">
        {error ? (
          <div className="rounded-2xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-500">
            {error}
          </div>
        ) : null}
        <div className="rounded-3xl border border-dashed border-outline-variant/20 dark:border-transparent bg-surface-container-low px-5 py-6 text-center">
          <h4 className="text-sm font-bold text-on-surface">No assessments found</h4>
          <p className="mt-2 text-sm leading-6 text-on-surface-variant">
            Complete your first MCQ, Situational, or Written assessment to see it here.
          </p>
          <Link
            href="/assessments"
            className="mt-4 inline-flex rounded-full bg-primary/10 px-4 py-2 text-[11px] font-black uppercase tracking-[0.18em] text-primary transition hover:bg-primary/15"
          >
            Start now
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {error ? (
        <div className="rounded-2xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-500">
          {error}
        </div>
      ) : null}
      <div className="grid gap-4 sm:grid-cols-2">
        {entries.map((entry) => (
          <button
            key={entry.id}
            type="button"
            onClick={() => onEntryClick?.(entry)}
            className="lift-tile group flex flex-col items-start rounded-3xl border border-outline-variant/12 dark:border-transparent bg-surface-container-low p-5 text-left transition hover:border-primary/20"
          >
            <div className="mb-auto w-full">
              <div className="mb-3 flex items-center justify-between">
                <span
                  className={`rounded-full px-2.5 py-0.5 text-[10px] font-black uppercase tracking-[0.12em] ${
                    entry.type === "mcq"
                      ? "bg-blue-500/10 text-blue-500"
                      : entry.type === "situational"
                        ? "bg-teal-500/10 text-teal-500"
                        : entry.type === "written"
                          ? "bg-purple-500/10 text-purple-500"
                          : "bg-amber-500/10 text-amber-500"
                  }`}
                >
                  {entry.type}
                </span>
                <span className="text-[10px] font-bold text-on-surface-variant">
                  {formatDate(entry.completed_at)}
                </span>
              </div>
              <h3 className="line-clamp-1 text-base font-bold text-on-surface transition-colors group-hover:text-primary">
                {entry.subject}
              </h3>
              <p className="mt-2 line-clamp-2 text-xs leading-5 text-on-surface-variant">
                {entry.insight || "Evaluation pending..."}
              </p>
            </div>

            <div className="mt-4 flex w-full items-center justify-between border-t border-outline-variant/5 pt-4">
              <div className="flex items-center gap-2">
                <span
                  className={`h-2 w-2 rounded-full ${
                    entry.status === "completed" ? "bg-green-500" : "bg-amber-500"
                  }`}
                />
                <span className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant">
                  {entry.status}
                </span>
              </div>
              <div className="text-right">
                <p className="text-xl font-extrabold tracking-tight text-on-surface">
                  {entry.score !== null ? formatPercent(entry.score) : "--"}
                </p>
              </div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
