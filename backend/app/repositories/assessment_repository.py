from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from postgrest.exceptions import APIError
from supabase import Client

from app.repositories.base import SupabaseTableRepository


def _is_uuid_like(value: str | None) -> bool:
    if not value:
        return False
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, TypeError):
        return False


def _question_type_candidates(question_type: str | None) -> list[str]:
    raw = str(question_type or "").strip()
    if not raw:
        return []

    variants: list[str] = []
    for candidate in (raw, raw.upper(), raw.lower()):
        if candidate and candidate not in variants:
            variants.append(candidate)
    return variants


def _is_invalid_uuid_filter_error(exc: Exception) -> bool:
    if not isinstance(exc, APIError):
        return False

    payload = exc.args[0] if exc.args else {}
    if isinstance(payload, dict):
        code = payload.get("code")
        message = str(payload.get("message") or "")
    else:
        code = None
        message = str(exc)

    return code == "22P02" and "invalid input syntax for type uuid" in message.lower()


class AssessmentRepository:
    def __init__(self, client: Client) -> None:
        self.client = client
        self.questions = SupabaseTableRepository(client, "questions")
        self.question_options = SupabaseTableRepository(client, "question_options")
        self.mcq_questions = SupabaseTableRepository(client, "mcq_questions") # Legacy
        self.situational_questions = SupabaseTableRepository(client, "situational_mcq_questions")
        self.descriptive_questions = SupabaseTableRepository(client, "descriptive_questions")
        self.assessments = SupabaseTableRepository(client, "assessments")
        self.descriptive_answers = SupabaseTableRepository(client, "descriptive_answers")
        self.user_answers = SupabaseTableRepository(client, "user_answers")

    @staticmethod
    def _utc_now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _default_written_prompt() -> str:
        return (
            "Write a structured response showing your approach, reasoning, "
            "tradeoffs, and verification plan."
        )

    @staticmethod
    def _default_written_rubric() -> dict[str, Any]:
        return {
            "criteria": [
                "technical_accuracy",
                "structure",
                "tradeoff_reasoning",
                "practicality",
            ]
        }

    def _hydrate_assessment_row(
        self,
        row: dict[str, Any],
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        merged_payload = payload or {}
        overall_score = row.get("overall_score")
        created_at = row.get("created_at")
        updated_at = row.get("updated_at") or created_at
        status = (
            merged_payload.get("status")
            or row.get("status")
            or ("completed" if overall_score is not None else "in_progress")
        )

        return {
            **row,
            "category": merged_payload.get("category") or row.get("category") or "General",
            "question_type": (
                merged_payload.get("question_type") or row.get("question_type") or "MCQ"
            ),
            "skill_id": merged_payload.get("skill_id") or row.get("skill_id"),
            "skill_request_id": (
                merged_payload.get("skill_request_id") or row.get("skill_request_id")
            ),
            "score": (
                merged_payload.get("score")
                if merged_payload.get("score") is not None
                else overall_score
            ),
            "overall_score": overall_score,
            "status": status,
            "metadata": merged_payload.get("metadata") or row.get("metadata") or {},
            "completed_at": row.get("completed_at") or (updated_at if overall_score is not None else None),
        }

    def _parse_written_state(self, raw_value: Any) -> dict[str, Any]:
        if not raw_value:
            return {}
        if isinstance(raw_value, dict):
            return raw_value
        if not isinstance(raw_value, str):
            return {}
        try:
            decoded = json.loads(raw_value)
        except json.JSONDecodeError:
            return {"feedback": raw_value}
        return decoded if isinstance(decoded, dict) else {}

    def _serialize_written_state(self, state: dict[str, Any]) -> str:
        return json.dumps(state, separators=(",", ":"), default=str)

    def _hydrate_written_session(
        self,
        assessment_row: dict[str, Any],
        state_row: dict[str, Any] | None,
    ) -> dict[str, Any]:
        parsed_state = self._parse_written_state((state_row or {}).get("ai_feedback"))
        metadata = parsed_state.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        evaluator_mode = parsed_state.get("evaluator_mode") or metadata.get("evaluator_mode")
        if evaluator_mode:
            metadata = {**metadata, "evaluator_mode": evaluator_mode}

        score = (state_row or {}).get("score")
        if score is None:
            score = assessment_row.get("overall_score")

        created_at = assessment_row.get("created_at")
        updated_at = parsed_state.get("updated_at") or assessment_row.get("updated_at") or created_at
        completed_at = parsed_state.get("completed_at") or (updated_at if score is not None else None)

        return {
            "id": assessment_row["id"],
            "user_id": assessment_row["user_id"],
            "skill_id": parsed_state.get("skill_id"),
            "skill_request_id": parsed_state.get("skill_request_id"),
            "prompt": parsed_state.get("prompt") or self._default_written_prompt(),
            "rubric": parsed_state.get("rubric") or self._default_written_rubric(),
            "submission_text": (state_row or {}).get("user_answer"),
            "score": score,
            "feedback": parsed_state.get("feedback"),
            "status": (
                parsed_state.get("status")
                or ("completed" if score is not None else "draft")
            ),
            "metadata": metadata,
            "created_at": created_at,
            "updated_at": updated_at,
            "completed_at": completed_at,
        }

    async def _get_latest_written_state_row(
        self,
        assessment_id: str,
    ) -> dict[str, Any] | None:
        rows = await self.descriptive_answers.list(
            filters={"assessment_id": assessment_id},
            limit=1,
            order_by="created_at",
        )
        return rows[0] if rows else None

    def _resolve_skill_uuid(self, skill_id: str | None) -> str | None:
        """
        Resolves source skill identifiers like `machine-learning` to the UUID used by
        legacy/repair-schema question tables. When the database already stores text
        skill IDs, the caller will still fall back to the original identifier.
        """
        normalized = str(skill_id or "").strip()
        if not normalized or _is_uuid_like(normalized):
            return normalized or None

        query_text = normalized.replace("-", " ")
        lookups = (
            ("skill_id", normalized, "eq"),
            ("normalized_name", normalized, "eq"),
            ("skill_name", query_text, "ilike"),
        )

        for column, value, operator in lookups:
            query = self.client.table("skills").select("id").limit(1)
            if operator == "eq":
                query = query.eq(column, value)
            else:
                query = query.ilike(column, value)

            result = query.execute()
            rows = result.data or []
            if rows and rows[0].get("id"):
                return str(rows[0]["id"])

        return None

    def _resolve_subskill_uuid(self, subskill_id: str | None) -> str | None:
        normalized = str(subskill_id or "").strip()
        if not normalized or _is_uuid_like(normalized):
            return normalized or None

        query_text = normalized.replace("-", " ")
        lookups = (
            ("subskill_id", normalized, "eq"),
            ("normalized_name", normalized, "eq"),
            ("subskill_name", query_text, "ilike"),
        )

        for column, value, operator in lookups:
            query = self.client.table("subskills").select("id").limit(1)
            if operator == "eq":
                query = query.eq(column, value)
            else:
                query = query.ilike(column, value)

            result = query.execute()
            rows = result.data or []
            if rows and rows[0].get("id"):
                return str(rows[0]["id"])

        return None

    async def upsert_question(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Upserts a question into the core table. 
        In production schema, MCQ options are in a separate table.
        """
        # Production ingestion uses source_question_id for conflict
        # But for general usage we might want to check text too.
        on_conflict = "source_question_id" if payload.get("source_question_id") else "question_text"
        
        # Ensure we don't pass fields that don't exist in the core table if we are using legacy code
        # But here we want the production fields.
        rows = await self.questions.upsert(payload, on_conflict=on_conflict)
        return rows[0] if rows else payload

    async def upsert_options(self, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Upserts multiple options linked to a question.
        Each payload has: question_id, option_key, option_text, is_correct
        """
        if not payloads:
            return []
        
        # Uniqueness on (question_id, option_key)
        return await self.question_options.upsert(payloads, on_conflict="question_id,option_key")

    async def get_questions(
        self,
        *,
        category: str | None,
        difficulty: str | None,
        limit: int,
        question_type: str = "mcq",
        skill_id: str | None = None,
        subskill_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Fetches questions joined with their options.
        """
        normalized_question_type = str(question_type or "").strip().lower()
        skill_candidates: list[str | None]
        subskill_candidates: list[str | None]

        resolved_skill_uuid = self._resolve_skill_uuid(skill_id)
        resolved_subskill_uuid = self._resolve_subskill_uuid(subskill_id)

        skill_candidates = [None]
        if skill_id:
            skill_candidates = []
            if _is_uuid_like(skill_id):
                skill_candidates.append(skill_id)
            elif resolved_skill_uuid:
                skill_candidates.append(resolved_skill_uuid)
            else:
                skill_candidates.append(None)

        subskill_candidates = [None]
        if subskill_id:
            subskill_candidates = []
            if _is_uuid_like(subskill_id):
                subskill_candidates.append(subskill_id)
            elif resolved_subskill_uuid:
                subskill_candidates.append(resolved_subskill_uuid)
            else:
                subskill_candidates.append(None)

        def run_query(
            *,
            skill_filter: str | None,
            subskill_filter: str | None,
            requested_question_type: str | None = None,
        ) -> list[dict[str, Any]]:
            query = (
                self.client.table("questions")
                .select("*, question_options(*)")
                .eq("is_active", True)
            )

            effective_question_type = requested_question_type or question_type
            question_type_values = _question_type_candidates(effective_question_type)
            if len(question_type_values) == 1:
                query = query.eq("question_type", question_type_values[0])
            elif len(question_type_values) > 1:
                query = query.in_("question_type", question_type_values)

            if skill_filter:
                query = query.eq("skill_id", skill_filter)

            if subskill_filter:
                query = query.eq("subskill_id", subskill_filter)

            if difficulty:
                difficulty_values = _question_type_candidates(difficulty)
                if len(difficulty_values) == 1:
                    query = query.eq("difficulty", difficulty_values[0])
                elif len(difficulty_values) > 1:
                    query = query.in_("difficulty", difficulty_values)

            if category:
                # Category matching needs to tolerate:
                # - spaces vs hyphens vs underscores (e.g. "Deep Learning" vs "deep-learning")
                # - partial matches and inconsistent seeding
                raw = str(category).strip()
                normalized = raw.lower().replace("_", " ").replace("-", " ")
                slug = normalized.replace(" ", "-")
                tokens = [t for t in normalized.split() if t]
                fuzzy = "%".join(tokens) if tokens else normalized

                patterns = []
                for value in (raw, normalized, slug, fuzzy):
                    value = value.strip()
                    if value and value not in patterns:
                        patterns.append(value)

                or_fragments: list[str] = []
                for pattern in patterns:
                    # Note: postgrest filters are not SQL; keep patterns simple.
                    or_fragments.append(f"category.ilike.%{pattern}%")
                    or_fragments.append(f"subject_id.ilike.%{pattern}%")

                query = query.or_(",".join(or_fragments))

            result = query.limit(limit).execute()
            return result.data or []

        def attempt_query_set(requested_question_type: str | None) -> list[dict[str, Any]]:
            for skill_filter in skill_candidates:
                for subskill_filter in subskill_candidates:
                    try:
                        rows = run_query(
                            skill_filter=skill_filter,
                            subskill_filter=subskill_filter,
                            requested_question_type=requested_question_type,
                        )
                    except Exception as exc:
                        invalid_skill_filter = (
                            skill_filter
                            and not _is_uuid_like(skill_filter)
                            and _is_invalid_uuid_filter_error(exc)
                        )
                        invalid_subskill_filter = (
                            subskill_filter
                            and not _is_uuid_like(subskill_filter)
                            and _is_invalid_uuid_filter_error(exc)
                        )
                        if invalid_skill_filter or invalid_subskill_filter:
                            continue
                        raise

                    if rows:
                        return rows
            return []

        def op():
            rows = attempt_query_set(question_type)
            if rows:
                return rows

            # Live subject banks can be partially seeded. When a situational bank is
            # missing for an otherwise valid subject, fall back to MCQ rows for the
            # same filters so the assessment flow still opens and completes.
            if normalized_question_type.startswith("situational"):
                rows = attempt_query_set("MCQ")
                if rows:
                    return rows

            # Final fallback for legacy UUID-backed schemas: if we were passed a slug
            # that cannot be applied directly, use the other filters (category/type/etc.)
            # so subject assessments still load their seeded bank.
            if (
                (skill_id and not _is_uuid_like(skill_id))
                or (subskill_id and not _is_uuid_like(subskill_id))
            ):
                rows = run_query(
                    skill_filter=None,
                    subskill_filter=None,
                    requested_question_type=question_type,
                )
                if rows:
                    return rows

                if normalized_question_type.startswith("situational"):
                    return run_query(
                        skill_filter=None,
                        subskill_filter=None,
                        requested_question_type="MCQ",
                    )

            return []

        rows = await self.questions._run_read(op)
        return rows if isinstance(rows, list) else []

    async def get_questions_by_ids(self, question_ids: list[str]) -> list[dict[str, Any]]:
        def op():
            return self.client.table("questions").select(
                "*, question_options(*)"
            ).in_("id", question_ids).execute()

        result = await self.questions._run_read(op)
        return result if isinstance(result, list) else []

    async def create_assessment(self, payload: dict[str, Any]) -> dict[str, Any]:
        created_at = payload.get("created_at") or self._utc_now_iso()
        db_payload = {
            "user_id": payload["user_id"],
            "assessment_type": payload.get("assessment_type") or "mcq",
            "overall_score": payload.get("overall_score", payload.get("score")),
            "created_at": created_at,
            "updated_at": payload.get("updated_at") or created_at,
        }
        row = await self.assessments.insert(db_payload)
        return self._hydrate_assessment_row(row, payload)

    async def get_assessment(self, assessment_id: str) -> dict[str, Any] | None:
        row = await self.assessments.get_by_id(assessment_id)
        if row is None:
            return None
        return self._hydrate_assessment_row(row)

    async def update_assessment(
        self,
        assessment_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        db_payload: dict[str, Any] = {}
        if "overall_score" in payload or "score" in payload:
            db_payload["overall_score"] = payload.get("overall_score", payload.get("score"))
        if db_payload or payload.get("updated_at"):
            db_payload["updated_at"] = payload.get("updated_at") or self._utc_now_iso()

        rows: list[dict[str, Any]] = []
        if db_payload:
            rows = await self.assessments.update(filters={"id": assessment_id}, payload=db_payload)

        if rows:
            return self._hydrate_assessment_row(rows[0], payload)

        existing = await self.assessments.get_by_id(assessment_id)
        if existing is None:
            return self._hydrate_assessment_row({"id": assessment_id}, payload)
        return self._hydrate_assessment_row(existing, payload)

    async def list_user_assessments(self, user_id: str, limit: int = 25) -> list[dict[str, Any]]:
        rows = await self.assessments.list(
            filters={"user_id": user_id},
            limit=limit,
            order_by="created_at",
        )
        return [self._hydrate_assessment_row(row) for row in rows]

    async def list_assessments(self, user_id: str, limit: int = 25) -> list[dict[str, Any]]:
        return await self.list_user_assessments(user_id=user_id, limit=limit)

    async def insert_user_answers(self, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not payloads:
            return []
        inserted: list[dict[str, Any]] = []
        for payload in payloads:
            if "user_answer" in payload:
                db_payload = {
                    "assessment_id": payload["assessment_id"],
                    "question_id": payload.get("question_id"),
                    "user_answer": payload.get("user_answer"),
                    "ai_feedback": payload.get("ai_feedback"),
                    "score": payload.get("score"),
                    "created_at": payload.get("created_at") or self._utc_now_iso(),
                }
                inserted.append(await self.descriptive_answers.insert(db_payload))
            else:
                db_payload = {
                    "assessment_id": payload["assessment_id"],
                    "user_id": payload["user_id"],
                    "question_id": payload["question_id"],
                    "selected_option_id": payload.get("selected_option_id"),
                    "is_correct": payload.get("is_correct"),
                    "created_at": payload.get("created_at") or self._utc_now_iso(),
                }
                inserted.append(await self.user_answers.insert(db_payload))
        return inserted

    async def list_user_answers(self, assessment_id: str) -> list[dict[str, Any]]:
        return await self.user_answers.list(
            filters={"assessment_id": assessment_id},
            limit=500,
            order_by="created_at",
            descending=False,
        )

    async def get_option(self, option_id: str) -> dict[str, Any] | None:
        return await self.question_options.get_by_id(option_id)

    async def get_question_options(self, question_id: str) -> list[dict[str, Any]]:
        """Fetch all answer options for a given question_id."""
        def op():
            result = (
                self.client.table("question_options")
                .select("*")
                .eq("question_id", question_id)
                .execute()
            )
            return result.data or []

        rows = await self.question_options._run_read(op)
        return rows if isinstance(rows, list) else []


    async def create_written_session(
        self,
        *,
        user_id: str,
        skill_id: str | None,
        skill_request_id: str | None,
        prompt: str,
        evaluator_mode: str,
    ) -> dict[str, Any]:
        assessment = await self.create_assessment(
            {
                "user_id": user_id,
                "assessment_type": "descriptive",
                "created_at": self._utc_now_iso(),
            }
        )
        state = {
            "skill_id": skill_id,
            "skill_request_id": skill_request_id,
            "prompt": prompt,
            "rubric": self._default_written_rubric(),
            "status": "draft",
            "evaluator_mode": evaluator_mode,
            "metadata": {"evaluator_mode": evaluator_mode},
            "updated_at": assessment.get("created_at") or self._utc_now_iso(),
        }
        await self.descriptive_answers.insert(
            {
                "assessment_id": assessment["id"],
                "question_id": None,
                "user_answer": "",
                "ai_feedback": self._serialize_written_state(state),
                "score": None,
                "created_at": assessment.get("created_at") or self._utc_now_iso(),
            }
        )
        return await self.get_written_session(assessment["id"]) or self._hydrate_written_session(
            assessment,
            None,
        )

    async def get_written_session(self, session_id: str) -> dict[str, Any] | None:
        assessment_row = await self.assessments.get_by_id(session_id)
        if assessment_row is None:
            return None
        state_row = await self._get_latest_written_state_row(session_id)
        return self._hydrate_written_session(assessment_row, state_row)

    async def list_written_sessions(self, user_id: str, limit: int = 25) -> list[dict[str, Any]]:
        assessments = await self.assessments.list(
            filters={"user_id": user_id, "assessment_type": "descriptive"},
            limit=limit,
            order_by="created_at",
        )
        sessions: list[dict[str, Any]] = []
        for row in assessments:
            state_row = await self._get_latest_written_state_row(row["id"])
            sessions.append(self._hydrate_written_session(row, state_row))
        return sessions

    async def update_written_session(
        self,
        session_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        assessment_row = await self.assessments.get_by_id(session_id)
        if assessment_row is None:
            raise ValueError(f"Written session {session_id} not found")

        state_row = await self._get_latest_written_state_row(session_id)
        parsed_state = self._parse_written_state((state_row or {}).get("ai_feedback"))
        metadata = parsed_state.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        if isinstance(payload.get("metadata"), dict):
            metadata = {**metadata, **payload["metadata"]}

        for key in ("skill_id", "skill_request_id", "prompt", "feedback", "status", "rubric"):
            if key in payload and payload.get(key) is not None:
                parsed_state[key] = payload[key]

        if "evaluator_mode" in payload and payload.get("evaluator_mode") is not None:
            parsed_state["evaluator_mode"] = payload["evaluator_mode"]
            metadata["evaluator_mode"] = payload["evaluator_mode"]

        parsed_state["metadata"] = metadata
        parsed_state["updated_at"] = payload.get("updated_at") or self._utc_now_iso()
        if payload.get("completed_at") is not None:
            parsed_state["completed_at"] = payload["completed_at"]

        answer_payload = {
            "user_answer": payload.get(
                "submission_text",
                payload.get("user_answer", (state_row or {}).get("user_answer") or ""),
            ),
            "ai_feedback": self._serialize_written_state(parsed_state),
            "score": payload.get("score", (state_row or {}).get("score")),
        }

        if state_row and state_row.get("id"):
            await self.descriptive_answers.update(
                filters={"id": state_row["id"]},
                payload=answer_payload,
            )
        else:
            await self.descriptive_answers.insert(
                {
                    "assessment_id": session_id,
                    "question_id": None,
                    "created_at": parsed_state["updated_at"],
                    **answer_payload,
                }
            )

        assessment_update: dict[str, Any] = {"updated_at": parsed_state["updated_at"]}
        if "score" in payload and payload.get("score") is not None:
            assessment_update["overall_score"] = payload["score"]
        await self.assessments.update(filters={"id": session_id}, payload=assessment_update)
        return await self.get_written_session(session_id) or self._hydrate_written_session(
            assessment_row,
            None,
        )

    async def find_question_bank(
        self,
        requested_name: str,
        normalized_name: str,
        skill_id: str | None = None,
    ) -> dict | None:
        """
        Checks if we have actual questions in the database for this subject.
        Searches by skill_id, or by matching the category column with
        requested_name or normalized_name.
        Uses wildcard matches for better discovery.
        """
        def op():
            # 1. Try by exact skill_id if provided (highest precision)
            if skill_id:
                try:
                    uuid_val = uuid.UUID(str(skill_id))
                    res = (
                        self.client.table("questions")
                        .select("skill_id")
                        .eq("skill_id", str(uuid_val))
                        .limit(1)
                        .execute()
                    )
                    if res.data:
                        return {"skill_id": skill_id}
                except (ValueError, TypeError):
                    pass
            
            # 2. Try by subject name matching in 'category' or 'subject_id' text columns
            # We use % wildcards to handle slight name variations
            # (e.g. "Machine Learning" matching "Machine Learning - Basic")
            search_pattern = f"%{requested_name}%"
            norm_pattern = f"%{normalized_name.replace('-', ' ')}%"
            
            # Build an OR query that covers both potential name formats.
            # Must double-quote strings inside .or_() so commas/parentheses aren't parsed as logic tree operators.
            or_search_pattern = f'"{search_pattern}"'
            or_norm_pattern = f'"{norm_pattern}"'
            or_query = (
                f"category.ilike.{or_search_pattern},"
                f"category.ilike.{or_norm_pattern},"
                f"subject_id.ilike.{or_search_pattern},"
                f"subject_id.ilike.{or_norm_pattern}"
            )
            
            # Check main 'questions' table
            res = (
                self.client.table("questions")
                .select("skill_id, category, subject_id")
                .or_(or_query)
                .limit(1)
                .execute()
            )
            
            if res.data:
                return {
                    "skill_id": res.data[0].get("skill_id"),
                    "category": res.data[0].get("category"),
                    "subject_id": res.data[0].get("subject_id")
                }
            
            # 3. Smart Fallback: Search question_text for the subject name
            # This handles cases where category might be generic (e.g. 'questions')
            text_res = (
                self.client.table("questions")
                .select("skill_id, category")
                .ilike("question_text", search_pattern) # no double quotes for direct ilike
                .limit(1)
                .execute()
            )
            if text_res.data:
                 return {
                    "skill_id": text_res.data[0].get("skill_id"),
                    "category": requested_name, # Map it to the requested name for consistency
                    "source": "text_match"
                }

            # 4. Fallback: check legacy 'mcq_questions' table if nothing found in main table
            try:
                legacy_res = self.client.table("mcq_questions").select("id").or_(
                    f"category.ilike.{or_search_pattern},subject.ilike.{or_search_pattern}"
                ).limit(1).execute()
                
                if legacy_res.data:
                    return {"category": requested_name, "source": "legacy"}
            except Exception:
                pass
            
            return None

        return await self.questions._run_read(op)

    async def list_unique_subjects(self) -> list[dict[str, Any]]:
        """
        Retrieves a list of unique subject categories and identifiers
        available in the questions table.
        """
        def op():
            # Current production table unique subjects
            res = (
                self.client.table("questions")
                .select("subject_id, category, skill_id")
                .execute()
            )
            data = res.data or []
            
            # Use a dict to dedup by category/title
            unique = {}
            for row in data:
                cat = (row.get("category") or "").strip()
                if not cat or len(cat) < 2:
                    continue
                
                # Normalize for deduplication
                norm = cat.lower()
                if norm not in unique:
                    unique[norm] = {
                        "category": cat,
                        "subject_id": row.get("subject_id"),
                        "skill_id": row.get("skill_id"),
                    }
            
            return list(unique.values())

        return await self.questions._run_read(op)
