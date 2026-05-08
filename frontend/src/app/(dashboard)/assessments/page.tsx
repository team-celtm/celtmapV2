"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";

import { apiFetch, getApiErrorMessage, ApiError } from "@/lib/api";
import type {
  ArtifactRead,
  LearningPathRead,
  ProfileRead,
  RoleFitRead,
  SkillGapRead,
  SkillRead,
  SkillRequestRead,
  WrittenAssessmentRead,
} from "@/lib/celtm";
import { formatPercent } from "@/lib/celtm";

const SubjectCard = dynamic(() => import("@/components/dashboard/SubjectCard").then(mod => mod.SubjectCard), {
  ssr: false,
  loading: () => <div className="h-64 animate-pulse rounded-[32px] bg-surface-container-low" />
});

interface AssessmentsState {
  profile: ProfileRead | null;
  roleFit: RoleFitRead | null;
  skills: SkillRead[];
  gaps: SkillGapRead[];
  learningPath: LearningPathRead | null;
  skillRequests: SkillRequestRead[];
  writtenSessions: WrittenAssessmentRead[];
  discoveredSubjects: AssessmentSubject[];
}

interface AssessmentSubject {
  key: string;
  title: string;
  description: string;
  source: string;
  severity: number;
  currentScore: number;
  resourceCount: number;
  isAvailable: boolean;
  skillId?: string | null;
  skillRequestId?: string | null;
}

const initialState: AssessmentsState = {
  profile: null,
  roleFit: null,
  skills: [],
  gaps: [],
  learningPath: null,
  skillRequests: [],
  writtenSessions: [],
  discoveredSubjects: [],
};

function normalizeKey(value: string) {
  return value.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-");
}

export default function AssessmentsHubPage() {
  const router = useRouter();
  const [data, setData] = useState<AssessmentsState>(initialState);
  const [isCoreLoading, setIsCoreLoading] = useState(true);
  const [isSubjectsLoading, setIsSubjectsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadSeed, setReloadSeed] = useState(0);
  const [requestForm, setRequestForm] = useState({ requestedName: "", description: "" });
  const [requestNotice, setRequestNotice] = useState<string | null>(null);
  const [isCreatingRequest, setIsCreatingRequest] = useState(false);

  useEffect(() => {
    let isMounted = true;
    const loadAssessmentState = async (showLoading = true, revalidate = false) => {
      try {
        if (showLoading) {
          setIsCoreLoading(true);
          setIsSubjectsLoading(true);
        }
        setError(null);
        const fetchOptions = { revalidate };
        
        // 1. Fast path: Core identity data
        const corePromise = Promise.allSettled([
          apiFetch<ProfileRead>("/profile/me", fetchOptions),
          apiFetch<RoleFitRead>("/skills/me/role-fit", fetchOptions),
          apiFetch<SkillRead[]>("/skills/me", fetchOptions),
        ]).then(([p, rf, sk]) => {
           if (isMounted) {
             setData(curr => ({
                ...curr,
                profile: p.status === "fulfilled" ? p.value : null,
                roleFit: rf.status === "fulfilled" ? rf.value : null,
                skills: sk.status === "fulfilled" ? sk.value : [],
             }));
             if (
               (p.status === "rejected" || rf.status === "rejected" || sk.status === "rejected") &&
               !error
             ) {
               const firstFailure =
                 p.status === "rejected"
                   ? p.reason
                   : rf.status === "rejected"
                     ? rf.reason
                     : sk.status === "rejected"
                       ? sk.reason
                       : null;
               if (firstFailure) {
                 setError(getApiErrorMessage(firstFailure, "Failed to load assessment workspace."));
               }
             }
             if (showLoading) setIsCoreLoading(false);
           }
        });

        // 2. Slow path: Subject gathering (EXCEPT learning path which we do asynchronously)
        const subjectsPromise = Promise.allSettled([
          apiFetch<SkillGapRead[]>("/skills/me/gaps", fetchOptions),
          apiFetch<SkillRequestRead[]>("/skills/requests", fetchOptions),
          apiFetch<WrittenAssessmentRead[]>("/written-assessments", fetchOptions),
          apiFetch<AssessmentSubject[]>("/assessments/subjects", fetchOptions),
        ]).then(([gapsResult, reqResult, waResult, subResult]) => {
            if (isMounted) {
              setData(curr => ({
                ...curr,
                gaps: gapsResult.status === "fulfilled" ? gapsResult.value : [],
                skillRequests: reqResult.status === "fulfilled" ? reqResult.value : [],
                writtenSessions: waResult.status === "fulfilled" ? waResult.value : [],
                discoveredSubjects: subResult.status === "fulfilled" ? subResult.value : [],
              }));
              if (
                (gapsResult.status === "rejected" ||
                  reqResult.status === "rejected" ||
                  waResult.status === "rejected" ||
                  subResult.status === "rejected") &&
                !error
              ) {
                const firstFailure =
                  gapsResult.status === "rejected"
                    ? gapsResult.reason
                    : reqResult.status === "rejected"
                      ? reqResult.reason
                      : waResult.status === "rejected"
                        ? waResult.reason
                        : subResult.status === "rejected"
                          ? subResult.reason
                          : null;
                if (firstFailure) {
                  setError(getApiErrorMessage(firstFailure, "Failed to load assessment subjects."));
                }
              }
              if (showLoading) setIsSubjectsLoading(false);
            }
        });

        await Promise.allSettled([corePromise, subjectsPromise]);

        // 3. Very Slow path: Learning path requires LLM generation
        // Trigger this asynchronously after fast data is fetched so it doesn't block the backend worker
        void apiFetch<LearningPathRead>("/learning/path", fetchOptions).then(lpResult => {
            if (isMounted) {
               setData(curr => ({ ...curr, learningPath: lpResult }));
            }
        }).catch(() => {});

      } catch (caught) {
        if (isMounted) setError(getApiErrorMessage(caught, "Failed to load the assessment workspace."));
      } finally {
        if (isMounted && showLoading) {
            setIsCoreLoading(false);
            setIsSubjectsLoading(false);
        }
      }
    };
    
    // Initial load (cache-first)
    void loadAssessmentState(true, false);
    
    // Background refresh
    void loadAssessmentState(false, true);

    return () => { isMounted = false; };
  }, [reloadSeed]);

  const focusRole = data.profile?.focus_role || data.roleFit?.role_name || "your target role";

  const subjects = useMemo(() => {
    const subjectMap = new Map<string, AssessmentSubject>();
    const skillMap = new Map(data.skills.map((s) => [normalizeKey(s.skill_name), s]));
    const gapMap = new Map(data.gaps.map((g) => [normalizeKey(g.skill_name), g]));
    const moduleMap = new Map((data.learningPath?.modules ?? []).map((m) => [normalizeKey(m.skill_name), m]));
    const requestMap = new Map(data.skillRequests.map((r) => [normalizeKey(r.requested_name), r]));

    for (const request of data.skillRequests) {
      const key = normalizeKey(request.requested_name);
      const skill = skillMap.get(key);
      const gap = gapMap.get(key);
      const mod = moduleMap.get(key);
      subjectMap.set(key, {
        key,
        title: request.requested_name,
        description: (request.generated_payload?.description as string) || `Custom validation track for ${request.requested_name}.`,
        source: "Custom Track",
        severity: gap?.gap_severity ?? 0.8,
        currentScore: skill?.verified_score ?? gap?.user_score ?? 0,
        resourceCount: mod?.resources.length ?? 0,
        isAvailable: true, // If it's a request, we assume it's being checked. Actually detail page will handle the real check.
        skillId: skill?.skill_id,
        skillRequestId: request.id,
      });
    }

    for (const mod of data.learningPath?.modules ?? []) {
      const key = normalizeKey(mod.skill_name);
      if (subjectMap.has(key)) {
        const existing = subjectMap.get(key)!;
        existing.isAvailable = mod.is_available ?? true;
        continue;
      }
      const skill = skillMap.get(key);
      const gap = gapMap.get(key);
      const request = requestMap.get(key);
      subjectMap.set(key, {
        key,
        title: mod.skill_name,
        description: mod.resources[0]?.content || `Core module for ${mod.skill_name}.`,
        source: `Learning Path (W${mod.week})`,
        severity: mod.gap_severity,
        currentScore: skill?.verified_score ?? gap?.user_score ?? 0,
        resourceCount: mod.resources.length,
        isAvailable: mod.is_available ?? true,
        skillId: skill?.skill_id,
        skillRequestId: request?.id,
      });
    }

    for (const gap of data.gaps) {
      const key = normalizeKey(gap.skill_name);
      if (subjectMap.has(key)) continue;
      const skill = skillMap.get(key);
      const request = requestMap.get(key);
      subjectMap.set(key, {
        key,
        title: gap.skill_name,
        description: `High-priority gap detected in ${gap.skill_name}.`,
        source: "Gap Analysis",
        severity: gap.gap_severity,
        currentScore: skill?.verified_score ?? gap.user_score,
        resourceCount: 0,
        isAvailable: true, // Default to true, detail will check
        skillId: skill?.skill_id,
        skillRequestId: request?.id,
      });
    }

    for (const sub of data.discoveredSubjects) {
      const subData = sub as any;
      if (subjectMap.has(sub.key)) {
        const existing = subjectMap.get(sub.key)!;
        // Enrich existing with database availability if source was just a gap/path module
        if (existing.source === "Gap Analysis") {
           existing.isAvailable = subData.is_available ?? true;
        }
        continue;
      }
      subjectMap.set(sub.key, {
        key: sub.key,
        title: sub.title,
        description: sub.description,
        source: "Skill Bank",
        severity: sub.severity || 0.5,
        currentScore: subData.current_score ?? null,
        resourceCount: subData.resource_count || 0,
        isAvailable: subData.is_available ?? true,
        skillId: subData.skill_id,
      });
    }

    return Array.from(subjectMap.values()).sort((a, b) => b.severity - a.severity);
  }, [data]);

  const createSkillRequest = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!requestForm.requestedName.trim()) return;
    try {
      setIsCreatingRequest(true);
      setRequestNotice(null);
      const created = await apiFetch<SkillRequestRead>("/skills/requests", {
        method: "POST",
        body: JSON.stringify({
          requested_name: requestForm.requestedName.trim(),
          requested_type: "skill",
          description: requestForm.description.trim() || undefined,
          strict_bank_match: true,
        }),
      });
      setData((curr) => ({ ...curr, skillRequests: [created, ...curr.skillRequests] }));
      setRequestForm({ requestedName: "", description: "" });
      setRequestNotice(`${created.requested_name} is available now.`);
      router.push(`/assessments/${normalizeKey(created.requested_name)}`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setRequestNotice("Subject not available at the moment.");
      } else {
        setRequestNotice(getApiErrorMessage(err, "Failed to check subject."));
      }
    } finally {
      setIsCreatingRequest(false);
    }
  };

  const SubjectSkeleton = () => (
    <div className="animate-pulse clay-card rounded-[32px] p-6 space-y-4">
      <div className="h-3 w-32 rounded bg-on-surface-variant/20" />
      <div className="h-6 w-48 rounded bg-on-surface-variant/15" />
      <div className="h-4 w-full rounded bg-on-surface-variant/10" />
      <div className="h-10 w-24 rounded-full bg-on-surface-variant/10" />
    </div>
  );

  return (
    <div className="mx-auto w-full max-w-[1520px] space-y-8 page-fade-in pb-12">
      {error ? (
        <div className="mx-2 rounded-3xl border border-amber-500/20 bg-amber-500/10 px-6 py-5 text-sm text-amber-200">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="leading-6">{error}</p>
            <button
              type="button"
              onClick={() => setReloadSeed((s) => s + 1)}
              className="inline-flex shrink-0 rounded-full bg-amber-400/15 px-5 py-2 text-[11px] font-black uppercase tracking-[0.18em] text-amber-100 hover:bg-amber-400/20"
            >
              Retry
            </button>
          </div>
          <p className="mt-3 text-xs leading-5 text-amber-100/70">
            If you see “Network connectivity issue or CORS failure”, start the backend at{" "}
            <span className="font-mono">http://127.0.0.1:8000</span> (FastAPI) and refresh.
          </p>
        </div>
      ) : null}
      <header className="clay-card rounded-[40px] p-8 md:p-10 relative overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 bg-primary/5 rounded-full blur-3xl -mr-20 -mt-20" />
        <div className="relative z-10 grid gap-10 lg:grid-cols-[1fr_0.8fr]">
          <div className="space-y-6">
            <p className="text-[11px] font-black uppercase tracking-[0.25em] text-primary">Assessment Matrix</p>
            <h1 className="text-4xl font-extrabold tracking-tight text-on-surface md:text-5xl leading-tight">
              Curated for <span className="text-primary">{focusRole}</span>
            </h1>
            <p className="text-lg text-on-surface-variant max-w-xl leading-relaxed">
              Explore subject-specific validation routes. Complete MCQ, situational, and written assessments to verify your expertise and bridge role-fit gaps.
            </p>
            <div className="flex flex-wrap gap-4 pt-4">
              <div className="rounded-3xl bg-surface-container-low px-6 py-4 ring-1 ring-outline-variant/5">
                <p className="text-[9px] font-black uppercase tracking-widest text-on-surface-variant mb-1">Total Subjects</p>
                <p className="text-2xl font-bold text-on-surface">{isSubjectsLoading ? "--" : subjects.filter(s => s.isAvailable).length}</p>
              </div>
              <div className="rounded-3xl bg-surface-container-low px-6 py-4 ring-1 ring-outline-variant/5">
                <p className="text-[9px] font-black uppercase tracking-widest text-on-surface-variant mb-1">Active Tracks</p>
                <p className="text-2xl font-bold text-on-surface">{isSubjectsLoading ? "--" : data.skillRequests.length}</p>
              </div>
              <div className="rounded-3xl bg-surface-container-low px-6 py-4 ring-1 ring-outline-variant/5">
                 <p className="text-[9px] font-black uppercase tracking-widest text-on-surface-variant mb-1">Role Fit</p>
                 <p className="text-2xl font-bold text-on-surface">{isCoreLoading ? "--" : formatPercent(data.roleFit?.fit_score ?? 0)}</p>
              </div>
            </div>
          </div>

          <div className="rounded-[32px] bg-surface-container-lowest p-8 shadow-inner ring-1 ring-outline-variant/10">
            <h2 className="text-xl font-bold text-on-surface mb-2">Request Custom Domain</h2>
            <p className="text-sm text-on-surface-variant mb-6">
              Check whether a subject already exists in the assessment bank. If it does, the track opens immediately. If not, you&apos;ll see that it is unavailable right now.
            </p>
            <form onSubmit={createSkillRequest} className="space-y-4">
              <input
                value={requestForm.requestedName}
                onChange={(e) => setRequestForm({...requestForm, requestedName: e.target.value})}
                placeholder="Subject name (e.g. Distributed Systems)"
                className="w-full rounded-2xl bg-surface-container-low px-5 py-3 text-sm outline-none ring-1 ring-outline-variant/20 focus:ring-primary/50 transition-all"
              />
              <textarea
                value={requestForm.description}
                onChange={(e) => setRequestForm({...requestForm, description: e.target.value})}
                placeholder="Context or specific topics to cover..."
                className="w-full rounded-2xl bg-surface-container-low px-5 py-3 text-sm outline-none ring-1 ring-outline-variant/20 focus:ring-primary/50 transition-all min-h-[80px]"
              />
              <button
                type="submit"
                disabled={isCreatingRequest}
                className="w-full rounded-full bg-primary py-3 text-[11px] font-black uppercase tracking-widest text-white hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                {isCreatingRequest ? "Checking..." : "Check Subject"}
              </button>
            </form>
            {requestNotice ? (
              <p className="mt-4 text-sm text-on-surface-variant">{requestNotice}</p>
            ) : null}
          </div>
        </div>
      </header>

      <section className="space-y-6">
        <div className="flex items-center justify-between px-2">
          <h2 className="text-2xl font-bold tracking-tight text-on-surface">Subject Inventory</h2>
          <div className="flex items-center gap-4 text-[11px] font-black uppercase tracking-widest text-on-surface-variant">
            <span>Filter</span>
            <span className="h-1 w-1 rounded-full bg-outline-variant" />
            <span className="text-primary cursor-pointer hover:underline">All Subjects</span>
          </div>
        </div>

        {isSubjectsLoading ? (
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4 px-2">
            {[1,2,3,4,5,6].map(i => <SubjectSkeleton key={i} />)}
          </div>
        ) : subjects.filter(s => s.isAvailable).length ? (
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4 px-2">
            {subjects.filter(s => s.isAvailable).map((s) => (
              <SubjectCard key={s.key} subject={s} />
            ))}
          </div>
        ) : (
          <div className="mx-auto max-w-2xl py-12 px-6">
            <div className="rounded-[48px] bg-surface-container-low border border-outline-variant/15 p-12 text-center shadow-sm">
               <div className="mx-auto mb-8 flex h-24 w-24 items-center justify-center rounded-full bg-primary/5 text-primary">
                  <svg className="h-12 w-12" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                  </svg>
               </div>
               <h2 className="text-3xl font-extrabold tracking-tight text-on-surface">Subject Vault Empty</h2>
               <p className="mt-4 text-on-surface-variant text-lg leading-relaxed">
                 You haven&apos;t defined any target skills yet or the current subjects are not fully populated. Select a focus role in your profile to generate your validation tracks.
               </p>
               <div className="mt-10 flex flex-wrap justify-center gap-4">
                  <Link 
                    href="/dashboard?refresh=1" 
                    className="rounded-full bg-primary px-12 py-4 text-[12px] font-black uppercase tracking-widest text-white hover:opacity-90 transition-opacity shadow-lg shadow-primary/20"
                  >
                    Back to Dashboard
                  </Link>
               </div>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
