interface AssessmentLinkSubject {
  title: string;
  skillId?: string | null;
  skillRequestId?: string | null;
}

export function buildAssessmentQuizHref(
  subject: AssessmentLinkSubject,
  questionType: "MCQ" | "SITUATIONAL" = "MCQ",
) {
  const params = new URLSearchParams({
    title: `${subject.title} ${
      questionType === "MCQ" ? "MCQ" : "Situational"
    } Assessment`,
    category: subject.title,
    questionType,
    assessmentType: questionType === "MCQ" ? "mcq" : "situational",
  });

  if (subject.skillId) {
    params.set("skillId", subject.skillId);
  }

  if (subject.skillRequestId) {
    params.set("skillRequestId", subject.skillRequestId);
  }

  return `/assessments/quiz?${params.toString()}`;
}

export function buildWrittenAssessmentHref(subject: AssessmentLinkSubject) {
  const params = new URLSearchParams({
    title: `${subject.title} Written Assessment`,
  });

  if (subject.skillId) {
    params.set("skillId", subject.skillId);
  }

  if (subject.skillRequestId) {
    params.set("skillRequestId", subject.skillRequestId);
  }

  return `/assessments/written-protocol?${params.toString()}`;
}
