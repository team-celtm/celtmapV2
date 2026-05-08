from __future__ import annotations

from supabase import Client

from app.models.enums import HiddenSkillStatus
from app.repositories.base import SupabaseTableRepository


class SkillRepository:
    def __init__(self, client: Client) -> None:
        self.client = client
        self.subjects = SupabaseTableRepository(client, "subjects")
        self.skills = SupabaseTableRepository(client, "skills")
        self.subskills = SupabaseTableRepository(client, "subskills")
        self.user_skills = SupabaseTableRepository(client, "user_skills")
        self.user_hidden_skills = SupabaseTableRepository(client, "user_hidden_skills")
        self.roles = SupabaseTableRepository(client, "roles")
        self.role_requirements = SupabaseTableRepository(client, "role_requirements")
        self.skill_requests = SupabaseTableRepository(client, "skill_requests")

    # --- Subject Management ---

    async def get_subject_by_source_id(self, subject_id: str) -> dict | None:
        return await self.subjects.get_one(filters={"subject_id": subject_id})

    async def get_subject_by_name(self, normalized_name: str) -> dict | None:
        return await self.subjects.get_one(filters={"normalized_name": normalized_name})

    async def upsert_subject(self, payload: dict) -> dict:
        rows = await self.subjects.upsert(payload, on_conflict="subject_id")
        return rows[0] if rows else payload

    # --- Skill Management ---

    async def get_skill_by_source_id(self, skill_id: str) -> dict | None:
        return await self.skills.get_one(filters={"skill_id": skill_id})

    async def get_skill_by_name(self, name: str) -> dict | None:
        # Check both the 'name' (legacy) and 'skill_name' (production)
        res = await self.skills.get_one(filters={"skill_name": name})
        if not res:
            res = await self.skills.get_one(filters={"normalized_name": name})
        return res

    async def upsert_skill_catalog(self, payload: dict) -> dict:
        # Production ingestion uses 'skill_id' for uniqueness
        rows = await self.skills.upsert(payload, on_conflict="skill_id")
        return rows[0] if rows else payload

    async def get_all_mappings(self) -> dict[str, dict[str, str]]:
        """Returns maps of skill_id -> id and subskill_id -> id for all records."""
        skills_rows = await self.skills.list(limit=1000)
        subskills_rows = await self.subskills.list(limit=5000)
        
        return {
            "skills": {s["skill_id"]: s["id"] for s in skills_rows if s.get("skill_id") and s.get("id")},
            "subskills": {ss["subskill_id"]: ss["id"] for ss in subskills_rows if ss.get("subskill_id") and ss.get("id")},
            "subjects": {sj["subject_id"]: sj["id"] for sj in await self.subjects.list(limit=100) if sj.get("subject_id") and sj.get("id")}
        }

    async def get_subskill_by_source_id(self, subskill_id: str) -> dict | None:
        return await self.subskills.get_one(filters={"subskill_id": subskill_id})

    async def upsert_subskill_catalog(self, payload: dict) -> dict:
        rows = await self.subskills.upsert(payload, on_conflict="subskill_id")
        return rows[0] if rows else payload

    async def upsert_skill(self, payload: dict) -> dict:
        # Legacy/UI sync uses name
        rows = await self.skills.upsert(payload, on_conflict="skill_name")
        return rows[0] if rows else payload

    # --- Subskill Management ---

    async def get_subskill_by_source_id(self, subskill_id: str) -> dict | None:
        return await self.subskills.get_one(filters={"subskill_id": subskill_id})

    async def get_subskill_by_name(self, skill_ref_id: str, normalized_name: str) -> dict | None:
        return await self.subskills.get_one(
            filters={"skill_ref_id": skill_ref_id, "normalized_name": normalized_name}
        )

    async def upsert_subskill(self, payload: dict) -> dict:
        rows = await self.subskills.upsert(payload, on_conflict="subskill_id")
        return rows[0] if rows else payload

    # --- Role Management ---

    async def upsert_role(self, payload: dict) -> dict:
        rows = await self.roles.upsert(payload, on_conflict="normalized_name")
        return rows[0] if rows else payload

    async def upsert_role_requirement(self, payload: dict) -> dict:
        # Uniqueness on role_name and skill_name
        rows = await self.role_requirements.upsert(
            payload, on_conflict="role_name,skill_name"
        )
        return rows[0] if rows else payload

    async def list_roles(self) -> list[dict]:
        return await self.roles.list()

    async def get_role_by_name(self, role_name: str) -> dict | None:
        return await self.roles.get_one(filters={"role_name": role_name})

    # --- User Skill Management ---

    async def list_user_skills(self, user_id: str) -> list[dict]:
        def op():
            # Join with skills table to get names and categories
            # Note: We use !skill_id to specify the join column if ambiguous
            result = self.client.table("user_skills") \
                .select("*, skills:skills!skill_id(skill_name, category)") \
                .eq("user_id", user_id) \
                .execute()
            return result.data or []
        
        try:
            result = await self.user_skills._run_read(op)
            rows = result if isinstance(result, list) else []
            flattened = []
            for row in rows:
                skill_info = row.get("skills")
                item = {**row}
                if isinstance(skill_info, dict):
                    item["skill_name"] = skill_info.get("skill_name")
                    item["category"] = skill_info.get("category")
                
                # Fallback for display if join failed (e.g. unregistered skill)
                if not item.get("skill_name"):
                    raw_id = str(item.get("skill_id") or "")
                    item["skill_name"] = raw_id.replace("-", " ").title()
                    item["category"] = item.get("category") or "General"
                
                item["verified_score"] = float(item.get("proficiency_score", 0.0))
                
                if "skills" in item:
                    del item["skills"]
                flattened.append(item)
            return flattened
        except Exception as e:
            print(f"[SkillRepository] list_user_skills join error: {e}")
            # Fallback to simple select if join logic fails
            raw_res = await self.user_skills.list(filters={"user_id": user_id})
            return raw_res

    async def upsert_user_skill(self, payload: dict) -> dict:
        sanitized_payload = {
            key: value
            for key, value in payload.items()
            if key
            in {
                "user_id",
                "skill_id",
                "proficiency_score",
                "assessment_score",
                "written_score",
                "interview_score",
                "artifact_score",
                "metadata",
                "created_at",
                "updated_at",
                "last_synced_at",
            }
        }
        rows = await self.user_skills.upsert(sanitized_payload, on_conflict="user_id,skill_id")
        return rows[0] if rows else payload

    # ... remaining methods (skill requests etc) kept logic same
    async def list_skill_requests(self, user_id: str) -> list[dict]:
        return await self.skill_requests.list(filters={"user_id": user_id}, limit=100)

    async def get_skill_request(self, request_id: str) -> dict | None:
        return await self.skill_requests.get_by_id(request_id)

    async def upsert_skill_request(self, payload: dict) -> dict:
        if "id" in payload:
            rows = await self.skill_requests.update(payload["id"], payload)
        else:
            rows = await self.skill_requests.insert(payload)
        return rows[0] if rows else payload

    async def upsert_hidden_candidate(self, payload: dict) -> dict:
        return await self.user_hidden_skills.insert(payload)

    async def list_hidden_candidates(self, user_id: str) -> list[dict]:
        return await self.user_hidden_skills.list(filters={"user_id": user_id}, limit=200)

    async def list_role_requirements(
        self,
        *,
        role_id: str | None = None,
        role_name: str | None = None,
    ) -> list[dict]:
        """
        Fetches requirements for a role.
        Supports dual-lookup to handle cases where role_id might be missing in some records.
        """
        def op():
            query = self.client.table("role_requirements").select(
                "role_id, role_name, skill_name, weight"
            ).limit(50)
            if role_id and role_name:
                query = query.or_(f"role_id.eq.{role_id},role_name.ilike.{role_name}")
            elif role_id:
                query = query.eq("role_id", role_id)
            elif role_name:
                query = query.ilike("role_name", role_name)
            return query.execute()

        result = await self.role_requirements._run_read(op)
        return result if isinstance(result, list) else []
