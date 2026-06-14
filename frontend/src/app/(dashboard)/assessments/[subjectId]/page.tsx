"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { apiFetch, getApiErrorMessage } from "@/lib/api";
import { SubjectDetail, formatPercent } from "@/lib/celtm";
import { buildAssessmentQuizHref, buildWrittenAssessmentHref } from "@/lib/assessmentLinks";

export default function SubjectHubPage() {
  const { subjectId } = useParams();
  const router = useRouter();
  const [subject, setSubject] = useState<SubjectDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    const fetchDetail = async () => {
      try {
        setIsLoading(true);
        const data = await apiFetch<SubjectDetail>(`/assessments/subjects/${subjectId}`);
        if (isMounted) setSubject(data);
      } catch (err) {
        if (isMounted) setError(getApiErrorMessage(err, "Failed to load subject details."));
      } finally {
        if (isMounted) setIsLoading(false);
      }
    };
    fetchDetail();
    return () => { isMounted = false; };
  }, [subjectId]);

  const SubjectDetailSkeleton = () => (
    <div className="mx-auto w-full max-w-[1520px] space-y-6 page-fade-in pb-10 animate-pulse">
      <div className="clay-card rounded-[32px] p-8 space-y-4">
        <div className="h-3 w-24 rounded bg-on-surface-variant/20" />
        <div className="h-10 w-64 rounded bg-on-surface-variant/15" />
        <div className="h-5 w-full rounded bg-on-surface-variant/10" />
      </div>
      <div className="grid gap-6 sm:grid-cols-3">
        {[1,2,3].map(i => (
          <div key={i} className="clay-card rounded-[32px] p-6 space-y-3">
            <div className="h-8 w-8 rounded-2xl bg-on-surface-variant/15" />
            <div className="h-5 w-32 rounded bg-on-surface-variant/15" />
            <div className="h-4 w-full rounded bg-on-surface-variant/10" />
            <div className="h-4 w-3/4 rounded bg-on-surface-variant/10" />
          </div>
        ))}
      </div>
    </div>
  );

  if (isLoading) return <SubjectDetailSkeleton />;

  if (error || !subject) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-20 text-center">
        <div className="mb-6 inline-flex h-16 w-16 items-center justify-center rounded-3xl bg-error/10 text-error">
          <svg className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        <h2 className="text-2xl font-bold text-on-surface">Subject Unavailable</h2>
        <p className="mt-2 text-on-surface-variant">{error || "The requested subject track could not be found."}</p>
        <button
          onClick={() => router.back()}
          className="mt-8 rounded-full bg-surface-container-high px-8 py-3 text-[11px] font-black uppercase tracking-widest text-on-surface transition hover:opacity-90"
        >
          Return to Hub
        </button>
      </div>
    );
  }

  const assessmentCards = [
    {
      type: "MCQ",
      label: "Foundation Check",
      description: `Quick-fire conceptual validation for ${subject.title} with instant feedback.`,
      icon: "M",
      color: "bg-blue-500/10 text-blue-500",
      href: buildAssessmentQuizHref({ 
        title: subject.title, 
        skillId: subject.skill_id, 
        skillRequestId: subject.skill_request_id 
      }, "MCQ"),
      isEnabled: subject.availability?.mcq ?? subject.is_available,
    },
    {
      type: "Situational",
      label: "Situational Practice",
      description: `Scenario-based ${subject.title} decisions with practical reasoning checks.`,
      icon: "S",
      color: "bg-teal-500/10 text-teal-500",
      href: buildAssessmentQuizHref({ 
        title: subject.title, 
        skillId: subject.skill_id, 
        skillRequestId: subject.skill_request_id 
      }, "SITUATIONAL"),
      isEnabled: subject.availability?.situational ?? false,
    },
    {
      type: "Written",
      label: "Written Analysis",
      description: `Structured written verification for ${subject.title}, graded for relevance and reasoning.`,
      icon: "W",
      color: "bg-purple-500/10 text-purple-500",
      href: buildWrittenAssessmentHref({ 
        title: subject.title, 
        skillId: subject.skill_id, 
        skillRequestId: subject.skill_request_id 
      }),
      isEnabled: subject.availability?.written ?? false,
    }
  ];

  return (
    <div className="mx-auto w-full max-w-6xl space-y-10 animate-fade-in pb-12">
      <header className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
        <div className="space-y-4">
          <Link 
            href="/assessments" 
            className="inline-flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.2em] text-on-surface-variant hover:text-primary transition-colors"
          >
            Back to Subject Hub
          </Link>
          <div className="flex items-center gap-3">
             <span className="rounded-full bg-primary/10 px-3 py-1 text-[10px] font-black uppercase tracking-widest text-primary">
              {subject.source}
            </span>
             <span className="text-[10px] font-extrabold text-on-surface-variant">{subject.resource_count} live questions</span>
          </div>
          <h1 className="text-4xl font-extrabold tracking-tight text-on-surface md:text-5xl">{subject.title}</h1>
          <p className="max-w-2xl text-lg text-on-surface-variant leading-relaxed">
            {subject.description}
          </p>
        </div>

        <div className="flex shrink-0 flex-col items-center rounded-[32px] bg-surface-container-low px-8 py-6 text-center shadow-inner ring-1 ring-outline-variant/10">
          <p className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant">Mastery</p>
          <div className="mt-3 flex h-24 w-24 items-center justify-center rounded-full border-8 border-primary/15 bg-primary/5">
            <span className="text-2xl font-black text-on-surface">{formatPercent(subject.current_score ?? 0)}</span>
          </div>
          <p className="mt-3 text-[10px] font-black uppercase tracking-widest text-primary">Verified Score</p>
        </div>
      </header>

      <div className="h-px w-full bg-outline-variant/10" />

      <section className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-on-surface">Select Sequence</h2>
          <p className="mt-1 text-sm text-on-surface-variant">Choose your assessment vector to begin validation.</p>
        </div>

        <div className="grid gap-6 md:grid-cols-3 relative">
          {!subject.is_available && (
            <div className="inset-0 z-20 flex flex-col items-center justify-center rounded-[40px] bg-surface-container-highest/60 backdrop-blur-md border-2 border-dashed border-primary/20 p-12 text-center glass-card w-full min-h-[400px]">
              <div className="mb-4 flex h-20 w-20 items-center justify-center rounded-3xl bg-primary/10 text-primary">
                <svg className="h-10 w-10" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                </svg>
              </div>
              <h3 className="text-2xl font-black text-on-surface">Subject Content Pending</h3>
              <p className="mt-2 text-on-surface-variant max-w-sm">
                The assessment bank for {subject.title} is currently being populated. 
                Please return to your main dashboard for other active tracks.
              </p>
              <Link
                href="/dashboard?refresh=1"
                className="mt-6 rounded-full bg-primary px-12 py-3 text-[11px] font-black uppercase tracking-widest text-white transition hover:opacity-90 shadow-lg shadow-primary/25"
              >
                Return to Dashboard
              </Link>
            </div>
          )}

          {subject.is_available && assessmentCards.map((card) => (
            <Link
              key={card.type}
              href={card.href}
              aria-disabled={!card.isEnabled}
              className={`lift-card flex flex-col rounded-[32px] border border-outline-variant/12 dark:border-transparent bg-surface-container-low p-8 transition group ${
                card.isEnabled ? "hover:border-primary/30" : "pointer-events-none opacity-50"
              }`}
            >
              <div className={`mb-6 flex h-14 w-14 items-center justify-center rounded-2xl text-xl font-black ${card.color}`}>
                {card.icon}
              </div>
              <h3 className="text-xl font-bold text-on-surface group-hover:text-primary transition-colors">
                {card.label}
              </h3>
              <p className="mt-3 text-sm leading-6 text-on-surface-variant">
                {card.description}
              </p>
              <div className="mt-8 flex items-center justify-between border-t border-outline-variant/5 pt-4">
                <span className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant group-hover:text-primary transition-colors">
                  {card.isEnabled ? "Begin Track ->" : "Not available"}
                </span>
                <span className="rounded-full bg-surface-container px-2 py-1 text-[9px] font-bold text-on-surface-variant">
                  {card.type}
                </span>
              </div>
            </Link>
          ))}
        </div>

      </section>

      <section className="rounded-[40px] bg-surface-container-lowest p-8 md:p-10 shadow-inner ring-1 ring-outline-variant/5">
        <div className="grid gap-10 md:grid-cols-[1fr_2fr]">
          <div className="space-y-4">
            <h2 className="text-xl font-bold text-on-surface">Track Breakdown</h2>
            <div className="space-y-3">
              <div className="rounded-2xl bg-surface px-4 py-3">
                <p className="text-[9px] font-black uppercase tracking-widest text-on-surface-variant">Gap Severity</p>
                <div className="mt-2 flex items-center gap-3">
                  <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-outline-variant/20">
                    <div className="h-full bg-primary" style={{ width: `${subject.severity * 100}%` }} />
                  </div>
                  <span className="text-sm font-bold text-on-surface">{Math.round(subject.severity * 100)}%</span>
                </div>
              </div>
              <div className="rounded-2xl bg-surface px-4 py-3">
                <p className="text-[9px] font-black uppercase tracking-widest text-on-surface-variant">Documentation</p>
                <p className="mt-1 text-sm font-bold text-on-surface">{subject.resource_count} live questions</p>
              </div>
            </div>
          </div>
          
          <div className="rounded-3xl border border-outline-variant/12 p-6">
             <h3 className="text-sm font-bold text-on-surface mb-4">Preparation Insights</h3>
             <ul className="space-y-3 text-sm text-on-surface-variant list-disc pl-4">
               <li>Foundation check verifies your grasp of {subject.title} concepts.</li>
               <li>Situational practice measures how well you apply {subject.title} in practical choices.</li>
               <li>Written analysis requires clear explanation, evidence, risk, and next action.</li>
               <li>Repeated attempts build a subject-wise trend instead of a broad capability guess.</li>
             </ul>
          </div>
        </div>
      </section>
    </div>
  );
}
