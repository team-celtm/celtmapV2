from __future__ import annotations

from datetime import datetime, timezone

from app.repositories.profile_repository import ProfileRepository
from app.repositories.report_repository import ReportRepository
from app.services.schedule_service import ScheduleService
from app.services.skill_service import SkillService


class DashboardService:
    def __init__(
        self,
        report_repository: ReportRepository,
        skill_service: SkillService,
        schedule_service: ScheduleService,
        profile_repository: ProfileRepository,
    ) -> None:
        self.report_repository = report_repository
        self.skill_service = skill_service
        self.schedule_service = schedule_service
        self.profile_repository = profile_repository

    async def build_summary_payload(self, user_id: str) -> dict:
        try:
            import asyncio
            
            # Fetch all components in parallel
            results = await asyncio.gather(
                self.skill_service.get_role_fit(user_id),
                self.skill_service.list_user_skills(user_id),
                self.skill_service.list_hidden_candidates(user_id),
                self.schedule_service.list_events(user_id, limit=1, cursor=None),
                self.report_repository.get_latest_report(user_id),
                self.profile_repository.get_profile(user_id),
                return_exceptions=True
            )
            
            role_fit = results[0] if not isinstance(results[0], Exception) else None
            user_skills = results[1] if not isinstance(results[1], Exception) else []
            hidden = results[2] if not isinstance(results[2], Exception) else []
            events = results[3] if not isinstance(results[3], Exception) else []
            latest_report = results[4] if not isinstance(results[4], Exception) else None
            profile = results[5] if not isinstance(results[5], Exception) else {}

            role_fit = role_fit or {
                "role_name": "Generalist", "fit_score": 0.0, "matched_skills": [], "missing_skills": []
            }
            
            # ALWAYS recalculate to ensure real-time accuracy
            import logging
            logging.info("DashboardService: Forcing skill recalculation for %s", user_id)
            recovered = await self.skill_service.recalculate_from_assessments(user_id)
            if recovered:
                logging.info("DashboardService: Skills recalculated, refreshing lists")
                user_skills = await self.skill_service.list_user_skills(user_id)
                role_fit = await self.skill_service.get_role_fit(user_id)
            logging.info("DashboardService: User skills count: %d", len(user_skills))

            domain_breakdown = await self.skill_service.get_domain_readiness(user_id)

            skills = sorted(
                user_skills,
                key=lambda item: float(item.get("proficiency_score") or 0.0),
                reverse=True,
            )
            
            # Initial readiness logic: check profile metadata for placement scores
            placement_score = 0.0
            if profile and isinstance(profile, dict) and profile.get("metadata"):
                placement_score = float(profile["metadata"].get("placement_overall_score") or 0.0)

            # Final readiness is max of role fit or placement score if role fit is low
            readiness = float(role_fit.get("fit_score", 0.0))
            if readiness < 5.0: # If less than 5%, use placement score as anchor
                readiness = max(readiness, placement_score)

            # Map skills to names, with fallback to ID if join failed
            top_skills = []
            for item in skills[:5]:
                name = item.get("skill_name")
                if not name:
                    # Try to derive from ID if name mapping is missing
                    raw_id = str(item.get("skill_id") or "Unknown")
                    name = raw_id.replace("-", " ").title()
                top_skills.append(name)

            return {
                "user_id": user_id,
                "readiness_score": readiness,
                "role_fit": role_fit.get("fit_score", 0.0),
                "top_skills": top_skills,
                "domain_breakdown": domain_breakdown,
                "pending_hidden_skills": len([item for item in hidden if isinstance(item, dict) and item.get("status") == "pending"]),
                "next_event": events[0] if events else None,
                "latest_report_id": latest_report.get("id") if latest_report else None,
                "latest_report_created_at": latest_report.get("created_at") if latest_report else None,
            }

        except Exception as e:
            # Diagnostic logging for "MAKE IT RUN" mandate
            print(f"[DashboardService] build_summary_payload failure for {user_id}: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # Fallback for completely empty profiles
            return {
                "user_id": user_id,
                "readiness_score": 0.0,
                "role_fit": 0.0,
                "top_skills": [],
                "domain_breakdown": {}, # MISSING IN PREVIOUS IMPLEMENTATION
                "pending_hidden_skills": 0,
                "next_event": None,
                "latest_report_id": None,
                "latest_report_created_at": None,
                "error": str(e)
            }



    async def get_summary(self, user_id: str, refresh: bool = False) -> dict:
        import logging
        logging.info("DashboardService: get_summary called for %s (refresh=%s)", user_id, refresh)
        if refresh:
            await self.skill_service.recalculate_from_assessments(user_id)

        # Build fresh payload
        payload = await self.build_summary_payload(user_id)
        logging.info("DashboardService: Dashboard payload built")

        # Optional fallback UX: if no real skills, check projection for initial placement data
        if not payload.get("top_skills"):
            projection = await self.report_repository.get_projection(user_id)
            if projection:
                proj_payload = projection.get("payload", {})
                if proj_payload.get("top_skills"):
                    logging.info("DashboardService: Using projection fallback for top_skills")
                    payload["top_skills"] = proj_payload.get("top_skills", [])
                    payload["readiness_score"] = max(payload.get("readiness_score", 0.0), proj_payload.get("readiness_score", 0.0))


        await self.report_repository.upsert_projection(
            {
                "user_id": user_id,
                "payload": payload,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        return payload
