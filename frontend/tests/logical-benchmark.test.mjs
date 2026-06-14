import assert from "node:assert/strict";
import test from "node:test";

import {
  breakdownProgressPercent,
  formatBreakdownScore,
  hasOnlyProfileLinksWithoutInsights,
  normalizeScoreBreakdown,
} from "../src/lib/dashboardLogic.mjs";

test("resume weighted breakdown displays education as full 20/20, not 20%", () => {
  const [education] = normalizeScoreBreakdown([{ label: "education", score: 20 }]);

  assert.equal(education.max, 20);
  assert.equal(formatBreakdownScore(education), "20/20");
  assert.equal(breakdownProgressPercent(education), 100);
});

test("resume weighted breakdown respects explicit category max values", () => {
  const [experience] = normalizeScoreBreakdown([{ label: "experience", score: 18, max: 25 }]);

  assert.equal(formatBreakdownScore(experience), "18/25");
  assert.equal(breakdownProgressPercent(experience), 72);
});

test("profile links only with no insights triggers the main-dashboard prompt", () => {
  assert.equal(
    hasOnlyProfileLinksWithoutInsights({
      resume: null,
      readinessComponents: [{ key: "profile_links", score: 66, weight: 0.1, effective_weight: 1 }],
      assessmentLogs: [],
      subjectProgress: [],
      breakdown: [],
      keywords: [],
      redFlags: [],
    }),
    true,
  );
});

test("profile links prompt is suppressed once assessments or resume insights exist", () => {
  assert.equal(
    hasOnlyProfileLinksWithoutInsights({
      resume: null,
      readinessComponents: [{ key: "profile_links", score: 66, weight: 0.1, effective_weight: 1 }],
      assessmentLogs: [{ id: "assessment-1" }],
      subjectProgress: [],
      breakdown: [],
      keywords: [],
      redFlags: [],
    }),
    false,
  );

  assert.equal(
    hasOnlyProfileLinksWithoutInsights({
      resume: { id: "resume-1" },
      readinessComponents: [{ key: "profile_links", score: 66, weight: 0.1, effective_weight: 1 }],
      assessmentLogs: [],
      subjectProgress: [],
      breakdown: [],
      keywords: [],
      redFlags: [],
    }),
    false,
  );
});
