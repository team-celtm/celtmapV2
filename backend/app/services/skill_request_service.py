from __future__ import annotations

import asyncio
import hashlib
import re
import time
from datetime import datetime, timezone, timedelta
from typing import Any

from app.core.exceptions import NotFoundError
from app.integrations.llm import OpenAIProvider
from app.models.enums import DomainEventType
from app.repositories.assessment_repository import AssessmentRepository
from app.repositories.skill_repository import SkillRepository
from app.services.domain_event_service import DomainEventService
from app.services.ops_service import OpsService
from app.services.rag_service import RagService
from app.services.schedule_service import ScheduleService
from app.utils.text import normalize_name

MCQ_BANK_SIZE = 12
SITUATIONAL_BANK_SIZE = 6
BLUEPRINT_GENERATION_TIMEOUT_SECONDS = 12


class SkillRequestService:
    def __init__(
        self,
        repository: SkillRepository,
        assessment_repository: AssessmentRepository,
        rag_service: RagService,
        llm_provider: OpenAIProvider,
        ops_service: OpsService,
        schedule_service: ScheduleService | None = None,
        event_service: DomainEventService | None = None,
    ) -> None:
        self.repository = repository
        self.assessment_repository = assessment_repository
        self.rag_service = rag_service
        self.llm_provider = llm_provider
        self.ops_service = ops_service
        self.schedule_service = schedule_service
        self.event_service = event_service

    async def list_requests(self, user_id: str) -> list[dict]:
        return await self.repository.list_skill_requests(user_id)

    async def get_request_for_user(self, user_id: str, request_id: str) -> dict | None:
        request = await self.repository.get_skill_request(request_id)
        if request is None or request["user_id"] != user_id:
            return None
        return request

    async def ensure_question_bank(self, *, request_id: str) -> dict | None:
        request = await self.repository.get_skill_request(request_id)
        if request is None:
            return None

        generated_payload = request.get("generated_payload")
        usable_payload: dict[str, Any] | None = None
        if isinstance(generated_payload, dict) and generated_payload:
            usable_payload = self._sanitize_blueprint(
                request["requested_name"],
                request["normalized_name"],
                generated_payload,
                request.get("description"),
            )
        mcq_count = len(usable_payload["mcq_questions"]) if usable_payload else 0
        situational_count = len(usable_payload["situational_questions"]) if usable_payload else 0
        written_prompt = str(usable_payload["written_prompt"]).strip() if usable_payload else ""

        if (
            usable_payload
            and mcq_count >= MCQ_BANK_SIZE
            and situational_count >= SITUATIONAL_BANK_SIZE
            and written_prompt
        ):
            if usable_payload != request.get("generated_payload"):
                request = await self.repository.update_skill_request(
                    request_id,
                    {
                        "generated_payload": usable_payload,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
            await self._persist_generated_questions(
                skill_id=request["matched_skill_id"],
                skill_request_id=request["id"],
                requested_name=request["requested_name"],
                blueprint=usable_payload,
            )
            await self._ensure_written_prompt_question(
                skill_id=request["matched_skill_id"],
                skill_request_id=request["id"],
                skill_name=request["requested_name"],
                written_prompt=written_prompt,
            )
            return request

        existing_skill = await self.repository.get_skill_by_name(request["normalized_name"])
        blueprint = await self._generate_blueprint(
            requested_name=request["requested_name"],
            normalized_name=request["normalized_name"],
            description=self._merge_context_description(
                request.get("description"),
                existing_skill.get("description") if existing_skill else None,
                existing_skill.get("industry_usage") if existing_skill else None,
            ),
            user_id=request["user_id"],
        )
        updated_request = await self.repository.update_skill_request(
            request_id,
            {
                "generated_payload": blueprint,
                "generation_status": "generated_refreshed",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        await self._persist_generated_questions(
            skill_id=request["matched_skill_id"],
            skill_request_id=request["id"],
            requested_name=request["requested_name"],
            blueprint=blueprint,
        )
        await self._ensure_written_prompt_question(
            skill_id=request["matched_skill_id"],
            skill_request_id=request["id"],
            skill_name=request["requested_name"],
            written_prompt=blueprint["written_prompt"],
        )
        return updated_request

    async def create_request(
        self,
        *,
        user_id: str,
        requested_name: str,
        requested_type: str = "skill",
        description: str | None = None,
        fast_generation: bool = False,
        strict_bank_match: bool = False,
    ) -> dict:
        now = datetime.now(timezone.utc)
        validation_ready_at = (now + timedelta(minutes=30)).isoformat()
        normalized_name = normalize_name(requested_name)
        existing_request = await self.repository.get_user_skill_request(user_id, normalized_name)
        if existing_request is not None:
            existing_request = await self._ensure_validation_schedule(
                request=existing_request,
                requested_name=requested_name,
                validation_ready_at=validation_ready_at,
            )
            await self._emit_dashboard_refresh(
                user_id=user_id,
                request_id=existing_request["id"],
                requested_name=requested_name,
            )
            return existing_request

        available_bank = await self._locate_existing_question_bank(
            requested_name=requested_name,
            normalized_name=normalized_name,
            description=description,
        )
        if available_bank is not None:
            return await self._create_bank_backed_request(
                user_id=user_id,
                requested_name=requested_name,
                requested_type=requested_type,
                normalized_name=normalized_name,
                validation_ready_at=now.isoformat(),
                available_bank=available_bank,
            )

        if strict_bank_match:
            raise NotFoundError(
                "Subject not available at the moment.",
                error_code="subject_not_available",
            )

        existing_skill = await self.repository.get_skill_by_name(normalized_name)
        if existing_skill is not None:
            merged_description = self._merge_context_description(
                description,
                existing_skill.get("description"),
                existing_skill.get("industry_usage"),
            )
            blueprint = (
                self._heuristic_blueprint(requested_name, normalized_name, merged_description)
                if fast_generation
                else await self._generate_blueprint(
                    requested_name=requested_name,
                    normalized_name=normalized_name,
                    description=merged_description,
                    user_id=user_id,
                )
            )
            request = await self.repository.upsert_skill_request(
                {
                    "user_id": user_id,
                    "requested_name": requested_name,
                    "normalized_name": normalized_name,
                    "requested_type": requested_type,
                    "matched_skill_id": existing_skill["skill_id"],
                    "status": "pending_validation",
                    "generation_status": (
                        "reused_catalog_fast" if fast_generation else "reused_catalog"
                    ),
                    "generated_payload": blueprint,
                    "metadata": self._build_request_metadata(
                        cache_source="catalog_fast" if fast_generation else "catalog",
                        validation_ready_at=validation_ready_at,
                    ),
                    "updated_at": now.isoformat(),
                }
            )
            await self._persist_generated_questions(
                skill_id=existing_skill["skill_id"],
                skill_request_id=request["id"],
                requested_name=requested_name,
                blueprint=blueprint,
            )
            await self._ensure_written_prompt_question(
                skill_id=existing_skill["skill_id"],
                skill_request_id=request["id"],
                skill_name=requested_name,
                written_prompt=blueprint["written_prompt"],
            )
            request = await self._ensure_validation_schedule(
                request=request,
                requested_name=requested_name,
                validation_ready_at=validation_ready_at,
            )
            await self._emit_dashboard_refresh(
                user_id=user_id,
                request_id=request["id"],
                requested_name=requested_name,
            )
            return request

        reusable_request = await self.repository.get_reusable_skill_request(normalized_name)
        reusable_payload = (
            reusable_request.get("generated_payload")
            if isinstance(reusable_request, dict)
            else None
        )
        if isinstance(reusable_payload, dict) and reusable_payload:
            blueprint = self._sanitize_blueprint(
                requested_name,
                normalized_name,
                reusable_payload,
                description,
            )
            reusable_skill_id = (
                reusable_request.get("matched_skill_id")
                or reusable_request.get("promoted_skill_id")
                or normalized_name
            )
            skill = await self.repository.get_skill_by_source_id(reusable_skill_id)
            if skill is None:
                skill = await self.repository.upsert_skill_catalog(
                    {
                        "skill_id": reusable_skill_id,
                        "skill_name": requested_name,
                        "normalized_name": normalized_name,
                        "description": blueprint["description"],
                        "industry_usage": blueprint["industry_usage"],
                        "hidden_skills_supported": blueprint["hidden_skills_supported"],
                        "metadata": {
                            "source": "skill_request_reuse",
                            "written_prompt": blueprint["written_prompt"],
                            "interview_focus": blueprint["interview_focus"],
                            "subskills": blueprint["subskills"],
                        },
                        "status": "active",
                        "is_generated": True,
                        "is_active": True,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
            request = await self.repository.upsert_skill_request(
                {
                    "user_id": user_id,
                    "requested_name": requested_name,
                    "normalized_name": normalized_name,
                    "requested_type": requested_type,
                    "matched_skill_id": skill["skill_id"],
                    "status": "pending_validation",
                    "generation_status": "reused_generated",
                    "generated_payload": blueprint,
                    "metadata": self._build_request_metadata(
                        cache_source="reused_generated",
                        validation_ready_at=validation_ready_at,
                    ),
                    "updated_at": now.isoformat(),
                }
            )
            await self._persist_generated_catalog(
                skill_id=skill["skill_id"],
                skill_request_id=request["id"],
                requested_name=requested_name,
                blueprint=blueprint,
            )
            await self._ensure_written_prompt_question(
                skill_id=skill["skill_id"],
                skill_request_id=request["id"],
                skill_name=requested_name,
                written_prompt=blueprint["written_prompt"],
            )
            request = await self._ensure_validation_schedule(
                request=request,
                requested_name=requested_name,
                validation_ready_at=validation_ready_at,
            )
            await self._emit_dashboard_refresh(
                user_id=user_id,
                request_id=request["id"],
                requested_name=requested_name,
            )
            return request

        blueprint = (
            self._heuristic_blueprint(requested_name, normalized_name, description)
            if fast_generation
            else await self._generate_blueprint(
                requested_name=requested_name,
                normalized_name=normalized_name,
                description=description,
                user_id=user_id,
            )
        )
        skill = await self.repository.upsert_skill_catalog(
            {
                "skill_id": normalized_name,
                "skill_name": requested_name,
                "normalized_name": normalized_name,
                "description": blueprint["description"],
                "industry_usage": blueprint["industry_usage"],
                "hidden_skills_supported": blueprint["hidden_skills_supported"],
                "metadata": {
                    "source": "skill_request",
                    "written_prompt": blueprint["written_prompt"],
                    "interview_focus": blueprint["interview_focus"],
                    "subskills": blueprint["subskills"],
                    "situational_question_count": len(blueprint["situational_questions"]),
                },
                "status": "active",
                "is_generated": True,
                "is_active": True,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        request = await self.repository.upsert_skill_request(
            {
                "user_id": user_id,
                "requested_name": requested_name,
                "normalized_name": normalized_name,
                "requested_type": requested_type,
                "matched_skill_id": skill["skill_id"],
                "status": "pending_validation",
                "generation_status": "generated_fast" if fast_generation else "generated",
                "generated_payload": blueprint,
                "metadata": self._build_request_metadata(
                    cache_source="generated_fast" if fast_generation else "generated",
                    validation_ready_at=validation_ready_at,
                ),
                "updated_at": now.isoformat(),
            }
        )
        await self._persist_generated_catalog(
            skill_id=skill["skill_id"],
            skill_request_id=request["id"],
            requested_name=requested_name,
            blueprint=blueprint,
        )
        await self._ensure_written_prompt_question(
            skill_id=skill["skill_id"],
            skill_request_id=request["id"],
            skill_name=requested_name,
            written_prompt=blueprint["written_prompt"],
        )
        request = await self._ensure_validation_schedule(
            request=request,
            requested_name=requested_name,
            validation_ready_at=validation_ready_at,
        )
        await self._emit_dashboard_refresh(
            user_id=user_id,
            request_id=request["id"],
            requested_name=requested_name,
        )
        return request

    async def _locate_existing_question_bank(
        self,
        *,
        requested_name: str,
        normalized_name: str,
        description: str | None,
    ) -> dict[str, Any] | None:
        if self.assessment_repository is None:
            return None

        existing_skill = await self.repository.get_skill_by_name(normalized_name)
        existing_subject = await self.repository.get_subject_by_name(normalized_name)
        skill_id = (
            (existing_skill or {}).get("skill_id")
            or (existing_subject or {}).get("subject_id")
            or normalized_name
        )
        question_bank = await self.assessment_repository.find_question_bank(
            requested_name=requested_name,
            normalized_name=normalized_name,
            skill_id=skill_id,
        )
        if question_bank is None:
            return None

        skill = existing_skill
        if skill is None:
            metadata = (existing_subject or {}).get("metadata") or {}
            skill = await self.repository.upsert_skill_catalog(
                {
                    "skill_id": skill_id,
                    "skill_name": (existing_subject or {}).get("subject_name") or requested_name,
                    "normalized_name": normalized_name,
                    "description": self._merge_context_description(
                        description,
                        (existing_subject or {}).get("description"),
                    )
                    or f"Assessment track for {requested_name}.",
                    "industry_usage": (existing_subject or {}).get("industry_relevance"),
                    "hidden_skills_supported": [],
                    "metadata": {
                        "source": "question_bank",
                        "written_prompt": (
                            f"Write a structured response showing how you would apply "
                            f"{requested_name} in a realistic scenario."
                        ),
                        "interview_focus": metadata.get("interview_focus", []),
                        "subskills": metadata.get("subskills", []),
                    },
                    "status": "active",
                    "is_generated": False,
                    "is_active": True,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            )

        return {
            "skill": skill,
            "subject": existing_subject,
            "question_bank": question_bank,
            "payload": self._catalog_payload(skill),
        }

    async def _create_bank_backed_request(
        self,
        *,
        user_id: str,
        requested_name: str,
        requested_type: str,
        normalized_name: str,
        validation_ready_at: str,
        available_bank: dict[str, Any],
    ) -> dict:
        skill = available_bank["skill"]
        payload = available_bank["payload"]
        payload["written_prompt"] = payload.get("written_prompt") or (
            f"Write a structured response showing how you would apply "
            f"{requested_name} in a realistic scenario."
        )

        request = await self.repository.upsert_skill_request(
            {
                "user_id": user_id,
                "requested_name": requested_name,
                "normalized_name": normalized_name,
                "requested_type": requested_type,
                "matched_skill_id": skill["skill_id"],
                "status": "pending_validation",
                "generation_status": "available_in_bank",
                "generated_payload": payload,
                "metadata": self._build_request_metadata(
                    cache_source="question_bank",
                    validation_ready_at=validation_ready_at,
                    validation_message="Subject available in question bank.",
                ),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        await self._ensure_written_prompt_question(
            skill_id=skill["skill_id"],
            skill_request_id=request["id"],
            skill_name=requested_name,
            written_prompt=str(payload["written_prompt"]),
        )
        request = await self._ensure_validation_schedule(
            request=request,
            requested_name=requested_name,
            validation_ready_at=validation_ready_at,
        )
        await self._emit_dashboard_refresh(
            user_id=user_id,
            request_id=request["id"],
            requested_name=requested_name,
        )
        return request

    async def record_mcq_score(self, request_id: str, score: float) -> dict:
        await self.repository.update_skill_request(
            request_id,
            {
                "mcq_score": round(score, 2),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return await self.evaluate_promotion(request_id)

    async def record_written_score(
        self,
        request_id: str,
        score: float,
        feedback: str | None = None,
    ) -> dict:
        request = await self.repository.get_skill_request(request_id)
        metadata: dict[str, Any] = dict(request.get("metadata") or {}) if request else {}
        if feedback:
            metadata["written_feedback"] = feedback
        await self.repository.update_skill_request(
            request_id,
            {
                "written_score": round(score, 2),
                "metadata": metadata,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return await self.evaluate_promotion(request_id)

    async def record_interview_score(self, request_id: str, score: float) -> dict:
        await self.repository.update_skill_request(
            request_id,
            {
                "interview_score": round(score, 2),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return await self.evaluate_promotion(request_id)

    async def evaluate_promotion(self, request_id: str) -> dict:
        request = await self.repository.get_skill_request(request_id)
        if request is None:
            return {"status": "missing", "request_id": request_id}

        mcq_score = request.get("mcq_score")
        written_score = request.get("written_score")
        interview_score = request.get("interview_score")
        if None in (mcq_score, written_score, interview_score):
            return request

        overall_score = self.compute_promotion_score(
            mcq_score=float(mcq_score),
            written_score=float(written_score),
            interview_score=float(interview_score),
        )
        update_payload: dict[str, Any] = {
            "overall_score": overall_score,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if self.qualifies_for_promotion(
            mcq_score=float(mcq_score),
            written_score=float(written_score),
            interview_score=float(interview_score),
            overall_score=overall_score,
        ):
            update_payload.update(
                {
                    "status": "promoted",
                    "promoted_skill_id": request["matched_skill_id"],
                    "promoted_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            await self._promote_to_user_skill(request, overall_score)
        else:
            update_payload.update(
                {
                    "status": "rejected",
                    "rejected_at": datetime.now(timezone.utc).isoformat(),
                }
            )
        updated_request = await self.repository.update_skill_request(request_id, update_payload)
        await self._update_validation_status(updated_request)
        await self._emit_dashboard_refresh(
            user_id=updated_request["user_id"],
            request_id=updated_request["id"],
            requested_name=updated_request["requested_name"],
        )
        return updated_request

    async def apply_admin_override(
        self,
        request_id: str,
        decision: str,
        reason: str | None = None,
    ) -> dict:
        request = await self.repository.get_skill_request(request_id)
        if request is None:
            return {"status": "missing", "request_id": request_id}

        decision_value = decision.strip().lower()
        payload: dict[str, Any] = {
            "admin_override_status": decision_value,
            "admin_override_reason": reason,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if decision_value == "promote":
            payload.update(
                {
                    "status": "promoted",
                    "promoted_skill_id": request["matched_skill_id"],
                    "promoted_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            overall_score = request.get("overall_score") or self.compute_promotion_score(
                mcq_score=float(request.get("mcq_score") or 0.0),
                written_score=float(request.get("written_score") or 0.0),
                interview_score=float(request.get("interview_score") or 0.0),
            )
            payload["overall_score"] = overall_score
            await self._promote_to_user_skill(request, float(overall_score))
        elif decision_value == "reject":
            payload.update(
                {
                    "status": "rejected",
                    "rejected_at": datetime.now(timezone.utc).isoformat(),
                }
            )
        else:
            raise ValueError("Unsupported admin override decision")
        updated_request = await self.repository.update_skill_request(request_id, payload)
        await self._update_validation_status(updated_request)
        await self._emit_dashboard_refresh(
            user_id=updated_request["user_id"],
            request_id=updated_request["id"],
            requested_name=updated_request["requested_name"],
        )
        return updated_request

    def compute_promotion_score(
        self,
        *,
        mcq_score: float,
        written_score: float,
        interview_score: float,
    ) -> float:
        return round(
            (mcq_score * 0.40) + (written_score * 0.30) + (interview_score * 0.30),
            2,
        )

    def qualifies_for_promotion(
        self,
        *,
        mcq_score: float,
        written_score: float,
        interview_score: float,
        overall_score: float,
    ) -> bool:
        return overall_score >= 65 and min(mcq_score, written_score, interview_score) >= 50

    async def _promote_to_user_skill(self, request: dict, overall_score: float) -> dict:
        matched_skill_id = request.get("matched_skill_id")
        skill = None
        if matched_skill_id:
            skill = await self.repository.get_skill_by_id(matched_skill_id)
        
        if not skill:
            skill = await self.repository.get_skill_by_name(request["requested_name"])
            
        skill_name = skill["name"] if skill else request["requested_name"]
        skill_id = skill["id"] if skill else None
        
        return await self.repository.upsert_user_skill(
            {
                "user_id": request["user_id"],
                "skill_id": skill_id,
                "source": "inferred", # Maps to allowed enum
                "proficiency_score": round(overall_score, 2),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    async def _persist_generated_catalog(
        self,
        *,
        skill_id: str,
        skill_request_id: str,
        requested_name: str,
        blueprint: dict[str, Any],
    ) -> None:
        skill_record = await self.repository.get_skill_by_id(skill_id)
        if skill_record is None:
            # Try by name if ID was passed as a name
            skill_record = await self.repository.get_skill_by_name(requested_name)
            if skill_record is None:
                return

        # Use actual skill ID (UUID)
        skill_uuid = skill_record["id"]

        for index, subskill_name in enumerate(blueprint["subskills"], start=1):
            await self.repository.upsert_subskill(
                {
                    "skill_id": skill_uuid,
                    "name": subskill_name,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )

        await self._persist_generated_questions(
            skill_id=skill_uuid,
            skill_request_id=skill_request_id,
            requested_name=requested_name,
            blueprint=blueprint,
        )

        await self.rag_service.upsert_knowledge(
            user_id=None, # Global knowledge
            content=f"Skill: {requested_name}\nDescription: {blueprint['description']}\nIndustry Usage: {blueprint['industry_usage']}\nSubskills: {', '.join(blueprint['subskills'])}\nInterview Focus: {', '.join(blueprint['interview_focus'])}",
            metadata={
                "source": "skill_request",
                "skill_name": requested_name,
                "skill_id": skill_id
            }
        )

    async def _persist_generated_questions(
        self,
        *,
        skill_id: str,
        skill_request_id: str,
        requested_name: str,
        blueprint: dict[str, Any],
    ) -> None:
        await self._persist_question_set(
            skill_id=skill_id,
            skill_request_id=skill_request_id,
            requested_name=requested_name,
            question_type="MCQ",
            questions=blueprint["mcq_questions"],
        )
        await self._persist_question_set(
            skill_id=skill_id,
            skill_request_id=skill_request_id,
            requested_name=requested_name,
            question_type="SITUATIONAL",
            questions=blueprint["situational_questions"],
        )

    async def _persist_question_set(
        self,
        *,
        skill_id: str,
        skill_request_id: str,
        requested_name: str,
        question_type: str,
        questions: list[dict[str, Any]],
    ) -> None:
        for question in questions:
            # Map options list into A, B, C, D
            options = question.get("options", [])
            correct_opt = "A"
            for opt in options:
                if opt.get("is_correct"):
                    correct_opt = opt["option_key"]
                    break
            
            payload = {
                "skill_id": skill_id,
                "question_text": question["question_text"],
                "subject_id": requested_name, # Map to subject_id column
                "difficulty": question["difficulty"],
                "question_type": question_type,
                "is_active": True,
                "option_a": options[0]["option_text"] if len(options) > 0 else "N/A",
                "option_b": options[1]["option_text"] if len(options) > 1 else "N/A",
                "option_c": options[2]["option_text"] if len(options) > 2 else "N/A",
                "option_d": options[3]["option_text"] if len(options) > 3 else "N/A",
                "correct_option": correct_opt,
                "metadata": {
                    "skill_request_id": skill_request_id,
                    "expected_concepts": question.get("expected_concepts", []),
                    "explanation": question.get("explanation"),
                }
            }
            
            if question_type == "situational_mcq":
                payload["scenario"] = question.get("scenario", "Follow the technical requirements.")

            await self.assessment_repository.upsert_question(payload)

    async def _ensure_written_prompt_question(
        self,
        *,
        skill_id: str,
        skill_request_id: str,
        skill_name: str,
        written_prompt: str,
    ) -> None:
        await self.assessment_repository.upsert_question(
            {
                "skill_id": skill_id,
                "skill_name": skill_name,
                "skill_request_id": skill_request_id,
                "question_text": written_prompt,
                "category": skill_name,
                "difficulty": "advanced",
                "question_type": "WRITTEN",
                "sample_answer": "Structure a concise, evidence-backed response.",
                "expected_concepts": [
                    "root cause analysis",
                    "tradeoff reasoning",
                    "implementation plan",
                    "validation strategy",
                ],
                "is_generated": True,
                "is_active": True,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    async def _generate_blueprint(
        self,
        *,
        requested_name: str,
        normalized_name: str,
        description: str | None,
        user_id: str,
    ) -> dict[str, Any]:
        context = await self._build_generation_context(
            requested_name=requested_name,
            description=description,
            user_id=user_id,
        )
        
        # Define specialized prompts for parallel execution
        base_context = (
            f"Skill name: {requested_name}. "
            f"User context: {description or 'No additional description.'} "
            f"Strength: {'rich' if context['has_rich_context'] else 'limited'}. "
            f"CELTM Context:\n{context['context_summary']}"
        )

        prompts = {
            "metadata": (
                "Generate CELTM metadata as JSON with keys: "
                "description, industry_usage, hidden_skills_supported, "
                "subskills, interview_focus, written_prompt. "
                "Ensure industry_usage focuses on production delivery. "
                f"{base_context}"
            ),
            "mcq": (
                f"Generate exactly {MCQ_BANK_SIZE} technical MCQ items as JSON "
                "under key 'mcq_questions'. "
                "Each item must have: question_text, difficulty, "
                "expected_concepts, options. "
                "Options must be a list of 4 objects with: option_key, "
                "option_text, is_correct (bool). "
                f"{base_context}"
            ),
            "situational": (
                f"Generate exactly {SITUATIONAL_BANK_SIZE} situational items as "
                "JSON under key 'situational_questions'. "
                "Each item must have: question_text, scenario (rich context), "
                "difficulty, expected_concepts, options, sample_answer. "
                "Options must be a list of 4 objects with: option_key, "
                "option_text, is_correct (bool). "
                f"{base_context}"
            ),
        }

        if not self.llm_provider.enabled:
            return self._heuristic_blueprint(requested_name, normalized_name, description)

        start_time = time.perf_counter()
        
        async def run_task(key: str, p: str):
            h = hashlib.sha256(p.encode("utf-8")).hexdigest()
            res = await self.llm_provider.chat_json(messages=[{"role": "user", "content": p}])
            lat = int((time.perf_counter() - start_time) * 1000)
            await self.ops_service.log_ai_call(
                user_id=user_id, provider="openai", model=res["model"],
                operation=f"skill_request.generate.{key}", prompt_hash=h,
                cache_hit=False, latency_ms=lat,
                input_tokens=res["usage"]["input_tokens"],
                output_tokens=res["usage"]["output_tokens"],
                status="success", source_entity_type="skill_request",
                source_entity_id=f"{normalized_name}:{key}",
            )
            return res["data"]

        # Run parallel tasks with a safety timeout for the gathering
        try:
            tasks = [run_task(k, v) for k, v in prompts.items()]
            completed_data = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=BLUEPRINT_GENERATION_TIMEOUT_SECONDS,
            )
            
            merged_data = {}
            metadata_keys = [
                "description",
                "industry_usage",
                "hidden_skills_supported",
                "subskills",
                "interview_focus",
                "written_prompt",
            ]
            for i, key in enumerate(prompts.keys()):
                chunk = completed_data[i]
                if isinstance(chunk, Exception):
                    # Fallback for failed task
                    fallback = self._heuristic_blueprint(
                        requested_name,
                        normalized_name,
                        description,
                    )
                    if key == "metadata":
                        merged_data.update(
                            {field: fallback[field] for field in metadata_keys}
                        )
                    elif key == "mcq":
                        merged_data["mcq_questions"] = fallback["mcq_questions"]
                    else:
                        merged_data["situational_questions"] = fallback["situational_questions"]
                else:
                    merged_data.update(chunk)

            return self._sanitize_blueprint(
                requested_name,
                normalized_name,
                merged_data,
                description,
            )

        except Exception:
            return self._heuristic_blueprint(requested_name, normalized_name, description)

    def _heuristic_blueprint(
        self,
        requested_name: str,
        normalized_name: str,
        description: str | None,
    ) -> dict[str, Any]:
        readable_name = requested_name.strip()
        focus_prefix = readable_name.split()[0]
        return {
            "description": description
            or (
                f"{readable_name} applied in production workflows, stakeholder delivery, "
                "and measurable execution."
            ),
            "industry_usage": (
                f"{readable_name} is used to diagnose problems, structure decisions, "
                "and deliver repeatable outcomes in live teams."
            ),
            "hidden_skills_supported": [
                f"{focus_prefix} systems thinking",
                f"{focus_prefix} troubleshooting",
            ],
            "subskills": [
                f"{readable_name} foundations",
                f"{readable_name} execution",
                f"{readable_name} review",
            ],
            "interview_focus": [
                f"Explain how you apply {readable_name} under delivery pressure.",
                f"Describe tradeoffs when choosing a {readable_name} approach.",
                f"Show how you would validate {readable_name} outcomes.",
            ],
            "written_prompt": (
                "Write a structured case-study response showing how you would apply "
                f"{readable_name} "
                "to diagnose a failing project, prioritize action, and explain the tradeoffs."
            ),
            "mcq_questions": [
                # Reuse a wrapped prompt catalog so heuristic banks stay readable and lint-clean.
                self._heuristic_question(
                    readable_name,
                    prompt,
                    difficulty,
                    concepts,
                    correct_index,
                )
                for prompt, difficulty, concepts, correct_index in [
                    (
                        (
                            f"What best describes strong {readable_name} practice "
                            "in a production setting?"
                        ),
                        "intermediate",
                        ["production readiness", "tradeoffs"],
                        1,
                    ),
                    (
                        (
                            "Which signal most strongly indicates that "
                            f"{readable_name} work is incomplete?"
                        ),
                        "foundational",
                        ["validation", "delivery risk"],
                        2,
                    ),
                    (
                        f"What is the best first step when using {readable_name} on a new problem?",
                        "foundational",
                        ["problem framing", "requirements"],
                        0,
                    ),
                    (
                        f"Which behaviour shows mature judgment in {readable_name} work?",
                        "advanced",
                        ["prioritization", "communication"],
                        3,
                    ),
                    (
                        (
                            f"How should {readable_name} decisions usually be "
                            "validated before rollout?"
                        ),
                        "advanced",
                        ["measurement", "iteration"],
                        2,
                    ),
                    (
                        (
                            f"What makes a {readable_name} implementation "
                            "resilient after the first release?"
                        ),
                        "advanced",
                        ["feedback loops", "operational safety"],
                        0,
                    ),
                    (
                        f"Which evidence most improves confidence in a {readable_name} proposal?",
                        "intermediate",
                        ["evidence", "decision quality"],
                        2,
                    ),
                    (
                        (
                            "What is the clearest warning sign that "
                            f"{readable_name} scope is too broad?"
                        ),
                        "intermediate",
                        ["scope control", "delivery risk"],
                        3,
                    ),
                    (
                        (
                            f"When should a {readable_name} plan be reconsidered "
                            "instead of pushed through?"
                        ),
                        "advanced",
                        ["risk management", "tradeoffs"],
                        1,
                    ),
                    (
                        f"Which action best protects long-term quality in {readable_name} work?",
                        "intermediate",
                        ["quality", "repeatability"],
                        0,
                    ),
                    (
                        (
                            "What does strong ownership look like when leading "
                            f"{readable_name} execution?"
                        ),
                        "advanced",
                        ["ownership", "communication"],
                        3,
                    ),
                    (
                        f"Which output proves that {readable_name} decisions are measurable?",
                        "foundational",
                        ["metrics", "validation"],
                        2,
                    ),
                ]
            ],
            "situational_questions": [
                self._heuristic_situational_question(
                    readable_name,
                    scenario,
                    difficulty,
                    concepts,
                    correct_index,
                )
                for scenario, difficulty, concepts, correct_index in [
                    (
                        (
                            f"A team wants to adopt {readable_name} quickly, but "
                            "their production signals are noisy and deadlines are tight."
                        ),
                        "intermediate",
                        ["prioritization", "risk management"],
                        0,
                    ),
                    (
                        (
                            f"You inherit a broken {readable_name} workflow with "
                            "missing ownership, poor observability, and unclear "
                            "acceptance criteria."
                        ),
                        "advanced",
                        ["diagnostics", "sequencing"],
                        2,
                    ),
                    (
                        (
                            "A stakeholder challenges the value of "
                            f"{readable_name} after a weak first iteration and "
                            "wants immediate proof."
                        ),
                        "advanced",
                        ["communication", "validation"],
                        3,
                    ),
                    (
                        (
                            f"A launch depends on {readable_name}, but the team "
                            "discovered a late reliability risk two hours before "
                            "deployment."
                        ),
                        "advanced",
                        ["risk management", "stakeholder alignment"],
                        0,
                    ),
                    (
                        (
                            "Two engineers disagree on the right "
                            f"{readable_name} approach and both have partial "
                            "evidence supporting their position."
                        ),
                        "intermediate",
                        ["decision quality", "evidence"],
                        2,
                    ),
                    (
                        (
                            f"You must improve {readable_name} outcomes for a "
                            "weak team without extending the deadline or changing "
                            "headcount."
                        ),
                        "advanced",
                        ["coaching", "execution strategy"],
                        0,
                    ),
                ]
            ],
        }

    def _heuristic_question(
        self,
        skill_name: str,
        prompt: str,
        difficulty: str,
        expected_concepts: list[str],
        correct_index: int,
    ) -> dict[str, Any]:
        focus = expected_concepts[0] if expected_concepts else skill_name
        secondary = (
            expected_concepts[1] if len(expected_concepts) > 1 else "measurable validation"
        )
        tertiary = (
            expected_concepts[2] if len(expected_concepts) > 2 else "stakeholder alignment"
        )
        options = [
            (
                f"Use {focus} to frame the first safe decision before executing {skill_name} work."
            ),
            f"Prioritize delivery speed and defer {secondary} checks until after release.",
            f"Validate progress with explicit {secondary} signals and refine the next step.",
            f"Align stakeholders around the {tertiary} tradeoff before scaling the solution.",
        ]
        return {
            "question_text": prompt,
            "difficulty": difficulty,
            "expected_concepts": expected_concepts,
            "options": [
                {
                    "option_key": chr(ord("A") + index),
                    "option_text": option_text,
                    "is_correct": index == correct_index,
                }
                for index, option_text in enumerate(options)
            ],
        }

    def _heuristic_situational_question(
        self,
        skill_name: str,
        scenario: str,
        difficulty: str,
        expected_concepts: list[str],
        correct_index: int,
    ) -> dict[str, Any]:
        focus = expected_concepts[0] if expected_concepts else skill_name
        secondary = expected_concepts[1] if len(expected_concepts) > 1 else "risk controls"
        scenario_tag = self._scenario_hint(scenario, skill_name)
        options = [
            (
                f"In the {scenario_tag} scenario, stabilize the highest-risk area "
                f"and inspect {focus} first."
            ),
            (
                f"In the {scenario_tag} scenario, expand scope immediately and "
                f"postpone {secondary} checks."
            ),
            (
                f"In the {scenario_tag} scenario, gather evidence on {secondary} "
                "before the next controlled move."
            ),
            (
                f"In the {scenario_tag} scenario, rely on status messaging alone "
                "and avoid measurable intervention."
            ),
        ]
        return {
            "question_text": f"What is the strongest next move in this {skill_name} scenario?",
            "scenario": scenario,
            "difficulty": difficulty,
            "expected_concepts": expected_concepts,
            "sample_answer": (
                "A strong response identifies the bottleneck, limits blast radius, "
                "and explains how success will be measured."
            ),
            "options": [
                {
                    "option_key": chr(ord("A") + index),
                    "option_text": option_text,
                    "is_correct": index == correct_index,
                }
                for index, option_text in enumerate(options)
            ],
        }

    def _scenario_hint(self, scenario: str, fallback: str) -> str:
        compact = re.sub(r"\s+", " ", str(scenario or "").strip())
        if not compact:
            return fallback
        tokens = compact.split(" ")
        return " ".join(tokens[: min(len(tokens), 6)]).rstrip(".,;:") or fallback

    def _sanitize_blueprint(
        self,
        requested_name: str,
        normalized_name: str,
        data: dict[str, Any],
        description: str | None,
    ) -> dict[str, Any]:
        fallback = self._heuristic_blueprint(requested_name, normalized_name, description)
        sanitized_mcqs = self._sanitize_choice_questions(
            questions=data.get("mcq_questions"),
            fallback_questions=fallback["mcq_questions"],
            limit=MCQ_BANK_SIZE,
        )
        sanitized_situational = self._sanitize_choice_questions(
            questions=data.get("situational_questions"),
            fallback_questions=fallback["situational_questions"],
            limit=SITUATIONAL_BANK_SIZE,
            include_scenario=True,
        )

        return {
            "description": str(data.get("description") or fallback["description"]).strip(),
            "industry_usage": str(data.get("industry_usage") or fallback["industry_usage"]).strip(),
            "hidden_skills_supported": self._normalize_string_list(
                data.get("hidden_skills_supported")
            )
            or fallback["hidden_skills_supported"],
            "subskills": self._normalize_string_list(data.get("subskills"))
            or fallback["subskills"],
            "interview_focus": self._normalize_string_list(data.get("interview_focus"))
            or fallback["interview_focus"],
            "written_prompt": str(data.get("written_prompt") or fallback["written_prompt"]).strip(),
            "mcq_questions": sanitized_mcqs,
            "situational_questions": sanitized_situational,
        }

    def _catalog_payload(self, skill: dict[str, Any]) -> dict[str, Any]:
        metadata = skill.get("metadata") or {}
        return {
            "description": skill.get("description"),
            "industry_usage": skill.get("industry_usage"),
            "hidden_skills_supported": skill.get("hidden_skills_supported") or [],
            "subskills": metadata.get("subskills", []),
            "interview_focus": metadata.get("interview_focus", []),
            "written_prompt": metadata.get("written_prompt"),
            "mcq_questions": [],
            "situational_questions": [],
        }

    def _build_request_metadata(
        self,
        *,
        cache_source: str,
        validation_ready_at: str,
        validation_message: str | None = None,
    ) -> dict[str, Any]:
        return {
            "cache_source": cache_source,
            "validation_status": "scheduled",
            "validation_ready_at": validation_ready_at,
            "validation_message": validation_message
            or "Your skill validation will unlock once AI-generated questions are ready.",
        }

    async def _build_generation_context(
        self,
        *,
        requested_name: str,
        description: str | None,
        user_id: str,
    ) -> dict[str, Any]:
        query = " ".join(part for part in [requested_name, description] if part).strip()
        context_lines: list[str] = []
        requested_tokens = self._tokenize_name(query or requested_name)

        try:
            documents = await self.rag_service.semantic_search(
                query=query or requested_name,
                top_k=4,
                user_id=user_id,
            )
        except Exception:
            documents = []

        for document in documents[:4]:
            if not isinstance(document, dict):
                continue
            title = str(
                document.get("title")
                or document.get("skill_name")
                or document.get("source_ref")
                or "Context"
            ).strip()
            raw_content = str(document.get("content") or document.get("text") or "").strip()
            snippet = re.sub(r"\s+", " ", raw_content)[:320]
            if snippet:
                context_lines.append(f"- {title}: {snippet}")

        try:
            active_skills = await self.repository.list_active_skills(limit=150)
        except Exception:
            active_skills = []

        for skill in active_skills:
            skill_name = str(skill.get("skill_name") or skill.get("name") or "").strip()
            if not skill_name:
                continue
            skill_tokens = self._tokenize_name(skill_name)
            if len(requested_tokens & skill_tokens) < 2:
                continue
            description_snippet = re.sub(
                r"\s+",
                " ",
                str(skill.get("description") or skill.get("industry_usage") or "").strip(),
            )[:220]
            line = f"- Related skill: {skill_name}"
            if description_snippet:
                line = f"{line} :: {description_snippet}"
            if line not in context_lines:
                context_lines.append(line)
            if len(context_lines) >= 6:
                break

        return {
            "has_rich_context": len(context_lines) >= 2,
            "context_summary": "\n".join(context_lines)
            or (
                "- No strong prior CELTM context was found. Generate a fresh, "
                "production-grounded blueprint."
            ),
        }

    def _sanitize_choice_questions(
        self,
        *,
        questions: Any,
        fallback_questions: list[dict[str, Any]],
        limit: int,
        include_scenario: bool = False,
    ) -> list[dict[str, Any]]:
        if not isinstance(questions, list) or len(questions) < limit:
            questions = fallback_questions

        sanitized_questions: list[dict[str, Any]] = []
        for index, question in enumerate(questions[:limit], start=1):
            fallback_question = fallback_questions[index - 1]
            if not isinstance(question, dict):
                sanitized_questions.append(fallback_question)
                continue
            options = question.get("options")
            if not isinstance(options, list) or len(options) < 4:
                options = fallback_question["options"]
            sanitized_options = []
            has_correct = False
            for option_index, option in enumerate(options[:4]):
                if not isinstance(option, dict):
                    option = fallback_question["options"][option_index]
                is_correct = bool(option.get("is_correct"))
                has_correct = has_correct or is_correct
                sanitized_options.append(
                    {
                        "option_key": option.get("option_key") or chr(ord("A") + option_index),
                        "option_text": option.get("option_text")
                        or fallback_question["options"][option_index]["option_text"],
                        "is_correct": is_correct,
                    }
                )
            if not has_correct:
                sanitized_options[0]["is_correct"] = True

            shaped_question = {
                "question_text": question.get("question_text")
                or fallback_question["question_text"],
                "difficulty": question.get("difficulty") or fallback_question["difficulty"],
                "expected_concepts": self._normalize_string_list(question.get("expected_concepts"))
                or fallback_question["expected_concepts"],
                "sample_answer": question.get("sample_answer")
                or fallback_question.get("sample_answer"),
                "explanation": question.get("explanation") or fallback_question.get("explanation"),
                "options": sanitized_options,
            }
            if include_scenario:
                shaped_question["scenario"] = question.get("scenario") or fallback_question.get(
                    "scenario"
                )
            sanitized_questions.append(shaped_question)
        return sanitized_questions

    def _normalize_string_list(self, raw_value: Any) -> list[str]:
        if raw_value is None:
            return []

        if isinstance(raw_value, str):
            normalized_text = raw_value.strip()
            if not normalized_text:
                return []
            if normalized_text.startswith("[") and normalized_text.endswith("]"):
                normalized_text = normalized_text[1:-1]
            candidates = re.split(r"[\n|;,]+", normalized_text)
        elif isinstance(raw_value, (list, tuple, set)):
            candidates = []
            for item in raw_value:
                if isinstance(item, (list, tuple, set)):
                    candidates.extend(self._normalize_string_list(item))
                else:
                    item_text = str(item).strip()
                    if item_text:
                        candidates.append(item_text)
        else:
            value = str(raw_value).strip()
            candidates = [value] if value else []

        normalized: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            cleaned = str(candidate).strip().strip("\"'").strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                normalized.append(cleaned)
        return normalized

    def _merge_context_description(self, *parts: Any) -> str | None:
        merged = [str(part).strip() for part in parts if str(part or "").strip()]
        return "\n".join(merged) if merged else None

    def _tokenize_name(self, value: str) -> set[str]:
        return {token for token in re.split(r"[^a-z0-9]+", value.lower()) if len(token) >= 3}

    async def _ensure_validation_schedule(
        self,
        *,
        request: dict[str, Any],
        requested_name: str,
        validation_ready_at: str,
    ) -> dict:
        metadata = dict(request.get("metadata") or {})
        if not metadata.get("validation_ready_at"):
            metadata["validation_ready_at"] = validation_ready_at
        metadata.setdefault("validation_status", "scheduled")
        metadata.setdefault(
            "validation_message",
            "Your skill validation will unlock once AI-generated questions are ready.",
        )

        updated_request = request
        if metadata != (request.get("metadata") or {}):
            updated_request = await self.repository.update_skill_request(
                request["id"],
                {
                    "metadata": metadata,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
            )

        if self.schedule_service is None:
            return updated_request

        await self.schedule_service.ensure_event(
            updated_request["user_id"],
            {
                "title": f"Validate {requested_name}",
                "starts_at": metadata["validation_ready_at"],
                "event_type": "skill_validation",
                "metadata": {
                    "skill_request_id": updated_request["id"],
                    "normalized_name": updated_request["normalized_name"],
                    "requested_name": requested_name,
                    "validation_status": str(metadata["validation_status"]),
                },
            },
        )
        return updated_request

    async def _update_validation_status(self, request: dict[str, Any]) -> None:
        metadata = dict(request.get("metadata") or {})
        if request["status"] == "pending_validation":
            metadata["validation_status"] = "scheduled"
        else:
            metadata["validation_status"] = request["status"]
            metadata["validation_completed_at"] = datetime.now(timezone.utc).isoformat()

        if metadata != (request.get("metadata") or {}):
            await self.repository.update_skill_request(
                request["id"],
                {
                    "metadata": metadata,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
            )

        if self.schedule_service is None:
            return

        await self.schedule_service.ensure_event(
            request["user_id"],
            {
                "title": f"Validate {request['requested_name']}",
                "starts_at": metadata.get("validation_ready_at") or datetime.now(timezone.utc).isoformat(),
                "event_type": "skill_validation",
                "metadata": {
                    "skill_request_id": request["id"],
                    "normalized_name": request["normalized_name"],
                    "requested_name": request["requested_name"],
                    "validation_status": str(metadata["validation_status"]),
                },
            },
        )

    async def _emit_dashboard_refresh(
        self,
        *,
        user_id: str,
        request_id: str,
        requested_name: str,
    ) -> None:
        if self.event_service is None:
            return
        await self.event_service.emit(
            event_type=DomainEventType.DASHBOARD_REFRESH_REQUESTED,
            aggregate_type="skill_request",
            aggregate_id=request_id,
            payload={
                "user_id": user_id,
                "request_id": request_id,
                "requested_name": requested_name,
            },
        )
