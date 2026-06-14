"use client";

import Link from "next/link";
import { Suspense, useCallback, useMemo, useState, useEffect, useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ApiError, apiFetch } from "@/lib/api";
import type { ReadinessComponent } from "@/lib/celtm";

interface PublicQuestion {
  id: string;
  question_id: string;
  dimension: string;
  difficulty: string;
  question_type: string;
  scenario?: string | null;
  question_text: string;
  options: Array<{ id: string; option_text: string }>;
}

interface QuestionsPayload {
  status: string;
  assessment_id: string;
  questions: PublicQuestion[];
  answers: Record<string, string>;
  progress?: { answered: number; total_required: number; percent: number };
}

interface AssessmentResult {
  assessment_id?: string;
  id?: string;
  score: number;
  readiness_score?: number | null;
  readiness_components?: ReadinessComponent[];
  readiness_formula?: string | null;
  correct_answers?: number;
  total_questions?: number;
  status: string;
  capability_profile?: Record<string, number>;
  hidden_skills?: unknown[];
  areas_of_betterment?: unknown[];
  inference?: { insight?: string; strengths?: string[]; risks?: string[]; recommendations?: string[] };
}

function resultItemLabel(value: unknown, preferredKey: "skill" | "area") {
  if (typeof value === "string") return value;
  if (value && typeof value === "object") {
    const record = value as Record<string, unknown>;
    return String(record[preferredKey] ?? record.name ?? JSON.stringify(record));
  }
  return String(value ?? "");
}

function QuizContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const mode = searchParams.get("mode") || "quick";
  const category = searchParams.get("category") || "capability-profile";
  const questionType = (searchParams.get("questionType") || "MIXED").toUpperCase();
  const assessmentType = searchParams.get("assessmentType") || (questionType === "SITUATIONAL" ? "situational" : "capability");
  const screenTitle = searchParams.get("title");
  const assignmentId = searchParams.get("assignmentId");
  const durationMinutes = Number(searchParams.get("duration") || 0);
  const [assessmentId, setAssessmentId] = useState("");
  const [questions, setQuestions] = useState<PublicQuestion[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [currentIndex, setCurrentIndex] = useState(0);
  const [result, setResult] = useState<AssessmentResult | null>(null);
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState("");

  const [isFullscreen, setIsFullscreen] = useState(false);
  const [warningCountdown, setWarningCountdown] = useState<number | null>(null);
  const [remainingSeconds, setRemainingSeconds] = useState<number | null>(null);

  const countdownRef = useRef<NodeJS.Timeout | null>(null);

  const title = useMemo(() => {
    if (screenTitle) return screenTitle;
    if (category !== "capability-profile") return `${category} Assessment`;
    if (mode === "deep") return "Deep Capability Assessment";
    if (mode === "standard") return "Standard Capability Assessment";
    return "Quick Capability Assessment";
  }, [category, mode, screenTitle]);

  const completeAssessment = useCallback(async () => {
    try {
      setIsBusy(true);
      const completion = await apiFetch<AssessmentResult>(`/assessments/${assessmentId}/complete`, { method: "POST" });
      setResult(completion);
      setIsFullscreen(false);
      if (document.fullscreenElement) {
        document.exitFullscreen().catch(() => {});
      }
      setWarningCountdown(null);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not submit assessment.");
    } finally {
      setIsBusy(false);
    }
  }, [assessmentId]);

  const exitAssessment = useCallback(() => {
    setIsFullscreen(false);
    setWarningCountdown(null);
    setRemainingSeconds(null);
    if (document.fullscreenElement) {
      document.exitFullscreen().catch(() => {});
    }
    router.push("/assessments");
  }, [router]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && isFullscreen && !result) {
        event.preventDefault();
        exitAssessment();
      }
    };

    const handleFullscreenChange = () => {
      if (!document.fullscreenElement && isFullscreen && assessmentId && !result) {
        exitAssessment();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("fullscreenchange", handleFullscreenChange);
    };
  }, [assessmentId, exitAssessment, isFullscreen, result]);

  useEffect(() => {
    // Focus loss detector
    const handleVisibilityChange = () => {
      if (document.hidden && assessmentId && !result) {
        // Tab lost focus
        setWarningCountdown(10);
      } else {
        if (warningCountdown !== null) {
          // Came back, clear warning if not finished
          setWarningCountdown(null);
        }
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => document.removeEventListener("visibilitychange", handleVisibilityChange);
  }, [assessmentId, result, warningCountdown]);

  useEffect(() => {
    if (warningCountdown !== null && warningCountdown > 0) {
      countdownRef.current = setTimeout(() => {
        setWarningCountdown(warningCountdown - 1);
      }, 1000);
    } else if (warningCountdown === 0) {
      // Auto submit
      void completeAssessment();
    }
    return () => {
      if (countdownRef.current) clearTimeout(countdownRef.current);
    };
  }, [completeAssessment, warningCountdown]);

  // Request Fullscreen
  const enterFullscreen = () => {
    const elem = document.documentElement;
    if (elem.requestFullscreen) {
      elem.requestFullscreen().then(() => setIsFullscreen(true)).catch(() => setIsFullscreen(true));
    } else {
      setIsFullscreen(true);
    }
  };

  const start = async () => {
    try {
      setIsBusy(true);
      setError("");
      setResult(null);
      enterFullscreen();
      const created = await apiFetch<{ id: string }>("/assessments", {
        method: "POST",
        body: JSON.stringify({
          mode,
          assessment_type: assessmentType,
          question_type: questionType,
          category,
          assignment_id: assignmentId,
        }),
      });
      setAssessmentId(created.id);
      if (assignmentId && durationMinutes > 0) {
        setRemainingSeconds(durationMinutes * 60);
      }
      await loadQuestions(created.id);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not start assessment.");
      setIsFullscreen(false);
      if (document.fullscreenElement) {
        document.exitFullscreen().catch(() => {});
      }
    } finally {
      setIsBusy(false);
    }
  };

  const loadQuestions = async (id = assessmentId) => {
    try {
      const payload = await apiFetch<QuestionsPayload>(`/assessments/${id}/questions`, {
        cache: "no-store",
      });

      if (!payload) {
        throw new Error("Empty response from server");
      }
      if (payload.status === "completed") {
        const completion = await apiFetch<AssessmentResult>(`/assessments/${id}/complete`, { method: "POST" });
        setResult(completion);
        setIsFullscreen(false);
        return;
      }
      if (!payload.questions) {
        throw new Error("Invalid response format: missing questions");
      }
      if (payload.questions.length === 0) {
        throw new Error("Subject not available at the moment.");
      }
      setQuestions(payload.questions);
      setAnswers(payload.answers || {});
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error loading questions");
      setIsFullscreen(false);
    }
  };

  const answer = async (optionId: string) => {
    const question = questions[currentIndex];
    if (!assessmentId || !question || isBusy) return;

    // Optimistic update
    setAnswers(prev => ({ ...prev, [question.id]: optionId }));

    try {
      await apiFetch<{ is_correct: boolean; correct_option_id: string; completed: boolean }>(
        `/assessments/${assessmentId}/answer`,
        {
          method: "POST",
          body: JSON.stringify({
            question_id: question.id,
            selected_answer: optionId,
          }),
        },
      );
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not submit answer.");
    }
  };

  useEffect(() => {
    if (!assessmentId || result || remainingSeconds === null) {
      return;
    }
    if (remainingSeconds <= 0) {
      void completeAssessment();
      return;
    }
    const timeoutId = setTimeout(() => {
      setRemainingSeconds((current) => (current === null ? null : Math.max(0, current - 1)));
    }, 1000);
    return () => clearTimeout(timeoutId);
  }, [assessmentId, completeAssessment, remainingSeconds, result]);

  const formattedRemaining = remainingSeconds === null
    ? null
    : `${String(Math.floor(remainingSeconds / 60)).padStart(2, "0")}:${String(remainingSeconds % 60).padStart(2, "0")}`;

  if (result) {
    const profile = result.capability_profile || {};
    const correct = result.correct_answers || 0;
    const total = result.total_questions || 1;
    const wrong = total - correct;
    const liveReadiness = result.readiness_score ?? result.score;
    const readinessComponents = result.readiness_components ?? [];

    return (
      <div className="mx-auto max-w-[1400px] space-y-8 px-5 py-8">
        <div className="flex items-center justify-between">
          <Link href="/assessments" className="text-sm font-bold text-on-surface-variant hover:text-on-surface">Back to assessments</Link>
          <span className="text-[10px] font-black uppercase tracking-[0.22em] text-primary">Complete</span>
        </div>

        <div className="grid lg:grid-cols-[1fr_2fr] gap-6">
          <section className="clay-card rounded-[36px] p-8 text-center flex flex-col justify-center items-center bg-gradient-to-br from-primary/5 to-transparent border border-primary/10">
            <p className="text-[11px] font-black uppercase tracking-[0.24em] text-primary">Updated readiness</p>
            <div className="relative my-8">
              <svg className="w-48 h-48 -rotate-90 transform" viewBox="0 0 160 160">
                <circle cx="80" cy="80" r="70" stroke="currentColor" strokeWidth="12" fill="transparent" className="text-surface-container-high" />
                <circle
                  cx="80" cy="80" r="70" stroke="currentColor" strokeWidth="12" fill="transparent"
                  strokeDasharray={2 * Math.PI * 70}
                  strokeDashoffset={2 * Math.PI * 70 * (1 - Math.max(0, Math.min(100, liveReadiness)) / 100)}
                  strokeLinecap="round"
                  className="text-primary transition-all duration-1000 ease-out"
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <p className="text-5xl font-black text-on-surface">{Math.round(liveReadiness)}%</p>
                <p className="mt-1 text-[10px] font-black uppercase tracking-widest text-on-surface-variant">Global</p>
              </div>
            </div>
            <p className="max-w-sm text-sm font-bold leading-6 text-on-surface-variant">
              Objective score: {Math.round(result.score)}%. Global readiness blends resume, objective assessments, written work, and credential evidence.
            </p>

            <div className="grid grid-cols-2 gap-4 w-full mt-5 sm:grid-cols-4">
              <div className="rounded-2xl bg-primary/10 p-3">
                <p className="text-xs font-bold text-primary uppercase">Exam score</p>
                <p className="text-xl font-black text-primary mt-1">{Math.round(result.score)}%</p>
              </div>
              <div className="rounded-2xl bg-surface-container-low p-3">
                <p className="text-xs font-bold text-on-surface-variant uppercase">Total</p>
                <p className="text-xl font-black text-on-surface mt-1">{total}</p>
              </div>
              <div className="rounded-2xl bg-emerald-500/10 p-3">
                <p className="text-xs font-bold text-emerald-600 dark:text-emerald-400 uppercase">Correct</p>
                <p className="text-xl font-black text-emerald-700 dark:text-emerald-300 mt-1">{correct}</p>
              </div>
              <div className="rounded-2xl bg-red-500/10 p-3">
                <p className="text-xs font-bold text-red-600 dark:text-red-400 uppercase">Wrong</p>
                <p className="text-xl font-black text-red-700 dark:text-red-300 mt-1">{wrong}</p>
              </div>
            </div>
            {readinessComponents.length ? (
              <div className="mt-5 grid w-full gap-2 text-left">
                {readinessComponents.map((component) => (
                  <div key={component.key} className="flex items-center justify-between rounded-2xl bg-surface-container-low px-4 py-3">
                    <span className="text-xs font-black uppercase tracking-widest text-on-surface-variant">{component.label}</span>
                    <span className="text-sm font-black text-on-surface">{Math.round(component.score)}%</span>
                  </div>
                ))}
              </div>
            ) : null}
          </section>

          <div className="space-y-6">
            <section className="clay-card rounded-[30px] p-8 bg-surface-container-low">
              <p className="text-[11px] font-black uppercase tracking-[0.24em] text-primary mb-4">AI Inference & Analysis</p>
              <div className="mt-8 rounded-3xl bg-surface-container-high p-6 text-center">
                <p className="text-sm font-medium leading-relaxed text-on-surface">
                  {result.inference?.insight || "Detailed analytics and inference have been saved to your profile. The system has updated your capabilities deterministically based on these responses."}
                </p>
              </div>
            </section>

            <div className="grid md:grid-cols-2 gap-6">
              <div className="clay-card rounded-[30px] p-6 border-l-4 border-l-emerald-500">
                <p className="text-[11px] font-black uppercase tracking-[0.24em] text-emerald-600 dark:text-emerald-400 mb-4">Hidden Skills Unlocked</p>
                <div className="flex flex-wrap gap-2">
                  {result.hidden_skills?.length ? (
                    result.hidden_skills.map((skill, i) => {
                      const skillStr = resultItemLabel(skill, "skill");
                      return (
                        <span key={i} className="px-4 py-2 rounded-xl bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 font-bold text-sm">
                          {skillStr}
                        </span>
                      );
                    })
                  ) : (
                    <p className="text-sm text-on-surface-variant italic">No new hidden skills identified in this run.</p>
                  )}
                </div>
              </div>

              <div className="clay-card rounded-[30px] p-6 border-l-4 border-l-amber-500">
                <p className="text-[11px] font-black uppercase tracking-[0.24em] text-amber-600 dark:text-amber-400 mb-4">Areas of Betterment</p>
                <div className="flex flex-wrap gap-2">
                  {result.areas_of_betterment?.length ? (
                    result.areas_of_betterment.map((area, i) => {
                      const areaStr = resultItemLabel(area, "area");
                      return (
                        <span key={i} className="px-4 py-2 rounded-xl bg-amber-500/10 text-amber-700 dark:text-amber-300 font-bold text-sm">
                          {areaStr}
                        </span>
                      );
                    })
                  ) : (
                    <p className="text-sm text-on-surface-variant italic">No major areas of concern identified.</p>
                  )}
                </div>
              </div>
            </div>

            <section className="clay-card rounded-[30px] p-8">
              <p className="text-[11px] font-black uppercase tracking-[0.24em] text-primary mb-6">Capability Profile Impact</p>
              <div className="grid gap-4 sm:grid-cols-2">
                {Object.entries(profile).map(([dimension, score]) => (
                  <div key={dimension} className="rounded-2xl bg-surface-container-low p-4">
                    <div className="flex items-center justify-between">
                      <p className="font-bold text-on-surface text-sm">{dimension}</p>
                      <p className="font-black text-primary text-sm">{Math.round(score)}%</p>
                    </div>
                    <div className="mt-3 h-1.5 rounded-full bg-surface-container-high">
                      <div className="h-1.5 rounded-full bg-primary" style={{ width: `${Math.min(100, score)}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </section>
          </div>
        </div>

        <div className="flex flex-wrap justify-center gap-4 mt-8">
          <Link href="/dashboard" className="rounded-2xl bg-primary px-8 py-4 text-[12px] font-black uppercase tracking-[0.2em] text-white hover:bg-primary/90 transition-colors">Dashboard impact</Link>
          <button onClick={() => window.location.reload()} className="rounded-2xl bg-surface-container-high px-8 py-4 text-[12px] font-black uppercase tracking-[0.2em] text-on-surface hover:bg-surface-container-highest transition-colors">Attempt again</button>
        </div>
      </div>
    );
  }

  return (
    <div className={isFullscreen ? "fixed inset-0 z-50 bg-surface overflow-y-auto" : ""}>
      {warningCountdown !== null && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-red-600/90 backdrop-blur-sm">
          <div className="text-center text-white">
            <h2 className="text-4xl font-black mb-4">Focus Lost!</h2>
            <p className="text-xl mb-4">You switched tabs. The assessment will automatically submit in:</p>
            <div className="text-8xl font-black">{warningCountdown}s</div>
            <p className="mt-6 text-sm">Return to this tab immediately to continue.</p>
          </div>
        </div>
      )}

      <div className="mx-auto w-full max-w-[1600px] space-y-7 px-6 lg:px-10 py-8 h-full flex flex-col">
        {!isFullscreen && (
          <div className="flex items-center justify-between">
            <Link href="/assessments" className="text-sm font-bold text-on-surface-variant hover:text-on-surface">Back to assessments</Link>
            <span className="text-[10px] font-black uppercase tracking-[0.22em] text-primary">{mode} mode</span>
          </div>
        )}

        {error ? <div className="rounded-3xl bg-red-500/10 px-5 py-4 text-sm font-bold text-red-500">{error}</div> : null}

        {!assessmentId ? (
          <section className="clay-card rounded-[36px] p-8 md:p-10 flex-1">
            <p className="text-[11px] font-black uppercase tracking-[0.24em] text-primary">Secure assessment</p>
            <h1 className="mt-3 text-4xl font-black tracking-tight text-on-surface">{title}</h1>
            <p className="mt-4 max-w-2xl text-lg leading-8 text-on-surface-variant">
              This assessment requires full-screen mode. If you switch tabs, you will have 10 seconds to return before it auto-submits.
              {assignmentId && durationMinutes > 0 ? ` This assigned test has a ${durationMinutes}-minute duration.` : ""}
            </p>
            <button
              onClick={start}
              disabled={isBusy}
              className="mt-8 rounded-full bg-primary px-8 py-4 text-[11px] font-black uppercase tracking-[0.2em] text-white disabled:opacity-60"
            >
              {isBusy ? "Starting..." : "Begin live attempt"}
            </button>
          </section>
        ) : questions.length > 0 ? (
          <div className="flex flex-col lg:flex-row gap-8 flex-1 h-full">
            {/* Sidebar Navigation */}
            <div className="lg:w-64 flex flex-col gap-4">
              <div className="clay-card rounded-3xl p-5">
                <h3 className="font-black text-on-surface mb-4">Questions</h3>
                <div className="grid grid-cols-4 lg:grid-cols-3 gap-2">
                  {questions.map((q, idx) => {
                    const isAnswered = !!answers[q.id];
                    const isActive = currentIndex === idx;
                    return (
                      <button
                        key={q.id}
                        onClick={() => setCurrentIndex(idx)}
                        className={`h-10 w-10 rounded-xl font-bold flex items-center justify-center transition-all ${
                          isActive
                            ? "bg-primary text-white scale-110 shadow-lg"
                            : isAnswered
                            ? "bg-emerald-500/20 text-emerald-700"
                            : "bg-surface-container-high text-on-surface hover:bg-surface-container-highest"
                        }`}
                      >
                        {idx + 1}
                      </button>
                    )
                  })}
                </div>
              </div>
              <div className="clay-card rounded-3xl p-5 mt-auto">
                <div className="flex justify-between items-center mb-4">
                  <span className="text-sm font-bold text-on-surface-variant">Progress</span>
                  <span className="text-sm font-black text-primary">
                    {Object.keys(answers).length} / {questions.length}
                  </span>
                </div>
                {formattedRemaining ? (
                  <div className="mb-4 rounded-2xl bg-surface-container-high px-4 py-3 text-center">
                    <p className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant">Time left</p>
                    <p className="mt-1 font-mono text-2xl font-black text-primary">{formattedRemaining}</p>
                  </div>
                ) : null}
                <button
                  onClick={exitAssessment}
                  type="button"
                  className="mb-3 w-full rounded-2xl bg-surface-container-high py-3 text-[10px] font-black uppercase tracking-widest text-on-surface hover:bg-surface-container-highest transition-colors"
                >
                  Exit assessment
                </button>
                <button
                  onClick={completeAssessment}
                  disabled={isBusy}
                  className="w-full rounded-2xl bg-[#0A1128] py-4 text-[11px] font-black uppercase tracking-widest text-white hover:bg-black transition-colors"
                >
                  {isBusy ? "Submitting..." : "Submit Test"}
                </button>
              </div>
            </div>

            {/* Question Content */}
            <div className="flex-1 flex flex-col">
              <section className="clay-card rounded-[36px] p-7 md:p-9 flex-1">
                <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-b pb-6 border-outline-variant/30">
                  <div>
                    <p className="text-[10px] font-black uppercase tracking-[0.22em] text-primary">
                      {questions[currentIndex].dimension} - {questions[currentIndex].difficulty}
                    </p>
                    <h2 className="mt-2 text-xl font-black tracking-tight text-on-surface">Question {currentIndex + 1}</h2>
                  </div>
                </div>

                {questions[currentIndex].scenario ? (
                  <div className="mb-6 rounded-3xl bg-amber-500/10 p-5 text-base leading-7 text-amber-800 dark:text-amber-200">
                    {questions[currentIndex].scenario}
                  </div>
                ) : null}

                <h2 className="text-2xl lg:text-3xl font-black leading-snug text-on-surface dark:text-white mb-8">
                  {questions[currentIndex].question_text}
                </h2>

                <div className="flex-1 overflow-y-auto custom-scroll pr-2">
                  <div className="flex flex-col gap-4">
                    {questions[currentIndex]?.options?.map((opt) => {
                      const isSelected = answers[questions[currentIndex].id] === opt.id;
                      return (
                        <button
                          key={opt.id}
                          onClick={() => answer(opt.id)}
                          className={`flex items-start gap-5 w-full rounded-[24px] border-2 p-6 text-left transition-all ${
                            isSelected
                              ? "border-primary bg-primary/5 shadow-md scale-[1.01]"
                              : "border-outline-variant/30 bg-surface-container hover:border-primary/50 hover:bg-surface-container-high"
                          }`}
                        >
                          <div className={`mt-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 ${
                            isSelected ? "border-primary bg-primary" : "border-outline-variant"
                          }`}>
                            {isSelected && <div className="h-2.5 w-2.5 rounded-full bg-white" />}
                          </div>
                          <span className={`text-xl font-medium leading-relaxed ${isSelected ? "text-primary font-bold" : "text-on-surface"}`}>
                            {opt.option_text}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div className="mt-10 flex justify-between items-center pt-6 border-t border-outline-variant/30">
                  <button
                    onClick={() => setCurrentIndex(Math.max(0, currentIndex - 1))}
                    disabled={currentIndex === 0}
                    className="px-6 py-3 rounded-full font-bold text-on-surface-variant hover:text-on-surface disabled:opacity-30 transition-colors"
                  >
                    Previous
                  </button>
                  <button
                    onClick={() => setCurrentIndex(Math.min(questions.length - 1, currentIndex + 1))}
                    disabled={currentIndex === questions.length - 1}
                    className="px-8 py-3 rounded-full bg-primary/10 font-bold text-primary hover:bg-primary/20 disabled:opacity-30 transition-colors"
                  >
                    Next Question
                  </button>
                </div>
              </section>
            </div>
          </div>
        ) : (
          <section className="clay-card rounded-[36px] p-8 text-center flex-1 flex flex-col items-center justify-center">
            <div className="mx-auto h-12 w-12 animate-spin rounded-full border-4 border-primary/20 border-t-primary" />
            <p className="mt-6 text-base font-bold text-on-surface-variant">Loading your assessment environment...</p>
          </section>
        )}
      </div>
    </div>
  );
}

export default function AssessmentQuizPage() {
  return (
    <Suspense fallback={<div className="flex min-h-screen items-center justify-center">Loading...</div>}>
      <QuizContent />
    </Suspense>
  );
}
