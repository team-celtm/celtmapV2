from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from app.integrations.cache import CacheClient
from app.repositories.learning_repository import LearningRepository
from app.services.mcq_service import MCQService
from app.services.rag_service import RagService
from app.services.skill_service import SkillService
from app.utils.text import normalize_name

log = logging.getLogger(__name__)

# ── tunables ────────────────────────────────────────────────────────────────
_CACHE_TTL = 60 * 8          # 8-minute learning-path cache
_MAX_CONCURRENT_MODULES = 3  # semaphore cap for parallel module enrichment
# ────────────────────────────────────────────────────────────────────────────

class LearningService:
    def __init__(
        self,
        repository: LearningRepository,
        profile_repository,
        skill_service: SkillService,
        rag_service: RagService,
        mcq_service: MCQService,
        cache: CacheClient | None = None,
    ) -> None:
        self.repository = repository
        self.profile_repository = profile_repository
        self.skill_service = skill_service
        self.rag_service = rag_service
        self.mcq_service = mcq_service
        self.cache = cache

    # ── public API ──────────────────────────────────────────────────────────

    async def get_learning_path(self, user_id: str, role_name: str) -> dict:
        cache_key = f"learning_path:{user_id}:{normalize_name(role_name)}"

        # 1. Try cache first
        if self.cache:
            cached = self.cache.get_json(cache_key)
            if cached is not None:
                log.info("learning_path cache HIT for %s / %s", user_id, role_name)
                return cached

        result = await self._compute_learning_path(user_id, role_name)

        # 2. Store in cache (fire-and-forget — never block the response)
        # Only cache if modules were successfully built
        if self.cache and result and result.get("modules"):
            try:
                self.cache.set_json(cache_key, result, _CACHE_TTL)
            except Exception:
                pass

        return result

    async def get_learning_resources(
        self, skill_name: str, user_id: str | None = None
    ) -> list[dict]:
        return await self.rag_service.fetch_learning_resources(skill_name, user_id=user_id)

    # ── internals ───────────────────────────────────────────────────────────

    async def _compute_learning_path(self, user_id: str, role_name: str) -> dict:
        existing_path = await self.repository.get_latest_path(user_id, role_name)

        if existing_path:
            return await self._enrich_existing_path(user_id, role_name, existing_path)

        return await self._build_new_path(user_id, role_name)

    # ── existing-path branch ────────────────────────────────────────────────

    async def _enrich_existing_path(
        self, user_id: str, role_name: str, existing_path: dict
    ) -> dict:
        modules = await self.repository.list_path_modules(existing_path["id"])

        # Fetch user_skills, profile, and gaps concurrently
        user_skills, profile, gaps = await asyncio.gather(
            self.skill_service.list_user_skills(user_id),
            self.profile_repository.get_profile(user_id),
            self.skill_service.get_skill_gaps(user_id, role_name=role_name),
        )

        shared_context = {
            "user_skills": user_skills,
            "profile": profile,
            "gaps": gaps,
            "path_modules": modules,  # avoids find_question_bank per module
        }

        enriched_modules = await self._enrich_modules_for_availability(
            user_id, modules, shared_context
        )
        return {"role_name": role_name, "modules": enriched_modules}

    async def _enrich_modules_for_availability(
        self, user_id: str, modules: list[dict], shared_context: dict
    ) -> list[dict]:
        sem = asyncio.Semaphore(_MAX_CONCURRENT_MODULES)

        async def _check_mod(mod: dict) -> dict:
            async with sem:
                detail = await self.mcq_service.get_subject_detail(
                    user_id=user_id,
                    subject_key=normalize_name(mod["skill_name"]),
                    context=shared_context,
                )
                mod["is_available"] = (detail or {}).get("is_available", False)
                return mod

        return list(await asyncio.gather(*(_check_mod(m) for m in modules)))

    # ── new-path branch ─────────────────────────────────────────────────────

    async def _build_new_path(self, user_id: str, role_name: str) -> dict:
        gaps = await self.skill_service.get_skill_gaps(user_id, role_name=role_name)

        if not gaps:
            gaps = await self._generate_gaps_from_llm(role_name)

        selected_gaps = (gaps or [])[:6]

        path = await self.repository.create_path(
            {
                "user_id": user_id,
                "role_name": role_name,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        # Fetch user_skills and profile concurrently
        user_skills, profile = await asyncio.gather(
            self.skill_service.list_user_skills(user_id),
            self.profile_repository.get_profile(user_id),
        )

        # Modules are empty for a brand-new path, so find_question_bank WILL run,
        # but we still pass the list so the context key exists.
        shared_context = {
            "user_skills": user_skills,
            "profile": profile,
            "gaps": gaps or [],
            "path_modules": [],
        }

        response_modules = await self._enrich_modules_with_resources(
            user_id, path, selected_gaps, shared_context
        )

        # Persist in background — don't block the response
        asyncio.ensure_future(
            _safe_upsert_modules(self.repository, response_modules)
        )

        return {"role_name": role_name, "modules": response_modules}

    async def _enrich_modules_with_resources(
        self,
        user_id: str,
        path: dict,
        selected_gaps: list[dict],
        shared_context: dict,
    ) -> list[dict]:
        sem = asyncio.Semaphore(_MAX_CONCURRENT_MODULES)

        async def _enrich_module(week: int, gap: dict) -> dict:
            async with sem:
                resources, detail = await asyncio.gather(
                    self.rag_service.fetch_learning_resources(
                        gap["skill_name"], user_id=user_id
                    ),
                    self.mcq_service.get_subject_detail(
                        user_id=user_id,
                        subject_key=normalize_name(gap["skill_name"]),
                        context=shared_context,
                    ),
                )
            return {
                "path_id": path["id"],
                "title": f"Week {week} - {gap['skill_name']}",
                "week": week,
                "skill_name": gap["skill_name"],
                "gap_severity": gap.get("gap_severity", 0.5),
                "resources": resources or [],
                "is_available": (detail or {}).get("is_available", False),
            }

        return list(
            await asyncio.gather(
                *(
                    _enrich_module(week, gap)
                    for week, gap in enumerate(selected_gaps, start=1)
                )
            )
        )

    async def _generate_gaps_from_llm(self, role_name: str) -> list[dict]:
        prompt = (
            f"We have a custom role '{role_name}'. Provide exactly 6 core skills or subjects that a "
            "person must learn to achieve this role. Return as JSON object with a single key 'skills' "
            "containing an array of objects. Each object must have keys 'skill_name' (string), "
            "'target_weight' (float between 0.6 and 1.0) and 'gap_severity' (float between 0.6 and 1.0)."
        )
        try:
            # We add a generous timeout to the LLM call just to ensure it doesn't hang indefinitely,
            # but allow it to run for long enough (30s) to not lose data under normal load.
            response = await asyncio.wait_for(
                self.rag_service.llm_provider.chat_json(
                    messages=[{"role": "user", "content": prompt}]
                ),
                timeout=30.0
            )
            data = (response or {}).get("data", {})
            generated = data.get("skills") if isinstance(data, dict) else data
            if isinstance(generated, list):
                return [
                    {
                        "skill_name": s.get("skill_name", "Core Subject"),
                        "target_weight": float(s.get("target_weight", 0.8)),
                        "user_score": 0.0,
                        "gap_severity": float(s.get("gap_severity", 0.8)),
                    }
                    for s in generated
                ]
        except Exception as exc:
            log.error("LLM gap generation failed: %s", exc)

        # Static fallback so the path is never empty
        return [
            {"skill_name": f"{role_name} Fundamentals", "target_weight": 1.0, "user_score": 0.0, "gap_severity": 1.0},
            {"skill_name": f"Advanced {role_name}", "target_weight": 0.9, "user_score": 0.0, "gap_severity": 0.9},
            {"skill_name": f"{role_name} Best Practices", "target_weight": 0.8, "user_score": 0.0, "gap_severity": 0.8},
            {"skill_name": f"{role_name} Tools & Ecosystem", "target_weight": 0.7, "user_score": 0.0, "gap_severity": 0.7},
            {"skill_name": f"Applied {role_name}", "target_weight": 0.8, "user_score": 0.0, "gap_severity": 0.8},
            {"skill_name": f"{role_name} Projects", "target_weight": 0.7, "user_score": 0.0, "gap_severity": 0.7},
        ]


async def _safe_upsert_modules(repository, modules: list[dict]) -> None:
    """Fire-and-forget upsert — errors are logged, never raised."""
    try:
        await repository.upsert_modules(modules)
    except Exception as exc:
        log.warning("Background upsert_modules failed: %s", exc)

