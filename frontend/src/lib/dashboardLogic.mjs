const RESUME_BREAKDOWN_WEIGHT_CAPS = {
  education: 20,
  academic: 20,
  academics: 20,
  experience: 25,
  internship: 25,
  internships: 25,
  skills: 25,
  "technical skills": 25,
  projects: 15,
  project: 15,
  certifications: 7,
  certification: 7,
  certificates: 7,
  publications: 5,
  publication: 5,
};

function cleanLabel(value, index) {
  const label = String(value ?? "").trim();
  return label || `Area ${index + 1}`;
}

function numericValue(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function inferBreakdownMax(label, score, explicitMax) {
  const normalizedLabel = label.trim().toLowerCase();
  const knownCap = RESUME_BREAKDOWN_WEIGHT_CAPS[normalizedLabel];
  const parsedMax = numericValue(explicitMax, 0);

  if (parsedMax > 0 && parsedMax !== 100) {
    return parsedMax;
  }

  if (knownCap && score <= knownCap) {
    return knownCap;
  }

  return parsedMax > 0 ? parsedMax : 100;
}

export function normalizeScoreBreakdown(value) {
  const rawItems = Array.isArray(value)
    ? value
    : value && typeof value === "object"
      ? Object.entries(value).map(([label, raw]) => (
          raw && typeof raw === "object"
            ? { label, ...raw }
            : { label, score: raw }
        ))
      : [];

  return rawItems
    .filter((item) => item && typeof item === "object")
    .map((item, index) => {
      const label = cleanLabel(item.label ?? item.name, index);
      const score = Math.max(0, numericValue(item.score ?? item.value, 0));
      const max = Math.max(1, inferBreakdownMax(label, score, item.max ?? item.total));
      return { label, score: Math.min(score, max), max };
    });
}

export function formatBreakdownScore(item) {
  const score = Math.round(numericValue(item?.score, 0));
  const max = Math.round(Math.max(1, numericValue(item?.max, 100)));
  return `${score}/${max}`;
}

export function breakdownProgressPercent(item) {
  const score = numericValue(item?.score, 0);
  const max = Math.max(1, numericValue(item?.max, 100));
  return Math.max(0, Math.min(100, (score / max) * 100));
}

export function hasOnlyProfileLinksWithoutInsights({
  resume,
  readinessComponents,
  assessmentLogs,
  subjectProgress,
  breakdown,
  keywords,
  redFlags,
}) {
  const components = Array.isArray(readinessComponents) ? readinessComponents : [];
  const onlyProfileLinks = components.length > 0 && components.every((component) => component?.key === "profile_links");
  const hasAssessmentInsight = (assessmentLogs?.length ?? 0) > 0 || (subjectProgress?.length ?? 0) > 0;
  const hasResumeInsight = Boolean(resume) || (breakdown?.length ?? 0) > 0 || (keywords?.length ?? 0) > 0 || (redFlags?.length ?? 0) > 0;
  return onlyProfileLinks && !hasAssessmentInsight && !hasResumeInsight;
}
