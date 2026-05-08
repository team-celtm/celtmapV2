"use client";

import { Suspense, useEffect, useEffectEvent, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ApiError, apiFetch } from "@/lib/api";
import type {
  ArtifactRead,
  PlagiarismReportRead,
  RoleFitRead,
  WrittenAssessmentRead,
} from "@/lib/celtm";
import { formatDateTime, formatPercent, formatRelativeTime, toTitleCase } from "@/lib/celtm";

type Mode = "choose" | "editor" | "upload";
type EvaluatorMode = "teacher" | "liberal_ai" | "strict_ai";
type CompletionSummary = {
  session: WrittenAssessmentRead;
  roleFit: RoleFitRead | null;
};

const evaluatorModes: Array<{
  value: EvaluatorMode;
  label: string;
  description: string;
}> = [
  {
    value: "teacher",
    label: "Teacher",
    description: "Balanced marking focused on clarity, correctness, and reasoning.",
  },
  {
    value: "liberal_ai",
    label: "Liberal AI",
    description: "Gives more credit for partial correctness and promising structure.",
  },
  {
    value: "strict_ai",
    label: "Strict AI",
    description: "Penalizes shallow detail and weak validation more aggressively.",
  },
];

function resolveEvaluatorMode(session: WrittenAssessmentRead | null): EvaluatorMode {
  const stored = session?.metadata?.evaluator_mode;
  if (stored === "liberal_ai" || stored === "strict_ai" || stored === "teacher") {
    return stored;
  }
  return "teacher";
}

function readStringList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.filter((item): item is string => typeof item === "string" && item.trim().length > 0);
}

function readPlagiarismReport(value: unknown): PlagiarismReportRead | null {
  if (!value || typeof value !== "object") {
    return null;
  }

  const candidate = value as Partial<PlagiarismReportRead>;
  return {
    risk_score: typeof candidate.risk_score === "number" ? candidate.risk_score : 0,
    risk_level:
      typeof candidate.risk_level === "string" && candidate.risk_level.trim()
        ? candidate.risk_level
        : "low",
    summary:
      typeof candidate.summary === "string" && candidate.summary.trim()
        ? candidate.summary
        : "No plagiarism summary available.",
    signals: readStringList(candidate.signals),
  };
}

function WrittenProtocolPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const skillId = searchParams.get("skillId");
  const skillRequestId = searchParams.get("skillRequestId");
  const title = searchParams.get("title") ?? "Written Case Assessment";
  const initialEvaluator = searchParams.get("evaluatorMode");

  const [mode, setMode] = useState<Mode>("choose");
  const [evaluatorMode, setEvaluatorMode] = useState<EvaluatorMode>(
    initialEvaluator === "liberal_ai" || initialEvaluator === "strict_ai"
      ? initialEvaluator
      : "teacher",
  );
  const [session, setSession] = useState<WrittenAssessmentRead | null>(null);
  const [submissionText, setSubmissionText] = useState("");
  const [notes, setNotes] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadedArtifact, setUploadedArtifact] = useState<ArtifactRead | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [completionSummary, setCompletionSummary] = useState<CompletionSummary | null>(null);

  const autosaveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const completionPopupRef = useRef<string | null>(null);

  const prompt =
    session?.prompt ??
    `Prepare a concise technical analysis for "${title}" covering root cause, affected surface, remediation, and hardening recommendations.`;

  useEffect(() => {
    if (session) {
      setEvaluatorMode(resolveEvaluatorMode(session));
    }
  }, [session]);

  const persistSubmissionEvent = useEffectEvent((content: string) => {
    void persistSubmission(content, { silent: true });
  });

  const sessionId = session?.id;
  const sessionStatus = session?.status;

  const openCompletionSummaryEvent = useEffectEvent(
    async (completedSession: WrittenAssessmentRead) => {
      if (completedSession.status !== "completed") {
        return;
      }

      if (completionPopupRef.current === completedSession.id) {
        return;
      }

      completionPopupRef.current = completedSession.id;

      let roleFit: RoleFitRead | null = null;
      try {
        roleFit = await apiFetch<RoleFitRead>("/skills/me/role-fit", {
          cache: "no-store",
          skipCache: true,
        });
      } catch {
        roleFit = null;
      }

      setCompletionSummary({
        session: completedSession,
        roleFit,
      });

      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("celtm-assessment-log-refresh"));
      }
    },
  );

  useEffect(() => {
    if (!sessionId || sessionStatus !== "processing") {
      return;
    }

    let cancelled = false;
    let timeoutId: ReturnType<typeof setTimeout> | null = null;

    const pollSession = async () => {
      try {
        const latest = (await apiFetch(`/written-assessments/${sessionId}`, {
          cache: "no-store",
          skipCache: true,
        })) as WrittenAssessmentRead;

        if (cancelled) {
          return;
        }

        setSession(latest);
        if (latest.submission_text) {
          setSubmissionText(latest.submission_text);
        }

        if (latest.status === "completed") {
          await openCompletionSummaryEvent(latest);
        }

        if (latest.status === "processing") {
          timeoutId = setTimeout(() => {
            void pollSession();
          }, 1500);
          return;
        }

        if (latest.status === "failed") {
          setError("Written assessment evaluation failed. Review the draft and resubmit.");
        }
      } catch (caught) {
        if (cancelled) {
          return;
        }

        const message =
          caught instanceof ApiError
            ? caught.message
            : "Failed to refresh the written assessment status.";
        setError(message);
      }
    };

    timeoutId = setTimeout(() => {
      void pollSession();
    }, 1500);

    return () => {
      cancelled = true;
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
    };
  }, [sessionId, sessionStatus]);

  useEffect(() => {
    if (!session || session.status !== "completed") {
      return;
    }

    void openCompletionSummaryEvent(session);
  }, [session]);

  const ensureSession = async () => {
    if (session) {
      return session;
    }

    const created = await apiFetch<WrittenAssessmentRead>("/written-assessments", {
      method: "POST",
      body: JSON.stringify({
        skill_id: skillId,
        skill_request_id: skillRequestId,
        evaluator_mode: evaluatorMode,
      }),
    });
    setSession(created);
    setSubmissionText(created.submission_text ?? "");
    setEvaluatorMode(resolveEvaluatorMode(created));
    return created;
  };

  const openMode = async (nextMode: Exclude<Mode, "choose">) => {
    try {
      setIsLoading(true);
      setError(null);
      const activeSession = await ensureSession();
      if (activeSession.submission_text && !submissionText) {
        setSubmissionText(activeSession.submission_text);
      }
      setMode(nextMode);
    } catch (caught) {
      const message =
        caught instanceof ApiError
          ? caught.message
          : "Unable to initialise the written protocol session.";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  const persistSubmission = async (
    content: string,
    options: {
      silent?: boolean;
    } = {},
  ) => {
    if (!session) {
      return;
    }

    const normalizedContent = content.trim();
    const currentSubmission = session.submission_text ?? "";

    if (!normalizedContent) {
      if (!options.silent) {
        setError("Add at least 20 characters before saving the written response.");
      }
      return;
    }

    if (normalizedContent.length < 20) {
      if (!options.silent) {
        setError("Written responses need at least 20 characters before they can be saved.");
      }
      return;
    }

    if (normalizedContent === currentSubmission.trim()) {
      return;
    }

    try {
      setIsSaving(true);
      if (!options.silent) {
        setError(null);
      }
      const updated = await apiFetch<WrittenAssessmentRead>(
        `/written-assessments/${session.id}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            submission_text: content,
            evaluator_mode: evaluatorMode,
          }),
        },
      );
      setSession(updated);
      setSubmissionText(updated.submission_text ?? content);
    } catch (caught) {
      const message =
        caught instanceof ApiError
          ? caught.message
          : "Failed to save the written response.";
      setError(message);
    } finally {
      setIsSaving(false);
    }
  };

  useEffect(() => {
    if (mode !== "editor" || !session) {
      return;
    }

    if (!submissionText.trim() || submissionText.trim().length < 20) {
      return;
    }

    if (autosaveTimeoutRef.current) {
      clearTimeout(autosaveTimeoutRef.current);
    }

    autosaveTimeoutRef.current = setTimeout(() => {
      persistSubmissionEvent(submissionText);
    }, 900);

    return () => {
      if (autosaveTimeoutRef.current) {
        clearTimeout(autosaveTimeoutRef.current);
      }
    };
  }, [mode, session, submissionText, evaluatorMode]);

  const uploadArtifact = async () => {
    if (!selectedFile) {
      return null;
    }

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);
      formData.append("file_type", "written_assessment");

      const artifact = await apiFetch<ArtifactRead>("/profile/me/artifacts", {
        method: "POST",
        body: formData,
      });
      setUploadedArtifact(artifact);
      return artifact;
    } catch (caught) {
      const message = caught instanceof ApiError ? caught.message : "Upload failed. Please try a smaller file or different format.";
      setError(message);
      return null;
    }
  };

  const submitProtocol = async () => {
    try {
      setIsSubmitting(true);
      setError(null);
      completionPopupRef.current = null;
      setCompletionSummary(null);

      const activeSession = await ensureSession();
      let content = submissionText.trim();

      if (mode === "upload") {
        const artifact = await uploadArtifact();
        content = [
          "Uploaded written evidence submitted through CELTM upload flow.",
          artifact ? `Artifact: ${artifact.file_name}` : "",
          notes.trim(),
        ]
          .filter(Boolean)
          .join("\n\n");
      }

      if (!content || content.trim().length < 20) {
        setError("Add a detailed written response or upload evidence notes (minimum 20 characters) before submitting.");
        setIsSubmitting(false);
        return;
      }

      const saved = await apiFetch<WrittenAssessmentRead>(
        `/written-assessments/${activeSession.id}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            submission_text: content,
            evaluator_mode: evaluatorMode,
          }),
        },
      );
      setSession(saved);

      const completed = await apiFetch<WrittenAssessmentRead>(
        `/written-assessments/${activeSession.id}/complete`,
        {
          method: "POST",
        },
      );
      setSession(completed);
      setSubmissionText(completed.submission_text ?? content);
    } catch (caught) {
      console.error("Written assessment submit failed:", caught);
      const message =
        caught instanceof ApiError
          ? caught.message
          : "Failed to submit. Please check your connection or try again.";
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const statusLabel = session ? toTitleCase(session.status) : "Not started";
  const activeEvaluator = evaluatorModes.find((item) => item.value === evaluatorMode);
  const evaluationInsights = readStringList(
    session?.metadata?.insights ?? session?.metadata?.strengths,
  );
  const evaluationLoopholes = readStringList(
    session?.metadata?.loopholes ?? session?.metadata?.risks,
  );
  const evaluationRecommendations = readStringList(session?.metadata?.recommendations);
  const plagiarismReport = readPlagiarismReport(session?.metadata?.plagiarism);
  const sessionReadinessScore =
    typeof session?.metadata?.readiness_score === "number"
      ? session.metadata.readiness_score
      : null;
  const sessionRoleName =
    typeof session?.metadata?.role_name === "string" && session.metadata.role_name.trim().length > 0
      ? session.metadata.role_name
      : null;
  const completionInsights = completionSummary
    ? readStringList(
        completionSummary.session.metadata?.insights ??
          completionSummary.session.metadata?.strengths,
      )
    : [];
  const completionLoopholes = completionSummary
    ? readStringList(
        completionSummary.session.metadata?.loopholes ??
          completionSummary.session.metadata?.risks,
      )
    : [];
  const completionRecommendations = completionSummary
    ? readStringList(completionSummary.session.metadata?.recommendations)
    : [];
  const completionPlagiarism = completionSummary
    ? readPlagiarismReport(completionSummary.session.metadata?.plagiarism)
    : null;
  const completionReadinessScore =
    completionSummary && typeof completionSummary.session.metadata?.readiness_score === "number"
      ? completionSummary.session.metadata.readiness_score
      : null;
  const completionRoleName =
    completionSummary &&
    typeof completionSummary.session.metadata?.role_name === "string" &&
    completionSummary.session.metadata.role_name.trim().length > 0
      ? completionSummary.session.metadata.role_name
      : null;

  if (mode === "choose") {
    return (
      <div className="mx-auto w-full max-w-[1320px] space-y-6 pb-8 page-fade-in">
        <section className="clay-card rounded-[30px] p-6 md:p-7">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className="text-[11px] font-black uppercase tracking-[0.22em] text-primary">
                Written assessment
              </p>
              <h1 className="mt-2 text-3xl font-extrabold tracking-tight text-on-surface md:text-4xl">
                {title}
              </h1>
              <p className="mt-3 text-sm leading-7 text-on-surface-variant">
                Choose how you want to submit the response, then select how the evaluator
                should grade it. Drafts persist to the backend and final scoring runs
                asynchronously.
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-3 lg:w-[30rem]">
              {[
                { label: "Status", value: statusLabel },
                {
                  label: "Evaluator",
                  value: activeEvaluator?.label ?? "Teacher",
                },
                {
                  label: "Last update",
                  value: session?.updated_at
                    ? formatRelativeTime(session.updated_at)
                    : "New draft",
                },
              ].map((item) => (
                <div
                  key={item.label}
                  className="rounded-3xl bg-surface-container-low px-4 py-4"
                >
                  <p className="text-[10px] font-black uppercase tracking-[0.2em] text-on-surface-variant">
                    {item.label}
                  </p>
                  <p className="mt-2 text-lg font-extrabold tracking-tight text-on-surface">
                    {item.value}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {error ? (
          <div className="rounded-2xl border border-red-500/20 bg-red-500/10 px-5 py-4 text-sm text-red-400">
            {error}
          </div>
        ) : null}

        <section className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
          <div className="clay-card rounded-[30px] p-6">
            <h2 className="text-xl font-bold tracking-tight text-on-surface">
              Evaluation mode
            </h2>
            <p className="mt-2 text-sm leading-6 text-on-surface-variant">
              This setting changes how the backend evaluates your final answer.
            </p>

            <div className="mt-5 space-y-3">
              {evaluatorModes.map((item) => {
                const selected = evaluatorMode === item.value;
                return (
                  <button
                    key={item.value}
                    type="button"
                    onClick={() => setEvaluatorMode(item.value)}
                    className={`w-full rounded-3xl border px-4 py-4 text-left transition ${
                      selected
                        ? "border-primary/30 bg-primary/10"
                        : "border-outline-variant/12 dark:border-transparent bg-surface-container-low hover:border-primary/20"
                    }`}
                  >
                    <p className="text-sm font-bold text-on-surface">{item.label}</p>
                    <p className="mt-2 text-sm leading-6 text-on-surface-variant">
                      {item.description}
                    </p>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="clay-card rounded-[30px] p-6">
            <h2 className="text-xl font-bold tracking-tight text-on-surface">
              Submission method
            </h2>
            <p className="mt-2 text-sm leading-6 text-on-surface-variant">
              Keep the old card-based flow: choose the response channel first, then open the
              assessment workspace.
            </p>

            <div className="mt-5 grid gap-4 md:grid-cols-2">
              <button
                onClick={() => void openMode("editor")}
                disabled={isLoading}
                className="rounded-[28px] border border-outline-variant/12 dark:border-transparent bg-surface-container-low p-6 text-left transition hover:border-primary/25 disabled:opacity-50"
              >
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-primary">
                  Digital editor
                </p>
                <h3 className="mt-3 text-xl font-bold text-on-surface">Write inside CELTM</h3>
                <p className="mt-2 text-sm leading-6 text-on-surface-variant">
                  Use the built-in editor with autosave and final asynchronous scoring.
                </p>
              </button>

              <button
                onClick={() => void openMode("upload")}
                disabled={isLoading}
                className="rounded-[28px] border border-outline-variant/12 dark:border-transparent bg-surface-container-low p-6 text-left transition hover:border-primary/25 disabled:opacity-50"
              >
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-primary">
                  Analog upload
                </p>
                <h3 className="mt-3 text-xl font-bold text-on-surface">
                  Upload external evidence
                </h3>
                <p className="mt-2 text-sm leading-6 text-on-surface-variant">
                  Attach PDF or image-based work, then add notes for the evaluator.
                </p>
              </button>
            </div>

            <div className="mt-5 flex justify-start">
              <Link
                href="/assessments"
                className="inline-flex rounded-full bg-surface-container-high px-4 py-2 text-[11px] font-black uppercase tracking-[0.18em] text-on-surface"
              >
                Back to assessments
              </Link>
            </div>
          </div>
        </section>
      </div>
    );
  }

  if (isSubmitting) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-background dark:bg-surface-container-lowest px-6">
        <div className="flex flex-col items-center gap-8 text-center">
          {/* Orbit spinner */}
          <div className="relative h-24 w-24">
            <div className="absolute inset-0 rounded-full border-4 border-primary/10" />
            <div className="absolute inset-0 rounded-full border-4 border-transparent border-t-primary animate-spin" />
            <div
              className="absolute inset-2 rounded-full border-4 border-transparent border-t-primary/40 animate-spin"
              style={{ animationDuration: "1.4s", animationDirection: "reverse" }}
            />
            <div className="absolute inset-0 flex items-center justify-center">
              <svg className="h-7 w-7 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
            </div>
          </div>

          <div className="space-y-2">
            <p className="text-[11px] font-black uppercase tracking-[0.28em] text-primary">
              Submitting Written Assessment
            </p>
            <h2 className="text-2xl font-extrabold tracking-tight text-on-surface">
              Evaluating your response
            </h2>
            <p className="text-sm text-on-surface-variant max-w-xs leading-6">
              Your submission is being processed and scored. This may take a few seconds.
            </p>
          </div>

          <div className="flex flex-col gap-3 w-full max-w-xs">
            {["Uploading response", "Running evaluation", "Updating skill profile"].map((step, i) => (
              <div
                key={step}
                className="flex items-center gap-3 rounded-2xl bg-surface-container-low px-4 py-3"
                style={{ animation: `fadein 0.4s ease \s both` }}
              >
                <div className="h-2 w-2 rounded-full bg-primary animate-pulse" style={{ animationDelay: `\s` }} />
                <span className="text-xs font-bold text-on-surface-variant">{step}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-[1480px] space-y-6 pb-8">
      <section className="clay-card rounded-[30px] p-6 md:p-7">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <p className="text-[11px] font-black uppercase tracking-[0.22em] text-primary">
              Assessment canvas
            </p>
            <h1 className="mt-2 text-3xl font-extrabold tracking-tight text-on-surface">
              {title}
            </h1>
            <p className="mt-3 text-sm leading-7 text-on-surface-variant">
              Prompt-driven written validation with autosave, evaluator selection, and async
              scoring.
            </p>
          </div>

          <div className="flex flex-wrap gap-3">
            <button
              onClick={() => setMode("editor")}
              className={`inline-flex rounded-full px-4 py-2 text-[11px] font-black uppercase tracking-[0.18em] ${
                mode === "editor"
                  ? "bg-primary text-white"
                  : "bg-surface-container-high text-on-surface"
              }`}
            >
              Editor
            </button>
            <button
              onClick={() => setMode("upload")}
              className={`inline-flex rounded-full px-4 py-2 text-[11px] font-black uppercase tracking-[0.18em] ${
                mode === "upload"
                  ? "bg-primary text-white"
                  : "bg-surface-container-high text-on-surface"
              }`}
            >
              Upload
            </button>
            <Link
              href="/assessments"
              className="inline-flex rounded-full bg-surface-container-high px-4 py-2 text-[11px] font-black uppercase tracking-[0.18em] text-on-surface"
            >
              Back
            </Link>
            <button
              onClick={() => void submitProtocol()}
              disabled={isSubmitting || isLoading}
              className="inline-flex rounded-full bg-primary px-5 py-2 text-[11px] font-black uppercase tracking-[0.18em] text-white disabled:opacity-50"
            >
              {isSubmitting ? "Submitting..." : "Submit assessment"}
            </button>
          </div>
        </div>
      </section>

      {error ? (
        <div className="rounded-2xl border border-red-500/20 bg-red-500/10 px-5 py-4 text-sm text-red-400">
          {error}
        </div>
      ) : null}

      <section className="grid gap-6 xl:grid-cols-[0.78fr_1.22fr]">
        <div className="space-y-6">
          <div className="clay-card rounded-[30px] p-6">
            <h2 className="text-xl font-bold tracking-tight text-on-surface">Prompt</h2>
            <div className="mt-4 rounded-3xl border border-outline-variant/12 dark:border-transparent bg-surface-container-low p-5">
              <div className="whitespace-pre-wrap text-sm leading-7 text-on-surface-variant">
                {prompt}
              </div>
            </div>
          </div>

          <div className="clay-card rounded-[30px] p-6">
            <h2 className="text-xl font-bold tracking-tight text-on-surface">
              Evaluator mode
            </h2>
            <div className="mt-4 space-y-3">
              {evaluatorModes.map((item) => {
                const selected = evaluatorMode === item.value;
                return (
                  <button
                    key={item.value}
                    type="button"
                    onClick={() => setEvaluatorMode(item.value)}
                    className={`w-full rounded-3xl border px-4 py-4 text-left transition ${
                      selected
                        ? "border-primary/30 bg-primary/10"
                        : "border-outline-variant/12 dark:border-transparent bg-surface-container-low hover:border-primary/20"
                    }`}
                  >
                    <p className="text-sm font-bold text-on-surface">{item.label}</p>
                    <p className="mt-2 text-sm leading-6 text-on-surface-variant">
                      {item.description}
                    </p>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="clay-card rounded-[30px] p-6">
            <h2 className="text-xl font-bold tracking-tight text-on-surface">
              Session details
            </h2>
            <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {[
                {
                  label: "Status",
                  value: statusLabel,
                },
                {
                  label: "Score",
                  value: session?.score != null ? `${Math.round(session.score)}%` : "Pending",
                },
                {
                  label: "Created",
                  value: session?.created_at
                    ? formatDateTime(session.created_at)
                    : "Not started",
                },
                {
                  label: "Updated",
                  value: session?.updated_at
                    ? formatRelativeTime(session.updated_at)
                    : "No edits yet",
                },
                {
                  label: "Readiness",
                  value: sessionReadinessScore != null ? formatPercent(sessionReadinessScore) : "Pending",
                },
                {
                  label: "Role fit",
                  value: sessionRoleName || "Not updated yet",
                },
              ].map((item) => (
                <div
                  key={item.label}
                  className="rounded-2xl bg-surface-container-low px-4 py-4"
                >
                  <p className="text-[10px] font-black uppercase tracking-[0.2em] text-on-surface-variant">
                    {item.label}
                  </p>
                  <p className="mt-2 text-sm font-bold text-on-surface">{item.value}</p>
                </div>
              ))}
            </div>

            {session?.feedback ? (
              <div className="mt-4 rounded-3xl border border-emerald-500/15 bg-emerald-500/5 p-4">
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-emerald-500">
                  Evaluator feedback
                </p>
                <p className="mt-2 text-sm leading-6 text-on-surface-variant">
                  {session.feedback}
                </p>
              </div>
            ) : null}

            {evaluationInsights.length > 0 ||
            evaluationLoopholes.length > 0 ||
            evaluationRecommendations.length > 0 ? (
              <div className="mt-4 grid gap-4 xl:grid-cols-3">
                <div className="rounded-3xl border border-primary/15 bg-primary/5 p-4">
                  <p className="text-[10px] font-black uppercase tracking-[0.2em] text-primary">
                    Insights
                  </p>
                  <ul className="mt-3 space-y-2 text-sm leading-6 text-on-surface-variant">
                    {evaluationInsights.length > 0 ? (
                      evaluationInsights.map((item) => <li key={item}>{item}</li>)
                    ) : (
                      <li>No specific strengths were returned yet.</li>
                    )}
                  </ul>
                </div>

                <div className="rounded-3xl border border-amber-500/15 bg-amber-500/5 p-4">
                  <p className="text-[10px] font-black uppercase tracking-[0.2em] text-amber-500">
                    Loopholes
                  </p>
                  <ul className="mt-3 space-y-2 text-sm leading-6 text-on-surface-variant">
                    {evaluationLoopholes.length > 0 ? (
                      evaluationLoopholes.map((item) => <li key={item}>{item}</li>)
                    ) : (
                      <li>No major risks were returned yet.</li>
                    )}
                  </ul>
                </div>

                <div className="rounded-3xl border border-blue-500/15 bg-blue-500/5 p-4">
                  <p className="text-[10px] font-black uppercase tracking-[0.2em] text-blue-500">
                    Next improvements
                  </p>
                  <ul className="mt-3 space-y-2 text-sm leading-6 text-on-surface-variant">
                    {evaluationRecommendations.length > 0 ? (
                      evaluationRecommendations.map((item) => <li key={item}>{item}</li>)
                    ) : (
                      <li>No follow-up recommendations were returned yet.</li>
                    )}
                  </ul>
                </div>
              </div>
            ) : null}

            {plagiarismReport ? (
              <div className="mt-4 rounded-3xl border border-rose-500/15 bg-rose-500/5 p-4">
                <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                  <div>
                    <p className="text-[10px] font-black uppercase tracking-[0.2em] text-rose-500">
                      Plagiarism risk
                    </p>
                    <p className="mt-2 text-sm leading-6 text-on-surface-variant">
                      {plagiarismReport.summary}
                    </p>
                  </div>
                  <div className="rounded-2xl bg-surface px-4 py-3 text-center shadow-inner ring-1 ring-outline-variant/5">
                    <p className="text-[10px] font-black uppercase tracking-[0.2em] text-on-surface-variant">
                      Risk
                    </p>
                    <p className="mt-2 text-sm font-extrabold uppercase tracking-tight text-on-surface">
                      {plagiarismReport.risk_level}
                    </p>
                    <p className="mt-1 text-xs font-semibold text-rose-500">
                      {formatPercent(plagiarismReport.risk_score)}
                    </p>
                  </div>
                </div>

                {plagiarismReport.signals.length > 0 ? (
                  <ul className="mt-3 space-y-2 text-sm leading-6 text-on-surface-variant">
                    {plagiarismReport.signals.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                ) : null}
              </div>
            ) : null}
          </div>
        </div>

        <div className="clay-card rounded-[30px] p-6">
          <div className="mb-5 flex items-center justify-between gap-4">
            <div>
              <h2 className="text-xl font-bold tracking-tight text-on-surface">
                {mode === "editor" ? "Written response" : "Upload written evidence"}
              </h2>
              <p className="mt-1 text-sm text-on-surface-variant">
                {isSaving
                  ? "Saving draft..."
                  : session?.updated_at
                    ? `Saved ${formatRelativeTime(session.updated_at)}`
                    : "Draft not saved yet"}
              </p>
            </div>
            {mode === "editor" ? (
              <button
                type="button"
                onClick={() => void persistSubmission(submissionText)}
                disabled={isSaving || !session}
                className="inline-flex rounded-full bg-surface-container-high px-4 py-2 text-[11px] font-black uppercase tracking-[0.18em] text-on-surface disabled:opacity-50"
              >
                Save now
              </button>
            ) : null}
          </div>

          {mode === "editor" ? (
            <textarea
              value={submissionText}
              onChange={(event) => setSubmissionText(event.target.value)}
              placeholder="Write your response here. The draft autosaves to your written-assessment session."
              className="min-h-[640px] w-full resize-none rounded-[28px] border border-outline-variant/12 dark:border-transparent bg-surface-container-low px-5 py-5 text-sm leading-7 text-on-surface outline-none"
            />
          ) : (
            <div className="space-y-5">
              <div className="rounded-[28px] border border-outline-variant/12 dark:border-transparent bg-surface-container-low p-5">
                <div className="flex flex-wrap items-center justify-between gap-4">
                  <div>
                    <p className="text-sm font-bold text-on-surface">
                      {selectedFile ? selectedFile.name : "No file selected yet"}
                    </p>
                    <p className="mt-1 text-xs text-on-surface-variant">
                      {selectedFile
                        ? `${(selectedFile.size / 1024 / 1024).toFixed(2)} MB staged for upload`
                        : "Accepted formats: PNG, JPG, PDF"}
                    </p>
                  </div>
                  <label className="inline-flex cursor-pointer rounded-full bg-primary px-4 py-2 text-[11px] font-black uppercase tracking-[0.18em] text-white">
                    Select file
                    <input
                      type="file"
                      accept="image/*,.pdf"
                      className="hidden"
                      onChange={(event) =>
                        setSelectedFile(event.target.files?.[0] ?? null)
                      }
                    />
                  </label>
                </div>
              </div>

              <textarea
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                placeholder="Add evaluator notes, context, or a typed summary of the uploaded evidence."
                className="min-h-[260px] w-full resize-none rounded-[28px] border border-outline-variant/12 dark:border-transparent bg-surface-container-low px-5 py-5 text-sm leading-7 text-on-surface outline-none"
              />

              {uploadedArtifact ? (
                <div className="rounded-2xl border border-emerald-500/15 bg-emerald-500/5 p-4">
                  <p className="text-sm font-bold text-emerald-500">Artifact synced</p>
                  <p className="mt-1 text-xs text-on-surface-variant">
                    {uploadedArtifact.file_name}
                  </p>
                </div>
              ) : null}
            </div>
          )}
        </div>
      </section>

      {completionSummary ? (
        <div className="fixed inset-0 z-[75] flex items-center justify-center bg-black/60 px-4 backdrop-blur-sm">
          <div className="max-h-[90vh] w-full max-w-4xl overflow-y-auto rounded-[40px] border border-outline-variant/12 dark:border-transparent bg-surface-container p-8 shadow-3xl md:p-10">
            <div className="flex items-start justify-between gap-6">
              <div className="flex-1">
                <p className="text-[11px] font-black uppercase tracking-[0.22em] text-primary">
                  Written assessment submitted
                </p>
                <h2 className="mt-3 text-3xl font-extrabold tracking-tight text-on-surface">
                  {title}
                </h2>
                <p className="mt-3 text-sm leading-7 text-on-surface-variant">
                  The evaluator has finished scoring this response. The same result is now
                  available again from the dashboard exam log.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setCompletionSummary(null)}
                className="flex h-10 w-10 items-center justify-center rounded-full border border-outline-variant/20 bg-surface-container-high transition hover:bg-surface-container-highest"
                aria-label="Close submission summary"
              >
                <span className="text-xl">&times;</span>
              </button>
            </div>

            <div className="mt-8 grid gap-4 md:grid-cols-3">
              <div className="rounded-3xl bg-surface p-5 shadow-inner ring-1 ring-outline-variant/5">
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-on-surface-variant">
                  Assessment score
                </p>
                <p className="mt-3 text-4xl font-extrabold tracking-tight text-on-surface">
                  {completionSummary.session.score != null
                    ? formatPercent(completionSummary.session.score)
                    : "--"}
                </p>
              </div>

              <div className="rounded-3xl bg-surface p-5 shadow-inner ring-1 ring-outline-variant/5">
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-on-surface-variant">
                  Updated readiness
                </p>
                <p className="mt-3 text-4xl font-extrabold tracking-tight text-on-surface">
                  {completionSummary.roleFit?.fit_score != null
                    ? formatPercent(completionSummary.roleFit.fit_score)
                    : completionReadinessScore != null
                      ? formatPercent(completionReadinessScore)
                      : "--"}
                </p>
                <p className="mt-2 text-xs uppercase tracking-[0.18em] text-primary">
                  {completionSummary.roleFit?.role_name ||
                    completionRoleName ||
                    "Role fit snapshot"}
                </p>
              </div>

              <div className="rounded-3xl bg-surface p-5 shadow-inner ring-1 ring-outline-variant/5">
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-on-surface-variant">
                  Plagiarism risk
                </p>
                <p className="mt-3 text-4xl font-extrabold tracking-tight text-on-surface">
                  {completionPlagiarism?.risk_score != null
                    ? formatPercent(completionPlagiarism.risk_score)
                    : "--"}
                </p>
                <p className="mt-2 text-xs uppercase tracking-[0.18em] text-rose-500">
                  {completionPlagiarism?.risk_level || "No check"}
                </p>
              </div>
            </div>

            <div className="mt-8 rounded-3xl bg-primary/5 p-6">
              <p className="text-[10px] font-black uppercase tracking-[0.2em] text-primary">
                Evaluator feedback
              </p>
              <p className="mt-3 text-sm leading-7 text-on-surface-variant">
                {completionSummary.session.feedback || "No evaluator summary returned yet."}
              </p>
            </div>

            {completionPlagiarism ? (
              <div className="mt-4 rounded-3xl border border-rose-500/15 bg-rose-500/5 p-6">
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-rose-500">
                  Plagiarism summary
                </p>
                <p className="mt-3 text-sm leading-7 text-on-surface-variant">
                  {completionPlagiarism.summary}
                </p>
              </div>
            ) : null}

            <div className="mt-6 grid gap-4 xl:grid-cols-3">
              <div className="rounded-3xl border border-primary/15 bg-primary/5 p-5">
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-primary">
                  Insights
                </p>
                <ul className="mt-3 space-y-2 text-sm leading-6 text-on-surface-variant">
                  {completionInsights.length > 0 ? (
                    completionInsights.map((item) => <li key={item}>{item}</li>)
                  ) : (
                    <li>No strengths were returned yet.</li>
                  )}
                </ul>
              </div>

              <div className="rounded-3xl border border-amber-500/15 bg-amber-500/5 p-5">
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-amber-500">
                  Loopholes
                </p>
                <ul className="mt-3 space-y-2 text-sm leading-6 text-on-surface-variant">
                  {completionLoopholes.length > 0 ? (
                    completionLoopholes.map((item) => <li key={item}>{item}</li>)
                  ) : (
                    <li>No gaps were returned yet.</li>
                  )}
                </ul>
              </div>

              <div className="rounded-3xl border border-blue-500/15 bg-blue-500/5 p-5">
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-blue-500">
                  Next improvements
                </p>
                <ul className="mt-3 space-y-2 text-sm leading-6 text-on-surface-variant">
                  {completionRecommendations.length > 0 ? (
                    completionRecommendations.map((item) => <li key={item}>{item}</li>)
                  ) : (
                    <li>No follow-up recommendations were returned yet.</li>
                  )}
                </ul>
              </div>
            </div>

            <div className="mt-8 flex justify-end">
              <button
                type="button"
                onClick={() => router.push("/assessments")}
                className="rounded-full bg-gradient-to-r from-indigo-500 to-violet-600 px-8 py-3 text-[11px] font-black uppercase tracking-[0.2em] text-white shadow-xl shadow-indigo-500/20 transition-all hover:scale-[1.02] active:scale-[0.98]"
              >
                Return to Assessments
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function WrittenProtocolFallback() {
  return (
    <div className="flex min-h-[calc(100vh-120px)] items-center justify-center px-4">
      <div className="text-center">
        <div className="w-14 h-14 rounded-2xl border border-primary/20 border-t-primary animate-spin mx-auto mb-5" />
        <p className="text-[11px] font-black uppercase tracking-[0.2em] text-on-surface-variant">
          Loading written protocol
        </p>
      </div>
    </div>
  );
}

export default function WrittenProtocolPage() {
  return (
    <Suspense fallback={<WrittenProtocolFallback />}>
      <WrittenProtocolPageContent />
    </Suspense>
  );
}
