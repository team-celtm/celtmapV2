"use client";

import { useEffect, useMemo, useState } from "react";
import AppIcon from "@/components/AppIcon";

interface CeltmProgressLoaderProps {
  title?: string;
  caption?: string;
  stages?: string[];
  forceComplete?: boolean;
  minHeightClassName?: string;
  className?: string;
}

const defaultStages = [
  "Reading your profile signals",
  "Mapping capability evidence",
  "Scoring readiness signals",
  "Preparing the result",
];

export default function CeltmProgressLoader({
  title = "Preparing your CELTM profile",
  caption = "Cooking your goal",
  stages = defaultStages,
  forceComplete = false,
  minHeightClassName = "min-h-[40vh]",
  className = "",
}: CeltmProgressLoaderProps) {
  const [progress, setProgress] = useState(10);

  useEffect(() => {
    if (forceComplete) {
      setProgress(100);
      return;
    }

    setProgress(10);
    const interval = window.setInterval(() => {
      setProgress((current) => {
        if (current >= 95) return 95;
        if (current < 40) return current + 10;
        if (current < 75) return current + 8;
        return Math.min(95, current + 3);
      });
    }, 520);

    return () => window.clearInterval(interval);
  }, [forceComplete]);

  const displayProgress = forceComplete ? 100 : Math.min(95, Math.max(10, Math.floor(progress / 10) * 10));
  const circumference = 2 * Math.PI * 54;
  const offset = circumference - (circumference * displayProgress) / 100;
  const stage = useMemo(() => {
    const safeStages = stages.length ? stages : defaultStages;
    const index = Math.min(safeStages.length - 1, Math.floor((displayProgress / 100) * safeStages.length));
    return forceComplete ? "Finalizing your analysis" : safeStages[index];
  }, [displayProgress, forceComplete, stages]);

  return (
    <div className={`flex ${minHeightClassName} items-center justify-center px-4 ${className}`}>
      <div className="relative w-full max-w-xl overflow-hidden rounded-[36px] border border-outline-variant/15 bg-surface-container-low p-8 text-center shadow-xl">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(99,102,241,0.18),transparent_45%)]" />
        <div className="relative z-10">
          <div className="mx-auto mb-6 flex h-36 w-36 items-center justify-center">
            <svg className="absolute h-36 w-36 -rotate-90" viewBox="0 0 128 128">
              <circle cx="64" cy="64" r="54" fill="none" stroke="currentColor" strokeWidth="10" className="text-primary/10" />
              <circle
                cx="64"
                cy="64"
                r="54"
                fill="none"
                stroke="currentColor"
                strokeWidth="10"
                strokeDasharray={circumference}
                strokeDashoffset={offset}
                strokeLinecap="round"
                className="text-primary transition-all duration-500 ease-out"
              />
            </svg>
            <div className="relative flex h-24 w-24 items-center justify-center rounded-full bg-surface shadow-lg">
              <div className="absolute inset-2 rounded-full border border-primary/15" />
              <AppIcon name="route" className="h-8 w-8 text-primary" />
            </div>
          </div>

          <p className="text-[11px] font-black uppercase tracking-[0.24em] text-primary">{title}</p>
          <h2 className="mt-3 text-3xl font-black tracking-tight text-on-surface">
            {caption} {displayProgress}%
          </h2>
          <p className="mt-3 text-sm font-semibold leading-6 text-on-surface-variant">{stage}</p>

          <div className="mx-auto mt-6 h-2 max-w-sm overflow-hidden rounded-full bg-surface-container-high">
            <div
              className="h-full rounded-full bg-gradient-to-r from-primary via-secondary to-emerald-400 transition-all duration-500 ease-out"
              style={{ width: `${displayProgress}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
