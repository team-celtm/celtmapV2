from __future__ import annotations

from app.schemas.interview import CompatibilityInterviewSubmission


def test_compatibility_interview_submission_accepts_frontend_camel_case_fields() -> None:
    payload = CompatibilityInterviewSubmission.model_validate(
        {
            "sessionId": "session-1",
            "roleName": "ML Engineer",
            "transcript": "Candidate explains gradient descent well.",
            "mediaReference": "supabase://bucket/interview.mp4",
        }
    )

    assert payload.session_id == "session-1"
    assert payload.role_name == "ML Engineer"
    assert payload.media_reference == "supabase://bucket/interview.mp4"
