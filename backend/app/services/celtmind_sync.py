from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models.enums import DomainEventType
from app.repositories.assessment_repository import AssessmentRepository
from app.repositories.skill_repository import SkillRepository
from app.repositories.sync_repository import SyncRepository
from app.services.domain_event_service import DomainEventService
from app.services.rag_service import RagService
from app.utils.text import normalize_name, normalize_question_text


@dataclass(slots=True)
class IngestionSummary:
    file_name: str
    checksum: str
    inserted_questions: int = 0
    updated_questions: int = 0
    skipped_rows: int = 0
    inserted_records: int = 0
    updated_records: int = 0
    seeded_documents: int = 0
    skipped_checksum: bool = False

    def to_payload(self) -> dict[str, Any]:
        return {
            "file_name": self.file_name,
            "checksum": self.checksum,
            "inserted_questions": self.inserted_questions,
            "updated_questions": self.updated_questions,
            "skipped_rows": self.skipped_rows,
            "inserted_records": self.inserted_records,
            "updated_records": self.updated_records,
            "seeded_documents": self.seeded_documents,
            "skipped_checksum": self.skipped_checksum,
        }


class CeltmindSyncService:
    def __init__(
        self,
        *,
        sync_repository: SyncRepository,
        assessment_repository: AssessmentRepository,
        event_service: DomainEventService,
        celtmind_path: Path,
        skill_repository: SkillRepository | None = None,
        rag_service: RagService | None = None,
    ) -> None:
        self.sync_repository = sync_repository
        self.assessment_repository = assessment_repository
        self.skill_repository = skill_repository
        self.rag_service = rag_service
        self.event_service = event_service
        self.celtmind_path = celtmind_path
        self._id_maps: dict[str, dict[str, str]] = {"skills": {}, "subskills": {}, "subjects": {}}

    async def _refresh_mappings(self) -> None:
        """Loads UUID mappings from the database."""
        if self.skill_repository:
            self._id_maps = await self.skill_repository.get_all_mappings()

    async def sync(self) -> dict[str, Any]:
        started_at = datetime.now(timezone.utc).isoformat()
        run = await self.sync_repository.create_run(
            {
                "status": "running",
                "started_at": started_at,
                "summary": [],
                "error": None,
            }
        )
        try:
            file_summaries: list[IngestionSummary] = []
            file_summaries.append(await self.ingest_file(self.celtmind_path / "subjects.csv"))
            file_summaries.append(await self.ingest_file(self.celtmind_path / "skills_master.csv"))
            file_summaries.append(await self.ingest_file(self.celtmind_path / "roles.csv"))

            # Refresh mappings after primary data is ingested
            await self._refresh_mappings()

            # Root question files
            root_question_files = [
                "mcq_questions.csv",
                "situational_mcq_questions.csv",
                "descriptive_questions.csv",
                "questions.csv"
            ]
            for fname in root_question_files:
                fpath = self.celtmind_path / fname
                if fpath.exists():
                    file_summaries.append(await self.ingest_file(fpath))

            questions_dir = self.celtmind_path / "questions"
            if questions_dir.exists():
                for question_file in sorted(questions_dir.glob("*.csv")):
                    file_summaries.append(await self.ingest_file(question_file))

            summary_payload = [item.to_payload() for item in file_summaries]
            await self.sync_repository.update_run(
                run["id"],
                {
                    "status": "completed",
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "summary": summary_payload,
                    "error": None,
                },
            )
            await self.event_service.emit(
                event_type=DomainEventType.CELTMIND_SYNCED,
                aggregate_type="celtmind_ingestion_run",
                aggregate_id=run["id"],
                payload={"run_id": run["id"], "summary": summary_payload},
            )
            return {
                "id": run["id"],
                "status": "completed",
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "summary": summary_payload,
            }
        except Exception as exc:
            await self.sync_repository.update_run(
                run["id"],
                {
                    "status": "failed",
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "error": str(exc),
                },
            )
            raise

    async def ingest_file(self, csv_path: Path) -> IngestionSummary:
        checksum = self._checksum(csv_path)
        summary = IngestionSummary(file_name=csv_path.name, checksum=checksum)
        existing_registry = await self.sync_repository.get_file_registry(csv_path.name)
        if existing_registry and existing_registry.get("checksum") == checksum:
            summary.skipped_checksum = True
            return summary

        rows = self._read_csv_rows(csv_path)
        lower_name = csv_path.name.lower()

        if lower_name == "subjects.csv":
            await self._ingest_subject_rows(rows, summary, csv_path.name)
            category = "subjects"
        elif lower_name == "skills_master.csv":
            await self._ingest_skill_rows(rows, summary, csv_path.name)
            category = "skills"
        elif lower_name == "roles.csv":
            await self._ingest_role_rows(rows, summary, csv_path.name)
            category = "roles"
        else:
            await self._ingest_question_rows(rows, summary, csv_path.stem)
            category = "questions"

        await self.sync_repository.upsert_file_registry(
            {
                "file_name": csv_path.name,
                "checksum": checksum,
                "category": category,
                "last_ingested_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        return summary

    async def _ingest_subject_rows(
        self,
        rows: list[dict[str, str]],
        summary: IngestionSummary,
        file_name: str,
    ) -> None:
        if self.skill_repository is None:
            summary.skipped_rows = len(rows)
            return

        rag_documents: dict[str, dict[str, Any]] = {}
        for row in rows:
            subject_id = (row.get("subject_id") or "").strip()
            subject_name = (row.get("subject_name") or "").strip()
            if not subject_id or not subject_name:
                summary.skipped_rows += 1
                continue

            existing = await self.skill_repository.get_subject_by_source_id(subject_id)
            if existing is None:
                existing = await self.skill_repository.get_subject_by_name(
                    normalize_name(subject_name)
                )

            payload = {
                "subject_id": subject_id,
                "subject_name": subject_name,
                "normalized_name": normalize_name(subject_name),
                "track": (row.get("track") or "").strip() or None,
                "description": (row.get("subject_definition") or "").strip() or None,
                "domain_group": (row.get("domain_group") or "").strip() or None,
                "industry_relevance": (row.get("industry_relevance") or "").strip() or None,
                "metadata": {"source_file": file_name},
                "is_active": True,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            await self.skill_repository.upsert_subject(payload)
            if existing is None:
                summary.inserted_records += 1
            else:
                summary.updated_records += 1

            source_ref = f"subject:{subject_id}"
            rag_documents[source_ref] = {
                "source_ref": source_ref,
                "title": subject_name,
                "skill_id": subject_id,
                "content": "\n".join(
                    [
                        f"Subject: {subject_name}",
                        f"Track: {row.get('track') or 'General'}",
                        f"Definition: {row.get('subject_definition') or ''}",
                        f"Domain Group: {row.get('domain_group') or ''}",
                        f"Industry Relevance: {row.get('industry_relevance') or ''}",
                    ]
                ).strip(),
                "metadata": {
                    "catalog_type": "subject",
                    "source_file": file_name,
                    "normalized_name": normalize_name(subject_name),
                },
            }

        summary.seeded_documents += await self._seed_global_rag(
            source_type="celtmind.subject",
            documents=rag_documents.values(),
        )

    async def _ingest_skill_rows(
        self,
        rows: list[dict[str, str]],
        summary: IngestionSummary,
        file_name: str,
    ) -> None:
        if self.skill_repository is None:
            summary.skipped_rows = len(rows)
            return

        rag_documents: dict[str, dict[str, Any]] = {}
        for row in rows:
            skill_id = (row.get("skill_id") or "").strip()
            skill_name = (row.get("skill_name") or "").strip()
            subject_id = (row.get("subject_id") or "").strip()
            subskill_id = (row.get("subskill_id") or "").strip()
            subskill_name = (row.get("subskill_name") or "").strip()
            if not skill_id or not skill_name or not subject_id:
                summary.skipped_rows += 1
                continue

            subject = await self.skill_repository.get_subject_by_source_id(subject_id)
            existing_skill = await self.skill_repository.get_skill_by_source_id(skill_id)
            if existing_skill is None:
                existing_skill = await self.skill_repository.get_skill_by_name(
                    normalize_name(skill_name)
                )

            skill_payload = {
                "skill_id": skill_id,
                "subject_ref_id": subject["id"] if subject else None,
                "name": skill_name,           # legacy NOT NULL column
                "skill_name": skill_name,
                "normalized_name": normalize_name(skill_name),
                "description": (row.get("skill_definition") or "").strip() or None,
                "industry_usage": (row.get("industry_usage") or "").strip() or None,
                "hidden_skills_supported": self._split_values(
                    row.get("hidden_skills_supported"),
                    separators="|",
                ),
                "metadata": {
                    "source_file": file_name,
                    "subject_id": subject_id,
                },
                "is_active": True,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            skill_record = await self.skill_repository.upsert_skill_catalog(skill_payload)
            if existing_skill is None:
                summary.inserted_records += 1
            else:
                summary.updated_records += 1

            if subskill_id and subskill_name:
                existing_subskill = await self.skill_repository.get_subskill_by_source_id(
                    subskill_id
                )
                if existing_subskill is None:
                    existing_subskill = await self.skill_repository.get_subskill_by_name(
                        skill_record["id"],
                        normalize_name(subskill_name),
                    )
                await self.skill_repository.upsert_subskill(
                    {
                        "subskill_id": subskill_id,
                        "skill_ref_id": skill_record["id"],
                        "name": subskill_name,           # legacy NOT NULL column
                        "subskill_name": subskill_name,
                        "normalized_name": normalize_name(subskill_name),
                        "description": (row.get("subskill_definition") or "").strip() or None,
                        "metadata": {"source_file": file_name, "skill_id": skill_id},
                        "is_active": True,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
                if existing_subskill is None:
                    summary.inserted_records += 1
                else:
                    summary.updated_records += 1

                source_ref = f"subskill:{subskill_id}"
                rag_documents[source_ref] = {
                    "source_ref": source_ref,
                    "title": subskill_name,
                    "skill_id": skill_id,
                    "subskill_id": subskill_id,
                    "content": "\n".join(
                        [
                            f"Subskill: {subskill_name}",
                            f"Parent Skill: {skill_name}",
                            f"Definition: {row.get('subskill_definition') or ''}",
                        ]
                    ).strip(),
                    "metadata": {
                        "catalog_type": "subskill",
                        "source_file": file_name,
                        "subject_id": subject_id,
                    },
                }

            source_ref = f"skill:{skill_id}"
            rag_documents[source_ref] = {
                "source_ref": source_ref,
                "title": skill_name,
                "skill_id": skill_id,
                "subskill_id": subskill_id or None,
                "content": "\n".join(
                    [
                        f"Skill: {skill_name}",
                        f"Subject ID: {subject_id}",
                        f"Definition: {row.get('skill_definition') or ''}",
                        f"Industry Usage: {row.get('industry_usage') or ''}",
                        f"Hidden Skills Supported: {row.get('hidden_skills_supported') or ''}",
                    ]
                ).strip(),
                "metadata": {
                    "catalog_type": "skill",
                    "source_file": file_name,
                    "subject_id": subject_id,
                },
            }

        summary.seeded_documents += await self._seed_global_rag(
            source_type="celtmind.skill",
            documents=rag_documents.values(),
        )

    async def _ingest_role_rows(
        self,
        rows: list[dict[str, str]],
        summary: IngestionSummary,
        file_name: str,
    ) -> None:
        if self.skill_repository is None:
            summary.skipped_rows = len(rows)
            return

        rag_documents: dict[str, dict[str, Any]] = {}
        for row in rows:
            role_id = (row.get("role_id") or "").strip()
            role_name = (row.get("role_name") or "").strip()
            if not role_name:
                summary.skipped_rows += 1
                continue

            existing_role = await self.skill_repository.roles.get_one(
                filters={"normalized_name": normalize_name(role_name)}
            )
            await self.skill_repository.upsert_role(
                {
                    "role_id": role_id or None,
                    "role_name": role_name,
                    "normalized_name": normalize_name(role_name),
                    "role_category": (row.get("role_category") or "").strip() or None,
                    "description": (row.get("role_definition") or "").strip() or None,
                    "target_industries": self._split_values(row.get("target_industries")),
                    "required_subjects": self._split_values(row.get("required_subjects")),
                    "core_skills": self._split_values(row.get("core_skills")),
                    "metadata": {"source_file": file_name},
                    "is_active": True,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            if existing_role is None:
                summary.inserted_records += 1
            else:
                summary.updated_records += 1

            required_subjects = self._split_values(row.get("required_subjects"))
            for subject_name in required_subjects:
                normalized_subject = normalize_name(subject_name)
                subject = await self.skill_repository.get_subject_by_name(normalized_subject)
                subject_skills: list[dict[str, Any]] = []
                if subject is not None:
                    subject_skills = await self.skill_repository.skills.list(
                        filters={"subject_ref_id": subject["id"], "is_active": True},
                        limit=500,
                    )

                if subject_skills:
                    per_skill_weight = round(1 / len(subject_skills), 4)
                    for subject_skill in subject_skills:
                        await self.skill_repository.upsert_role_requirement(
                            {
                                "role_name": role_name,
                                "skill_name": subject_skill["skill_name"],
                                "weight": per_skill_weight,
                                "metadata": {
                                    "source": "required_subject",
                                    "subject_name": subject_name,
                                    "source_file": file_name,
                                },
                            }
                        )
                else:
                    await self.skill_repository.upsert_role_requirement(
                        {
                            "role_name": role_name,
                            "skill_name": subject_name,
                            "weight": 1,
                            "metadata": {
                                "source": "required_subject",
                                "source_file": file_name,
                            },
                        }
                    )

            for core_skill in self._split_values(row.get("core_skills")):
                await self.skill_repository.upsert_role_requirement(
                    {
                        "role_name": role_name,
                        "skill_name": core_skill,
                        "weight": 0.5,
                        "metadata": {
                            "source": "core_skill",
                            "source_file": file_name,
                        },
                    }
                )

            source_ref = f"role:{role_id or normalize_name(role_name)}"
            rag_documents[source_ref] = {
                "source_ref": source_ref,
                "title": role_name,
                "content": "\n".join(
                    [
                        f"Role: {role_name}",
                        f"Category: {row.get('role_category') or ''}",
                        f"Definition: {row.get('role_definition') or ''}",
                        f"Target Industries: {row.get('target_industries') or ''}",
                        f"Required Subjects: {row.get('required_subjects') or ''}",
                        f"Core Skills: {row.get('core_skills') or ''}",
                    ]
                ).strip(),
                "metadata": {
                    "catalog_type": "role",
                    "source_file": file_name,
                    "role_id": role_id,
                },
            }

        summary.seeded_documents += await self._seed_global_rag(
            source_type="celtmind.role",
            documents=rag_documents.values(),
        )

    async def _ingest_question_rows(
        self,
        rows: list[dict[str, str]],
        summary: IngestionSummary,
        category_fallback: str,
    ) -> None:
        rag_documents: dict[str, dict[str, Any]] = {}
        for index, row in enumerate(rows, start=1):
            question_text = normalize_question_text(
                row.get("question") or row.get("question_text") or ""
            )
            if not question_text:
                summary.skipped_rows += 1
                continue

            question_type = (row.get("question_type") or "mcq").strip().lower()
            if question_type not in ["mcq", "situational"]:
                question_type = "descriptive"
            skill_source_id = (row.get("skill_id") or "").strip()
            subskill_source_id = (row.get("subskill_id") or "").strip()
            subject_source_id = (row.get("subject_id") or "").strip()

            # Map source IDs to actual UUIDs
            skill_uuid = self._id_maps["skills"].get(skill_source_id)
            subskill_uuid = self._id_maps["subskills"].get(subskill_source_id)

            source_question_id = (row.get("question_id") or str(index)).strip()

            existing_question = await self.assessment_repository.questions.get_one(
                filters={
                    "source_question_id": source_question_id,
                }
            )

            category = (
                (row.get("skill_name") or "").strip()
                or (row.get("category") or "").strip()
                or category_fallback.replace("-", " ").replace("_", " ").strip().lower()
            )
            question_payload = {
                "source_question_id": source_question_id,
                "subject_id": subject_source_id,
                "subject_name": (row.get("subject_name") or "").strip() or None,
                "skill_id": skill_uuid, # ACTUAL UUID
                "source_skill_id": skill_source_id, # Numeric ID for reference
                "skill_name": (row.get("skill_name") or "").strip() or None,
                "subskill_id": subskill_uuid, # ACTUAL UUID
                "source_subskill_id": subskill_source_id, # Numeric ID for reference
                "subskill_name": (row.get("subskill_name") or "").strip() or None,
                "role_ids": self._split_values(row.get("role_ids"), separators="|"),
                "question_text": question_text,
                "question_text_normalized": question_text.lower(),
                "category": category,
                "difficulty": (row.get("difficulty") or "unassigned").strip().lower(),
                "question_type": question_type,
                "sample_answer": (row.get("sample_answer") or "").strip() or None,
                "explanation": (row.get("explanation") or "").strip() or None,
                "expected_concepts": self._split_values(
                    row.get("expected_concepts"),
                    separators="|,;",
                ),
                "hidden_skills_targeted": self._split_values(
                    row.get("hidden_skills_targeted"),
                    separators="|,;",
                ),
                "evaluation_mode": (row.get("evaluation_mode") or "").strip() or None,
                "rag_tags": self._split_values(row.get("rag_tags"), separators="|,;"),
                "metadata": {
                    "source_file": category_fallback,
                    "raw_category": row.get("category"),
                },
                "is_active": True,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

            question_record = await self.assessment_repository.upsert_question(question_payload)
            if existing_question is None:
                summary.inserted_questions += 1
                summary.inserted_records += 1
            else:
                summary.updated_questions += 1
                summary.updated_records += 1

            options_payload = self._build_option_payloads(row, question_record["id"])
            if options_payload:
                await self.assessment_repository.upsert_options(options_payload)

            source_question_id = question_payload["source_question_id"]
            source_ref = f"question:{source_question_id}"
            rag_documents[source_ref] = {
                "source_ref": source_ref,
                "title": question_text[:120],
                "skill_id": skill_uuid or None,
                "subskill_id": subskill_uuid or None,
                "content": "\n".join(
                    [
                        f"Question Type: {question_type}",
                        f"Category: {category}",
                        f"Difficulty: {question_payload['difficulty']}",
                        f"Question: {question_text}",
                        f"Explanation: {row.get('explanation') or ''}",
                        f"Sample Answer: {row.get('sample_answer') or ''}",
                        f"Expected Concepts: {row.get('expected_concepts') or ''}",
                    ]
                ).strip(),
                "metadata": {
                    "catalog_type": "question",
                    "category": category,
                    "difficulty": question_payload["difficulty"],
                    "source_file": category_fallback,
                },
            }

        summary.seeded_documents += await self._seed_global_rag(
            source_type="celtmind.question",
            documents=rag_documents.values(),
        )

    async def _seed_global_rag(
        self,
        *,
        source_type: str,
        documents: Any,
    ) -> int:
        if self.rag_service is None:
            return 0
        payload = list(documents)
        if not payload:
            return 0
        stored = await self.rag_service.upsert_documents(
            scope="global",
            source_type=source_type,
            documents=payload,
        )
        return len(stored)

    def _read_csv_rows(self, csv_path: Path) -> list[dict[str, str]]:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            return [{key: (value or "") for key, value in row.items()} for row in reader]

    def _checksum(self, csv_path: Path) -> str:
        return hashlib.sha256(csv_path.read_bytes()).hexdigest()

    def _split_values(self, raw_value: str | None, separators: str = ";|,") -> list[str]:
        if not raw_value:
            return []
        values = [raw_value]
        for separator in separators:
            next_values: list[str] = []
            for value in values:
                next_values.extend(value.split(separator))
            values = next_values
        return [value.strip() for value in values if value.strip()]

    def _build_option_payloads(self, row: dict[str, str], question_id: str) -> list[dict[str, Any]]:
        option_candidates = [
            ("A", row.get("option_a")),
            ("B", row.get("option_b")),
            ("C", row.get("option_c")),
            ("D", row.get("option_d")),
            ("E", row.get("option_e")),
            ("1", row.get("option1")),
            ("2", row.get("option2")),
            ("3", row.get("option3")),
            ("4", row.get("option4")),
            ("5", row.get("option5")),
        ]
        options = [
            (key, (value or "").strip())
            for key, value in option_candidates
            if (value or "").strip()
        ]
        correct_answer = (
            (row.get("correct_answer") or row.get("correct_option") or "").strip().upper()
        )
        normalized_correct = correct_answer
        if normalized_correct.isdigit():
            normalized_correct = str(int(normalized_correct))

        payloads: list[dict[str, Any]] = []
        for option_key, option_text in options:
            payloads.append(
                {
                    "question_id": question_id,
                    "option_key": option_key,
                    "option_text": option_text,
                    "is_correct": option_key.upper() == normalized_correct,
                }
            )
        return payloads
