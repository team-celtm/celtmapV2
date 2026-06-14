"use client";

import { useEffect, useMemo, useState } from "react";
import { ApiError, apiFetch } from "@/lib/api";
import type { HiddenSkillCandidateRead, SkillRead } from "@/lib/celtm";
import { formatDate, toTitleCase } from "@/lib/celtm";
import AppIcon from "@/components/AppIcon";
import CeltmProgressLoader from "@/components/CeltmProgressLoader";

type Category = "All" | "Technical" | "Leadership" | "Cognitive";

interface HiddenSkillWithCategory extends HiddenSkillCandidateRead {
  category: Category;
}

function classifyCandidate(candidate: HiddenSkillCandidateRead): Category {
  const content = `${candidate.skill_name} ${candidate.source} ${candidate.evidence}`.toLowerCase();
  if (/(lead|mentor|team|stakeholder|manager|collaboration)/.test(content)) {
    return "Leadership";
  }
  if (/(pattern|intuition|reason|analysis|problem|cognitive)/.test(content)) {
    return "Cognitive";
  }
  return "Technical";
}

export default function HiddenSkillsAnalytics() {
  const [activeCategory, setActiveCategory] = useState<Category>("All");
  const [hiddenSkills, setHiddenSkills] = useState<HiddenSkillWithCategory[]>([]);
  const [approvedSkills, setApprovedSkills] = useState<SkillRead[]>([]);
  const [pendingActionId, setPendingActionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    const loadSkills = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const [candidates, skills] = await Promise.all([
          apiFetch<HiddenSkillCandidateRead[]>("/skills/me/hidden"),
          apiFetch<SkillRead[]>("/skills/me"),
        ]);

        if (!isMounted) {
          return;
        }

        setHiddenSkills(
          candidates.map((candidate) => ({
            ...candidate,
            category: classifyCandidate(candidate),
          })),
        );
        setApprovedSkills(skills);
      } catch (caught) {
        if (!isMounted) {
          return;
        }
        const message = caught instanceof ApiError ? caught.message : "Failed to load hidden skill candidates.";
        setError(message);
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    void loadSkills();

    return () => {
      isMounted = false;
    };
  }, []);

  const filteredSkills = activeCategory === "All" ? hiddenSkills : hiddenSkills.filter((skill) => skill.category === activeCategory);
  const approvedCount = hiddenSkills.filter((skill) => skill.status === "approved").length;
  const pendingCount = hiddenSkills.filter((skill) => skill.status === "pending").length;
  const averageConfidence = hiddenSkills.length
    ? Math.round(hiddenSkills.reduce((total, skill) => total + skill.confidence_score, 0) / hiddenSkills.length * 100)
    : 0;

  const topApproved = useMemo(() => approvedSkills.slice(0, 3), [approvedSkills]);
  const selectedCandidate = filteredSkills.find((skill) => skill.id === selectedCandidateId) ?? null;

  const updateCandidateStatus = async (candidateId: string, action: "approve" | "reject") => {
    try {
      setPendingActionId(candidateId);
      setError(null);
      const updated = await apiFetch<HiddenSkillCandidateRead | null>(`/skills/me/hidden/${candidateId}/${action}`, {
        method: "POST",
      });

      setHiddenSkills((current) =>
        current.map((candidate) =>
          candidate.id === candidateId && updated
            ? {
                ...candidate,
                ...updated,
                category: classifyCandidate(updated),
              }
            : candidate,
        ),
      );

      if (action === "approve") {
        const refreshedSkills = await apiFetch<SkillRead[]>("/skills/me");
        setApprovedSkills(refreshedSkills);
      }
    } catch (caught) {
      const message = caught instanceof ApiError ? caught.message : `Failed to ${action} the hidden skill candidate.`;
      setError(message);
    } finally {
      setPendingActionId(null);
    }
  };

  return (
    <div className="w-full max-w-[1600px] mx-auto min-h-screen space-y-8 animate-fade-in pb-16">
      <header className="mb-10">
        <span className="text-indigo-500 font-bold tracking-[0.3em] uppercase text-xs mb-2 block">CELTM Discovery Engine</span>
        <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-6">
          <h1 className="text-4xl font-extrabold tracking-tighter text-slate-900 dark:text-white max-w-2xl leading-[1.1] sm:text-5xl">
            Reveal the <span className="bg-clip-text text-transparent bg-gradient-to-r from-indigo-500 to-purple-500">Untapped</span> Potential.
          </h1>

          <div className="flex bg-surface-container-low p-1.5 rounded-full shadow-inner overflow-x-auto max-w-full custom-scrollbar border border-outline-variant/10 dark:border-transparent">
            {(["All", "Technical", "Leadership", "Cognitive"] as Category[]).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveCategory(tab)}
                className={`px-5 py-2 rounded-full text-xs font-bold transition-all duration-300 ${
                  activeCategory === tab
                    ? "bg-surface shadow-sm text-primary"
                    : "text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high/50"
                }`}
              >
                {tab}
              </button>
            ))}
          </div>
        </div>
      </header>

      {error ? (
        <div className="rounded-2xl border border-red-500/20 bg-red-500/10 px-5 py-4 text-sm text-red-400">
          {error}
        </div>
      ) : null}

      {isLoading ? (
        <CeltmProgressLoader
          title="Loading hidden skills"
          caption="Cooking your hidden skill graph"
          stages={["Scanning detected signals", "Reading approved skills", "Mapping confidence", "Preparing the discovery radar"]}
        />
      ) : (
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-12">
          <div className="flex flex-col gap-8 lg:col-span-5">
            <div className="clay-card bg-surface/70 backdrop-blur-md rounded-2xl p-8 border border-outline-variant/5 dark:border-transparent shadow-xl relative overflow-hidden group min-h-[400px] flex flex-col">
              <div className="flex justify-between items-start mb-6 z-10">
                <div>
                  <h3 className="text-lg font-bold text-on-surface">Discovery Radar</h3>
                  <p className="text-xs text-on-surface-variant mt-1">Cross-functional scanning...</p>
                </div>
                <span className="px-3 py-1 bg-primary/10 text-primary text-[10px] font-bold uppercase tracking-widest rounded-full border border-primary/20">Live Sync</span>
              </div>

              <div className="flex-grow relative flex items-center justify-center">
                <svg className="w-[85%] h-[85%] transform rotate-12 z-10 filter drop-shadow-[0_0_15px_rgba(99,102,241,0.2)] overflow-visible" viewBox="0 0 100 100">
                  {[0.25, 0.5, 0.75, 1].map((scale) => (
                    <polygon
                      key={scale}
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="0.5"
                      className="text-on-surface-variant/10"
                      points={`${50},${50 - 40 * scale} ${50 + 35 * scale},${50 - 15 * scale} ${50 + 25 * scale},${50 + 35 * scale} ${50 - 25 * scale},${50 + 35 * scale} ${50 - 35 * scale},${50 - 15 * scale}`}
                    />
                  ))}
                  {[
                    [50, 10],
                    [85, 35],
                    [75, 85],
                    [25, 85],
                    [15, 35],
                  ].map(([x, y], index) => (
                    <line
                      key={index}
                      x1="50"
                      y1="50"
                      x2={x}
                      y2={y}
                      stroke="currentColor"
                      strokeWidth="0.5"
                      strokeDasharray="2 2"
                      className="text-on-surface-variant/20"
                    />
                  ))}
                  <polygon
                    fill="url(#grad1)"
                    fillOpacity="0.4"
                    points="50,22 81,38 72,75 32,80 18,40"
                    stroke="#6366f1"
                    strokeWidth="1.5"
                  />
                  <defs>
                    <linearGradient id="grad1" x1="0%" x2="100%" y1="0%" y2="100%">
                      <stop offset="0%" stopColor="#6366f1" />
                      <stop offset="100%" stopColor="#a855f7" />
                    </linearGradient>
                  </defs>
                </svg>

                <div className="absolute top-2 left-1/2 -translate-x-1/2 bg-white/90 dark:bg-black/80 backdrop-blur-md px-2 py-1 rounded text-[9px] font-black tracking-widest uppercase border border-outline-variant/10 dark:border-transparent shadow-lg z-20">
                  Pending {pendingCount}
                </div>
                <div className="absolute bottom-4 right-8 bg-white/90 dark:bg-black/80 backdrop-blur-md px-2 py-1 rounded text-[9px] font-black tracking-widest uppercase border border-outline-variant/10 dark:border-transparent shadow-lg z-20">
                  Confidence {averageConfidence}%
                </div>
              </div>
            </div>

            <div className="clay-card bg-primary/5 backdrop-blur-md rounded-2xl p-8 border border-primary/10 shadow-lg">
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-lg font-bold text-on-surface">Discovery Summary</h3>
                <AppIcon name="analytics" className="h-5 w-5 text-primary" />
              </div>
              <div className="space-y-6">
                {[
                  { name: "Pending candidates", gap: `${pendingCount}`, width: `${Math.min(100, pendingCount * 18)}%` },
                  { name: "Approved signals", gap: `${approvedCount}`, width: `${Math.min(100, approvedCount * 18)}%` },
                  { name: "Average confidence", gap: `${averageConfidence}%`, width: `${averageConfidence}%` },
                ].map((stat) => (
                  <div key={stat.name}>
                    <div className="flex justify-between text-[10px] font-bold uppercase tracking-wider mb-2">
                      <span className="text-on-surface-variant">{stat.name}</span>
                      <span className="text-primary">{stat.gap}</span>
                    </div>
                    <div className="h-1.5 w-full bg-surface-container rounded-full overflow-hidden">
                      <div className="h-full bg-primary rounded-full" style={{ width: stat.width }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="clay-card bg-surface/70 backdrop-blur-md rounded-2xl p-6 border border-outline-variant/5 dark:border-transparent shadow-xl">
              <h3 className="text-lg font-bold text-on-surface mb-4">Approved Skill Sync</h3>
              <div className="space-y-3">
                {topApproved.map((skill) => (
                  <div key={skill.skill_id} className="flex items-center justify-between rounded-xl border border-outline-variant/10 dark:border-transparent bg-surface-container-low/40 px-4 py-3">
                    <div>
                      <p className="text-sm font-bold text-on-surface">{skill.skill_name}</p>
                      <p className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant">Verified profile skill</p>
                    </div>
                    <span className="text-sm font-black text-emerald-500">{Math.round(skill.verified_score)}%</span>
                  </div>
                ))}
                {!topApproved.length ? (
                  <p className="text-sm text-on-surface-variant">Approve a hidden candidate to sync it into the verified skill graph.</p>
                ) : null}
              </div>
            </div>
          </div>

          <div className="lg:col-span-7">
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-2xl font-bold text-slate-800 dark:text-white">Detected Competencies</h3>
              <span className="text-xs font-bold text-slate-500">{filteredSkills.length} Traits Identified</span>
            </div>

            <div className="max-h-[760px] overflow-y-auto custom-scrollbar pr-3 -mr-3 space-y-4">
              {filteredSkills.map((skill) => (
                <div
                  key={skill.id}
                  className="clay-card bg-surface/70 backdrop-blur-md rounded-xl p-6 relative overflow-hidden flex flex-col md:flex-row md:items-center justify-between gap-6 shadow-md border border-outline-variant/5 dark:border-transparent"
                >
                  <div className="absolute right-[-20px] top-1/2 -translate-y-1/2 opacity-[0.03] transition-opacity">
                    <AppIcon
                      name={skill.category === "Technical" ? "terminal" : skill.category === "Leadership" ? "groups" : "psychology"}
                      className="h-36 w-36"
                    />
                  </div>

                  <div className="relative z-10 flex-1">
                    <span
                      className={`text-[10px] font-bold uppercase tracking-[0.2em] mb-2 block ${
                        skill.category === "Technical"
                          ? "text-primary"
                          : skill.category === "Leadership"
                            ? "text-teal-500"
                            : "text-purple-500"
                      }`}
                    >
                      {skill.category} Capability
                    </span>
                    <h4 className="text-xl font-bold text-on-surface mb-1">{skill.skill_name}</h4>
                    <p className="text-xs text-on-surface-variant font-medium">Detected via: {skill.source}</p>
                    <p className="text-xs text-on-surface-variant font-medium mt-2 line-clamp-2">{skill.evidence}</p>
                    <p className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant mt-3">
                      {skill.created_at ? `Detected ${formatDate(skill.created_at)}` : "Recently detected"}
                    </p>
                  </div>

                  <div className="relative z-10 w-full md:w-auto flex md:flex-col items-center md:items-end justify-between md:justify-center gap-3 border-t md:border-t-0 md:border-l border-outline-variant/10 dark:border-transparent pt-4 md:pt-0 md:pl-6">
                    <div className="flex flex-col items-start md:items-end">
                      <span className="text-[10px] text-on-surface-variant uppercase font-black tracking-widest shrink-0">Model Confidence</span>
                      <span className="text-2xl font-extrabold text-on-surface shrink-0">{Math.round(skill.confidence_score * 100)}%</span>
                    </div>
                    <span className="px-3 py-1 bg-surface-container-high text-on-surface-variant text-[10px] font-bold rounded-lg whitespace-nowrap">
                      {toTitleCase(skill.status)}
                    </span>
                  </div>

                  <div className="relative z-10 flex gap-3">
                    <button
                      type="button"
                      onClick={() => setSelectedCandidateId(skill.id)}
                      className="px-4 py-2 rounded-xl bg-surface-container-high text-xs font-bold uppercase tracking-widest text-on-surface"
                    >
                      View log
                    </button>
                    <button
                      onClick={() => void updateCandidateStatus(skill.id, "approve")}
                      disabled={skill.status !== "pending" || pendingActionId === skill.id}
                      className="px-4 py-2 rounded-xl bg-gradient-to-r from-indigo-500 to-purple-600 text-white text-xs font-bold uppercase tracking-widest disabled:opacity-40"
                    >
                      {pendingActionId === skill.id ? "Working..." : "Approve"}
                    </button>
                    <button
                      onClick={() => void updateCandidateStatus(skill.id, "reject")}
                      disabled={skill.status !== "pending" || pendingActionId === skill.id}
                      className="px-4 py-2 rounded-xl border border-outline-variant/15 dark:border-transparent text-xs font-bold uppercase tracking-widest text-on-surface-variant hover:bg-surface-container-high disabled:opacity-40"
                    >
                      Reject
                    </button>
                  </div>
                </div>
              ))}

              {!filteredSkills.length ? (
                <div className="p-12 text-center rounded-xl bg-surface-container border border-dashed border-outline-variant/20 dark:border-transparent">
                  <AppIcon name="search_off" className="mx-auto mb-2 h-10 w-10 text-on-surface-variant" />
                  <h4 className="text-sm font-bold text-on-surface-variant">No latent traits found in this category.</h4>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      )}

      {selectedCandidate ? (
        <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/70 px-4">
          <div className="w-full max-w-2xl rounded-[32px] border border-outline-variant/12 dark:border-transparent bg-surface-container p-8 shadow-2xl">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-primary">
                  Hidden skill detail
                </p>
                <h3 className="mt-2 text-3xl font-extrabold tracking-tight text-on-surface">
                  {selectedCandidate.skill_name}
                </h3>
                <p className="mt-2 text-sm leading-6 text-on-surface-variant">
                  Validation evidence and detection status for this hidden capability.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedCandidateId(null)}
                className="rounded-full bg-surface px-3 py-2 text-[10px] font-black uppercase tracking-[0.18em] text-on-surface"
              >
                Close
              </button>
            </div>

            <div className="mt-8 grid gap-4 sm:grid-cols-2">
              {[
                { label: "Confidence", value: `${Math.round(selectedCandidate.confidence_score * 100)}%` },
                { label: "Status", value: toTitleCase(selectedCandidate.status) },
                { label: "Category", value: selectedCandidate.category },
                { label: "Source", value: selectedCandidate.source },
              ].map((row) => (
                <div key={row.label} className="rounded-3xl bg-surface px-5 py-5 shadow-inner">
                  <p className="text-[10px] font-black uppercase tracking-[0.18em] text-on-surface-variant">
                    {row.label}
                  </p>
                  <p className="mt-2 text-2xl font-extrabold tracking-tight text-on-surface">{row.value}</p>
                </div>
              ))}
            </div>

            <div className="mt-6 rounded-3xl bg-surface px-5 py-5 shadow-inner">
              <p className="text-[10px] font-black uppercase tracking-[0.18em] text-on-surface-variant">
                Evidence trail
              </p>
              <p className="mt-3 text-sm leading-7 text-on-surface-variant">{selectedCandidate.evidence}</p>
              <p className="mt-4 text-[10px] font-black uppercase tracking-[0.18em] text-primary">
                {selectedCandidate.created_at ? `Detected ${formatDate(selectedCandidate.created_at)}` : "Recently detected"}
              </p>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
