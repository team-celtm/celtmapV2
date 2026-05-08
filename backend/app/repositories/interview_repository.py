from __future__ import annotations

from supabase import Client

from app.repositories.base import SupabaseTableRepository


class InterviewRepository:
    def __init__(self, client: Client) -> None:
        self.sessions = SupabaseTableRepository(client, "interview_sessions")
        self.questions = SupabaseTableRepository(client, "interview_questions")
        self.answers = SupabaseTableRepository(client, "interview_answers")
        self.evaluations = SupabaseTableRepository(client, "interview_evaluations")

    async def create_session(self, payload: dict) -> dict:
        return await self.sessions.insert(payload)

    async def get_session(self, session_id: str) -> dict | None:
        return await self.sessions.get_by_id(session_id)

    async def update_session(self, session_id: str, payload: dict) -> dict:
        rows = await self.sessions.update(filters={"id": session_id}, payload=payload)
        if isinstance(rows, list) and rows:
            return rows[0]
        return payload

    async def list_session_questions(self, session_id: str) -> list[dict]:
        return await self.questions.list(
            filters={"session_id": session_id},
            limit=500,
            order_by="created_at",
            descending=False,
        )

    async def list_session_answers(self, session_id: str) -> list[dict]:
        return await self.answers.list(
            filters={"session_id": session_id},
            limit=500,
            order_by="created_at",
            descending=False,
        )

    async def create_question(self, payload: dict) -> dict:
        return await self.questions.insert(payload)

    async def create_answer(self, payload: dict) -> dict:
        return await self.answers.insert(payload)

    async def list_sessions(
        self, user_id: str, limit: int = 25, cursor: str | None = None
    ) -> list[dict]:
        return await self.sessions.list(filters={"user_id": user_id}, limit=limit, cursor=cursor)

    async def create_evaluation(self, payload: dict) -> dict:
        return await self.evaluations.insert(payload)

    async def get_latest_evaluation(self, session_id: str) -> dict | None:
        rows = await self.evaluations.list(
            filters={"session_id": session_id},
            limit=1,
            order_by="created_at",
            descending=True,
        )
        return rows[0] if rows else None

    async def get_session_turns(self, session_id: str) -> list[dict]:
        questions = await self.list_session_questions(session_id)
        answers = await self.list_session_answers(session_id)
        answers_by_question_id = {
            answer.get("question_id"): answer for answer in answers if answer.get("question_id")
        }
        unmatched_answers = [answer for answer in answers if not answer.get("question_id")]
        turns: list[dict] = []

        for index, question in enumerate(questions):
            answer = answers_by_question_id.get(question["id"])
            if answer is None and index < len(unmatched_answers):
                answer = unmatched_answers[index]
            answer_metadata = (answer or {}).get("metadata") or {}
            turns.append(
                {
                    "question_id": question["id"],
                    "question_text": question["question_text"],
                    "source_document": question.get("source_document"),
                    "answer_id": answer.get("id") if answer else None,
                    "answer_text": answer.get("answer_text") if answer else None,
                    "evaluation_metrics": answer_metadata.get("evaluation_metrics", {}),
                    "evidence": answer_metadata.get("evidence"),
                    "created_at": question.get("created_at"),
                }
            )

        if turns:
            return turns

        return [
            {
                "question_id": None,
                "question_text": None,
                "source_document": None,
                "answer_id": answer.get("id"),
                "answer_text": answer.get("answer_text"),
                "evaluation_metrics": (answer.get("metadata") or {}).get("evaluation_metrics", {}),
                "evidence": (answer.get("metadata") or {}).get("evidence"),
                "created_at": answer.get("created_at"),
            }
            for answer in answers
        ]
