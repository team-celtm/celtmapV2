from __future__ import annotations

from app.repositories.assessment_repository import AssessmentRepository
from app.repositories.skill_repository import SkillRepository


class WrittenAssessmentService:
    def __init__(
        self,
        repository: AssessmentRepository,
        skill_repository: SkillRepository,
    ) -> None:
        self.repository = repository
        self.skill_repository = skill_repository

    async def list_sessions(self, user_id: str, limit: int = 25) -> list[dict]:
        return await self.repository.list_written_sessions(user_id=user_id, limit=limit)

    async def get_session_for_user(self, user_id: str, assessment_id: str) -> dict | None:
        session = await self.repository.get_written_session(assessment_id)
        if session is None or str(session["user_id"]) != user_id:
            return None
        return session

    async def create_session(
        self,
        *,
        user_id: str,
        skill_id: str | None = None,
        skill_request_id: str | None = None,
        prompt: str | None = None,
        evaluator_mode: str = "teacher",
    ) -> dict:
        resolved_prompt = prompt or await self._resolve_prompt(
            skill_id=skill_id,
            skill_request_id=skill_request_id,
        )
        return await self.repository.create_written_session(
            user_id=user_id,
            skill_id=skill_id,
            skill_request_id=skill_request_id,
            prompt=resolved_prompt,
            evaluator_mode=evaluator_mode,
        )

    async def save_submission(
        self,
        *,
        user_id: str,
        session_id: str,
        submission_text: str,
        evaluator_mode: str | None = None,
    ) -> dict | None:
        session = await self.get_session_for_user(user_id, session_id)
        if session is None:
            return None

        update_payload: dict[str, object] = {
            "submission_text": submission_text,
        }
        if evaluator_mode:
            update_payload["evaluator_mode"] = evaluator_mode

        return await self.repository.update_written_session(session_id, update_payload)

    async def mark_processing(
        self,
        *,
        user_id: str,
        session_id: str,
    ) -> dict | None:
        session = await self.get_session_for_user(user_id, session_id)
        if session is None:
            return None

        return await self.repository.update_written_session(
            session_id,
            {"status": "processing"},
        )

    async def _resolve_prompt(
        self,
        *,
        skill_id: str | None,
        skill_request_id: str | None,
    ) -> str:
        # Strategy 1: Direct skill ID match or Skill Name match
        skill_name = None
        if skill_id:
            try:
                skill_data = await self.skill_repository.get_skill(skill_id)
                if skill_data:
                    skill_name = skill_data.get("name")
            except Exception:
                pass

        # Try to get question by skill_id first
        if skill_id:
            written_questions = await self.repository.get_questions(
                limit=5,
                question_type="descriptive",
                skill_id=skill_id,
            )
            if written_questions:
                import random
                return random.choice(written_questions)["question_text"]

        # Strategy 2: Subject/Category/Keyword Discovery
        # Use the name of the skill or the ID as a keyword
        search_query = skill_name or skill_id
        if search_query:
            clean_query = str(search_query).replace("-", " ").strip()
            
            # 2a: Try discovery logic in repository
            bank = await self.repository.find_question_bank(
                requested_name=clean_query,
                normalized_name=clean_query.lower().replace(" ", "-"),
                skill_id=skill_id if _is_uuid_like(skill_id) else None
            )
            
            # If bank found, try to fetch by category derived from it
            if bank:
                cat = bank.get("category") or bank.get("subject_id")
                if cat:
                    cat_questions = await self.repository.get_questions(
                        category=cat,
                        limit=10,
                        question_type="descriptive",
                    )
                    if cat_questions:
                        import random
                        # Try to find one that actually mentions our topic
                        matches = [q for q in cat_questions if clean_query.lower() in q["question_text"].lower()]
                        return random.choice(matches or cat_questions)["question_text"]

            # 2b: Search directly by keyword in category filter (fuzzy)
            keyword_questions = await self.repository.get_questions(
                category=clean_query,
                limit=10,
                question_type="descriptive",
            )
            if keyword_questions:
                import random
                return random.choice(keyword_questions)["question_text"]

        # Strategy 3: Global Descriptive Question Pool
        # Instead of searching sub-category "questions", we search without category filter
        # but with question_type="descriptive" to find ANY available question.
        pool_questions = await self.repository.get_questions(
            category=None,
            difficulty=None,
            limit=100,  # Increase limit to allow for better keyword filtering in memory
            question_type="descriptive",
        )
        if pool_questions:
            import random
            
            # If we had a search query, try a final keyword filter in the random pool
            if search_query:
                q_text = str(search_query).lower()
                matches = [q for q in pool_questions if q_text in q["question_text"].lower()]
                if matches:
                    return random.choice(matches)["question_text"]
                
                # Try parts of the query if multiple words
                parts = [p for p in q_text.split() if len(p) > 3]
                for part in parts:
                    matches = [q for q in pool_questions if part in q["question_text"].lower()]
                    if matches:
                        return random.choice(matches)["question_text"]
            
            # If still no keyword match, just pick a random descriptive question
            # This ensures we NEVER fall back to the test prompt if descriptive questions exist
            return random.choice(pool_questions)["question_text"]

        # Strategy 4: Fallback to structured prompt if DB is completely empty for this type
        if skill_id:
            name = skill_name or str(skill_id).replace("-", " ").title()
            return (
                f"Identify a critical challenge in {name} and explain how you would solve it. "
                "Include your architectural reasoning, potential risks, and evaluation metrics."
            )

        return (
            "Describe a complex technical problem you solved recently. "
            "Explain your methodology, the tradeoffs you considered, and the final outcome."
        )


def _is_uuid_like(value: str | None) -> bool:
    if not value:
        return False
    import uuid
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, TypeError):
        return False
