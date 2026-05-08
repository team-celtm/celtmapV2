from __future__ import annotations

import re
from datetime import datetime, timezone
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.repositories.assessment_repository import AssessmentRepository
from app.repositories.interview_repository import InterviewRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.report_repository import ReportRepository
from app.services.skill_service import SkillService


class ReportService:
    def __init__(
        self,
        report_repository: ReportRepository,
        assessment_repository: AssessmentRepository,
        interview_repository: InterviewRepository,
        skill_service: SkillService,
        profile_repository: ProfileRepository,
    ) -> None:
        self.report_repository = report_repository
        self.assessment_repository = assessment_repository
        self.interview_repository = interview_repository
        self.skill_service = skill_service
        self.profile_repository = profile_repository

    async def generate_report(self, user_id: str) -> dict:
        role_fit = await self.skill_service.get_role_fit(user_id)
        skills = await self.skill_service.list_user_skills(user_id)
        hidden = await self.skill_service.list_hidden_candidates(user_id)
        sessions = await self.interview_repository.list_sessions(
            user_id=user_id, limit=5, cursor=None
        )
        payload = {
            "user_id": user_id,
            "role_fit": role_fit,
            "skills": skills,
            "hidden_skill_candidates": hidden,
            "recent_sessions": sessions,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        return await self.report_repository.create_report(
            {
                "user_id": user_id,
                "payload": payload,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    async def get_latest_report(self, user_id: str) -> dict | None:
        latest_report = await self.report_repository.get_latest_report(user_id)
        if latest_report is not None:
            return latest_report
        return await self.generate_report(user_id)

    async def build_skill_passport(self, user_id: str) -> dict[str, Any]:
        profile = await self.profile_repository.get_profile(user_id) or {}
        metadata = profile.get("metadata") or {}
        preferences = await self.profile_repository.get_preferences(user_id) or {}
        role_fit = await self.skill_service.get_role_fit(user_id)
        skills = await self.skill_service.list_user_skills(user_id)
        artifacts = await self.profile_repository.list_artifacts(user_id, limit=200)

        sorted_artifacts = sorted(
            artifacts,
            key=lambda artifact: str(artifact.get("created_at") or ""),
            reverse=True,
        )
        resume_artifact = next(
            (
                artifact
                for artifact in sorted_artifacts
                if str(artifact.get("file_type") or "").lower() == "resume"
            ),
            None,
        )
        resume_text = str((resume_artifact or {}).get("extracted_text") or "").strip()

        return {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "full_name": str(profile.get("full_name") or "CELTM User"),
            "email": str(profile.get("email") or ""),
            "headline": str(profile.get("headline") or ""),
            "focus_role": str(profile.get("focus_role") or ""),
            "weekly_goal": str(profile.get("weekly_goal") or ""),
            "location": str(metadata.get("location") or ""),
            "target_industry": str(metadata.get("target_industry") or ""),
            "bio": str(metadata.get("bio") or ""),
            "security_mode": str(preferences.get("security_mode") or "standard"),
            "readiness_score": float(role_fit.get("fit_score") or 0.0),
            "role_match": str(role_fit.get("role_name") or ""),
            "top_skills": [
                f"{skill['skill_name']} {round(float(skill.get('proficiency_score') or 0.0))}%"
                for skill in sorted(
                    skills,
                    key=lambda item: float(item.get("proficiency_score") or 0.0),
                    reverse=True,
                )[:6]
            ],
            "artifacts": [str(artifact.get("file_name") or "") for artifact in sorted_artifacts],
            "resume_file_name": str((resume_artifact or {}).get("file_name") or ""),
            "resume_highlights": self._extract_resume_highlights(resume_text),
            "resume_excerpt": self._build_resume_excerpt(resume_text),
        }

    async def render_skill_passport_pdf(self, user_id: str) -> tuple[str, bytes]:
        passport = await self.build_skill_passport(user_id)
        file_name = self._sanitize_file_name(passport["full_name"])
        return file_name, self._build_skill_passport_pdf(passport)

    def _build_skill_passport_pdf(self, passport: dict[str, Any]) -> bytes:
        buffer = BytesIO()
        document = SimpleDocTemplate(
            buffer,
            pagesize=LETTER,
            leftMargin=0.65 * inch,
            rightMargin=0.65 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.65 * inch,
            pageCompression=0,
            title="CELTM Skill Passport",
        )
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "PassportTitle",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=24,
            leading=28,
            textColor=colors.HexColor("#10172f"),
            spaceAfter=6,
        )
        subtitle_style = ParagraphStyle(
            "PassportSubtitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#586277"),
            spaceAfter=12,
        )
        section_title_style = ParagraphStyle(
            "SectionTitle",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            textColor=colors.HexColor("#2d5bff"),
            spaceBefore=10,
            spaceAfter=6,
        )
        body_style = ParagraphStyle(
            "PassportBody",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#1f2937"),
            alignment=TA_LEFT,
        )
        story: list[Any] = [
            Paragraph("CELTM Skill Passport", title_style),
            Paragraph(
                self._escape_html(
                    self._join_non_empty(
                        [
                            passport.get("headline")
                            or passport.get("focus_role")
                            or "Learner profile",
                            "Exported "
                            + self._format_export_timestamp(
                                str(passport.get("exported_at") or "")
                            ),
                        ],
                        " - ",
                    )
                ),
                subtitle_style,
            ),
            Paragraph(self._format_labeled_value("Name", passport["full_name"]), body_style),
            Paragraph(self._format_labeled_value("Email", passport["email"]), body_style),
            Spacer(1, 0.14 * inch),
        ]

        metrics = Table(
            [
                [
                    self._metric_cell("Readiness", f"{round(float(passport['readiness_score']))}%"),
                    self._metric_cell("Role Match", passport["role_match"] or "In progress"),
                    self._metric_cell(
                        "Security Mode", self._to_title_case(str(passport["security_mode"]))
                    ),
                    self._metric_cell("Credentials", str(len(passport["artifacts"]))),
                ]
            ],
            colWidths=[1.55 * inch, 1.9 * inch, 1.45 * inch, 1.1 * inch],
        )
        metrics.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f7f9ff")),
                    ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#d7def2")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#d7def2")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.extend([metrics, Spacer(1, 0.18 * inch)])

        story.extend(
            [
                Paragraph("Career Direction", section_title_style),
                Paragraph(
                    self._format_labeled_value(
                        "Focus role", passport["focus_role"] or "Not set"
                    ),
                    body_style,
                ),
                Paragraph(
                    self._format_labeled_value(
                        "Target industry", passport["target_industry"] or "Not set"
                    ),
                    body_style,
                ),
                Paragraph(
                    self._format_labeled_value(
                        "Weekly goal", passport["weekly_goal"] or "Not set"
                    ),
                    body_style,
                ),
                Paragraph("Professional Summary", section_title_style),
                Paragraph(
                    self._escape_html(passport["bio"] or "No professional summary saved yet."),
                    body_style,
                ),
                Paragraph("Verified Skills", section_title_style),
            ]
        )

        top_skills = passport["top_skills"] or ["No verified skills recorded yet."]
        for skill in top_skills:
            story.append(Paragraph(f"- {self._escape_html(str(skill))}", body_style))

        story.extend([Paragraph("Credential Ledger", section_title_style)])
        credentials = passport["artifacts"] or ["No credentials uploaded yet."]
        for artifact_name in credentials:
            story.append(Paragraph(f"- {self._escape_html(str(artifact_name))}", body_style))

        story.extend([Paragraph("Resume Details", section_title_style)])
        story.append(
            Paragraph(
                self._format_labeled_value(
                    "Resume file", passport["resume_file_name"] or "No resume uploaded"
                ),
                body_style,
            )
        )

        resume_highlights = passport["resume_highlights"] or []
        if resume_highlights:
            for highlight in resume_highlights:
                story.append(Paragraph(f"- {self._escape_html(str(highlight))}", body_style))
        else:
            story.append(
                Paragraph(
                    self._escape_html(
                        passport["resume_excerpt"]
                        or "No parsed resume text is available for this user yet."
                    ),
                    body_style,
                )
            )

        document.build(story)
        return buffer.getvalue()

    def _metric_cell(self, label: str, value: str) -> Table:
        styles = getSampleStyleSheet()
        label_style = ParagraphStyle(
            "MetricLabel",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#586277"),
        )
        value_style = ParagraphStyle(
            "MetricValue",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=14,
            textColor=colors.HexColor("#10172f"),
        )
        cell = Table(
            [
                [Paragraph(self._escape_html(label), label_style)],
                [Paragraph(self._escape_html(value), value_style)],
            ],
            colWidths=["*"],
        )
        cell.setStyle(
            TableStyle(
                [
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        return cell

    def _extract_resume_highlights(self, resume_text: str) -> list[str]:
        normalized = re.sub(r"\s+", " ", resume_text).strip()
        if not normalized:
            return []

        segments = [
            segment.strip(" -;,.")
            for segment in re.split(r"(?<=[.!?])\s+|\s*[|•]\s*|;\s+", normalized)
            if segment.strip(" -;,.")
        ]
        highlights: list[str] = []
        seen: set[str] = set()

        for segment in segments:
            if len(segment) < 18:
                continue
            lowered = segment.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            highlights.append(segment[:220])
            if len(highlights) == 6:
                break

        return highlights

    def _build_resume_excerpt(self, resume_text: str) -> str:
        normalized = re.sub(r"\s+", " ", resume_text).strip()
        if not normalized:
            return ""
        return normalized[:1400]

    def _format_labeled_value(self, label: str, value: str) -> str:
        return (
            f"<font name='Helvetica-Bold'>{self._escape_html(label)}:</font> "
            f"{self._escape_html(value)}"
        )

    def _format_export_timestamp(self, value: str) -> str:
        if not value:
            return "now"
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
        return parsed.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    def _join_non_empty(self, values: list[str], separator: str) -> str:
        return separator.join(value for value in values if value)

    def _sanitize_file_name(self, value: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
        normalized = normalized.strip("-")
        return f"{normalized or 'celtm-user'}-skill-passport.pdf"

    def _to_title_case(self, value: str) -> str:
        return value.replace("_", " ").title()

    def _escape_html(self, value: str) -> str:
        return (
            str(value)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )
