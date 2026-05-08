from __future__ import annotations

import re
from datetime import datetime, timezone

from app.models.enums import DomainEventType
from app.repositories.learning_repository import LearningRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.skill_repository import SkillRepository
from app.services.domain_event_service import DomainEventService
from app.services.learning_service import LearningService
from app.services.skill_request_service import SkillRequestService
from app.services.skill_service import SkillService
from app.utils.text import normalize_name


class TrajectoryService:
    def __init__(
        self,
        repository: LearningRepository,
        profile_repository: ProfileRepository,
        skill_repository: SkillRepository,
        skill_service: SkillService,
        learning_service: LearningService,
        skill_request_service: SkillRequestService,
        event_service: DomainEventService,
    ) -> None:
        self.repository = repository
        self.profile_repository = profile_repository
        self.skill_repository = skill_repository
        self.skill_service = skill_service
        self.learning_service = learning_service
        self.skill_request_service = skill_request_service
        self.event_service = event_service

    async def get_trajectory(self, user_id: str, role_name: str) -> dict:
        requirements = await self.skill_repository.list_role_requirements(role_name)
        learning_path = await self.learning_service.get_learning_path(user_id, role_name)
        fit = await self.skill_service.get_role_fit(user_id)
        trajectory = {
            "role_name": role_name,
            "fit_score": fit["fit_score"] if fit["role_name"] == role_name else 0.0,
            "required_skills": [item["skill_name"] for item in requirements],
            "modules": learning_path["modules"],
        }
        await self.repository.upsert_trajectory_roles(
            [
                {
                    "user_id": user_id,
                    "role_name": role_name,
                    "fit_score": trajectory["fit_score"],
                    "payload": trajectory,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            ]
        )
        return trajectory

    async def bootstrap_user_path(self, user_id: str, role_name: str | None = None) -> dict:
        profile = await self.profile_repository.get_profile(user_id)
        metadata = (profile or {}).get("metadata") or {}
        resolved_role_name = str(
            role_name or (profile or {}).get("focus_role") or ""
        ).strip()

        if not resolved_role_name:
            role_fit = await self.skill_service.get_role_fit(user_id)
            resolved_role_name = (
                role_fit["role_name"] if role_fit["role_name"] != "Unassigned" else ""
            )

        role_requirements = (
            await self.skill_repository.list_role_requirements(resolved_role_name)
            if resolved_role_name
            else []
        )
        artifacts = await self.profile_repository.list_artifacts(user_id, limit=50)
        onboarding_artifacts = [
            artifact
            for artifact in artifacts
            if str(artifact.get("file_type") or "").lower() != "written_assessment"
        ]
        artifact_text = "\n".join(
            str(artifact.get("extracted_text") or "").strip()
            for artifact in onboarding_artifacts
            if str(artifact.get("extracted_text") or "").strip()
        )
        normalized_corpus = normalize_name(artifact_text)
        corpus_tokens = {
            token
            for token in re.split(r"[^a-z0-9]+", normalized_corpus)
            if len(token) >= 3
        }
        normalized_reported_skills = {
            normalize_name(str(item).strip())
            for item in metadata.get("self_reported_skills") or []
            if str(item).strip()
        }

        active_skills = await self.skill_repository.list_active_skills(limit=500)
        candidate_skills: dict[str, dict[str, str]] = {
            normalize_name(item["skill_name"]): {
                "skill_id": item["skill_id"],
                "skill_name": item["skill_name"],
            }
            for item in active_skills
            if item.get("skill_name") and item.get("skill_id")
        }
        for requirement in role_requirements:
            normalized_name = normalize_name(requirement["skill_name"])
            candidate_skills.setdefault(
                normalized_name,
                {
                    "skill_id": normalized_name,
                    "skill_name": requirement["skill_name"],
                },
            )

        existing_skills = await self.skill_repository.list_user_skills(user_id)
        existing_scores = {
            item["skill_name"]: float(item.get("proficiency_score") or 0.0)
            for item in existing_skills
        }
        detected_skills: list[str] = []
        seeded_skills: list[str] = []

        for normalized_name, candidate in candidate_skills.items():
            self_match = self._matches_reported_skill(
                normalized_name=normalized_name,
                normalized_reported_skills=normalized_reported_skills,
            )
            artifact_match = self._matches_artifact_corpus(
                normalized_name=normalized_name,
                corpus_tokens=corpus_tokens,
                normalized_corpus=normalized_corpus,
            )
            if not self_match and not artifact_match:
                continue

            detected_skills.append(candidate["skill_name"])
            baseline_score = 68.0 if self_match and artifact_match else 62.0 if self_match else 58.0
            if existing_scores.get(candidate["skill_name"], 0.0) >= baseline_score:
                continue

            seeded_skills.append(candidate["skill_name"])
            await self.skill_service.record_skill_measurement(
                user_id=user_id,
                skill_id=candidate["skill_id"],
                skill_name=candidate["skill_name"],
                proficiency_score=baseline_score,
                source="onboarding_bootstrap",
            )

        learning_path = (
            await self.learning_service.get_learning_path(user_id, resolved_role_name)
            if resolved_role_name
            else {"role_name": "", "modules": []}
        )

        await self.event_service.emit(
            event_type=DomainEventType.DASHBOARD_REFRESH_REQUESTED,
            aggregate_type="profile",
            aggregate_id=user_id,
            payload={"user_id": user_id, "role_name": resolved_role_name},
        )

        return {
            "role_name": resolved_role_name,
            "detected_skills": sorted(set(detected_skills)),
            "seeded_skills": sorted(set(seeded_skills)),
            "skill_request_names": [],
            "modules": learning_path["modules"],
        }

    async def get_alternate_roles(self, user_id: str) -> list[dict]:
        roles = await self.skill_repository.list_roles()
        alternates = []
        for role in roles[:5]:
            trajectory = await self.get_trajectory(user_id, role["role_name"])
            alternates.append(trajectory)
        return sorted(alternates, key=lambda item: item["fit_score"], reverse=True)

    def _matches_reported_skill(
        self,
        *,
        normalized_name: str,
        normalized_reported_skills: set[str],
    ) -> bool:
        for reported_name in normalized_reported_skills:
            if reported_name == normalized_name:
                return True
            if normalized_name in reported_name or reported_name in normalized_name:
                return True
        return False

    def _matches_artifact_corpus(
        self,
        *,
        normalized_name: str,
        corpus_tokens: set[str],
        normalized_corpus: str,
    ) -> bool:
        if not normalized_corpus:
            return False

        if normalized_name in normalized_corpus:
            return True

        name_tokens = [token for token in normalized_name.split("-") if len(token) >= 3]
        if not name_tokens:
            return False

        required_matches = max(1, min(2, len(name_tokens)))
        return sum(token in corpus_tokens for token in name_tokens) >= required_matches
