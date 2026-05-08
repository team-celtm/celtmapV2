"use client";

import Link from "next/link";
import { formatPercent } from "@/lib/celtm";

interface SubjectCardProps {
  subject: {
    key: string;
    title: string;
    description: string;
    source: string;
    severity: number;
    currentScore: number;
    resourceCount: number;
    isAvailable?: boolean;
    skillId?: string | null;
    skillRequestId?: string | null;
  };
}

export function SubjectCard({ subject }: SubjectCardProps) {
  const isAvailable = subject.isAvailable ?? true;
  // A simplistic helper to generate initial letter
  const initial = subject.source ? subject.source.charAt(0).toUpperCase() : subject.title.charAt(0).toUpperCase();

  return (
    <Link
      href={isAvailable ? `/assessments/${subject.key}` : "#"}
      onClick={(e) => !isAvailable && e.preventDefault()}
      className={`flex flex-col bg-white dark:bg-zinc-950/50 rounded-[32px] overflow-hidden p-7 shadow-[0_2px_24px_rgba(0,0,0,0.02)] dark:shadow-none border border-black/[0.04] dark:border-white/[0.04] hover:shadow-[0_12px_40px_rgba(0,0,0,0.06)] dark:hover:border-white/10 transition-all duration-300 group ${
        !isAvailable ? "opacity-60 cursor-not-allowed" : ""
      }`}
    >
      {/* Top Header Row */}
      <div className="flex items-start justify-between mb-8">
        <div className={`h-12 w-12 rounded-full overflow-hidden flex items-center justify-center bg-zinc-50 dark:bg-zinc-900 border border-black/5 dark:border-white/5 text-zinc-900 dark:text-zinc-100 font-bold text-lg ${!isAvailable ? "grayscale" : ""}`}>
          {initial}
        </div>
        
        <div className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl border border-black/5 dark:border-white/10 text-[11px] font-bold text-zinc-500 dark:text-zinc-400 hover:bg-zinc-50 dark:hover:bg-zinc-900 transition-colors">
          <span>{isAvailable ? "Save" : "Coming Soon"}</span>
          {isAvailable && (
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
            </svg>
          )}
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 mb-10">
        <div className="flex items-center gap-2 mb-2.5">
          <span className="font-bold text-[13px] text-zinc-900 dark:text-zinc-100 tracking-tight">{subject.source}</span>
          <span className="text-[11px] font-medium text-zinc-400 dark:text-zinc-500">{subject.resourceCount} Modules</span>
        </div>
        
        <h3 className="text-2xl font-extrabold text-zinc-900 dark:text-white tracking-tight leading-[1.1] mb-5">
          {subject.title}
        </h3>
        
        {/* Badges/Tags */}
        <div className="flex flex-wrap gap-2">
          <span className="px-3 py-1.5 bg-zinc-100 dark:bg-zinc-900 text-zinc-600 dark:text-zinc-300 rounded-lg text-[11px] font-bold tracking-wide">
            {formatPercent(subject.currentScore)} Score
          </span>
          <span className="px-3 py-1.5 bg-zinc-100 dark:bg-zinc-900 text-zinc-600 dark:text-zinc-300 rounded-lg text-[11px] font-bold tracking-wide">
            {Math.round(subject.severity * 100)}% Gap
          </span>
        </div>
      </div>

      {/* Footer Area */}
      <div className="flex items-end justify-between mt-auto">
        <div className="flex flex-col">
          <span className="font-bold text-lg text-zinc-900 dark:text-white leading-none">
            {formatPercent(subject.currentScore)}
          </span>
          <span className="text-[11px] font-medium text-zinc-400 dark:text-zinc-500 mt-1.5">
            Proficiency
          </span>
        </div>
        
        <button 
          disabled={!isAvailable}
          className={`px-6 py-2.5 rounded-[12px] text-sm font-bold shadow-sm transition-all ${
            isAvailable 
              ? "bg-zinc-950 dark:bg-white text-white dark:text-zinc-950 group-hover:-translate-y-0.5" 
              : "bg-zinc-200 text-zinc-400 cursor-not-allowed"
          }`}
        >
          {isAvailable ? "Start now" : "Coming Soon"}
        </button>
      </div>
    </Link>
  );
}
