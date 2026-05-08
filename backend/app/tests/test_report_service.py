from __future__ import annotations

import pytest

from app.services.report_service import ReportService


class FakeReportRepository:
    def __init__(self) -> None:
        self.created_payloads: list[dict] = []
        self.latest_report: dict | None = None

    async def create_report(self, payload: dict) -> dict:
        report = {"id": "report-1", **payload}
        self.created_payloads.append(report)
        self.latest_report = report
        return report

    async def get_latest_report(self, user_id: str) -> dict | None:
        return self.latest_report


class FakeInterviewRepository:
    async def list_sessions(self, user_id: str, limit: int, cursor: str | None) -> list[dict]:
        return []


class FakeSkillService:
    async def get_role_fit(self, user_id: str) -> dict:
        return {"role_name": "ML Engineer", "fit_score": 78.0}

    async def list_user_skills(self, user_id: str) -> list[dict]:
        return [
            {"skill_name": "Python", "proficiency_score": 91.0},
            {"skill_name": "Machine Learning", "proficiency_score": 87.0},
        ]

    async def list_hidden_candidates(self, user_id: str) -> list[dict]:
        return []


class FakeProfileRepository:
    async def get_profile(self, user_id: str) -> dict:
        return {
            "id": user_id,
            "email": "zian.surani@gmail.com",
            "full_name": "Zian",
            "headline": "Aspiring ML Engineer",
            "focus_role": "ML Engineer",
            "weekly_goal": "Ship one production-ready project each week",
            "metadata": {
                "bio": "Builder focused on machine learning systems and deployment.",
                "location": "India",
                "target_industry": "Applied AI",
            },
        }

    async def get_preferences(self, user_id: str) -> dict:
        return {"user_id": user_id, "security_mode": "strict"}

    async def list_artifacts(self, user_id: str, limit: int = 200) -> list[dict]:
        return [
            {
                "id": "artifact-1",
                "user_id": user_id,
                "file_name": "Resume 2025.pdf",
                "file_type": "resume",
                "created_at": "2026-04-14T12:00:00+00:00",
                "extracted_text": (
                    "Machine learning engineer with Python and TensorFlow experience. "
                    "Built deployment pipelines on AWS. "
                    "Delivered data products for applied AI teams."
                ),
            },
            {
                "id": "artifact-2",
                "user_id": user_id,
                "file_name": "Python Certificate.pdf",
                "file_type": "credential",
                "created_at": "2026-04-13T12:00:00+00:00",
                "extracted_text": None,
            },
        ]


@pytest.mark.asyncio
async def test_build_skill_passport_includes_resume_details() -> None:
    service = ReportService(
        report_repository=FakeReportRepository(),  # type: ignore[arg-type]
        assessment_repository=object(),  # type: ignore[arg-type]
        interview_repository=FakeInterviewRepository(),  # type: ignore[arg-type]
        skill_service=FakeSkillService(),  # type: ignore[arg-type]
        profile_repository=FakeProfileRepository(),  # type: ignore[arg-type]
    )

    passport = await service.build_skill_passport("user-1")

    assert passport["resume_file_name"] == "Resume 2025.pdf"
    assert passport["top_skills"] == ["Python 91%", "Machine Learning 87%"]
    assert passport["resume_highlights"]
    assert "deployment pipelines" in " ".join(passport["resume_highlights"]).lower()


@pytest.mark.asyncio
async def test_render_skill_passport_pdf_returns_pdf_bytes() -> None:
    service = ReportService(
        report_repository=FakeReportRepository(),  # type: ignore[arg-type]
        assessment_repository=object(),  # type: ignore[arg-type]
        interview_repository=FakeInterviewRepository(),  # type: ignore[arg-type]
        skill_service=FakeSkillService(),  # type: ignore[arg-type]
        profile_repository=FakeProfileRepository(),  # type: ignore[arg-type]
    )

    file_name, payload = await service.render_skill_passport_pdf("user-1")

    assert file_name == "zian-skill-passport.pdf"
    assert payload.startswith(b"%PDF")
    assert b"CELTM Skill Passport" in payload
    assert b"Resume 2025.pdf" in payload


@pytest.mark.asyncio
async def test_get_latest_report_generates_baseline_when_missing() -> None:
    repository = FakeReportRepository()
    service = ReportService(
        report_repository=repository,  # type: ignore[arg-type]
        assessment_repository=object(),  # type: ignore[arg-type]
        interview_repository=FakeInterviewRepository(),  # type: ignore[arg-type]
        skill_service=FakeSkillService(),  # type: ignore[arg-type]
        profile_repository=FakeProfileRepository(),  # type: ignore[arg-type]
    )

    report = await service.get_latest_report("user-1")

    assert report is not None
    assert report["id"] == "report-1"
    assert len(repository.created_payloads) == 1
    assert report["payload"]["role_fit"]["role_name"] == "ML Engineer"
