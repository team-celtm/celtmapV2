"use client";

import type { SkillRead } from "@/lib/celtm";
import { formatPercent } from "@/lib/celtm";

interface SkillInsightModalProps {
  skill: SkillRead | null;
  onClose: () => void;
}

export function SkillInsightModal({ skill, onClose }: SkillInsightModalProps) {
  if (!skill) {
    return null;
  }

  const rows = [
    { label: "Verified score", value: formatPercent(skill.verified_score) },
    { label: "Assessment score", value: formatPercent(skill.assessment_score) },
    { label: "Written score", value: formatPercent(skill.written_score) },
    { label: "Interview score", value: formatPercent(skill.interview_score) },
    { label: "Artifact score", value: formatPercent(skill.artifact_score) },
  ];

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/70 px-4">
      <div className="w-full max-w-xl rounded-[32px] border border-outline-variant/12 dark:border-transparent bg-surface-container p-8 shadow-2xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-primary">
              Skill verification log
            </p>
            <h3 className="mt-2 text-3xl font-extrabold tracking-tight text-on-surface">
              {skill.skill_name}
            </h3>
            <p className="mt-2 text-sm leading-6 text-on-surface-variant">
              Detailed score contributions currently persisted for this skill.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-outline-variant/12 dark:border-transparent bg-surface px-3 py-2 text-[10px] font-black uppercase tracking-[0.18em] text-on-surface transition hover:bg-surface-container-low"
          >
            Close
          </button>
        </div>

        <div className="mt-8 grid gap-4 sm:grid-cols-2">
          {rows.map((row) => (
            <div key={row.label} className="lift-tile rounded-3xl border border-outline-variant/12 dark:border-transparent bg-surface px-5 py-5 shadow-inner">
              <p className="text-[10px] font-black uppercase tracking-[0.18em] text-on-surface-variant">
                {row.label}
              </p>
              <p className="mt-2 text-2xl font-extrabold tracking-tight text-on-surface">{row.value}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
