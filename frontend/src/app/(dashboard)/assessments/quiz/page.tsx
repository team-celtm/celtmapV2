"use client";

import Link from "next/link";
import { Suspense, useEffect, useEffectEvent, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ApiError, apiFetch } from "@/lib/api";
import type {
  AssessmentCompletionResponse,
  AssessmentRead,
  MCQQuestionBatchResponse,
  MCQQuestionPublic,
} from "@/lib/celtm";
import { toTitleCase } from "@/lib/celtm";

type Screen = "intro" | "question" | "submitting" | "results";
type IntegrityReason = "focus-loss";

interface IntegrityNotice {
  reason: IntegrityReason;
  message: string;
  remainingAttempts: number;
  recordedAt: number;
}

interface PersistedAssessmentAttempt {
  version: 1;
  assessment: AssessmentRead | null;
  answers: Record<string, string>;
  currentIndex: number;
  deadlineAt: number | null;
  integrityNotice: IntegrityNotice | null;
  questions: MCQQuestionPublic[];
  results: AssessmentCompletionResponse | null;
  screen: Screen;
}

interface FinishAssessmentOptions {
  automatic?: boolean;
  errorMessage?: string | null;
  keepalive?: boolean;
  notice?: IntegrityNotice | null;
}

const letters = ["A", "B", "C", "D", "E", "F"];
const defaultAttemptLimit = 3;

function deriveDurationMinutes(questionCount: number): number {
  return Math.max(10, Math.ceil((questionCount || 10) * 0.75));
}

function readBrowserStorage<T>(key: string, kind: "local" | "session"): T | null {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    const storage = kind === "local" ? window.localStorage : window.sessionStorage;
    const value = storage.getItem(key);
    return value ? (JSON.parse(value) as T) : null;
  } catch {
    return null;
  }
}

function writeBrowserStorage(key: string, value: unknown, kind: "local" | "session") {
  if (typeof window === "undefined") {
    return;
  }

  try {
    const storage = kind === "local" ? window.localStorage : window.sessionStorage;
    storage.setItem(key, JSON.stringify(value));
  } catch {
    // Ignore storage quota and serialization failures.
  }
}

function removeBrowserStorage(key: string, kind: "local" | "session") {
  if (typeof window === "undefined") {
    return;
  }

  try {
    const storage = kind === "local" ? window.localStorage : window.sessionStorage;
    storage.removeItem(key);
  } catch {
    // Ignore storage access failures.
  }
}

function readRemainingAttempts(storageKey: string): number {
  const value = readBrowserStorage<number>(storageKey, "local");
  if (typeof value !== "number" || Number.isNaN(value)) {
    return defaultAttemptLimit;
  }
  return Math.max(0, Math.floor(value));
}

function writeRemainingAttempts(storageKey: string, value: number) {
  writeBrowserStorage(storageKey, Math.max(0, Math.floor(value)), "local");
}

function readPersistedAssessmentAttempt(storageKey: string): PersistedAssessmentAttempt | null {
  const value = readBrowserStorage<PersistedAssessmentAttempt>(storageKey, "session");
  if (!value || value.version !== 1 || !Array.isArray(value.questions)) {
    return null;
  }
  return value;
}

function writePersistedAssessmentAttempt(storageKey: string, payload: PersistedAssessmentAttempt) {
  writeBrowserStorage(storageKey, payload, "session");
}

function clearPersistedAssessmentAttempt(storageKey: string) {
  removeBrowserStorage(storageKey, "session");
}

function AssessmentQuizPageContent() {
  const searchParams = useSearchParams();
  const skillId = searchParams.get("skillId");
  const skillRequestId = searchParams.get("skillRequestId");
  const category = searchParams.get("category") ?? "general";
  const difficulty = searchParams.get("difficulty");
  const title = searchParams.get("title") ?? "Technical Assessment";
  const assessmentType = searchParams.get("assessmentType") ?? "mcq";
  const questionType = searchParams.get("questionType") ?? "MCQ";

  const [screen, setScreen] = useState<Screen>("intro");
  const [questions, setQuestions] = useState<MCQQuestionPublic[]>([]);
  const [assessment, setAssessment] = useState<AssessmentRead | null>(null);
  const [results, setResults] = useState<AssessmentCompletionResponse | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [answerCorrectness, setAnswerCorrectness] = useState<Record<string, { isCorrect: boolean, correctOptionId: string }>>({});
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [isStarting, setIsStarting] = useState(false);
  const [isFinishing, setIsFinishing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [timeLeft, setTimeLeft] = useState(25 * 60);
  const [deadlineAt, setDeadlineAt] = useState<number | null>(null);
  const [remainingAttempts, setRemainingAttempts] = useState(defaultAttemptLimit);
  const [integrityNotice, setIntegrityNotice] = useState<IntegrityNotice | null>(null);
  const [showIntegrityModal, setShowIntegrityModal] = useState(false);
  const [hasHydratedAttemptState, setHasHydratedAttemptState] = useState(false);
  const [randomLimit] = useState(15);

  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const integrityTriggeredRef = useRef(false);
  const integrityTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const trackKey = useMemo(
    () =>
      [
        skillRequestId ?? "skill-request:none",
        skillId ?? "skill:none",
        category,
        difficulty ?? "difficulty:any",
        assessmentType,
        questionType,
      ].join("::"),
    [assessmentType, category, difficulty, questionType, skillId, skillRequestId],
  );
  const persistedAttemptStorageKey = useMemo(
    () => `celtm-assessment-active:${trackKey}`,
    [trackKey],
  );
  const attemptsStorageKey = useMemo(
    () => `celtm-assessment-remaining:${trackKey}`,
    [trackKey],
  );

  const effectiveQuestionType = questions[0]?.question_type ?? questionType;
  const requestedAssessmentModeLabel =
    questionType === "SITUATIONAL" ? "Situational" : "MCQ";
  const assessmentModeLabel =
    effectiveQuestionType === "SITUATIONAL" ? "Situational" : "MCQ";
  const currentQuestion = questions[currentIndex] ?? null;
  const answeredCount = Object.keys(answers).length;
  const progress = questions.length ? ((currentIndex + 1) / questions.length) * 100 : 0;
  const assessmentLabel = skillRequestId ? "Skill validation track" : toTitleCase(category);
  const durationMinutes = useMemo(() => deriveDurationMinutes(questions.length), [questions.length]);
  const finishAssessmentEvent = useEffectEvent((options?: FinishAssessmentOptions) => {
    void finishAssessment(options);
  });

  useEffect(() => {
    let isMounted = true;

    const loadQuestions = async () => {
      const persistedAttempt = readPersistedAssessmentAttempt(persistedAttemptStorageKey);
      const nextRemainingAttempts = readRemainingAttempts(attemptsStorageKey);

      integrityTriggeredRef.current = false;
      setRemainingAttempts(nextRemainingAttempts);
      setError(null);
      setShowIntegrityModal(false);
      setHasHydratedAttemptState(false);

      if (persistedAttempt?.questions.length) {
        const restoredTimeLeft =
          persistedAttempt.deadlineAt == null
            ? deriveDurationMinutes(persistedAttempt.questions.length) * 60
            : Math.max(0, Math.ceil((persistedAttempt.deadlineAt - Date.now()) / 1000));

        if (!isMounted) {
          return;
        }

        setQuestions(persistedAttempt.questions);
        setAssessment(persistedAttempt.assessment);
        setAnswers(persistedAttempt.answers);
        setCurrentIndex(
          Math.min(
            Math.max(persistedAttempt.currentIndex, 0),
            Math.max(persistedAttempt.questions.length - 1, 0),
          ),
        );
        setResults(persistedAttempt.results);
        setIntegrityNotice(persistedAttempt.integrityNotice);
        setShowIntegrityModal(Boolean(persistedAttempt.integrityNotice));
        setDeadlineAt(
          persistedAttempt.screen === "question" && !persistedAttempt.results
            ? persistedAttempt.deadlineAt
            : null,
        );
        setTimeLeft(persistedAttempt.screen === "question" ? restoredTimeLeft : 0);
        setScreen(
          persistedAttempt.screen === "results" && persistedAttempt.results
            ? "results"
            : persistedAttempt.screen === "question" && persistedAttempt.assessment
              ? "question"
              : "intro",
        );
        setIsLoading(false);
        setHasHydratedAttemptState(true);
        return;
      }

      try {
        setIsLoading(true);
        setError(null);
        setScreen("intro");
        setQuestions([]);
        setAssessment(null);
        setResults(null);
        setAnswers({});
        setCurrentIndex(0);
        setDeadlineAt(null);
        setTimeLeft(25 * 60);
        setIntegrityNotice(null);
        const controller = new AbortController();
        const timeoutId = window.setTimeout(() => controller.abort(), 20_000);
        const payload = await apiFetch<MCQQuestionBatchResponse>(
          "/mcq/questions?" +
            new URLSearchParams({
              category,
              ...(difficulty ? { difficulty } : {}),
              ...(skillId ? { skill_id: skillId } : {}),
              ...(skillRequestId ? { skill_request_id: skillRequestId } : {}),
              question_type: questionType,
              limit: randomLimit.toString(),
            }).toString(),
          { signal: controller.signal, revalidate: true, cache: "no-store" },
        ).finally(() => window.clearTimeout(timeoutId));
        if (!isMounted) {
          return;
        }
        setQuestions(payload.questions);
        setTimeLeft(deriveDurationMinutes(payload.questions.length) * 60);
        if (!payload.questions.length) {
          setError(`No test material available`);
        }
      } catch (caught) {
        if (!isMounted) {
          return;
        }
        console.error("Quiz load error:", caught);
        let message =
          "This assessment is taking too long to load. Please click Retry. If it persists, check the backend logs (Supabase/OpenAI) and confirm `http://127.0.0.1:8000/docs` opens.";
        if (caught instanceof ApiError) {
          if (caught.message.includes("No test material available") || caught.message.includes("Subject not available")) {
            message = "No test material available";
          } else {
            message = caught.message;
          }
        } else if (caught instanceof DOMException && caught.name === "AbortError") {
          message =
            "Timed out while loading questions (20s). Click Retry. If it keeps timing out, the backend is slow/unreachable.";
        }
        setError(message);
      } finally {
        if (isMounted) {
          setIsLoading(false);
          setHasHydratedAttemptState(true);
        }
      }
    };

    void loadQuestions();

    return () => {
      isMounted = false;
    };
  }, [
    attemptsStorageKey,
    category,
    difficulty,
    persistedAttemptStorageKey,
    questionType,
    requestedAssessmentModeLabel,
    randomLimit,
    skillId,
    skillRequestId,
  ]);

  useEffect(() => {
    if (screen !== "question" || results || deadlineAt == null) {
      return;
    }

    const updateTimer = () => {
      const remainingSeconds = Math.max(0, Math.ceil((deadlineAt - Date.now()) / 1000));
      setTimeLeft(remainingSeconds);

      if (remainingSeconds === 0) {
        if (timerRef.current) {
          clearInterval(timerRef.current);
        }
        finishAssessmentEvent({
          automatic: true,
          errorMessage: "Time expired. Finalising the attempt...",
        });
      }
    };

    updateTimer();
    timerRef.current = setInterval(() => {
      updateTimer();
    }, 1000);

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, [deadlineAt, results, screen]);

  useEffect(() => {
    if (!hasHydratedAttemptState) {
      return;
    }

    if (!assessment && !results && screen === "intro") {
      clearPersistedAssessmentAttempt(persistedAttemptStorageKey);
      return;
    }

    writePersistedAssessmentAttempt(persistedAttemptStorageKey, {
      version: 1,
      assessment,
      answers,
      currentIndex,
      deadlineAt,
      integrityNotice,
      questions,
      results,
      screen,
    });
  }, [
    answers,
    assessment,
    currentIndex,
    deadlineAt,
    hasHydratedAttemptState,
    integrityNotice,
    persistedAttemptStorageKey,
    questions,
    results,
    screen,
  ]);

  useEffect(() => {
    const handleFocusLoss = () => {
      if (document.visibilityState !== "hidden") return;
      if (screen !== "question" || !assessment || results || integrityTriggeredRef.current) return;

      // Debounce focus loss to avoid accidental triggers
      if (integrityTimeoutRef.current) clearTimeout(integrityTimeoutRef.current);
      
      integrityTimeoutRef.current = setTimeout(() => {
        if (document.visibilityState !== "hidden") return;

        integrityTriggeredRef.current = true;
        const nextRemainingAttempts = Math.max(0, readRemainingAttempts(attemptsStorageKey) - 1);
        writeRemainingAttempts(attemptsStorageKey, nextRemainingAttempts);
        setRemainingAttempts(nextRemainingAttempts);

        const notice: IntegrityNotice = {
          reason: "focus-loss",
          message:
            nextRemainingAttempts > 0
              ? "You switched tabs or windows. This attempt was auto-submitted and one attempt was deducted."
              : "You switched tabs or windows. This attempt was auto-submitted and no attempts remain for this track.",
          remainingAttempts: nextRemainingAttempts,
          recordedAt: Date.now(),
        };

        setIntegrityNotice(notice);
        setShowIntegrityModal(true);
        finishAssessmentEvent({
          automatic: true,
          errorMessage: "Focus changed. Finalising the attempt...",
          keepalive: true,
          notice,
        });
      }, 500);
    };

    document.addEventListener("visibilitychange", handleFocusLoss);
    window.addEventListener("blur", handleFocusLoss);

    return () => {
      document.removeEventListener("visibilitychange", handleFocusLoss);
      window.removeEventListener("blur", handleFocusLoss);
      if (integrityTimeoutRef.current) clearTimeout(integrityTimeoutRef.current);
    };
  }, [assessment, attemptsStorageKey, results, screen]);

  const refillAttempts = () => {
    writeRemainingAttempts(attemptsStorageKey, defaultAttemptLimit);
    setRemainingAttempts(defaultAttemptLimit);
    setError(null);
    integrityTriggeredRef.current = false;
    setIntegrityNotice(null);
  };

  const startAssessment = async () => {
    if (remainingAttempts <= 0) {
      setError("No attempts remain for this assessment track. Use the restore button below to reset your session.");
      return;
    }

    if (!questions.length) {
      setError(`No test material available`);
      return;
    }

    try {
      setIsStarting(true);
      setError(null);
      integrityTriggeredRef.current = false;
      setIntegrityNotice(null);
      setShowIntegrityModal(false);
      const created = await apiFetch<AssessmentRead>("/assessments", {
        method: "POST",
        body: JSON.stringify({
          category,
          assessment_type: assessmentType,
          question_type: effectiveQuestionType,
          skill_id: skillId,
          skill_request_id: skillRequestId,
        }),
      });
      setAssessment(created);
      setCurrentIndex(0);
      setAnswers({});
      setResults(null);
      setScreen("question");
      const nextDeadlineAt = Date.now() + durationMinutes * 60 * 1000;
      setDeadlineAt(nextDeadlineAt);
      setTimeLeft(durationMinutes * 60);
    } catch (caught) {
      let message = "Unable to initialise the assessment.";
      if (caught instanceof ApiError) {
        message = caught.message;
      }
      setError(message);
    } finally {
      setIsStarting(false);
    }
  };

  const selectAnswer = async (optionId: string) => {
    if (!assessment || !currentQuestion || answers[currentQuestion.id]) {
      return;
    }

    const nextAnswers = {
      ...answers,
      [currentQuestion.id]: optionId,
    };
    setAnswers(nextAnswers);

    try {
      const res = await apiFetch<{ 
        assessment_id: string; 
        answers_recorded: number; 
        results?: Array<{ question_id: string; selected_option_id: string; is_correct: boolean; correct_option_id?: string }> 
      }>(`/assessments/${assessment.id}/answers`, {
        method: "POST",
        body: JSON.stringify({
          answers: [
            {
              question_id: currentQuestion.id,
              selected_option_id: optionId,
            },
          ],
        }),
      });

      if (res.results) {
        const answerInfo = res.results.find(r => r.question_id === currentQuestion.id);
        if (answerInfo && answerInfo.correct_option_id) {
          setAnswerCorrectness(prev => ({
            ...prev,
            [currentQuestion.id]: { 
              isCorrect: answerInfo.is_correct, 
              correctOptionId: answerInfo.correct_option_id!
            }
          }));
        }
      }

    } catch (caught) {
      const message = caught instanceof ApiError ? caught.message : "Failed to save the selected answer.";
      setError(message);
      return;
    }

    // Wait slightly longer so the user can see if they got it right/wrong
    window.setTimeout(() => {
      if (currentIndex >= questions.length - 1) {
        void finishAssessment();
        return;
      }
      setCurrentIndex((previous) => previous + 1);
    }, 1500);
  };


  const finishAssessment = async (options: FinishAssessmentOptions = {}) => {
    if (!assessment || isFinishing || results) {
      return;
    }

    try {
      setIsFinishing(true);
      setScreen("submitting"); // ← immediately show loading screen
      if (options.notice) {
        setIntegrityNotice(options.notice);
      }
      setError(options.automatic ? (options.errorMessage ?? "Finalising the attempt...") : null);
      const completion = await apiFetch<AssessmentCompletionResponse>(`/assessments/${assessment.id}/complete`, {
        method: "POST",
        keepalive: options.keepalive,
      });
      setResults(completion);
      setScreen("results");
      setDeadlineAt(null);
      setTimeLeft(0);
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    } catch (caught) {
      const message = caught instanceof ApiError ? caught.message : "Failed to finalise the assessment.";
      setError(message);
      setScreen("question"); // revert so user can retry
    } finally {
      setIsFinishing(false);
    }
  };

  const retryLoad = () => {
    window.location.reload();
  };

  const formattedTime = `${Math.floor(timeLeft / 60)}:${String(timeLeft % 60).padStart(2, "0")}`;
  const timerTone =
    timeLeft <= 120 ? "text-red-400" : timeLeft <= 300 ? "text-amber-400" : "text-emerald-400";

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background px-6 dark:bg-surface-container-lowest">
        <div className="text-center">
          <div className="w-14 h-14 rounded-2xl border border-indigo-500/30 border-t-indigo-400 animate-spin mx-auto mb-5" />
          <p className="text-[11px] font-black uppercase tracking-[0.25em] text-primary mb-2">Synthesizing Question Bank</p>
          <p className="text-[12px] text-on-surface-variant max-w-xs mx-auto">
            AI is calibrating situational vectors and technical items for this track. This usually takes 10-15 seconds.
          </p>
        </div>
      </div>
    );
  }

  if (screen === "intro") {
    return (
      <div className="min-h-screen bg-background px-6 py-8 dark:bg-surface-container-lowest">
        <div className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-4xl items-center justify-center">
          <div className="clay-card w-full rounded-[40px] p-8 text-center md:p-10">
            <div className="mb-8 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-4 py-2 text-[10px] font-black uppercase tracking-[0.25em] text-primary">
              <span className="h-2 w-2 rounded-full bg-primary animate-pulse" />
              CELTM assessment protocol
            </div>
            <h1 className="mb-5 text-4xl font-black tracking-tight text-on-surface md:text-6xl">{title}</h1>
            <p className="mx-auto mb-10 max-w-2xl text-base leading-relaxed text-on-surface-variant md:text-lg">
              Live questions, real scoring persistence, and backend-linked progress updates. This attempt feeds your verified skill graph directly.
            </p>

            <div className="mb-10 grid grid-cols-1 gap-4 md:grid-cols-5">
              {[
                { label: "Question bank", value: `${questions.length} live items` },
                { label: "Scope", value: assessmentLabel },
                { label: "Difficulty", value: difficulty ? toTitleCase(difficulty) : "Adaptive" },
                { label: "Runtime", value: `${durationMinutes} min window` },
                { label: "Attempts left", value: `${remainingAttempts} remaining` },
              ].map((item) => (
                <div
                  key={item.label}
                  className={`lift-tile rounded-3xl border transition-all ${
                    item.label === "Question bank" && questions.length > 0
                      ? "border-emerald-500/30 bg-emerald-500/5"
                      : "border-outline-variant/12 dark:border-transparent bg-surface-container-low"
                  } p-5 text-left`}
                >
                  <p className="mb-2 text-[10px] font-black uppercase tracking-[0.25em] text-on-surface-variant">{item.label}</p>
                  <p className={`text-sm font-bold ${item.label === "Question bank" && questions.length > 0 ? "text-emerald-300" : "text-on-surface"}`}>
                    {item.value}
                  </p>
                </div>
              ))}
            </div>

            <div className="mb-10 rounded-[32px] border border-outline-variant/12 dark:border-transparent bg-surface-container-low p-6 text-left md:p-8">
              <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
                <div>
                  <p className="mb-3 text-[10px] font-black uppercase tracking-[0.2em] text-primary">Assessment logic</p>
                  <p className="text-sm leading-relaxed text-on-surface-variant">
                    Each answer is written to the backend immediately. Completion persists the final score and updates downstream skill signals.
                  </p>
                </div>
                <div>
                  <p className="mb-3 text-[10px] font-black uppercase tracking-[0.2em] text-primary">Timing</p>
                  <p className="text-sm leading-relaxed text-on-surface-variant">
                    The timer is enforced in-session. If it expires, the attempt is auto-completed with whatever has already been recorded.
                  </p>
                </div>
                <div>
                  <p className="mb-3 text-[10px] font-black uppercase tracking-[0.2em] text-primary">Promotion flow</p>
                  <p className="text-sm leading-relaxed text-on-surface-variant">
                    When this is linked to a skill request, the assessment score feeds the promotion gate used by written and interview validation.
                  </p>
                </div>
                <div>
                  <p className="mb-3 text-[10px] font-black uppercase tracking-[0.2em] text-primary">Integrity rule</p>
                  <p className="text-sm leading-relaxed text-on-surface-variant">
                    Switching tabs or windows auto-submits the test, shows an integrity warning, and deducts one remaining attempt for this track.
                  </p>
                </div>
              </div>
            </div>

            {error ? (
              <div className="mb-8 space-y-4">
                <div className="rounded-2xl border border-red-500/25 bg-red-500/10 p-5">
                  <p className="mb-2 text-[10px] font-black uppercase tracking-[0.2em] text-red-300">
                    {error.includes("No test material available") || error.includes("Subject not available") ? "No Test Material Available" : error.includes("No attempts") ? "Attempts Exhausted" : "Assessment Unavailable"}
                  </p>
                  <p className="text-sm leading-relaxed text-red-200">
                    {error}
                  </p>
                </div>
                {error.includes("No attempts") && (
                  <button
                    onClick={refillAttempts}
                    className="w-full flex items-center justify-center gap-2 rounded-2xl bg-emerald-500/15 border border-emerald-500/30 py-3 text-[11px] font-black uppercase tracking-[0.2em] text-emerald-300 transition hover:bg-emerald-500/25"
                  >
                    <span className="material-symbols-outlined text-base">refresh</span>
                    Restore Session Attempts
                  </button>
                )}
                {error.includes("No test material available") || error.includes("Subject not available") ? (
                  <div className="flex gap-3">
                    <button
                      onClick={retryLoad}
                      className="flex-1 flex items-center justify-center gap-2 rounded-2xl bg-indigo-500/10 py-3 text-[11px] font-black uppercase tracking-[0.2em] text-indigo-400 transition hover:bg-indigo-500/20"
                    >
                      <span>Retry</span>
                    </button>
                    <Link
                      href="/assessments"
                      className="flex-1 flex items-center justify-center rounded-2xl bg-surface-container-high py-3 text-[11px] font-black uppercase tracking-[0.2em] text-on-surface-variant transition hover:bg-surface-container"
                    >
                      Back to Assessments
                    </Link>
                  </div>
                ) : null}
                {remainingAttempts <= 0 && !error.includes("No attempts") && (
                  <button
                    onClick={refillAttempts}
                    className="flex w-full items-center justify-center gap-2 rounded-2xl bg-emerald-500/10 py-3 text-[11px] font-black uppercase tracking-[0.2em] text-emerald-400 transition hover:bg-emerald-500/20"
                  >
                    <span className="material-symbols-outlined text-base">refresh</span>
                    Restore Session Attempts
                  </button>
                )}
              </div>
            ) : null}

            <div className="flex flex-col items-center justify-center gap-4 sm:flex-row">
              <Link
                href="/assessments"
                className="rounded-full border border-outline-variant/12 dark:border-transparent px-6 py-3 text-sm font-bold text-on-surface-variant transition-all hover:bg-surface-container-low"
              >
                Back to assessments
              </Link>
              <button
                onClick={() => void startAssessment()}
                disabled={isStarting || !questions.length || remainingAttempts <= 0 || !!error}
                className="rounded-full bg-gradient-to-r from-indigo-500 to-violet-600 px-8 py-3 text-sm font-black uppercase tracking-[0.2em] text-white shadow-xl shadow-indigo-500/20 transition-all hover:scale-[1.02] active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-40"
              >
                {isStarting ? "Initialising..." : error ? (error.includes("No test material available") || error.includes("Subject not available") ? "No Questions" : "Unavailable") : remainingAttempts <= 0 ? "Attempts Exhausted" : !questions.length ? "Loading questions..." : "Begin live attempt"}
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (screen === "submitting") {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-background dark:bg-surface-container-lowest px-6">
        <div className="flex flex-col items-center gap-8 text-center">
          {/* Animated orbit spinner */}
          <div className="relative h-24 w-24">
            <div className="absolute inset-0 rounded-full border-4 border-primary/10" />
            <div className="absolute inset-0 rounded-full border-4 border-transparent border-t-primary animate-spin" />
            <div
              className="absolute inset-2 rounded-full border-4 border-transparent border-t-primary/40 animate-spin"
              style={{ animationDuration: "1.4s", animationDirection: "reverse" }}
            />
            <div className="absolute inset-0 flex items-center justify-center">
              <svg className="h-7 w-7 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
          </div>

          {/* Label */}
          <div className="space-y-2">
            <p className="text-[11px] font-black uppercase tracking-[0.28em] text-primary">
              Submitting Assessment
            </p>
            <h2 className="text-2xl font-extrabold tracking-tight text-on-surface">
              Calculating your results
            </h2>
            <p className="text-sm text-on-surface-variant max-w-xs leading-6">
              Your answers are being scored and your skill profile is updating. This only takes a moment.
            </p>
          </div>

          {/* Animated step indicators */}
          <div className="flex flex-col gap-3 w-full max-w-xs">
            {[
              "Saving your answers",
              "Running AI scoring",
              "Updating skill profile",
            ].map((step, i) => (
              <div
                key={step}
                className="flex items-center gap-3 rounded-2xl bg-surface-container-low px-4 py-3"
                style={{ animation: `fadeIn 0.4s ease ${i * 0.15}s both` }}
              >
                <div className="h-2 w-2 rounded-full bg-primary animate-pulse" style={{ animationDelay: `${i * 0.2}s` }} />
                <span className="text-xs font-bold text-on-surface-variant">{step}</span>
              </div>
            ))}
          </div>
        </div>

        <style>{`
          @keyframes fadeIn {
            from { opacity: 0; transform: translateY(8px); }
            to   { opacity: 1; transform: translateY(0); }
          }
        `}</style>
      </div>
    );
  }

  if (screen === "results" && results) {
    const readinessBand =
      results.score >= 80 ? "Expert" : results.score >= 65 ? "Advanced" : results.score >= 50 ? "Intermediate" : "Developing";

    return (
      <div className="min-h-screen bg-background px-6 py-10 dark:bg-surface-container-lowest">
        <div className="max-w-5xl mx-auto">
          <div className="flex items-center justify-between mb-8">
            <Link href="/assessments" className="text-sm font-bold text-on-surface-variant transition hover:text-on-surface">
              Back to assessments
            </Link>
            <span className="text-[10px] font-black uppercase tracking-[0.25em] text-primary">Assessment complete</span>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
            <div className="clay-card rounded-[32px] p-8">
              <p className="text-[10px] font-black uppercase tracking-[0.25em] text-primary mb-3">Readiness result</p>
              <div className="text-7xl font-black tracking-tighter text-transparent bg-clip-text bg-gradient-to-br from-indigo-400 to-violet-600 mb-3">
                {Math.round(results.score)}%
              </div>
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-400/10 border border-indigo-400/20 text-indigo-300 text-xs font-bold mb-4">
                {readinessBand} band
              </div>
              <p className="text-sm leading-relaxed text-on-surface-variant">
                Score persistence completed. This result is now available to your dashboard projections and role-fit computation.
              </p>
            </div>

            <div className="clay-card rounded-[32px] p-8">
              <p className="text-[10px] font-black uppercase tracking-[0.25em] text-on-surface-variant mb-5">Result breakdown</p>
              <div className="space-y-4">
                {[
                  { label: "Correct answers", value: `${results.correct_answers}/${results.total_questions}` },
                  { label: "Completion state", value: toTitleCase(results.status) },
                  { label: "Track scope", value: assessmentLabel },
                  { label: "Question type", value: toTitleCase(effectiveQuestionType) },
                  { label: "Attempts left", value: `${remainingAttempts}` },
                ].map((row) => (
                  <div key={row.label} className="flex items-center justify-between border-b border-outline-variant/12 dark:border-transparent pb-3 last:border-b-0 last:pb-0">
                    <span className="text-sm text-on-surface-variant">{row.label}</span>
                    <span className="text-sm font-bold text-on-surface">{row.value}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="clay-card rounded-[32px] p-6 md:p-8 mb-8">
            <p className="text-[10px] font-black uppercase tracking-[0.25em] text-primary mb-4">Next actions</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Link href="/dashboard?refresh=1" className="lift-tile rounded-2xl border border-outline-variant/12 dark:border-transparent bg-surface-container-low p-5 transition-all hover:border-primary/20">
                <p className="text-sm font-bold text-on-surface mb-2">Review dashboard impact</p>
                <p className="text-xs leading-relaxed text-on-surface-variant">See how the new assessment score changes your readiness and role-fit projections.</p>
              </Link>
              <Link href="/assessments/written-protocol" className="lift-tile rounded-2xl border border-outline-variant/12 dark:border-transparent bg-surface-container-low p-5 transition-all hover:border-primary/20">
                <p className="text-sm font-bold text-on-surface mb-2">Continue with written validation</p>
                <p className="text-xs leading-relaxed text-on-surface-variant">Pair this result with a written response for fuller competency verification.</p>
              </Link>
            </div>
          </div>

          <div className="flex flex-wrap gap-4">
            <button
              onClick={() => {
                setScreen("intro");
                setAssessment(null);
                setResults(null);
                setAnswers({});
                setCurrentIndex(0);
                setError(null);
                setDeadlineAt(null);
                setIntegrityNotice(null);
                setShowIntegrityModal(false);
                integrityTriggeredRef.current = false;
                clearPersistedAssessmentAttempt(persistedAttemptStorageKey);
              }}
              disabled={remainingAttempts <= 0}
              className="rounded-full border border-outline-variant/12 dark:border-transparent px-6 py-3 text-sm font-bold text-on-surface-variant transition-all hover:bg-surface-container-low disabled:cursor-not-allowed disabled:opacity-40"
            >
              Attempt again
            </button>
            <Link
              href="/assessments"
              className="px-8 py-3 rounded-full bg-gradient-to-r from-indigo-500 to-violet-600 text-white text-sm font-black uppercase tracking-[0.2em] shadow-xl shadow-indigo-500/20 hover:scale-[1.02] active:scale-[0.98] transition-all"
            >
              Return to assessment console
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-on-surface dark:bg-surface-container-lowest">
      <div className="mx-auto max-w-[1520px] px-4 py-6 md:px-5">
        <div className="flex items-center justify-between mb-8 gap-4">
          <div>
            <p className="text-[10px] font-black uppercase tracking-[0.25em] text-primary mb-2">Live assessment feed</p>
            <h1 className="text-2xl md:text-4xl font-black tracking-tight">{title}</h1>
          </div>
          <div className={`text-right ${timerTone}`}>
            <p className="text-[10px] font-black uppercase tracking-[0.25em] mb-1 text-on-surface-variant">Time remaining</p>
            <p className="text-3xl font-black font-mono">{formattedTime}</p>
          </div>
        </div>

        <div className="h-2 rounded-full bg-surface-container-high overflow-hidden mb-8">
          <div
            className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-violet-600 transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-[1.35fr,0.65fr] gap-6">
          <main className="clay-card rounded-[36px] overflow-hidden">
            <div className="px-8 py-6 border-b border-outline-variant/12 dark:border-transparent flex items-center justify-between gap-4">
              <div>
                <p className="text-[10px] font-black uppercase tracking-[0.25em] text-primary mb-2">
                  Question {currentIndex + 1} / {questions.length}
                </p>
                <p className="text-sm text-on-surface-variant">
                  {currentQuestion
                    ? `${toTitleCase(currentQuestion.category)} · ${toTitleCase(currentQuestion.difficulty)} · ${assessmentModeLabel}`
                    : "Awaiting question"}
                </p>
              </div>
              <button
                onClick={() => void finishAssessment()}
                disabled={isFinishing}
                className="px-4 py-2 rounded-full border border-outline-variant/12 dark:border-transparent text-on-surface-variant text-xs font-bold uppercase tracking-[0.2em] hover:bg-surface-container-low transition-all disabled:opacity-40"
              >
                Finish now
              </button>
            </div>

            <div className="px-8 py-8 md:py-10">
              {error ? (
                <div className="rounded-2xl border border-red-500/25 bg-red-500/10 p-4 mb-6 text-sm text-red-200">
                  {error}
                </div>
              ) : null}

              {currentQuestion ? (
                <>
                  {currentQuestion.question_type === "SITUATIONAL" && currentQuestion.scenario ? (
                    <div className="mb-6 rounded-3xl border border-amber-400/15 bg-amber-400/10 p-5">
                      <p className="mb-3 text-[10px] font-black uppercase tracking-[0.2em] text-amber-200">
                        Scenario
                      </p>
                      <p className="text-sm leading-7 text-amber-50/85">
                        {currentQuestion.scenario}
                      </p>
                    </div>
                  ) : null}

                  <h2 className="text-2xl md:text-3xl font-bold tracking-tight leading-tight mb-8">
                    {currentQuestion.question_text}
                  </h2>

                  <div className="grid grid-cols-1 gap-3">
                    {currentQuestion.options.map((option, optionIndex) => {
                      const selected = answers[currentQuestion.id] === option.id;
                      const correctness = answerCorrectness[currentQuestion.id];
                      
                      let containerStyles = "bg-surface-container-low border-outline-variant/12 dark:border-transparent hover:bg-surface-container hover:border-primary/20";
                      let letterStyles = "bg-surface border-outline-variant/12 dark:border-transparent text-on-surface-variant group-hover:text-on-surface";
                      let textStyles = "text-on-surface font-medium";

                      if (correctness) {
                        const isThisOptionCorrect = option.id === correctness.correctOptionId;
                        const isThisOptionSelectedAndWrong = selected && !correctness.isCorrect;

                        if (isThisOptionCorrect) {
                          containerStyles = "bg-emerald-500/15 border-emerald-400/50 shadow-xl shadow-emerald-500/10";
                          letterStyles = "bg-emerald-500 border-emerald-400 text-white";
                          textStyles = "text-emerald-950 dark:text-emerald-300 font-bold";
                        } else if (isThisOptionSelectedAndWrong) {
                          containerStyles = "bg-red-500/15 border-red-400/50 shadow-xl shadow-red-500/10";
                          letterStyles = "bg-red-500 border-red-400 text-white";
                          textStyles = "text-red-950 dark:text-red-300 font-bold";
                        } else {
                          containerStyles = "bg-surface-container-lowest border-outline-variant/5 dark:border-transparent cursor-not-allowed opacity-60";
                          letterStyles = "bg-surface border-outline-variant/5 dark:border-transparent text-on-surface-variant/50";
                          textStyles = "text-on-surface-variant/70 font-medium";
                        }
                      } else if (selected) {
                        containerStyles = "bg-indigo-500/15 border-indigo-400/30 shadow-xl shadow-indigo-500/10";
                        letterStyles = "bg-indigo-500 border-indigo-400 text-white";
                        textStyles = "text-indigo-950 dark:text-white font-bold";
                      }

                      return (
                        <button
                          key={option.id}
                          onClick={() => void selectAnswer(option.id)}
                          disabled={Boolean(answers[currentQuestion.id]) || isFinishing}
                          className={`lift-tile group relative p-6 md:p-8 rounded-[32px] border text-left flex items-start gap-5 transition-all duration-300 ${containerStyles} disabled:cursor-not-allowed`}
                        >
                          <div className={`w-12 h-12 rounded-2xl flex items-center justify-center shrink-0 border text-base font-black transition-all ${letterStyles}`}>
                            {letters[optionIndex] ?? optionIndex + 1}
                          </div>
                          <span className={`text-lg leading-relaxed transition-all ${textStyles}`}>
                            {option.option_text}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </>
              ) : (
                <div className="text-center py-16">
                  <p className="text-on-surface-variant mb-4">No question is currently loaded for this attempt.</p>
                  <button
                    onClick={retryLoad}
                    className="px-6 py-3 rounded-full bg-indigo-500 text-white text-sm font-bold"
                  >
                    Reload
                  </button>
                </div>
              )}
            </div>
          </main>

          <aside className="space-y-6">
            <div className="lift-card rounded-[32px] border border-outline-variant/12 dark:border-transparent bg-surface-container-low p-6">
              <p className="text-[10px] font-black uppercase tracking-[0.25em] text-primary mb-4">Attempt telemetry</p>
              <div className="space-y-4">
                {[
                  { label: "Recorded answers", value: `${answeredCount}/${questions.length}` },
                  { label: "Assessment id", value: assessment?.id ? assessment.id.slice(0, 8) : "Pending" },
                  { label: "Question type", value: effectiveQuestionType },
                  { label: "Track", value: assessmentLabel },
                  { label: "Attempts left", value: `${remainingAttempts}` },
                ].map((row) => (
                  <div key={row.label} className="flex items-center justify-between border-b border-outline-variant/12 dark:border-transparent pb-3 last:border-b-0 last:pb-0">
                    <span className="text-sm text-on-surface-variant">{row.label}</span>
                    <span className="text-sm font-bold text-on-surface">{row.value}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="lift-card rounded-[32px] border border-outline-variant/12 dark:border-transparent bg-surface-container-low p-6">
              <p className="text-[10px] font-black uppercase tracking-[0.25em] text-primary mb-4">Question map</p>
              <div className="grid grid-cols-5 gap-2">
                {questions.map((question, index) => {
                  const answered = Boolean(answers[question.id]);
                  const active = index === currentIndex;
                  return (
                    <div
                      key={question.id}
                      className={`h-10 rounded-2xl flex items-center justify-center text-xs font-black border transition-all ${
                        active
                          ? "bg-indigo-500 text-white border-indigo-400"
                          : answered
                            ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/20"
                            : "bg-surface text-on-surface-variant border-outline-variant/12 dark:border-transparent"
                      }`}
                    >
                      {index + 1}
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="lift-card rounded-[32px] border border-outline-variant/12 dark:border-transparent bg-surface-container-low p-6">
              <p className="text-[10px] font-black uppercase tracking-[0.25em] text-primary mb-4">Protocol notes</p>
              <div className="space-y-3 text-sm text-on-surface-variant leading-relaxed">
                <p>Each submission is written to the backend in real time. Leaving and returning to the page restores the live attempt instead of resetting it.</p>
                <p>This attempt contributes directly to skill verification and downstream readiness projections.</p>
                <p>Switching tabs or windows now triggers an automatic submission and deducts one remaining attempt for this track.</p>
              </div>
            </div>
          </aside>
        </div>
      </div>

      {showIntegrityModal && integrityNotice ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/55 px-6">
          <div
            role="dialog"
            aria-modal="true"
            className="w-full max-w-xl rounded-[32px] border border-red-500/20 bg-surface-container-low p-8 shadow-2xl shadow-black/40"
          >
            <p className="mb-3 text-[10px] font-black uppercase tracking-[0.25em] text-red-300">
              Assessment integrity triggered
            </p>
            <h2 className="mb-4 text-2xl font-black tracking-tight text-on-surface">
              Tab or window switch detected
            </h2>
            <p className="mb-6 text-sm leading-7 text-on-surface-variant">
              {integrityNotice.message}
            </p>
            <div className="mb-6 rounded-3xl border border-outline-variant/12 dark:border-transparent bg-background/60 p-5">
              <div className="flex items-center justify-between gap-4">
                <span className="text-sm text-on-surface-variant">Remaining attempts</span>
                <span className="text-lg font-black text-on-surface">{integrityNotice.remainingAttempts}</span>
              </div>
            </div>
            <div className="flex justify-end">
              <button
                onClick={() => setShowIntegrityModal(false)}
                className="rounded-full bg-gradient-to-r from-indigo-500 to-violet-600 px-6 py-3 text-sm font-black uppercase tracking-[0.2em] text-white shadow-xl shadow-indigo-500/20 transition-all hover:scale-[1.02] active:scale-[0.98]"
              >
                Understood
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function AssessmentQuizFallback() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-6 dark:bg-surface-container-lowest">
      <div className="text-center">
        <div className="w-14 h-14 rounded-2xl border border-indigo-500/30 border-t-indigo-400 animate-spin mx-auto mb-5" />
        <p className="text-[11px] font-black uppercase tracking-[0.25em] text-on-surface-variant">
          Loading assessment shell
        </p>
      </div>
    </div>
  );
}

export default function AssessmentQuizPage() {
  return (
    <Suspense fallback={<AssessmentQuizFallback />}>
      <AssessmentQuizPageContent />
    </Suspense>
  );
}
