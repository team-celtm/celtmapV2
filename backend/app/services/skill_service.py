from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.models.enums import DomainEventType, HiddenSkillStatus
from app.repositories.skill_repository import SkillRepository
from app.repositories.assessment_repository import AssessmentRepository
from app.services.domain_event_service import DomainEventService
from app.utils.text import normalize_name


class SkillService:
    def __init__(
        self, 
        repository: SkillRepository, 
        event_service: DomainEventService,
        assessment_repository: AssessmentRepository | None = None
    ) -> None:
        self.repository = repository
        self.event_service = event_service
        self.assessment_repository = assessment_repository

    async def list_user_skills(self, user_id: str) -> list[dict]:
        return await self.repository.list_user_skills(user_id)

    async def list_hidden_candidates(self, user_id: str) -> list[dict]:
        return await self.repository.list_hidden_candidates(user_id)

    async def add_hidden_candidate(
        self,
        *,
        user_id: str,
        skill_name: str,
        confidence_score: float,
        source: str,
        evidence: str,
        skill_id: str | None = None,
    ) -> dict:
        return await self.repository.upsert_hidden_candidate(
            {
                "user_id": user_id,
                "skill_id": skill_id,
                "skill_name": skill_name,
                "confidence_score": round(float(confidence_score), 2),
                "source": source,
                "evidence": evidence,
                "status": HiddenSkillStatus.PENDING.value,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    async def approve_hidden_candidate(self, user_id: str, candidate_id: str) -> dict | None:
        candidate = await self.repository.get_hidden_candidate(candidate_id)
        if candidate is None or candidate["user_id"] != user_id:
            return None
        updated = await self.repository.update_hidden_candidate(
            candidate_id,
            {
                "status": HiddenSkillStatus.APPROVED.value,
                "approved_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        proficiency_score = round(candidate["confidence_score"] * 100, 2)
        skill_id = await self._resolve_user_skill_id(
            skill_id=candidate.get("skill_id"),
            skill_name=candidate.get("skill_name"),
        )
        await self.repository.upsert_user_skill(
            {
                "user_id": user_id,
                "skill_id": skill_id,
                "proficiency_score": proficiency_score,
                "source": "inferred",
                "verified_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        await self.event_service.emit(
            event_type=DomainEventType.HIDDEN_SKILL_APPROVED,
            aggregate_type="hidden_skill_candidate",
            aggregate_id=candidate_id,
            payload={"user_id": user_id, "skill_name": candidate["skill_name"]},
        )
        return updated

    async def reject_hidden_candidate(self, user_id: str, candidate_id: str) -> dict | None:
        candidate = await self.repository.get_hidden_candidate(candidate_id)
        if candidate is None or candidate["user_id"] != user_id:
            return None
        return await self.repository.update_hidden_candidate(
            candidate_id,
            {
                "status": HiddenSkillStatus.REJECTED.value,
                "rejected_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    async def get_role_fit(self, user_id: str) -> dict:
        user_skills = await self.repository.list_user_skills(user_id)
        roles = await self.repository.list_roles()
        
        # Batch fetch ALL role requirements to avoid N+1 queries
        all_requirements = await self.repository.list_role_requirements()
        
        # Group requirements by role_name (primary key for role matching in this system)
        role_req_map: dict[str, list[dict]] = {}
        for req in all_requirements:
            rname = req.get("role_name")
            if rname:
                if rname not in role_req_map:
                    role_req_map[rname] = []
                role_req_map[rname].append(req)

        best_role: dict[str, Any] = {
            "role_name": "Unassigned",
            "fit_score": 0.0,
            "matched_skills": [],
            "missing_skills": [],
        }

        user_skill_map = {normalize_name(s["skill_name"]): s for s in user_skills if s.get("skill_name")}

        for role in roles:
            role_name = role["role_name"]
            requirements = role_req_map.get(role_name, [])
            
            if not requirements:
                continue
            
            requirement_weight_sum = sum(item["weight"] for item in requirements)
            matched = []
            missing = []
            running_total = 0.0
            
            for requirement in requirements:
                skill_name = requirement["skill_name"]
                normalized_req_name = normalize_name(skill_name)
                weight = requirement["weight"]
                
                matched_skill = user_skill_map.get(normalized_req_name)
                
                if matched_skill:
                    # Use proficiency_score from new schema
                    running_total += float(matched_skill.get("proficiency_score") or 0.0) * weight
                    matched.append(skill_name)
                else:
                    missing.append(skill_name)
                    
            fit_score = (
                (running_total / (100 * requirement_weight_sum) * 100)
                if requirement_weight_sum
                else 0.0
            )
            
            if fit_score > float(best_role["fit_score"]):
                best_role = {
                    "role_name": role_name,
                    "fit_score": round(fit_score, 2),
                    "matched_skills": matched,
                    "missing_skills": missing,
                }
        return best_role

    async def get_skill_gaps(self, user_id: str, role_name: str | None = None) -> list[dict]:
        role_record = None
        if role_name:
            role_record = await self.repository.get_role_by_name(role_name)
        
        if not role_record:
            role_fit = await self.get_role_fit(user_id)
            role_record = await self.repository.get_role_by_name(role_fit["role_name"])
        
        if not role_record:
            return []

        requirements = await self.repository.list_role_requirements(
            role_id=role_record["id"], role_name=role_record["role_name"]
        )
        user_skills = await self.repository.list_user_skills(user_id)
        gaps: list[dict[str, float | str]] = []
        for requirement in requirements:
            skill = next(
                (item for item in user_skills if item["skill_name"] == requirement["skill_name"]),
                None,
            )
            user_score = float(skill.get("proficiency_score", 0.0)) if skill else 0.0
            gap_severity = round(requirement["weight"] * (1 - user_score / 100), 4)
            gaps.append(
                {
                    "skill_name": requirement["skill_name"],
                    "target_weight": requirement["weight"],
                    "user_score": user_score,
                    "gap_severity": gap_severity,
                }
            )
        return sorted(gaps, key=lambda item: item["gap_severity"], reverse=True)

    async def record_skill_measurement(
        self,
        *,
        user_id: str,
        skill_id: str,
        skill_name: str,
        assessment_score: float | None = None,
        written_score: float | None = None,
        interview_score: float | None = None,
        artifact_score: float | None = None,
        skill_request_id: str | None = None,
        source: str | None = None,
        proficiency_score: float | None = None,
    ) -> dict:
        resolved_skill_id = await self._resolve_user_skill_id(
            skill_id=skill_id,
            skill_name=skill_name,
        )
        existing_skills = await self.repository.list_user_skills(user_id)
        existing = (
            next((item for item in existing_skills if item["skill_id"] == resolved_skill_id), None)
            or {}
        )
        # In new schema we only care about the final proficiency_score.
        # If passed, we use it, otherwise we compute it or use existing.
        resolved_proficiency = proficiency_score
        if resolved_proficiency is None:
            resolved_proficiency = self.compute_weighted_skill_score(
                assessment_score=assessment_score if assessment_score is not None else existing.get("assessment_score"),
                written_score=written_score if written_score is not None else existing.get("written_score"),
                interview_score=interview_score if interview_score is not None else existing.get("interview_score"),
                artifact_score=artifact_score if artifact_score is not None else existing.get("artifact_score"),
            )
        
        result = await self.repository.upsert_user_skill(
            {
                "user_id": user_id,
                "skill_id": resolved_skill_id,
                "proficiency_score": round(float(resolved_proficiency), 2),
                "source": source or existing.get("source") or "assessment",
                "verified_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        return result

    async def _resolve_user_skill_id(
        self,
        *,
        skill_id: str | None,
        skill_name: str | None = None,
    ) -> str | None:
        normalized_skill_id = str(skill_id or "").strip()
        if not normalized_skill_id:
            return None

        catalog_entry = await self.repository.get_skill_by_source_id(normalized_skill_id)
        if not catalog_entry:
            try:
                # If it's a UUID, it might be an internal ID or a legacy key
                # We still want to see if we can map it to a slug
                uuid.UUID(normalized_skill_id)
            except (ValueError, TypeError):
                pass
        if catalog_entry is None and skill_name:
            catalog_entry = await self.repository.get_skill_by_name(skill_name)
        if catalog_entry is None:
            catalog_entry = await self.repository.get_skill_by_name(normalized_skill_id)

        if catalog_entry is None:
            query_text = (skill_name or normalized_skill_id).replace("-", " ").strip()
            if query_text:
                result = (
                    self.repository.client.table("questions")
                    .select("skill_id")
                    .or_(
                        f"category.ilike.%{query_text}%,subject_id.ilike.%{query_text}%"
                    )
                    .limit(1)
                    .execute()
                )
                rows = result.data or []
                if rows and rows[0].get("skill_id"):
                    return str(rows[0]["skill_id"])

        return (
            (catalog_entry or {}).get("id")
            or (catalog_entry or {}).get("skill_id")
            or normalized_skill_id
        )

    async def recalculate_from_assessments(self, user_id: str) -> list[dict]:
        """
        Scans all user's assessment history and populates the user_skills table.
        This uses a deep-trace approach because session-level skill_id is often missing.
        """
        if not self.assessment_repository:
            print("[SkillService] No assessment repository available for recovery")
            return []

        print(f"[SkillService] Deep-tracing scores from history for user {user_id}")

        # 1. Fetch all assessment sessions for this user
        try:
            # We use the client directly to get exactly what we need
            client = self.assessment_repository.client
            sessions_res = client.table("assessments").select("*").eq("user_id", user_id).execute()
            sessions = sessions_res.data or []
        except Exception as e:
            print(f"[SkillService] Failed to fetch assessment sessions: {e}")
            sessions = []

        # 2. Fetch all descriptive/written answers (from descriptive_answers table)
        try:
            written_res = client.table("descriptive_answers").select("assessment_id, score, question_id").execute()
            written_map: dict[str, list[dict]] = {}
            for w in written_res.data or []:
                aid = w.get("assessment_id")
                if aid not in written_map:
                    written_map[aid] = []
                written_map[aid].append(w)
        except Exception as e:
            print(f"[SkillService] Failed to fetch descriptive answers: {e}")
            written_map = {}

        print(f"[SkillService] Found {len(sessions)} assessment sessions for tracing")

        # skill_id -> { "name": str, "mcq": [scores], "written": [scores] }
        skill_scores: dict[str, dict[str, Any]] = {}

        for sess in sessions:
            aid = sess.get("id")
            score = sess.get("overall_score")
            
            # Identify the skill_id for this session
            sid = sess.get("skill_id")
            sname = sess.get("category")

            # Deep Trace: If skill metadata is missing, look at the questions in this session
            if not sid:
                try:
                    # Look at user_answers for MCQs first
                    answers = client.table("user_answers").select("question_id").eq("assessment_id", aid).limit(1).execute()
                    qid = answers.data[0]["question_id"] if answers.data else None
                    
                    # If no MCQ answers, check descriptive_answers
                    if not qid and aid in written_map:
                        qid = written_map[aid][0].get("question_id")

                    if qid:
                        q_data = client.table("questions").select("skill_id, skill_name, category").eq("id", qid).execute()
                        if q_data.data:
                            sid = q_data.data[0].get("skill_id")
                            sname = q_data.data[0].get("skill_name") or q_data.data[0].get("category")
                except Exception as e:
                    print(f"[SkillService] Trace failed for assessment {aid}: {e}")

            if not sid:
                continue

            if sid not in skill_scores:
                skill_scores[sid] = {"name": sname or "General", "mcq": [], "written": []}
            
            # Map the session score
            if score is not None:
                skill_scores[sid]["mcq"].append(float(score))
            
            # Map written sub-scores if they exist
            if aid in written_map:
                for w in written_map[aid]:
                    w_score = w.get("score")
                    if w_score is not None:
                        skill_scores[sid]["written"].append(float(w_score))

        results = []
        for sid, data in skill_scores.items():
            avg_mcq = sum(data["mcq"]) / len(data["mcq"]) if data["mcq"] else None
            avg_written = sum(data["written"]) / len(data["written"]) if data["written"] else None
            
            try:
                # Resolve skill_name from DB if we only have sid
                final_name = data["name"]
                if not final_name or final_name == sid:
                     q_lookup = client.table("questions").select("skill_name").eq("skill_id", sid).limit(1).execute()
                     if q_lookup.data:
                         final_name = q_lookup.data[0].get("skill_name")

                res = await self.record_skill_measurement(
                    user_id=user_id,
                    skill_id=sid,
                    skill_name=final_name or sid,
                    assessment_score=avg_mcq,
                    written_score=avg_written,
                    source="deep_trace_recovery"
                )
                results.append(res)
            except Exception as e:
                print(f"[SkillService] Failed to record skill {sid}: {e}")
        
        print(f"[SkillService] Successfully recovered {len(results)} skill records via deep-trace")
        return results

    async def get_domain_readiness(self, user_id: str) -> dict[str, float]:
        """
        Aggregates proficiency across domains (categories) to feed the dashboard pie chart.
        If user_skills is empty, it attempts to derive from raw assessments + question categories.
        """
        try:
            user_skills = await self.repository.list_user_skills(user_id)
        except Exception:
            user_skills = []
        
        if not user_skills and self.assessment_repository:
            # Fallback to deep-traced assessments if skills mapping is empty
            try:
                client = self.assessment_repository.client
                # Category column does NOT exist on assessments table, must trace it
                sessions_res = client.table("assessments").select("id, overall_score").eq("user_id", user_id).execute()
                domain_map: dict[str, list[float]] = {}
                
                for m in (sessions_res.data or []):
                    score = m.get("overall_score")
                    if score is None: continue
                    
                    cat = m.get("category")
                    if not cat:
                        # Trace category from questions
                        ans = client.table("user_answers").select("question_id").eq("assessment_id", m["id"]).limit(1).execute()
                        if ans.data:
                            q = client.table("questions").select("category, subject_name").eq("id", ans.data[0]["question_id"]).execute()
                            if q.data:
                                cat = q.data[0].get("category") or q.data[0].get("subject_name")
                    
                    cat = cat or "General"
                    if cat not in domain_map:
                        domain_map[cat] = []
                    domain_map[cat].append(float(score))
                
                if not domain_map:
                    return {}
                return {cat: round(sum(scores)/len(scores), 2) for cat, scores in domain_map.items()}
            except Exception as e:
                print(f"[SkillService] get_domain_readiness deep-trace failed: {e}")
                return {}

        # Group verified skills by category (resolving category from Skill table if needed)
        domain_map: dict[str, list[float]] = {}
        for s in user_skills:
            # Note: user_skills has no skill_name or category in this schema, must join
            score = s.get("proficiency_score")
            if score is None: continue

            # Try to get category from associated question/skill metadata
            cat = s.get("metadata", {}).get("category")
            if not cat:
                try:
                    q_lookup = self.assessment_repository.client.table("questions").select("category").eq("skill_id", s["skill_id"]).limit(1).execute()
                    if q_lookup.data:
                        cat = q_lookup.data[0].get("category")
                except Exception:
                    cat = "General"
            
            cat = cat or "General"
            if cat not in domain_map:
                domain_map[cat] = []
            domain_map[cat].append(float(score))
        
        if not domain_map:
            return {}
        return {cat: round(sum(scores)/len(scores), 2) for cat, scores in domain_map.items()}


    def compute_weighted_skill_score(
        self,
        *,
        assessment_score: float | None,
        written_score: float | None,
        interview_score: float | None,
        artifact_score: float | None,
    ) -> float:
        weighted_sources = []
        if assessment_score is not None:
            weighted_sources.append((assessment_score, 0.35))
        if written_score is not None:
            weighted_sources.append((written_score, 0.25))
        if interview_score is not None:
            weighted_sources.append((interview_score, 0.25))
        if artifact_score is not None:
            weighted_sources.append((artifact_score, 0.15))
        if not weighted_sources:
            return 0.0
        total_weight = sum(weight for _, weight in weighted_sources)
        score = sum(score * weight for score, weight in weighted_sources) / total_weight
        return round(score, 2)

    async def add_hidden_candidate(
        self,
        user_id: str,
        skill_name: str,
        confidence_score: float,
        source: str,
        evidence: str,
    ) -> dict:
        payload = {
            "user_id": user_id,
            "skill_name": skill_name,
            "confidence_score": confidence_score,
            "source": source,
            "evidence": evidence,
            "status": HiddenSkillStatus.PENDING,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        return await self.repository.upsert_hidden_candidate(payload)

    async def list_hidden_candidates(self, user_id: str) -> list[dict]:
        return await self.repository.list_hidden_candidates(user_id)
