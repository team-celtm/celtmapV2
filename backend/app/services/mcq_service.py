from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from random import sample
from typing import Any

from app.models.enums import DomainEventType
from app.repositories.assessment_repository import AssessmentRepository
from app.repositories.interview_repository import InterviewRepository
from app.repositories.learning_repository import LearningRepository
from app.repositories.profile_repository import ProfileRepository
from app.services.domain_event_service import DomainEventService
from app.services.projection_service import ProjectionService
from app.services.skill_request_service import SkillRequestService
from app.services.skill_service import SkillService
from app.utils.shuffle import shuffled
from app.utils.text import normalize_name


class MCQService:
    def __init__(
        self,
        repository: AssessmentRepository,
        event_service: DomainEventService,
        skill_service: SkillService | None = None,
        skill_request_service: SkillRequestService | None = None,
        interview_repository: InterviewRepository | None = None,
        learning_repository: LearningRepository | None = None,
        profile_repository: ProfileRepository | None = None,
        rag_service: Any | None = None,
        projection_service: ProjectionService | None = None,
        cache: Any | None = None,
    ) -> None:
        self.repository = repository
        self.event_service = event_service
        self.skill_service = skill_service
        self.skill_request_service = skill_request_service
        self.interview_repository = interview_repository
        self.learning_repository = learning_repository
        self.profile_repository = profile_repository
        self.rag_service = rag_service
        self.projection_service = projection_service
        self.cache = cache

    async def get_questions(
        self,
        *,
        category: str | None,
        difficulty: str | None,
        limit: int,
        skill_id: str | None = None,
        skill_request_id: str | None = None,
        question_type: str = "mcq",
    ) -> list[dict]:
        # Enforce strict 10-question limit for professional assessments
        # except when explicitly requested at a different scale (like placement)
        # Note: Placement calls this with limit=4 per domain, which is fine.
        effective_limit = min(limit, 10)

        # Fetch a larger pool from the repository to ensure good randomization via sampling
        fetch_limit = max(50, effective_limit * 2)

        questions = await self.repository.get_questions(
            category=category,
            difficulty=difficulty,
            limit=fetch_limit,
            skill_id=skill_id,
            question_type=question_type,
        )

        # ── Category fallback ────────────────────────────────────────────────
        # The DB's `category` column is often mis-seeded (values like 'questions'
        # or NULL) so a subject-specific query can return far fewer rows than
        # effective_limit. When that happens, retry without the category filter
        # so the user always gets a full bank of questions.
        if len(questions) < effective_limit and category:
            import logging
            logging.info(
                "get_questions: only %d/%d rows for category=%r; retrying without category filter",
                len(questions), effective_limit, category,
            )
            questions = await self.repository.get_questions(
                category=None,       # drop the category constraint
                difficulty=difficulty,
                limit=fetch_limit,
                skill_id=skill_id,
                question_type=question_type,
            )

        if not questions:
            return []

        # Randomly sample the desired number from the pool
        selected = sample(questions, k=min(effective_limit, len(questions)))
        
        response = []
        for q in selected:
            options = []
            
            # 1. Try modern join structure (nested list from question_options table)
            db_options = q.get("question_options", [])
            if db_options:
                for opt in db_options:
                    options.append({
                        "id": str(opt.get("id") or opt.get("option_key") or ""),
                        "option_text": opt.get("option_text", "")
                    })
            
            # 2. Fallback to legacy flattened row columns if no nested options found
            if not options:
                for key in ["option_a", "option_b", "option_c", "option_d"]:
                    if q.get(key):
                        label = key.split("_")[-1].upper() # A, B, C, D
                        options.append({"id": label, "option_text": q[key]})
            
            response.append({
                "id": str(q["id"]),
                "question_text": q["question_text"],
                "category": q.get("category") or q.get("subject_id") or category,
                # API schema requires non-null strings for these fields.
                # Older seeded rows can have NULL difficulty/category.
                "difficulty": str(q.get("difficulty") or "unassigned"),
                "skill_id": q.get("skill_id"),
                "skill_request_id": q.get("skill_request_id"),
                "question_type": str(q.get("question_type") or question_type).upper(),
                "scenario": q.get("scenario") or (q.get("metadata") or {}).get("scenario"),
                "options": shuffled(options)
            })

        return response

    async def create_assessment(
        self,
        *,
        user_id: str,
        category: str,
        assessment_type: str = "mcq",
        question_type: str = "MCQ",
        skill_id: str | None = None,
        skill_request_id: str | None = None,
    ) -> dict:
        # Check for 2-hour retake limit
        recent_assessments = await self.repository.list_user_assessments(user_id=user_id, limit=20)
        for ass in recent_assessments:
            if ass.get("category") == category and ass.get("status") == "completed":
                completed_at = self._parse_completed_at(ass.get("completed_at"))
                now = datetime.now(timezone.utc)
                if now - completed_at < timedelta(hours=2):
                    diff = timedelta(hours=2) - (now - completed_at)
                    minutes = int(diff.total_seconds() / 60)
                    from fastapi import HTTPException
                    raise HTTPException(
                        status_code=429, 
                        detail=f"Safety Lock: Please wait {minutes} minutes before retaking the {category} assessment to ensure focus and stability."
                    )

        created = await self.repository.create_assessment(
            {
                "user_id": user_id,
                "category": category,
                "assessment_type": assessment_type,
                "question_type": question_type,
                "skill_id": skill_id,
                "skill_request_id": skill_request_id,
                "score": None,
                "status": "in_progress",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        return {
            **created,
            "category": category,
            "assessment_type": assessment_type,
            "question_type": question_type,
            "skill_id": skill_id,
            "skill_request_id": skill_request_id,
            "score": None,
            "status": "in_progress",
            "completed_at": None,
        }

    async def submit_answers(
        self, *, assessment_id: str, user_id: str, answers: list[dict]
    ) -> list[dict]:
        assessment = await self.repository.get_assessment(assessment_id)
        if not assessment:
            return []

        assessment_type = assessment.get("assessment_type", "mcq")
        
        payloads = []
        for answer in answers:
            selected_option_id = answer.get("selected_option_id")
            if not selected_option_id:
                continue
            option = await self.repository.get_option(selected_option_id)
            
            # Find the correct option for this question
            question_options = await self.repository.get_question_options(answer["question_id"])
            correct_option = next((opt for opt in question_options if opt.get("is_correct")), None)
            correct_option_id = str(correct_option.get("id")) if correct_option else None
            
            payloads.append(
                {
                    "assessment_id": assessment_id,
                    "user_id": user_id,
                    "question_id": answer["question_id"],
                    "selected_option_id": selected_option_id,
                    "is_correct": bool(option.get("is_correct")) if option else False,
                    "correct_option_id": correct_option_id,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )

        await self.repository.insert_user_answers(payloads)
        return payloads

    async def complete_assessment(self, *, assessment_id: str, user_id: str) -> dict:
        assessment = await self.repository.get_assessment(assessment_id)
        if not assessment:
             return {"error": "Assessment not found"}

        assessment_type = assessment.get("assessment_type", "mcq")
        correct_count = 0
        total_count = 0
        detailed_feedback: dict | None = None

        answers = await self.repository.list_user_answers(assessment_id)
        total_count = len(answers)
        correct_count = len([answer for answer in answers if answer.get("is_correct")])

        score = round((correct_count / total_count) * 100, 2) if total_count else 0.0

        # Generate question-level and subject-level feedback using RAG
        if self.rag_service and answers:
            try:
                question_ids = [str(a.get("question_id")) for a in answers if a.get("question_id")]
                questions_data = await self.repository.get_questions_by_ids(question_ids)
                q_map = {str(q["id"]): q for q in questions_data}
                
                enriched_answers = []
                for a in answers:
                    q = q_map.get(str(a.get("question_id")))
                    if q:
                        options = q.get("question_options", [])
                        selected_opt = next((o for o in options if str(o.get("id")) == str(a.get("selected_option_id"))), {})
                        correct_opt = next((o for o in options if o.get("is_correct")), {})
                        
                        enriched_answers.append({
                            **a,
                            "question_text": q.get("question_text"),
                            "category": q.get("category"),
                            "selected_option_text": selected_opt.get("option_text"),
                            "correct_option_text": correct_opt.get("option_text"),
                        })
                
                detailed_feedback = await self.rag_service.generate_analysis(
                    user_id=user_id,
                    assessment_results=enriched_answers,
                    assessment=assessment
                )
            except Exception as e:
                import logging
                logging.error(f"Analysis feedback generation failed: {e}")

        await self.repository.update_assessment(
            assessment_id,
            {
                "overall_score": score,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        # Emit event
        await self.event_service.emit(
            event_type=DomainEventType.ASSESSMENT_COMPLETED,
            aggregate_type="assessment",
            aggregate_id=assessment_id,
            payload={
                "user_id": user_id,
                "score": score,
                "type": assessment_type,
                "category": assessment.get("category"),
                "skill_id": assessment.get("skill_id"),
            },
        )

        # Automated Skill Profile Update — only if a real skill_id or meaningful category exists.
        # Skips generic categories like "general" which are not valid UUID skill IDs.
        skill_id_for_measurement = assessment.get("skill_id") or normalize_name(assessment.get("category") or "")
        is_generic = not skill_id_for_measurement or skill_id_for_measurement.lower() in ("general", "")
        if self.skill_service and not is_generic:
            try:
                await self.skill_service.record_skill_measurement(
                    user_id=user_id,
                    skill_id=skill_id_for_measurement,
                    skill_name=assessment.get("category"),
                    assessment_score=score,
                    source="assessment"
                )
                await self.skill_service.recalculate_from_assessments(user_id)
            except Exception as exc:
                import logging
                logging.warning("Skill measurement update skipped for %s: %s", skill_id_for_measurement, exc)

        # Automated Skill Discovery
        if score >= 75 and self.skill_service:
            await self._discover_related_skills(user_id, assessment.get("category"))

        # Refresh dashboard projection for immediate visibility
        if self.projection_service:
            try:
                await self.projection_service.refresh_dashboard_projection(user_id)
            except Exception as e:
                import logging
                logging.error(f"Failed to refresh dashboard projection: {e}")

        return {
            "assessment_id": assessment_id,
            "score": score,
            "correct_answers": correct_count,
            "total_questions": total_count,
            "status": "completed",
            "detailed_feedback": detailed_feedback or None,
        }

    async def _discover_related_skills(self, user_id: str, category: str | None) -> None:
        """
        Suggests related skills based on successful assessment performance.
        """
        if not category or not self.skill_service:
            return

        # Simple adjacency logic: suggest other skills in the same general domain
        related_map = {
            "Python": ["FastAPI", "Pandas", "Django"],
            "Data Science": ["Machine Learning", "Statistical Analysis", "Data Visualization"],
            "Frontend": ["React", "TypeScript", "Tailwind CSS"],
            "Backend": ["Node.js", "PostgreSQL", "Redis"],
            "Cyber Security": ["Networking", "Cryptography", "Penetration Testing"],
            "Cloud Computing": ["AWS", "Docker", "Kubernetes"],
            "English": ["Communication", "Writing"],
            "Maths": ["Calculus", "Linear Algebra"],
        }

        discovered = related_map.get(category, [])
        
        # If no hardcoded map, try to find from DB categories
        if not discovered:
             # Just an example: we could query the skills table for matching category
             pass

        user_skills = await self.skill_service.list_user_skills(user_id)
        known_skill_names = {s["skill_name"].lower() for s in user_skills if s.get("skill_name")}

        for skill_name in discovered:
            if skill_name.lower() in known_skill_names:
                continue
            
            # Record as a hidden skill candidate
            await self.skill_service.add_hidden_candidate(
                user_id=user_id,
                skill_name=skill_name,
                confidence_score=0.8,
                source="assessment_inference",
                evidence=f"Demonstrated high proficiency (>=75%) in related field: {category}",
            )

    async def _generate_ai_feedback(
        self, user_id: str, assessment: dict, feedback_items: list[dict]
    ) -> list[dict]:
        if not self.rag_service or not feedback_items:
            return []

        user_context = ""
        try:
            search_results = await self.rag_service.semantic_search(
                query="user background experience profile",
                user_id=user_id,
                top_k=2,
            )
            user_context = "\n".join([doc["content"] for doc in search_results])
        except Exception:
            pass

        insight_map: dict[str, str] = {}
        try:
            llm_payload = await self.rag_service.llm_provider.chat_json(
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "You are a CELTM career coach. Return JSON only in the shape "
                            '{"items":[{"question_id":"...","personalized_insight":"..."}]}. '
                            "Write one encouraging 1-2 sentence insight per question. "
                            "Explain why the answer was strong or what to review next. "
                            f"User profile context: {user_context[:400] or 'No extra context'}\n"
                            f"Assessment context: {assessment.get('category') or 'General'}\n"
                            f"Questions: {feedback_items}"
                        ),
                    }
                ],
                temperature=0.1,
            )
            items = llm_payload.get("data", {}).get("items")
            if isinstance(items, list):
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    question_id = str(item.get("question_id") or "").strip()
                    insight = str(item.get("personalized_insight") or "").strip()
                    if question_id and insight:
                        insight_map[question_id] = insight
        except Exception:
            pass

        return [
            {
                **item,
                "personalized_insight": (
                    insight_map.get(item["question_id"])
                    or self._fallback_feedback_insight(
                        category=item.get("category", "General"),
                        is_correct=bool(item["is_correct"]),
                        selected_option=item["selected_option"],
                        correct_option=item["correct_option"],
                    )
                ),
            }
            for item in feedback_items
        ]

    def _fallback_feedback_insight(
        self,
        *,
        category: str,
        is_correct: bool,
        selected_option: str,
        correct_option: str,
    ) -> str:
        if is_correct:
            return (
                f"Strong call in {category}. Keep using that reasoning pattern on similar prompts."
            )
        return (
            f"Review {category} with focus on why '{correct_option}' fits better than "
            f"'{selected_option}'."
        )

    async def _score_text_answers(self, answers: list[dict]) -> int:
        return 0

    async def _infer_hidden_skills_from_attempt(
        self, assessment: dict, user_id: str, score: float, total_questions: int
    ) -> None:
        return None
    PLACEMENT_DOMAINS = [
        "Quantitative Aptitude",
        "Logical Reasoning",
        "Science & Brain",
        "Verbal & Code Logic",
        "Core CS & Digital",
    ]

    async def get_placement_questions(self, role_name: str | None = None, questions_per_domain: int = 4) -> list[dict]:
        import asyncio
        import random
        import logging
        from app.services.fallback_placement_questions import FALLBACK_QUESTIONS

        TOTAL_QUESTIONS = 20
        domains = self.PLACEMENT_DOMAINS.copy()
        
        # We want to ensure exactly questions_per_domain from each domain
        tasks = [
            self.get_questions(
                category=domain,
                difficulty=None,
                limit=questions_per_domain,
            )
            for domain in domains
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        final_set = []
        for i, domain in enumerate(domains):
            res = results[i]
            domain_questions = []
            if isinstance(res, list) and len(res) >= questions_per_domain:
                domain_questions = res[:questions_per_domain]
            else:
                # Fallback to local questions for this domain
                fallback_pool = [q for q in FALLBACK_QUESTIONS if q["category"] == domain]
                if len(fallback_pool) >= questions_per_domain:
                    domain_questions = random.sample(fallback_pool, questions_per_domain)
                else:
                    domain_questions = fallback_pool # Take all if less than 4
            
            # Ensure each fallback question has the required keys for the assessment UI
            for q in domain_questions:
                if "options" in q:
                    # Shuffle options for randomization
                    random.shuffle(q["options"])
            
            final_set.extend(domain_questions)

        # Final shuffle of the 20 questions so they are randomized for the user
        random.shuffle(final_set)
        return final_set[:TOTAL_QUESTIONS]

    async def complete_placement_assessment(
        self,
        *,
        user_id: str,
        answers: list[dict],
        role_name: str | None = None,
        profile_service: object | None = None,
    ) -> dict:
        if not answers:
            return {"status": "skipped", "domain_scores": {}}

        db_question_ids = [answer["question_id"] for answer in answers if answer.get("question_id")]
        questions = await self.repository.get_questions_by_ids(db_question_ids) if db_question_ids else []
        question_map = {question["id"]: question for question in questions}

        domain_correct: dict[str, int] = {}
        domain_total: dict[str, int] = {}
        overall_correct = 0
        overall_total = 0
        
        assessment_id = f"placement_{user_id[:8]}"
        
        # We'll collect payloads for bulk insertion
        answer_payloads = []
        
        for answer in answers:
            question_id = answer.get("question_id")
            selected_option_id = answer.get("selected_option_id")
            question = question_map.get(question_id)
            if not question:
                continue

            category = question.get("category", "General")
            domain_total[category] = domain_total.get(category, 0) + 1
            overall_total += 1

            is_correct = False
            if selected_option_id:
                # In the new schema, correct_option is a column in the joined question row
                correct_option = question.get("correct_option")
                is_correct = (selected_option_id == correct_option)
                            
                if is_correct:
                    domain_correct[category] = domain_correct.get(category, 0) + 1
                    overall_correct += 1

            # Prepare answer payload for persistence (optional metadata storage)
            answer_payloads.append({
                "assessment_id": assessment_id,
                "user_id": user_id,
                "question_id": question_id,
                "selected_option_id": selected_option_id,
                "is_correct": is_correct,
            })

        # Persist answers to user_answers table
        if answer_payloads:
            try:
                await self.repository.insert_user_answers(answer_payloads)
            except Exception as e:
                import logging
                logging.error(f"Failed to persist placement answers: {e}")

        domain_scores: dict[str, float] = {}
        for category, total in domain_total.items():
            correct = domain_correct.get(category, 0)
            domain_scores[category] = round((correct / total) * 100, 2) if total > 0 else 0.0

        overall_score = round((overall_correct / overall_total) * 100, 2) if overall_total > 0 else 50.0

        inference = self._generate_placement_inference(domain_scores, overall_score)

        if self.skill_service:
            for category, category_score in domain_scores.items():
                normalized_name = normalize_name(category)
                catalog_entry = None
                if getattr(self.skill_service, "repository", None):
                    repository = self.skill_service.repository
                    get_skill_by_name = getattr(repository, "get_skill_by_name", None)
                    if callable(get_skill_by_name):
                        catalog_entry = await get_skill_by_name(normalized_name)

                resolved_skill_id = (
                    (catalog_entry or {}).get("skill_id")
                    or (catalog_entry or {}).get("id")
                    or normalized_name
                )
                await self.skill_service.record_skill_measurement(
                    user_id=user_id,
                    skill_id=resolved_skill_id,
                    skill_name=category,
                    assessment_score=category_score,
                    source="placement",
                )

        # Update profile to reflect placement completion
        try:
            existing_profile = await self.profile_repository.get_profile(user_id)
            existing_metadata = {}
            if existing_profile and isinstance(existing_profile, dict):
                existing_metadata = existing_profile.get("metadata") or {}
            
            # Merge metadata
            updated_metadata = {
                **existing_metadata,
                "has_completed_placement": True,
                "placement_overall_score": overall_score,
                "placement_domain_scores": domain_scores,
                "placement_completed_at": datetime.now(timezone.utc).isoformat()
            }
            
            profile_update = {
                "id": user_id,
                "metadata": updated_metadata,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }

            # RELIABILITY FIX: Explicitly update focus_role if provided or found in metadata
            resolved_role = role_name or updated_metadata.get("focus_role") or updated_metadata.get("target_role")
            if resolved_role:
                profile_update["focus_role"] = resolved_role

            # SYNC: If we have a profile service, use it for cross-table sync
            if profile_service and hasattr(profile_service, "update_profile"):
                await profile_service.update_profile(user_id, profile_update)
            else:
                await self.profile_repository.upsert_profile(profile_update)
            
            import logging
            logging.info(f"Placement status and role ({resolved_role}) recorded for user {user_id}")
        except Exception as e:
            import logging
            logging.error(f"Critical: Failed to update profile: {e}")


        # Refresh dashboard projection for immediate visibility
        if self.projection_service:
            try:
                await self.projection_service.refresh_dashboard_projection(user_id)
            except Exception as e:
                import logging
                logging.error(f"Failed to refresh dashboard projection: {e}")

        return {
            "status": "completed",
            "assessment_id": assessment_id,
            "overall_score": overall_score,
            "domain_scores": domain_scores,
            "preliminary_readiness": overall_score,
            "inference": inference,
            "role_name": role_name,
        }

    def _generate_placement_inference(
        self, domain_scores: dict[str, float], overall_score: float
    ) -> dict:
        strong = [d for d, s in domain_scores.items() if s >= 70]
        weak = [d for d, s in domain_scores.items() if s < 40]
        focus = weak[:3] if weak else list(domain_scores.keys())[:3]

        return {
            "overall_readiness": overall_score,
            "strong_areas": strong,
            "areas_to_focus": focus,
            "summary": f"Your readiness is {overall_score:.0f}%. "
            + (f"Strong in {', '.join(strong)}." if strong else "")
            + (f" Focus on {', '.join(focus)}." if focus else ""),
            "recommendations": [f"Focus on {d}" for d in focus],
        }

    @staticmethod
    def _parse_completed_at(value: object) -> datetime:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

        if isinstance(value, str) and value:
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                pass

        return datetime.min.replace(tzinfo=timezone.utc)

    @staticmethod
    def _coerce_string_list(value: object) -> list[str]:
        if not isinstance(value, list):
            return []

        items: list[str] = []
        for item in value:
            text = str(item).strip()
            if text:
                items.append(text)
        return items

    async def get_assessment_log(self, user_id: str, limit: int = 10) -> list[dict]:
        log_entries: list[dict] = []

        # All assessments (MCQ, Situational, Descriptive) are now in the 'assessments' table
        assessments = await self.repository.list_user_assessments(user_id=user_id, limit=limit)
        
        for assessment in assessments:
            assessment_type = str(assessment.get("assessment_type") or "mcq").lower()
            status = str(assessment.get("status") or "completed")
            metadata = assessment.get("metadata") or {}
            
            detailed_feedback: list[dict] = []
            
            if assessment_type == "descriptive":
                # For descriptive, we show the strengths/risks from metadata
                strengths = self._coerce_string_list(metadata.get("insights"))
                risks = self._coerce_string_list(metadata.get("loopholes"))
                recommendations = self._coerce_string_list(metadata.get("recommendations"))
                
                log_entries.append({
                    "id": assessment["id"],
                    "type": "written",
                    "subject": assessment.get("category") or metadata.get("prompt") or "Written Assessment",
                    "score": assessment.get("overall_score"),
                    "status": status,
                    "completed_at": assessment.get("completed_at"),
                    "insight": metadata.get("feedback") or (strengths[0] if strengths else None),
                    "feedback": metadata.get("feedback"),
                    "strengths": strengths,
                    "risks": risks,
                    "recommendations": recommendations,
                    "plagiarism": metadata.get("plagiarism"),
                    "readiness_score": metadata.get("readiness_score"),
                    "role_name": metadata.get("role_name"),
                })
            else:
                # For MCQ/Situational, we try to reconstruct feedback from metadata
                results = metadata.get("results", {})
                detailed_feedback = results.get("detailed_feedback", [])
                
                log_entries.append({
                    "id": assessment["id"],
                    "type": assessment_type,
                    "subject": assessment.get("category") or "General",
                    "score": assessment.get("overall_score"),
                    "status": status,
                    "completed_at": assessment.get("completed_at"),
                    "insight": metadata.get("feedback") or (f"Completed {assessment_type} assessment." if status == "completed" else None),
                    "detailed_feedback": detailed_feedback if detailed_feedback else None,
                })

        log_entries.sort(
            key=lambda entry: self._parse_completed_at(entry.get("completed_at")),
            reverse=True,
        )
        return log_entries[:limit]

    async def get_placement_status(self, user_id: str, profile_service: object) -> bool:
        try:
            profile = await profile_service.get_profile(user_id, None)
        except TypeError:
            profile = await profile_service.get_profile(user_id)
        except Exception:
            return False

        metadata = profile.get("metadata") or {}
        return bool(metadata.get("has_completed_placement", False))

    async def get_subject_detail(self, user_id: str, subject_key: str, context: dict | None = None) -> dict | None:
        skill_id = subject_key
        title = subject_key.replace("-", " ").title()
        current_score: float | None = None
        severity = 0.0
        resource_count = 0
        description = f"Core assessment track for {title}."
        source = "Skill Bank"

        # Extract context if provided, otherwise fetch on demand
        ctx = context or {}
        user_skills = ctx.get("user_skills")
        profile = ctx.get("profile")
        role_fit = ctx.get("role_fit")
        gaps = ctx.get("gaps")
        path_modules = ctx.get("path_modules")

        if self.skill_service:
            if user_skills is None:
                user_skills = await self.skill_service.list_user_skills(user_id)
            
            matched_skill = next(
                (
                    skill
                    for skill in user_skills
                    if skill.get("skill_id") == subject_key
                    or normalize_name(str(skill.get("skill_name") or "")) == subject_key
                ),
                None,
            )
            if matched_skill:
                title = matched_skill.get("skill_name") or title
                skill_id = matched_skill.get("skill_id") or skill_id
                current_score = float(matched_skill.get("proficiency_score") or 0.0)

            if profile is None and self.profile_repository:
                profile = await self.profile_repository.get_profile(user_id)
            
            role_name = profile.get("focus_role") if profile else None
            if not role_name:
                if role_fit is None:
                    role_fit = await self.skill_service.get_role_fit(user_id)
                role_name = role_fit.get("role_name")

            if gaps is None:
                gaps = await self.skill_service.get_skill_gaps(user_id, role_name=role_name)
            
            matched_gap = next(
                (
                    gap
                    for gap in gaps
                    if normalize_name(str(gap.get("skill_name") or "")) == subject_key
                ),
                None,
            )
            if matched_gap:
                title = matched_gap.get("skill_name") or title
                severity = float(matched_gap.get("gap_severity") or 0.0)
                if current_score is None:
                    current_score = float(matched_gap.get("user_score") or 0.0)

            # Catalog entry check (skipped if skill_id already resolved/matched)
            if skill_id == subject_key and getattr(self.skill_service, "repository", None):
                repository = self.skill_service.repository
                get_skill_by_name = getattr(repository, "get_skill_by_name", None)
                if callable(get_skill_by_name):
                    catalog_entry = await get_skill_by_name(subject_key)
                    if catalog_entry:
                        title = catalog_entry.get("skill_name") or title
                        skill_id = catalog_entry.get("skill_id") or skill_id

        if self.learning_repository:
            if path_modules is None:
                if profile is None and self.profile_repository:
                    profile = await self.profile_repository.get_profile(user_id)
                role_name = profile.get("focus_role") if profile else None
                if role_name:
                    path = await self.learning_repository.get_latest_path(user_id, role_name)
                    if path:
                        path_modules = await self.learning_repository.list_path_modules(path["id"])
            
            if path_modules:
                matched_module = next(
                    (
                        module
                        for module in path_modules
                        if normalize_name(str(module.get("skill_name") or "")) == subject_key
                        or module.get("skill_id") == skill_id
                    ),
                    None,
                )
                if matched_module:
                    title = matched_module.get("skill_name") or title
                    skill_id = matched_module.get("skill_id") or skill_id
                    severity = float(matched_module.get("gap_severity") or severity)
                    resources = matched_module.get("resources")
                    resources = resources if isinstance(resources, list) else []
                    resource_count = len(resources)
                    if resources:
                        first_resource = resources[0]
                        if isinstance(first_resource, dict):
                            description = (
                                first_resource.get("content")
                                or first_resource.get("title")
                                or description
                            )
                    week = matched_module.get("week")
                    source = f"Learning Path (W{week})" if week else "Learning Path"

        question_bank = await self.repository.find_question_bank(
            requested_name=title,
            normalized_name=subject_key,
            skill_id=skill_id,
        )

        return {
            "key": subject_key,
            "title": title,
            "description": description,
            "source": source,
            "severity": round(severity, 4),
            "current_score": current_score,
            "skill_id": skill_id,
            "resource_count": resource_count,
            "is_available": question_bank is not None,
        }

    async def _has_subject_question_bank(self, subject_key: str) -> bool:
        return (
            await self.repository.find_question_bank(
                requested_name=subject_key.replace("-", " ").title(),
                normalized_name=subject_key,
            )
        ) is not None

    async def get_discoverable_subjects(self, user_id: str) -> list[dict]:
        """
        Retrieves a list of all assessment subjects available in the skill bank,
        enriched with user profile context and past attempt data.
        Always fetches all data without truncating timeouts or defaults replacement.
        """
        cache_key = f"subjects:{user_id}"

        if self.cache:
            cached = self.cache.get_json(cache_key)
            if cached is not None:
                return cached

        import asyncio

        # We fetch without any hard wait_for timeout to ensure no data is dropped
        unique_subjects, user_assessments, profile = await asyncio.gather(
            self.repository.list_unique_subjects(),
            self.repository.list_user_assessments(user_id=user_id),
            self.profile_repository.get_profile(user_id) if self.profile_repository else asyncio.sleep(0, result={}),
            return_exceptions=True
        )

        if isinstance(unique_subjects, Exception):
            import logging
            logging.error("Failed to fetch unique subjects: %s", unique_subjects)
            unique_subjects = []
            
        if isinstance(user_assessments, Exception):
            user_assessments = []
            
        if isinstance(profile, Exception):
            profile = {}

        assessment_map = {}
        for ass in user_assessments:
            cat = (ass.get("category") or "").strip().lower()
            if ass.get("status") == "completed" and ass.get("overall_score") is not None:
                if cat not in assessment_map or ass.get("created_at", "") > assessment_map[cat].get("created_at", ""):
                    assessment_map[cat] = ass

        focus_role = (profile.get("focus_role") or "").lower() if isinstance(profile, dict) else ""
        role_keywords = focus_role.split() if focus_role else []

        results = []
        for sub in unique_subjects:
            cat_name = sub["category"]
            key = normalize_name(cat_name)
            cat_lower = cat_name.lower()
            
            description = f"Professional proficiency assessment for {cat_name}."
            
            past_ass = assessment_map.get(key)
            current_score = past_ass.get("overall_score") if past_ass else None
            
            is_relevant = bool(role_keywords) and (
                any(kw in cat_lower for kw in role_keywords)
            )

            results.append({
                "key": key,
                "title": cat_name,
                "description": description,
                "source": "Skill Bank",
                "severity": 0.8 if is_relevant else 0.5,
                "current_score": current_score,
                "skill_id": sub.get("skill_id"),
                "resource_count": 0,
                "is_available": True,
                "is_relevant": is_relevant
            })
            
        results.sort(key=lambda x: (not x["is_relevant"], x["title"]))
        
        # Cache only if we actually got a reasonable amount of real data
        # so we don't permanently cache a failed DB query result.
        if self.cache and len(unique_subjects) > 0 and results:
            try:
                self.cache.set_json(cache_key, results, 60 * 5)
            except Exception:
                pass
                
        return results
