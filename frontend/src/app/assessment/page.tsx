"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/contexts/AuthContext";
import { apiFetch, ApiError } from "@/lib/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface PlacementOption {
  id: string;
  option_text: string;
}

interface PlacementQuestion {
  id: string;
  question_text: string;
  category: string;
  difficulty: string | null;
  options: PlacementOption[];
}

interface PlacementAnswer {
  question_id: string;
  selected_option_id: string;
}

interface PlacementResult {
  status: string;
  assessment_id?: string;
  overall_score: number;
  domain_scores: Record<string, number>;
  preliminary_readiness: number;
  inference?: {
    overall_readiness: number;
    strong_areas: string[];
    areas_to_focus: string[];
    summary: string;
    recommendations: string[];
  };
  role_name?: string | null;
}

type PagePhase = "loading" | "quiz" | "submitting" | "done" | "error";

// ---------------------------------------------------------------------------
// Domain colour mapping
// ---------------------------------------------------------------------------

const DOMAIN_PALETTE: Record<string, { bg: string; text: string; glow: string }> = {
  "Mathematics":          { bg: "bg-blue-50",  text: "text-blue-600",  glow: "shadow-blue-500/10" },
  "Science":              { bg: "bg-cyan-50",    text: "text-cyan-600",    glow: "shadow-cyan-500/10" },
  "English":              { bg: "bg-amber-50",   text: "text-amber-600",   glow: "shadow-amber-500/10" },
  "Artificial Intelligence": { bg: "bg-indigo-50", text: "text-indigo-600",   glow: "shadow-indigo-500/10" },
  "Frontend Development": { bg: "bg-emerald-50", text: "text-emerald-600", glow: "shadow-emerald-500/10" },
};

function getDomainStyle(category: string) {
  return (
    DOMAIN_PALETTE[category] ?? {
      bg: "bg-white/10",
      text: "text-white/70",
      glow: "shadow-white/10",
    }
  );
}

// ---------------------------------------------------------------------------
// Animated radial progress ring
// ---------------------------------------------------------------------------

function ProgressRing({ current, total }: { current: number; total: number }) {
  const radius = 28;
  const circumference = 2 * Math.PI * radius;
  const progress = total > 0 ? (current / total) * circumference : 0;

  return (
    <div className="relative flex h-16 w-16 items-center justify-center">
      <svg className="absolute inset-0 -rotate-90" width="64" height="64">
        <circle
          cx="32"
          cy="32"
          r={radius}
          fill="none"
          stroke="rgba(0,0,0,0.04)"
          strokeWidth="4"
        />
        <circle
          cx="32"
          cy="32"
          r={radius}
          fill="none"
          stroke="#2D5BFF"
          strokeWidth="4"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference - progress}
          style={{ transition: "stroke-dashoffset 0.5s ease" }}
        />
      </svg>
      <span className="relative text-[10px] font-black text-[#0A1128] px-2 py-1 rounded bg-white shadow-sm border border-slate-100">
        {current}/{total}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page component
// ---------------------------------------------------------------------------

export default function AssessmentPage() {
  const router = useRouter();
  const { user, isLoading: isAuthLoading, refreshProfile } = useAuth();

  const [phase, setPhase] = useState<PagePhase>("loading");
  const [questions, setQuestions] = useState<PlacementQuestion[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<PlacementAnswer[]>([]);
  const [selectedOption, setSelectedOption] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PlacementResult | null>(null);

  // -------------------------------------------------------------------------
  // Boot: check auth + placement status
  // -------------------------------------------------------------------------
  useEffect(() => {
    if (isAuthLoading) return;

    if (!user) {
      router.replace("/login");
      return;
    }

    if (user.hasCompletedPlacement) {
      router.replace("/dashboard");
      return;
    }

    const loadQuestions = async () => {
      try {
        const url = user.focusRole 
          ? `/placement/questions?role_name=${encodeURIComponent(user.focusRole)}`
          : "/placement/questions";
        const data = await apiFetch<{ questions: PlacementQuestion[]; count: number }>(url);

        if (!data.questions || data.questions.length === 0) {
          setError("No placement questions found for your profile. Please contact support or retry onboarding.");
          setPhase("error");
          return;
        }


        setQuestions(data.questions);
        setPhase("quiz");
      } catch {
        setError("Couldn't load placement questions. Redirecting to dashboard…");
        setPhase("error");
        setTimeout(() => router.replace("/dashboard"), 2500);
      }
    };

    void loadQuestions();
  }, [isAuthLoading, user, router, refreshProfile]);

  // -------------------------------------------------------------------------
  // Handlers
  // -------------------------------------------------------------------------
  const handleOptionSelect = (optionId: string) => {
    setSelectedOption(optionId);
  };

  const handleNext = async () => {
    if (!selectedOption) return;

    const currentQuestion = questions[currentIndex];
    const newAnswers = [
      ...answers,
      { question_id: currentQuestion.id, selected_option_id: selectedOption },
    ];
    setAnswers(newAnswers);
    setSelectedOption(null);

    if (currentIndex < questions.length - 1) {
      setCurrentIndex((prev) => prev + 1);
      return;
    }

    // All answered — submit
    if (phase === "submitting") return;
    setPhase("submitting");
    try {
      const resultData = await apiFetch<PlacementResult>("/placement/submit", {
        method: "POST",
        body: JSON.stringify({
          answers: newAnswers,
          role_name: user?.focusRole || null,
        }),
      });
      setResult(resultData);
      
      // Crucial: wait for profile to be fully synced with new completion flags
      await refreshProfile();
      setPhase("done");
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        setError("You recently completed this assessment. Please wait 2 hours before your next attempt.");
      } else {
        setError("Couldn't save your results. Taking you to the dashboard anyway…");
      }
      setPhase("error");
      setTimeout(() => router.replace("/dashboard"), 3000);
    }
  };

  // -------------------------------------------------------------------------
  // Render helpers
  // -------------------------------------------------------------------------
  const currentQuestion = questions[currentIndex];
  const domainStyle = currentQuestion ? getDomainStyle(currentQuestion.category) : null;
  // =========================================================================
  // LOADING / AUTH STATE
  // =========================================================================
  if (phase === "loading" || isAuthLoading) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-5 bg-[#fafafa]">
        <div className="relative h-14 w-14">
          <div className="absolute inset-0 rounded-full border-2 border-[#2D5BFF]/20 border-t-[#2D5BFF] animate-spin" />
        </div>
        <p className="text-xs font-bold tracking-[0.18em] text-[#0A1128]/30 uppercase">
          Calibrating…
        </p>
      </div>
    );
  }

  // =========================================================================
  // DONE STATE - Show results with preliminary readiness
  // =========================================================================
  if (phase === "done") {
    const readiness = result?.preliminary_readiness ?? result?.overall_score ?? 0;
    const inference = result?.inference;
    const domainScores = result?.domain_scores ?? {};

    return (
      <div className="min-h-screen flex flex-col items-center bg-[#fafafa] px-4 py-12">
        <div className="w-full max-w-2xl">
          {/* Header Card */}
          <div className="rounded-[32px] border border-slate-200 bg-white p-8 shadow-[0_40px_100px_rgba(0,0,0,0.06)]">
            {/* Success Icon */}
            <div className="flex justify-center">
              <div className="relative flex h-20 w-20 items-center justify-center">
                <div className="absolute inset-0 rounded-full bg-emerald-500/10 blur-xl" />
                <div className="relative flex h-20 w-20 items-center justify-center rounded-full border border-emerald-500/20 bg-emerald-50">
                  <svg className="h-8 w-8 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                </div>
              </div>
            </div>

            <div className="mt-6 text-center">
              <p className="text-[10px] font-black uppercase tracking-[0.28em] text-emerald-500">
                Assessment Complete
              </p>
              <h1 className="mt-3 text-2xl font-black tracking-tight text-[#0A1128]">
                Your Preliminary Readiness Score
              </h1>
            </div>

            {/* Main Score Display */}
            <div className="mt-8 flex items-center justify-center gap-3">
              <div className="text-6xl font-black text-[#0A1128]">
                {Math.round(readiness)}
              </div>
              <div className="text-2xl font-bold text-[#0A1128]/20">%</div>
            </div>

            {/* Progress Bar */}
            <div className="mt-6 h-2 overflow-hidden rounded-full bg-slate-100">
              <div
                className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-[#2D5BFF]"
                style={{ width: `${readiness}%`, transition: "width 1s ease" }}
              />
            </div>
          </div>

          {/* Domain Scores Card */}
          <div className="mt-6 rounded-[32px] border border-slate-200 bg-white p-6 shadow-xl">
            <p className="text-[10px] font-black uppercase tracking-wider text-slate-400">Subject Breakdown</p>
            <div className="mt-4 grid grid-cols-2 gap-3">
              {Object.entries(domainScores).map(([domain, score]) => (
                <div
                  key={domain}
                  className={`flex items-center justify-between rounded-2xl px-4 py-3 ${
                    score >= 70
                      ? "bg-emerald-50 border border-emerald-500/10"
                      : score >= 40
                      ? "bg-amber-50 border border-amber-500/10"
                      : "bg-red-50 border border-red-500/10"
                  }`}
                >
                  <span className="text-[13px] font-bold text-[#0A1128]">{domain}</span>
                  <span className={`text-[13px] font-black ${
                    score >= 70 ? "text-emerald-600" : score >= 40 ? "text-amber-600" : "text-red-600"
                  }`}>
                    {Math.round(score)}%
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Insights Card */}
          {inference && (
            <div className="mt-6 rounded-[32px] border border-slate-200 bg-white p-6 shadow-xl">
              <p className="text-[10px] font-black uppercase tracking-wider text-slate-400">Key Insights</p>
              <p className="mt-3 text-[14px] leading-6 text-slate-600">
                {inference.summary}
              </p>
              {inference.recommendations && inference.recommendations.length > 0 && (
                <div className="mt-4">
                  <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Action Items</p>
                  <ul className="mt-2 space-y-2">
                    {inference.recommendations.slice(0, 3).map((rec, idx) => (
                      <li key={idx} className="flex items-start gap-3 text-[13px] text-slate-500">
                        <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-blue-600" />
                        {rec}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Continue Button */}
          <div className="mt-8 flex justify-center">
            <button
              onClick={() => router.replace("/dashboard")}
              className="group relative overflow-hidden rounded-2xl bg-gradient-to-r from-[#2D5BFF] to-[#3b6fff] px-10 py-4 text-sm font-bold text-white shadow-lg shadow-[#2D5BFF]/20 transition-all hover:shadow-xl hover:shadow-[#2D5BFF]/30"
            >
              <span className="relative">Continue to Dashboard</span>
              <svg className="absolute right-4 h-4 w-4 opacity-0 transition-opacity group-hover:opacity-100" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <line x1="5" y1="12" x2="19" y2="12" />
                <polyline points="12 5 19 12 12 19" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    );
  }

  // =========================================================================
  // SUBMITTING STATE
  // =========================================================================
  if (phase === "submitting") {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-5 bg-[#fafafa]">
        <div className="relative h-14 w-14">
          <div className="absolute inset-0 rounded-full border-2 border-[#2D5BFF]/20 border-t-[#2D5BFF] animate-spin" />
        </div>
        <p className="text-xs font-bold tracking-[0.18em] text-[#0A1128]/30 uppercase">
          Analysing results…
        </p>
      </div>
    );
  }

  // =========================================================================
  // ERROR STATE
  // =========================================================================
  if (phase === "error") {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-[#fafafa] px-4">
        <p className="text-[13px] font-bold text-red-500">{error}</p>
      </div>
    );
  }

  // =========================================================================
  // QUIZ (main state)
  // =========================================================================
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-[#fafafa] px-4 py-12 sm:px-8">
      <div className="w-full max-w-3xl">
        
        {/* Top bar: ring + meta */}
        <div className="mb-8 flex items-center justify-between px-2">
          <ProgressRing current={currentIndex + 1} total={questions.length} />
          <span className="rounded-full bg-slate-100 border border-slate-200 px-4 py-1.5 text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">
            Placement Assessment
          </span>
        </div>

        {/* Question card */}
        <div
          key={currentQuestion?.id || "loading-q"}
          className="animate-fade-in rounded-[32px] border border-slate-100 bg-white p-8 shadow-[0_40px_100px_rgba(0,0,0,0.04)] sm:p-12"
          style={{ animation: "fadeSlideUp 0.35s ease forwards" }}
        >
          {/* Domain pill */}
          {domainStyle && (
            <span
              className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[10px] font-black uppercase tracking-[0.22em] ${domainStyle.bg} ${domainStyle.text}`}
            >
              {currentQuestion.category}
              {currentQuestion.difficulty && (
                <span className="opacity-60">· {currentQuestion.difficulty}</span>
              )}
            </span>
          )}

          {/* Question text */}
          <h3 className="mt-8 text-2xl font-black leading-snug tracking-tight text-[#0A1128] sm:text-3xl">
            {currentQuestion?.question_text || "Loading question..."}
          </h3>

          {/* Options (2x2 Grid) */}
          <div className="mt-10 grid grid-cols-1 gap-4 sm:grid-cols-2">
            {(currentQuestion?.options || []).map((option, index) => {
              const prefix = String.fromCharCode(65 + index); // A, B, C, D
              const isSelected = selectedOption === option.id;
              return (
                <button
                  key={option.id}
                  type="button"
                  onClick={() => handleOptionSelect(option.id)}
                  className={`group relative flex items-center gap-4 overflow-hidden rounded-[20px] border px-5 py-4 text-left transition-all duration-200 ${
                    isSelected
                      ? "border-blue-600 bg-blue-50 shadow-sm"
                      : "border-slate-100 bg-slate-50 hover:border-slate-300 hover:bg-white"
                  }`}
                >
                  {/* Prefix letter */}
                  <span
                    className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-xs font-bold transition-colors ${
                      isSelected
                        ? "bg-blue-600 text-white"
                        : "bg-white text-slate-400 border border-slate-100 group-hover:bg-slate-100 group-hover:text-slate-600"
                    }`}
                  >
                    {prefix}
                  </span>

                  <span
                    className={`text-[15px] font-bold leading-6 transition-colors ${
                      isSelected ? "text-blue-600" : "text-slate-500 group-hover:text-[#0A1128]"
                    }`}
                  >
                    {option.option_text}
                  </span>
                  
                  {/* Selection Checkmark */}
                  {isSelected && (
                    <div className="absolute right-4 ml-auto flex h-5 w-5 items-center justify-center rounded-full bg-blue-600 text-white animate-scale-in">
                      <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* Footer (Pagination & CTA) */}
        <div className="mt-10 flex flex-col items-center justify-between gap-6 sm:flex-row sm:px-2">
          {/* Discrete Pagination */}
          <div className="flex w-full flex-1 gap-1.5 sm:max-w-[240px]">
            {questions.map((_, i) => (
              <div
                key={i}
                className={`h-1.5 flex-1 rounded-full transition-all duration-500 ${
                  i < currentIndex
                    ? "bg-blue-600"
                    : i === currentIndex
                    ? "bg-blue-600/30"
                    : "bg-slate-200"
                }`}
              />
            ))}
          </div>

          <button
            type="button"
            disabled={!selectedOption}
            onClick={() => void handleNext()}
            className={`group relative inline-flex h-14 items-center justify-center gap-3 overflow-hidden rounded-2xl px-8 text-sm font-bold tracking-[0.2em] uppercase transition-all duration-200 w-full sm:w-auto ${
              selectedOption
                ? "bg-[#0A1128] text-white shadow-lg hover:bg-black"
                : "cursor-not-allowed bg-slate-200 text-slate-400"
            }`}
          >
            {/* shimmer */}
            {selectedOption && (
              <span className="pointer-events-none absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/5 to-transparent transition-transform duration-700 group-hover:translate-x-full" />
            )}
            <span className="relative">
              {currentIndex === questions.length - 1 ? "Finish Quiz" : "Confirm Answer"}
            </span>
            <svg className="relative h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <line x1="5" y1="12" x2="19" y2="12" />
              <polyline points="12 5 19 12 12 19" />
            </svg>
          </button>
        </div>
      </div>

      {/* Global keyframe animations */}
      <style>{`
        @keyframes fadeSlideUp {
          from { opacity: 0; transform: translateY(14px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes scale-in {
          from { transform: scale(0); }
          to   { transform: scale(1); }
        }
        .animate-scale-in { animation: scale-in 0.15s ease forwards; }
      `}</style>
    </div>
  );
}
