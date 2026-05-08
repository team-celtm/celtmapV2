from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from random import sample

from app.models.enums import DomainEventType
from app.repositories.assessment_repository import AssessmentRepository
from app.repositories.interview_repository import InterviewRepository
from app.repositories.learning_repository import LearningRepository
from app.repositories.profile_repository import ProfileRepository
from app.services.domain_event_service import DomainEventService
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
    ) -> None:
        self.repository = repository
        self.event_service = event_service
        self.skill_service = skill_service
        self.skill_request_service = skill_request_service
        self.interview_repository = interview_repository
        self.learning_repository = learning_repository
        self.profile_repository = profile_repository

    async def get_questions(
        self,
        *,
        category: str | None,
        difficulty: str | None,
        limit: int,
        skill_id: str | None = None,
        skill_request_id: str | None = None,
        question_type: str = "MCQ",
    ) -> list[dict]:
        questions = await self.repository.get_questions(
            category=category,
            difficulty=difficulty,
            limit=limit,
            skill_id=skill_id,
            skill_request_id=skill_request_id,
            question_type=question_type,
        )
        selected = sample(questions, k=min(limit, len(questions))) if questions else []
        option_rows = await self.repository.get_options_for_questions(
            [item["id"] for item in selected]
        )
        option_map: dict[str, list[dict]] = {}
        for option in option_rows:
            option_map.setdefault(option["question_id"], []).append(option)

        response = []
        for question in selected:
            randomized_options = shuffled(option_map.get(question["id"], []))
            question_metadata = question.get("metadata")
            if not isinstance(question_metadata, dict):
                question_metadata = {}
            response.append(
                {
                    "id": question["id"],
                    "question_text": question["question_text"],
                    "category": question["category"],
                    "difficulty": question.get("difficulty"),
                    "skill_id": question.get("skill_id"),
                    "skill_request_id": question.get("skill_request_id"),
                    "question_type": question.get("question_type", "MCQ"),
                    "scenario": question_metadata.get("scenario"),
                    "options": [
                        {"id": option["id"], "option_text": option["option_text"]}
                        for option in randomized_options
                    ],
                }
            )
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
        return await self.repository.create_assessment(
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

    async def submit_answers(
        self, *, assessment_id: str, user_id: str, answers: list[dict]
    ) -> list[dict]:
        payloads = []
        for answer in answers:
            selected_option_id = answer.get("selected_option_id")
            answer_text = str(answer.get("answer_text") or "").strip()
            option = None
            if selected_option_id:
                option = await self.repository.get_option(selected_option_id)
                if option is None:
                    continue
            if option is None and not answer_text:
                continue
            payloads.append(
                {
                    "assessment_id": assessment_id,
                    "user_id": user_id,
                    "question_id": answer["question_id"],
                    "selected_option_id": selected_option_id,
                    "answer_text": answer_text or None,
                    "is_correct": bool(option["is_correct"]) if option else False,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )
        return await self.repository.insert_user_answers(payloads)

    async def complete_assessment(self, *, assessment_id: str, user_id: str) -> dict:
        assessment = await self.repository.get_assessment(assessment_id)
        answers = await self.repository.list_user_answers(assessment_id)
        has_option_answers = any(answer.get("selected_option_id") for answer in answers)
        has_text_answers = any(str(answer.get("answer_text") or "").strip() for answer in answers)
        if has_option_answers and not has_text_answers:
            correct_answers = len([answer for answer in answers if answer["is_correct"]])
        else:
            correct_answers = await self._score_text_answers(answers)
        total_questions = len(answers)
        score = round((correct_answers / total_questions) * 100, 2) if total_questions else 0.0
        await self.repository.update_assessment(
            assessment_id,
            {
                "score": score,
                "status": "completed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        await self.event_service.emit(
            event_type=DomainEventType.ASSESSMENT_COMPLETED,
            aggregate_type="assessment",
            aggregate_id=assessment_id,
            payload={
                "user_id": user_id,
                "score": score,
                "category": assessment.get("category") if assessment else None,
            },
        )
        if assessment and assessment.get("skill_request_id") and self.skill_request_service:
            await self.skill_request_service.record_mcq_score(
                assessment["skill_request_id"],
                float(score),
            )
        if assessment and assessment.get("skill_id") and self.skill_service:
            await self.skill_service.record_skill_measurement(
                user_id=user_id,
                skill_id=assessment["skill_id"],
                skill_name=assessment.get("category") or assessment["skill_id"],
                assessment_score=score,
                skill_request_id=assessment.get("skill_request_id"),
                source="assessment",
            )
            await self._infer_hidden_skills_from_attempt(
                assessment=assessment,
                user_id=user_id,
                score=score,
                total_questions=total_questions,
            )
        return {
            "assessment_id": assessment_id,
            "score": score,
            "correct_answers": correct_answers,
            "total_questions": total_questions,
            "status": "completed",
        }

    async def _score_text_answers(self, answers: list[dict]) -> int:
        return 0

    async def _infer_hidden_skills_from_attempt(
        self, assessment: dict, user_id: str, score: float, total_questions: int
    ) -> None:
        pass

    PLACEMENT_DOMAINS: list[str] = [
        "Mathematics",
        "Science",
        "English",
        "Artificial Intelligence",
        "Frontend Development",
        "Software Engineering",
    ]

    async def get_placement_questions(self, questions_per_domain: int = 3) -> list[dict]:
        import random
        import uuid

        TOTAL_QUESTIONS = 20
        candidate_questions: list[dict] = []
        questions_per_domain_calc = max(3, TOTAL_QUESTIONS // len(self.PLACEMENT_DOMAINS))

        for domain in self.PLACEMENT_DOMAINS:
            rows = await self.repository.get_questions(
                category=domain,
                difficulty=None,
                limit=questions_per_domain_calc,
                skill_id=None,
                skill_request_id=None,
                question_type="MCQ",
            )
            if rows:
                candidate_questions.extend(rows[:questions_per_domain_calc])

        if len(candidate_questions) < TOTAL_QUESTIONS:
            fallback = self._get_fallback_placement_questions(questions_per_domain_calc)
            for q in fallback:
                if q["id"] not in [xq["id"] for xq in candidate_questions]:
                    candidate_questions.append(q)

        random.shuffle(candidate_questions)

        candidate_questions = candidate_questions[:TOTAL_QUESTIONS]

        result: list[dict] = []
        for question in candidate_questions:
            if "options" in question:
                result.append(question)
            else:
                option_rows = await self.repository.get_options_for_questions([question["id"]])
                options_list = shuffled(option_rows) if option_rows else []
                q_meta = question.get("metadata") or {}
                result.append(
                    {
                        "id": question["id"],
                        "question_text": question["question_text"],
                        "category": question["category"],
                        "difficulty": question.get("difficulty"),
                        "question_type": "MCQ",
                        "scenario": q_meta.get("scenario"),
                        "options": [
                            {"id": opt["id"], "option_text": opt["option_text"]}
                            for opt in options_list
                        ],
                    }
                )
        return result

    def _get_fallback_placement_questions(self, questions_per_domain: int = 2) -> list[dict]:
        import uuid

        fallback_questions = [
            {
                "id": str(uuid.uuid4()),
                "question_text": "Solve for x: 2x + 5 = 17",
                "category": "Mathematics",
                "difficulty": "easy",
                "question_type": "MCQ",
                "options": [
                    {"id": str(uuid.uuid4()), "option_text": "4"},
                    {"id": str(uuid.uuid4()), "option_text": "5"},
                    {"id": str(uuid.uuid4()), "option_text": "6"},
                    {"id": str(uuid.uuid4()), "option_text": "7"},
                ],
                "_correct_idx": 2,
            },
            {
                "id": str(uuid.uuid4()),
                "question_text": "What is the slope of the line passing through (2,3) and (6,11)?",
                "category": "Mathematics",
                "difficulty": "easy",
                "question_type": "MCQ",
                "options": [
                    {"id": str(uuid.uuid4()), "option_text": "1"},
                    {"id": str(uuid.uuid4()), "option_text": "2"},
                    {"id": str(uuid.uuid4()), "option_text": "3"},
                    {"id": str(uuid.uuid4()), "option_text": "4"},
                ],
                "_correct_idx": 1,
            },
            {
                "id": str(uuid.uuid4()),
                "question_text": "Which is a supervised learning algorithm?",
                "category": "Artificial Intelligence",
                "difficulty": "medium",
                "question_type": "MCQ",
                "options": [
                    {"id": str(uuid.uuid4()), "option_text": "K-Means Clustering"},
                    {"id": str(uuid.uuid4()), "option_text": "Linear Regression"},
                    {"id": str(uuid.uuid4()), "option_text": "PCA"},
                    {"id": str(uuid.uuid4()), "option_text": "Autoencoders"},
                ],
                "_correct_idx": 1,
            },
            {
                "id": str(uuid.uuid4()),
                "question_text": "What does relu activation output for negative inputs?",
                "category": "Artificial Intelligence",
                "difficulty": "medium",
                "question_type": "MCQ",
                "options": [
                    {"id": str(uuid.uuid4()), "option_text": "The input value"},
                    {"id": str(uuid.uuid4()), "option_text": "Zero"},
                    {"id": str(uuid.uuid4()), "option_text": "One"},
                    {"id": str(uuid.uuid4()), "option_text": "Negative of input"},
                ],
                "_correct_idx": 1,
            },
            {
                "id": str(uuid.uuid4()),
                "question_text": "Which HTML tag is used for the largest heading?",
                "category": "Frontend Development",
                "difficulty": "easy",
                "question_type": "MCQ",
                "options": [
                    {"id": str(uuid.uuid4()), "option_text": "<heading>"},
                    {"id": str(uuid.uuid4()), "option_text": "<h6>"},
                    {"id": str(uuid.uuid4()), "option_text": "<h1>"},
                    {"id": str(uuid.uuid4()), "option_text": "<head>"},
                ],
                "_correct_idx": 2,
            },
            {
                "id": str(uuid.uuid4()),
                "question_text": "What does CSS stand for?",
                "category": "Frontend Development",
                "difficulty": "easy",
                "question_type": "MCQ",
                "options": [
                    {"id": str(uuid.uuid4()), "option_text": "Creative Style Sheets"},
                    {"id": str(uuid.uuid4()), "option_text": "Cascading Style Sheets"},
                    {"id": str(uuid.uuid4()), "option_text": "Computer Style Sheets"},
                    {"id": str(uuid.uuid4()), "option_text": "Colorful Style Sheets"},
                ],
                "_correct_idx": 1,
            },
            {
                "id": str(uuid.uuid4()),
                "question_text": "Which sorting algo has the best average-case complexity?",
                "category": "Software Engineering",
                "difficulty": "medium",
                "question_type": "MCQ",
                "options": [
                    {"id": str(uuid.uuid4()), "option_text": "Bubble Sort"},
                    {"id": str(uuid.uuid4()), "option_text": "Quick Sort"},
                    {"id": str(uuid.uuid4()), "option_text": "Selection Sort"},
                    {"id": str(uuid.uuid4()), "option_text": "Insertion Sort"},
                ],
                "_correct_idx": 1,
            },
            {
                "id": str(uuid.uuid4()),
                "question_text": "What is the time complexity of binary search?",
                "category": "Software Engineering",
                "difficulty": "medium",
                "question_type": "MCQ",
                "options": [
                    {"id": str(uuid.uuid4()), "option_text": "O(n)"},
                    {"id": str(uuid.uuid4()), "option_text": "O(log n)"},
                    {"id": str(uuid.uuid4()), "option_text": "O(n log n)"},
                    {"id": str(uuid.uuid4()), "option_text": "O(1)"},
                ],
                "_correct_idx": 1,
            },
        ]
        return fallback_questions[: questions_per_domain * len(self.PLACEMENT_DOMAINS)]

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

question_ids = [a.get("question_id") for a in answers if a.get("question_id")]
        questions = await self.repository.get_questions_by_ids(question_ids)
        question_map = {q["id"]: q for q in questions}

        domain_correct: dict[str, int] = {}
        domain_total: dict[str, int] = {}
        fallback_questions = {q["id"]: q for q in self._get_fallback_placement_questions(3)}
        
        for answer in answers:
            qid = answer.get("question_id")
            selected_option_id = answer.get("selected_option_id")
            question = question_map.get(qid)
            
            if not question and qid in fallback_questions:
                question = fallback_questions[qid]
            
            if not question:
                continue
            
            category = question.get("category", "General")
            domain_total[category] = domain_total.get(category, 0) + 1
            
            if selected_option_id:
                option = await self.repository.get_option(selected_option_id)
                if option and option.get("is_correct"):
                    domain_correct[category] = domain_correct.get(category, 0) + 1
        
        if not domain_total:
            for answer in answers:
                qid = answer.get("question_id")
                if qid in fallback_questions:
                    q = fallback_questions[qid]
                    category = q.get("category", "General")
                    domain_total[category] = domain_total.get(category, 0) + 1
        
        domain_scores: dict[str, float] = {}
        for cat, total in domain_total.items():
            correct = domain_correct.get(cat, 0)
            domain_scores[cat] = round((correct / total) * 100, 2) if total > 0 else 0.0
        
        overall_correct = sum(domain_correct.values())
        overall_total = sum(domain_total.values())
        overall_score = round((overall_correct / overall_total) * 100, 2) if overall_total > 0 else 50.0
        
        assessment_id = f"placement_{user_id[:8]}"
        
        inference = self._generate_placement_inference(domain_scores, overall_score)
        
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
        strong_domains = []
        weak_domains = []
        for domain, score in domain_scores.items():
            if score >= 70:
                strong_domains.append(domain)
            elif score < 40:
                weak_domains.append(domain)

        areas_to_focus = weak_domains[:3] if weak_domains else list(domain_scores.keys())[:3]

        return {
            "overall_readiness": overall_score,
            "strong_areas": strong_domains,
            "areas_to_focus": areas_to_focus,
            "summary": (
                f"Your overall readiness is {overall_score:.0f}%. "
                f"{'Strong in ' + ', '.join(strong_domains) + '.' if strong_domains else ''} "
                f"{'Focus on ' + ', '.join(areas_to_focus) + '.' if areas_to_focus else ''}"
            ),
            "recommendations": [
                f"Focus on {domain} to improve your profile" for domain in areas_to_focus
            ],
        }

    async def get_placement_status(self, user_id: str, profile_service: object) -> bool:
        try:
            profile = await profile_service.get_profile(user_id, None)
            meta = profile.get("metadata") or {}
            return bool(meta.get("has_completed_placement", False))
        except Exception:
            return False

    async def get_assessment_log(self, user_id: str, limit: int = 10) -> list[dict]:
        log_entries = []

        mcq_assessments = await self.repository.list_assessments(user_id=user_id, limit=limit)
        for a in mcq_assessments:
            if a.get("assessment_type") in ("mcq", "placement"):
                log_entries.append(
                    {
                        "id": a["id"],
                        "type": "mcq",
                        "subject": a.get("category", "General"),
                        "score": a.get("score"),
                        "status": a.get("status"),
                        "completed_at": a.get("completed_at"),
                    }
                )

        return log_entries[:limit]

    async def get_subject_detail(self, user_id: str, subject_key: str) -> dict | None:
        return None

    async def _has_subject_question_bank(self, subject_key: str) -> bool:
        return True
