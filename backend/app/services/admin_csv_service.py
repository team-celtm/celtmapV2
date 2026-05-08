from __future__ import annotations

import csv
import io
import uuid
from typing import Any

from app.repositories.assessment_repository import AssessmentRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.skill_repository import SkillRepository


class AdminCSVService:
    def __init__(
        self,
        assessment_repo: AssessmentRepository,
        skill_repo: SkillRepository,
        profile_repo: ProfileRepository,
    ) -> None:
        self.assessment_repo = assessment_repo
        self.skill_repo = skill_repo
        self.profile_repo = profile_repo

    async def ingest_questions_from_csv(
        self, file_content: bytes, role_name: str | None = None
    ) -> dict[str, Any]:
        """
        Parses a CSV file and populates the questions/options tables.
        The CSV expected format:
        Subject, Skill, Question, Option A, Option B, Option C, Option D, Correct Answer, Difficulty
        """
        text = file_content.decode("utf-8")
        f = io.StringIO(text)
        reader = csv.DictReader(f)

        stats = {
            "total_rows": 0,
            "questions_added": 0,
            "subjects_created": 0,
            "skills_created": 0,
            "errors": [],
        }

        # Cache for performance
        subject_map = {} # name -> id
        skill_map = {}   # name -> id
        processed_skills = set()

        for row in reader:
            stats["total_rows"] += 1
            try:
                subject_name = row.get("Subject", "General").strip()
                skill_name = row.get("Skill", "").strip() or subject_name
                question_text = row.get("Question", "").strip()
                options = {
                    "A": row.get("Option A", "").strip(),
                    "B": row.get("Option B", "").strip(),
                    "C": row.get("Option C", "").strip(),
                    "D": row.get("Option D", "").strip(),
                }
                correct_answer = row.get("Correct Answer", "A").strip().upper()
                difficulty = row.get("Difficulty", "Intermediate").strip().lower()

                if not question_text:
                    continue

                # 1. Resolve Subject
                if subject_name not in subject_map:
                    sj = await self.skill_repo.get_subject_by_name(subject_name.lower())
                    if not sj:
                        sj = await self.skill_repo.upsert_subject({
                            "subject_id": str(uuid.uuid4()),
                            "subject_name": subject_name,
                            "normalized_name": subject_name.lower(),
                        })
                        stats["subjects_created"] += 1
                    subject_map[subject_name] = sj["id"]

                # 2. Resolve Skill
                if skill_name not in skill_map:
                    sk = await self.skill_repo.get_skill_by_name(skill_name)
                    if not sk:
                        sk = await self.skill_repo.upsert_skill_catalog({
                            "skill_id": str(uuid.uuid4()),
                            "skill_name": skill_name,
                            "normalized_name": skill_name.lower(),
                            "category": subject_name,
                            "subject_id": subject_map[subject_name]
                        })
                        stats["skills_created"] += 1
                    skill_map[skill_name] = sk["id"]
                
                processed_skills.add(skill_name)

                # 3. Create Question
                q_payload = {
                    "question_text": question_text,
                    "question_type": "mcq",
                    "difficulty": difficulty,
                    "category": subject_name,
                    "skill_id": skill_map[skill_name],
                    "metadata": {"source": "admin_csv_ingestion"}
                }
                
                question = await self.assessment_repo.upsert_question(q_payload)
                q_id = question.get("id")

                # 4. Create Options
                if q_id:
                    option_payloads = []
                    for key, text in options.items():
                        if text:
                            option_payloads.append({
                                "question_id": q_id,
                                "option_key": key,
                                "option_text": text,
                                "is_correct": key == correct_answer
                            })
                    await self.assessment_repo.upsert_options(option_payloads)
                    stats["questions_added"] += 1

            except Exception as e:
                stats["errors"].append(f"Row {stats['total_rows']}: {str(e)}")

        # 5. Post-ingestion: Link to relevant users/roles
        if role_name and processed_skills:
            await self._auto_assign_subjects(list(processed_skills), role_name)

        return stats

    async def _auto_assign_subjects(self, skill_names: list[str], role_name: str) -> None:
        """
        Logic to ensure users whose focus_role covers these subjects see them in assessments.
        Maps the skills to the specified role.
        """
        # Ensure role exists or get it
        role = await self.skill_repo.get_role_by_name(role_name)
        if not role:
            # Create a basic role record if missing
            role = await self.skill_repo.upsert_role({
                "role_name": role_name,
                "normalized_name": role_name.lower(),
                "description": f"Automatically created role during ingestion for {role_name}",
            })
        
        role_id = role.get("id")
        
        for skill_name in skill_names:
            await self.skill_repo.upsert_role_requirement({
                "role_id": role_id,
                "role_name": role_name,
                "skill_name": skill_name,
                "importance": "core", # Default core importance
                "metadata": {"source": "admin_csv_auto_assignment"}
            })
