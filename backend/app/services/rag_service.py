from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from time import perf_counter
from typing import Any
from urllib.parse import quote_plus

from app.config.settings import Settings
from app.integrations.cache import CacheClient
from app.integrations.llm import OpenAIProvider
from app.repositories.profile_repository import ProfileRepository
from app.repositories.rag_repository import RagRepository
from app.repositories.report_repository import ReportRepository
from app.services.ops_service import OpsService
from app.utils.text import normalize_free_text, normalize_name


class RagService:
    def __init__(
        self,
        *,
        settings: Settings,
        cache: CacheClient,
        repository: RagRepository,
        report_repository: ReportRepository,
        profile_repository: ProfileRepository,
        llm_provider: OpenAIProvider,
        ops_service: OpsService,
    ) -> None:
        self.settings = settings
        self.cache = cache
        self.repository = repository
        self.report_repository = report_repository
        self.profile_repository = profile_repository
        self.llm_provider = llm_provider
        self.ops_service = ops_service

    async def semantic_search(
        self,
        *,
        query: str,
        top_k: int | None = None,
        user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        normalized_query = normalize_free_text(query)
        safe_top_k = min(top_k or self.settings.rag_top_k, self.settings.rag_top_k)
        cache_key = (
            f"rag:search:{user_id or 'global'}:{safe_top_k}:{normalize_name(normalized_query)}"
        )
        cached = self.cache.get_json(cache_key)
        if cached is not None:
            return cached

        started_at = perf_counter()
        embedding_result = await self.llm_provider.embed_texts([normalized_query])
        
        # Call the new search_knowledge method
        raw_results = await self.repository.search_knowledge(
            query_embedding=embedding_result["embeddings"][0],
            user_id=user_id,
            limit=safe_top_k,
        )
        
        # Map content_chunk -> content for service compatibility
        search_results = [
            {**item, "content": item.get("content_chunk", "")}
            for item in raw_results
        ]
        
        latency_ms = int((perf_counter() - started_at) * 1000)
        self.cache.set_json(cache_key, search_results, self.settings.rag_cache_ttl_seconds)
        
        await self.ops_service.log_ai_call(
            user_id=user_id,
            provider="openai",
            model=embedding_result["model"],
            operation="rag.semantic_search",
            prompt_hash=_hash_text(normalized_query),
            cache_hit=False,
            latency_ms=latency_ms,
            input_tokens=embedding_result["usage"]["input_tokens"],
            output_tokens=0,
            status="success",
            metadata={"top_k": safe_top_k},
        )
        await self._touch_documents(search_results)
        return search_results

    async def fetch_learning_resources(
        self,
        skill_name: str,
        user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        try:
            documents = await self.semantic_search(query=skill_name, top_k=4, user_id=user_id)
        except Exception:
            documents = []
        resources = [
            {
                "title": item.get("title") or item.get("source_ref") or "Learning resource",
                "content": item["content"],
                "resource_type": item.get("source_type", "knowledge"),
                "skill_name": skill_name,
                "resource_url": self._resolve_learning_resource_url(item, skill_name),
            }
            for item in documents
        ]
        if len(resources) < 4:
            resources.extend(
                self._build_fallback_learning_resources(skill_name)[len(resources) : 4]
            )
        return resources

    async def upsert_documents(
        self,
        *,
        scope: str,
        source_type: str,
        documents: list[dict[str, Any]],
        user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if not documents:
            return []
        
        now = datetime.now(timezone.utc).isoformat()
        
        # 1. Gather all chunks
        all_chunks: list[str] = []
        doc_chunk_map: list[tuple[dict[str, Any], int, str, int]] = [] # item, idx, chunk_text, total_chunks
        
        for item in documents:
            content = normalize_free_text(item["content"])
            chunks = self._chunk_text(content)
            for idx, chunk_text in enumerate(chunks):
                all_chunks.append(chunk_text)
                doc_chunk_map.append((item, idx, chunk_text, len(chunks)))

        # 2. Embed in batches (max 100 chunks per request to stay safe)
        all_embeddings: list[Any] = []
        batch_size = 100
        for i in range(0, len(all_chunks), batch_size):
            batch = all_chunks[i:i + batch_size]
            result = await self.llm_provider.embed_texts(batch)
            all_embeddings.extend(result["embeddings"])

        # 3. Build payloads
        payloads: list[dict[str, Any]] = []
        for (item, idx, chunk_text, total_chunks), embedding in zip(doc_chunk_map, all_embeddings, strict=False):
            chunk_ref = item.get("source_ref", "")
            if idx > 0:
                chunk_ref = f"{chunk_ref}#chunk-{idx}"
                
            dedupe_hash = _hash_text(
                "|".join(
                    [
                        scope,
                        user_id or "",
                        source_type,
                        chunk_ref,
                        str(item.get("skill_id") or ""),
                        str(item.get("subskill_id") or ""),
                        chunk_text,
                    ]
                )
            )
            payloads.append(
                {
                    "scope": scope,
                    "source_type": source_type,
                    "source_ref": chunk_ref,
                    "skill_id": item.get("skill_id"),
                    "subskill_id": item.get("subskill_id"),
                    "title": item.get("title"),
                    "user_id": user_id,
                    "artifact_id": item.get("artifact_id"),
                    "content": chunk_text,
                    "content_chunk": chunk_text,
                    "embedding": embedding,
                    "metadata": {
                        **item.get("metadata", {}),
                        "chunk_index": idx,
                        "total_chunks": total_chunks,
                        "source_type": source_type,
                        "scope": scope,
                        "source_ref": chunk_ref,
                        "skill_id": item.get("skill_id"),
                    },
                    "created_at": item.get("created_at", now),
                    "updated_at": now,
                    "dedupe_hash": dedupe_hash,
                }
            )
        upserted = await self.repository.upsert_knowledge(payloads)
        if scope == "user" and user_id:
            await self.repository.archive_stale_user_knowledge(
                user_id,
                self.settings.rag_user_memory_limit,
            )
        await self.ops_service.log_ai_call(
            user_id=user_id,
            provider="openai",
            model=self.settings.openai_embedding_model,
            operation="rag.upsert_documents",
            prompt_hash=None,
            cache_hit=False,
            latency_ms=0,
            input_tokens=0, # We don't have the exact usage accumulated easily here
            output_tokens=0,
            status="success",
            metadata={"doc_count": len(documents), "chunk_count": len(payloads), "scope": scope},
        )
        return upserted

    async def build_copilot_reply(
        self,
        *,
        user_id: str,
        page_context: str,
        message: str,
    ) -> dict[str, Any]:
        documents = await self.semantic_search(
            query=f"{page_context}\n{message}",
            top_k=self.settings.rag_top_k,
            user_id=user_id,
        )
        formatted_sources = [
            {
                "title": item.get("title") or item.get("source_ref") or item["source_type"],
                "detail": item["content"][:800],
                "tag": item["source_type"].replace("_", " ").title(),
            }
            for item in documents
        ]

        # Fetch real-time user metrics
        projection = await self.report_repository.get_projection(user_id)
        profile = await self.profile_repository.get_profile(user_id)
        
        metadata = profile.get("metadata", {}) if profile else {}
        focus_role = profile.get("focus_role") or "unspecified role"
        user_bio = metadata.get("bio", "Not provided")
        user_skills = ", ".join(metadata.get("self_reported_skills", [])) or "Not provided"
        weekly_goal = profile.get("weekly_goal", "Not provided") if profile else "Not provided"
        
        user_metrics = ""
        if projection and "payload" in projection:
            metrics = projection["payload"]
            user_metrics = (
                f"User Profile Stats (Role: {focus_role}):\n"
                f"- Bio & Background: {user_bio}\n"
                f"- Existing Skills: {user_skills}\n"
                f"- Current Goal: {weekly_goal}\n"
                f"- Overall Readiness: {metrics.get('readiness_score', 'N/A')}%\n"
                f"- Completed Assessments: {metrics.get('completed_count', 0)}\n"
                f"- Skill Breakdown: {metrics.get('skill_distribution', {})}\n"
            )
        else:
            user_metrics = (
                f"User Profile (Role: {focus_role})\n"
                f"- Bio & Background: {user_bio}\n"
                f"- Existing Skills: {user_skills}\n"
                f"- Current Goal: {weekly_goal}\n"
                "(No detailed metrics yet)\n"
            )

        prompt = (
            f"You are the 'CELTM Workspace Copilot'—an elite, data-driven career strategist for a user aiming for the '{focus_role}' role. "
            "Your personality is precise, professional, and results-oriented. Use the evidence and metrics provided to give actionable, no-fluff advice.\n\n"
            f"STRATEGIC USER CONTEXT:\n{user_metrics}\n\n"
            f"CURRENT WORKSPACE LOCATION: {page_context}\n"
            f"USER QUERY: {message}\n"
            f"RETRIEVED KNOWLEDGE EVIDENCE: {formatted_sources}\n\n"
            "CRITICAL OPERATING DIRECTIVES:\n"
            f"1. PERSONALIZATION: You are advising a {focus_role}. Every answer MUST be tailored to this role. "
            "If they are a Frontend Developer, emphasize UI/UX, React, and CSS. If Backend, focus on distributed systems, APIs, and databases.\n"
            "2. DATA-DRIVEN: If the user's readiness score is low, prioritize foundational learning. If high, suggest advanced optimization or situational practice.\n"
            "3. ACTIONABILITY: Don't just explain; recommend the next specific assessment or skill gap they should tackle based on their metrics.\n"
            "4. BREVITY: Keep responses under 3 concise paragraphs. Use bullet points for steps.\n"
            "5. NO PLACEHOLDERS: If you don't know something, state it clearly based on the evidence provided."
        )
        result = await self.llm_provider.chat_text(messages=[{"role": "user", "content": prompt}])
        await self.ops_service.log_ai_call(
            user_id=user_id,
            provider="openai",
            model=result["model"],
            operation="copilot.chat",
            prompt_hash=_hash_text(prompt),
            cache_hit=False,
            latency_ms=0,
            input_tokens=result["usage"]["input_tokens"],
            output_tokens=result["usage"]["output_tokens"],
            status="success",
            metadata={"page_context": page_context},
        )
        return {
            "answer": result["text"],
            "confidence": 0.88 if documents else 0.64,
            "sources": formatted_sources,
        }

    async def generate_analysis(
        self,
        *,
        user_id: str,
        assessment_results: list[dict[str, Any]],
        assessment: Any,
    ) -> dict[str, Any]:
        """
        Generates a detailed post-assessment feedback report using AI and RAG context.
        """
        # Fetch user context for better personalization
        profile = await self.profile_repository.get_profile(user_id)
        focus_role = profile.get("focus_role", "Professional") if profile else "Professional"
        
        # Summarize results to send to LLM
        correct_count = sum(1 for a in assessment_results if a.get("is_correct"))
        total_questions = len(assessment_results)
        score = (correct_count / total_questions * 100) if total_questions > 0 else 0
        
        incorrect_questions = [
            {
                "question": a.get("question_text", "Unknown Question"),
                "category": a.get("category", "General"),
                "selected": a.get("selected_option_text", "N/A"),
                "correct": a.get("correct_option_text", "N/A"),
            }
            for a in assessment_results if not a.get("is_correct")
        ]

        # Use RAG to find relevant instructional context for missed areas
        missed_categories = list(set(a.get("category", "General") for a in assessment_results if not a.get("is_correct")))
        rag_context = []

        try:
            started_at = perf_counter()
            if missed_categories:
                search_query = f"instructional guide for {', '.join(missed_categories)}"
                rag_context = await self.semantic_search(query=search_query, top_k=3, user_id=user_id)

            prompt = (
                f"You are the 'CELTM Assessment Analyst'. Your goal is to provide deep, constructive feedback for a user who just completed a '{assessment.get('category', 'Professional')}' assessment.\n\n"
                f"USER PROFILE:\nRole: {focus_role}\n\n"
                f"PERFORMANCE SUMMARY:\n"
                f"- Score: {score:.1f}%\n"
                f"- Correct: {correct_count}/{total_questions}\n\n"
                f"INCORRECT ANSWERS:\n{incorrect_questions[:10]}\n\n"
                f"RAG CONTEXT (Educational data):\n{rag_context}\n\n"
                "TASK:\n"
                "Provide a structured feedback report in JSON format with the following keys:\n"
                "1. overall_feedback (string, 2 sentences max)\n"
                "2. strengths (list of strings)\n"
                "3. risks (list of strings, areas of concern)\n"
                "4. recommendations (list of strings, next steps or resources)\n"
                "5. question_level_analysis (list of short comments for incorrectly answered questions)\n\n"
                "JSON ONLY. NO MARKDOWN."
            )

            result = await self.llm_provider.chat_text(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            
            import json
            feedback = json.loads(result["text"])
            
            latency_ms = int((perf_counter() - started_at) * 1000)
            await self.ops_service.log_ai_call(
                user_id=user_id,
                provider="openai",
                model=result["model"],
                operation="rag.generate_analysis",
                prompt_hash=_hash_text(prompt),
                cache_hit=False,
                latency_ms=latency_ms,
                input_tokens=result["usage"]["input_tokens"],
                output_tokens=result["usage"]["output_tokens"],
                status="success"
            )
            
            return feedback
        except Exception as e:
            # Fallback analysis if AI fails
            return {
                "overall_feedback": f"You completed the assessment with a score of {score:.1f}%. Review your incorrect answers to improve.",
                "strengths": ["Completed the assessment session"],
                "risks": [f"Missed {total_questions - correct_count} questions"],
                "recommendations": ["Re-review the course material", "Take a follow-up assessment"],
                "question_level_analysis": ["No detailed analysis available at this time."]
            }

    async def _touch_documents(self, documents: list[dict[str, Any]]) -> None:
        # Simplified: we don't have access_count in the new minimalist schema
        # but we can update metadata or just skip if we want to keep it ultra light
        pass

    def _resolve_learning_resource_url(
        self,
        item: dict[str, Any],
        skill_name: str,
    ) -> str:
        metadata = item.get("metadata") or {}
        explicit_url = metadata.get("url") if isinstance(metadata, dict) else None
        if isinstance(explicit_url, str) and explicit_url.startswith(("http://", "https://")):
            return explicit_url

        source_ref = item.get("source_ref")
        if isinstance(source_ref, str) and source_ref.startswith(("http://", "https://")):
            return source_ref

        fallback_links = self._build_fallback_learning_resources(skill_name)
        resource_type = str(item.get("source_type") or "").lower()
        if "video" in resource_type:
            return fallback_links[0]["resource_url"]
        if "practice" in resource_type:
            return fallback_links[2]["resource_url"]
        return fallback_links[1]["resource_url"]

    def _build_fallback_learning_resources(self, skill_name: str) -> list[dict[str, Any]]:
        encoded = quote_plus(skill_name)
        return [
            {
                "title": f"{skill_name} video practice",
                "content": (
                    f"Curated YouTube search for {skill_name} walkthroughs, "
                    "crash courses, and interview-style problem solving."
                ),
                "resource_type": "youtube_search",
                "skill_name": skill_name,
                "resource_url": f"https://www.youtube.com/results?search_query={encoded}+tutorial+practice",
            },
            {
                "title": f"{skill_name} free reading",
                "content": (
                    f"Free reading path covering explanations, guides, and "
                    f"structured notes for {skill_name}."
                ),
                "resource_type": "web_search",
                "skill_name": skill_name,
                "resource_url": (
                    "https://www.google.com/search?q="
                    f"{encoded}+free+tutorial+guide+site%3Afreecodecamp.org+OR+site%3Aroadmap.sh+OR+site%3Ageeksforgeeks.org"
                ),
            },
            {
                "title": f"{skill_name} hands-on practice",
                "content": (
                    f"Hands-on practice search for {skill_name} exercises, "
                    "project prompts, and implementation drills."
                ),
                "resource_type": "practice_search",
                "skill_name": skill_name,
                "resource_url": (
                    "https://www.google.com/search?q="
                    f"{encoded}+practice+project+exercise+github+OR+kaggle+OR+leetcode"
                ),
            },
            {
                "title": f"{skill_name} interview revision",
                "content": (
                    f"Revision search focused on interview questions, scenario drills, "
                    f"and conceptual refreshers for {skill_name}."
                ),
                "resource_type": "interview_search",
                "skill_name": skill_name,
                "resource_url": f"https://www.google.com/search?q={encoded}+interview+questions+answers",
            },
        ]


    def _chunk_text(self, text: str, chunk_size: int = 1500, overlap: int = 200) -> list[str]:
        if not text:
            return []
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start += (chunk_size - overlap)
        return chunks


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
