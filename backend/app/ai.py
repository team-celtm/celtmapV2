from __future__ import annotations

import json
import re
import base64
import hashlib
import time
from typing import Any

import httpx

from app.database import DIMENSIONS
from app.settings import Settings


class AnalysisUnavailableError(RuntimeError):
    pass


_AI_CACHE: dict[str, tuple[float, Any]] = {}


def _ai_cache_key(kind: str, payload: dict[str, Any]) -> str:
    raw = json.dumps({"kind": kind, "payload": payload}, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _clone_cached(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.loads(json.dumps(value, ensure_ascii=False))
    return value


def _ai_cache_get(settings: Settings, key: str) -> Any | None:
    if not settings.ai_cache_enabled or settings.ai_cache_ttl_seconds <= 0:
        return None
    entry = _AI_CACHE.get(key)
    if not entry:
        return None
    expires_at, value = entry
    if expires_at <= time.time():
        _AI_CACHE.pop(key, None)
        return None
    return _clone_cached(value)


def _ai_cache_set(settings: Settings, key: str, value: Any) -> None:
    if not settings.ai_cache_enabled or settings.ai_cache_ttl_seconds <= 0:
        return
    if len(_AI_CACHE) >= max(1, settings.ai_cache_max_entries):
        expired = [cache_key for cache_key, (expires_at, _) in _AI_CACHE.items() if expires_at <= time.time()]
        for cache_key in expired[:500]:
            _AI_CACHE.pop(cache_key, None)
        if len(_AI_CACHE) >= max(1, settings.ai_cache_max_entries):
            oldest_key = min(_AI_CACHE.items(), key=lambda item: item[1][0])[0]
            _AI_CACHE.pop(oldest_key, None)
    _AI_CACHE[key] = (time.time() + settings.ai_cache_ttl_seconds, _clone_cached(value))


def _allow_heuristic_fallback(settings: Settings) -> bool:
    return bool(getattr(settings, "allow_heuristic_ai_fallbacks", False))


def _raise_analysis_unavailable(kind: str) -> None:
    raise AnalysisUnavailableError(
        f"{kind} analysis is not available because the AI provider returned no usable response. "
        "Heuristic fallback analysis is disabled."
    )


ROLE_KEYWORDS = {
    "ai": ["llm", "machine learning", "python", "pytorch", "tensorflow", "rag", "agents", "mlops"],
    "ml": ["machine learning", "python", "statistics", "model", "pytorch", "scikit", "mlops"],
    "data": ["sql", "python", "dashboard", "statistics", "analytics", "experimentation"],
    "software": ["api", "system design", "testing", "database", "cloud", "deployment"],
    "pilot": ["physics", "navigation", "safety", "medical fitness", "flight training", "communication"],
}

WRITTEN_STOPWORDS = {
    "about",
    "above",
    "after",
    "again",
    "against",
    "answer",
    "assessment",
    "because",
    "before",
    "being",
    "below",
    "between",
    "could",
    "does",
    "from",
    "have",
    "into",
    "only",
    "question",
    "response",
    "shall",
    "should",
    "that",
    "their",
    "there",
    "these",
    "this",
    "through",
    "what",
    "when",
    "where",
    "which",
    "with",
    "would",
    "write",
    "your",
}


def normalize_role(value: str) -> str:
    text = value.lower()
    if "pilot" in text:
        return "pilot"
    if "data" in text:
        return "data"
    if "software" in text or "developer" in text:
        return "software"
    if "ml" in text or "machine learning" in text:
        return "ml"
    return "ai"


def _clean_role_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())[:80]


def _compact_role_text(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _display_role_text(value: str | None) -> str:
    raw = _clean_role_text(value)
    if not raw:
        return ""
    if raw.isupper() and len(raw) <= 6:
        return raw
    small_words = {"and", "or", "of", "for", "to", "in", "as", "the"}
    parts = re.split(r"(\s+)", raw)
    formatted: list[str] = []
    for index, part in enumerate(parts):
        if not part.strip():
            formatted.append(part)
            continue
        lower = part.lower()
        if 0 < index < len(parts) - 1 and lower in small_words:
            formatted.append(lower)
        elif len(part) <= 4 and part.isupper():
            formatted.append(part)
        else:
            formatted.append(part[:1].upper() + part[1:].lower())
    return "".join(formatted).strip()


def _known_role_match(raw_role: str, known_roles: list[dict[str, Any]]) -> dict[str, Any] | None:
    compact = _compact_role_text(raw_role)
    normalized = re.sub(r"[^a-z0-9]+", "-", raw_role.lower()).strip("-")
    if not compact and not normalized:
        return None
    for item in known_roles:
        candidates = [str(item.get("label") or item.get("value") or ""), *[str(alias) for alias in item.get("aliases", [])]]
        normalized_candidates = {re.sub(r"[^a-z0-9]+", "-", candidate.lower()).strip("-") for candidate in candidates}
        compact_candidates = {_compact_role_text(candidate) for candidate in candidates}
        if normalized in normalized_candidates or compact in compact_candidates:
            return item
    return None


def _heuristic_career_aim_resolution(raw_role: str, known_roles: list[dict[str, Any]]) -> dict[str, Any]:
    match = _known_role_match(raw_role, known_roles)
    if match:
        label = str(match.get("label") or match.get("value") or raw_role).strip()
        return {
            "input": raw_role,
            "normalized_role": label,
            "matched_catalog_role": label,
            "is_supported_catalog": True,
            "confidence": 0.96,
            "source": "catalog",
            "interpretation": f"Matched the typed aim to {label}.",
            "alternatives": [],
        }

    common_expansions = {
        "cpa": "Certified Public Accountant",
        "cs": "Company Secretary",
        "cma": "Cost and Management Accountant",
        "ias": "Indian Administrative Service Officer",
        "ips": "Indian Police Service Officer",
        "ifs": "Indian Foreign Service Officer",
        "pm": "Product Manager",
        "sde": "Software Development Engineer",
        "ux": "UX Designer",
        "ui": "UI Designer",
    }
    expanded = common_expansions.get(_compact_role_text(raw_role))
    normalized = expanded or _display_role_text(raw_role)
    return {
        "input": raw_role,
        "normalized_role": normalized,
        "matched_catalog_role": None,
        "is_supported_catalog": False,
        "confidence": 0.55 if expanded else 0.42,
        "source": "heuristic",
        "interpretation": "Using a custom career aim because it is not in the fixed catalog.",
        "alternatives": [],
    }


COMMON_CAREER_ABBREVIATION_SUGGESTIONS: dict[str, list[str]] = {
    "ca": ["Chartered Accountant", "Career Analyst", "Compliance Analyst"],
    "cs": ["Company Secretary", "Computer Scientist", "Customer Success Manager"],
    "cma": ["Cost and Management Accountant", "Certified Management Accountant"],
    "pm": ["Product Manager", "Project Manager", "Program Manager"],
    "ba": ["Business Analyst", "Brand Analyst", "Banking Associate"],
    "qa": ["Quality Assurance Engineer", "Quality Analyst"],
    "hr": ["Human Resources Manager", "HR Business Partner"],
    "ui": ["UI Designer", "User Interface Designer"],
    "ux": ["UX Designer", "User Experience Researcher"],
    "sde": ["Software Development Engineer"],
    "devops": ["DevOps Engineer"],
    "ias": ["Indian Administrative Service Officer"],
    "ips": ["Indian Police Service Officer"],
    "ifs": ["Indian Foreign Service Officer"],
    "cpa": ["Certified Public Accountant"],
}


def _career_aim_suggestion(
    label: str,
    *,
    known_roles: list[dict[str, Any]],
    confidence: float,
    source: str,
    interpretation: str = "",
) -> dict[str, Any] | None:
    clean_label = _display_role_text(label)
    if not clean_label:
        return None
    matched = _known_role_match(clean_label, known_roles)
    if matched:
        clean_label = str(matched.get("label") or matched.get("value") or clean_label).strip()
    description = ""
    aliases: list[str] = []
    profile_key = "custom"
    if matched:
        description = str(matched.get("description") or "")
        aliases = [str(alias) for alias in matched.get("aliases", []) if str(alias).strip()]
        profile_key = str(matched.get("profile_key") or "custom")
    return {
        "value": clean_label,
        "label": clean_label,
        "profile_key": profile_key,
        "aliases": aliases,
        "description": description or interpretation,
        "matched_catalog_role": clean_label if matched else None,
        "is_supported_catalog": bool(matched),
        "confidence": round(max(0.0, min(1.0, confidence)), 2),
        "source": source,
        "interpretation": interpretation or ("Matched a supported CELTM career role." if matched else "AI-suggested custom career interpretation."),
    }


def _local_career_aim_suggestions(raw_role: str, known_roles: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    compact = _compact_role_text(raw_role)
    clean_query = re.sub(r"[^a-z0-9]+", " ", raw_role.lower()).strip()
    suggestions: list[dict[str, Any]] = []

    def add(label: str, confidence: float, source: str, interpretation: str = "") -> None:
        suggestion = _career_aim_suggestion(
            label,
            known_roles=known_roles,
            confidence=confidence,
            source=source,
            interpretation=interpretation,
        )
        if suggestion:
            suggestions.append(suggestion)

    if compact in COMMON_CAREER_ABBREVIATION_SUGGESTIONS:
        for index, label in enumerate(COMMON_CAREER_ABBREVIATION_SUGGESTIONS[compact]):
            add(
                label,
                0.9 - index * 0.08,
                "abbreviation",
                f"{raw_role} can commonly expand to {label}.",
            )

    for item in known_roles:
        label = str(item.get("label") or item.get("value") or "").strip()
        aliases = [str(alias) for alias in item.get("aliases", [])]
        candidates = [label, str(item.get("value") or ""), *aliases]
        normalized_candidates = {re.sub(r"[^a-z0-9]+", " ", candidate.lower()).strip() for candidate in candidates}
        compact_candidates = {_compact_role_text(candidate) for candidate in candidates}
        haystack = " ".join(normalized_candidates)
        if compact and compact in compact_candidates:
            add(label, 0.96, "catalog", f"Matched {raw_role} to a supported CELTM role.")
        elif clean_query and (clean_query in haystack or all(token in haystack for token in clean_query.split())):
            add(label, 0.78, "catalog", f"Matched the typed aim to {label}.")

    if not suggestions and raw_role:
        add(_display_role_text(raw_role), 0.42, "typed", "Use the typed career aim as a custom target role.")

    return _dedupe_career_aim_suggestions(suggestions, limit)


def _dedupe_career_aim_suggestions(items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    for item in items:
        label = str(item.get("label") or item.get("value") or "").strip()
        key = _compact_role_text(label)
        if not key:
            continue
        existing = unique.get(key)
        if not existing or float(item.get("confidence", 0) or 0) > float(existing.get("confidence", 0) or 0):
            unique[key] = {**item, "value": label, "label": label}
    return sorted(
        unique.values(),
        key=lambda item: (
            bool(item.get("is_supported_catalog")),
            float(item.get("confidence", 0) or 0),
            1 if item.get("source") == "ai" else 0,
        ),
        reverse=True,
    )[:limit]


async def suggest_career_aims(
    settings: Settings,
    desired_role: str,
    known_roles: list[dict[str, Any]],
    context: dict[str, Any] | None = None,
    limit: int = 6,
) -> list[dict[str, Any]]:
    raw_role = _clean_role_text(desired_role)
    if not raw_role:
        return []

    limit = max(1, min(8, int(limit or 6)))
    fallback = _local_career_aim_suggestions(raw_role, known_roles, limit)
    known_role_payload = [
        {
            "label": item.get("label") or item.get("value"),
            "aliases": item.get("aliases", []),
            "description": item.get("description", ""),
        }
        for item in known_roles[:40]
    ]
    prompt = f"""
Return strict JSON only.
Suggest likely professional career aims for this typed input: {raw_role}
Known CELTM catalog roles: {json.dumps(known_role_payload, ensure_ascii=False)}
Learner context: {json.dumps(context or {}, ensure_ascii=False, default=str)[:2000]}

Rules:
- If the input is an abbreviation, return multiple credible expansions instead of only one.
- Include a supported catalog role when it is plausible, but also include real custom roles outside the catalog when the abbreviation can mean them.
- Example behavior: CA can mean Chartered Accountant and Career Analyst; choose confidence from context, not hard-coded software defaults.
- Do not force Full Stack Developer or software unless the typed input actually means it.
- Do not invent joke/fantasy roles. Convert vague wording to practical real career roles.

Return an object with key suggestions.
suggestions must be an array of up to {limit} objects.
Each object must contain label, confidence, interpretation, and optional matched_catalog_role.
confidence must be a number from 0 to 1.
"""
    ai = await call_ai_json(
        settings,
        "You suggest career aim dropdown options from typed text and ambiguous abbreviations. Return JSON only.",
        prompt,
    )
    ai_items: list[dict[str, Any]] = []
    raw_items = ai.get("suggestions") if isinstance(ai, dict) else None
    if isinstance(raw_items, list):
        for raw_item in raw_items[:limit]:
            if not isinstance(raw_item, dict):
                continue
            label = str(raw_item.get("label") or raw_item.get("normalized_role") or raw_item.get("role") or "").strip()
            if not label:
                continue
            try:
                confidence = float(raw_item.get("confidence", 0.62))
            except Exception:
                confidence = 0.62
            suggestion = _career_aim_suggestion(
                label,
                known_roles=known_roles,
                confidence=confidence,
                source="ai",
                interpretation=str(raw_item.get("interpretation") or "AI-suggested career interpretation."),
            )
            if suggestion:
                matched_label = str(raw_item.get("matched_catalog_role") or "").strip()
                matched = _known_role_match(matched_label, known_roles) if matched_label else _known_role_match(label, known_roles)
                if matched:
                    matched_label = str(matched.get("label") or matched.get("value") or matched_label).strip()
                    suggestion["value"] = matched_label
                    suggestion["label"] = matched_label
                    suggestion["matched_catalog_role"] = matched_label
                    suggestion["is_supported_catalog"] = True
                    suggestion["profile_key"] = str(matched.get("profile_key") or "custom")
                    suggestion["aliases"] = [str(alias) for alias in matched.get("aliases", []) if str(alias).strip()]
                    suggestion["description"] = str(matched.get("description") or suggestion["description"])
                ai_items.append(suggestion)

    return _dedupe_career_aim_suggestions([*ai_items, *fallback], limit)


async def resolve_career_aim(
    settings: Settings,
    desired_role: str,
    known_roles: list[dict[str, Any]],
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    raw_role = _clean_role_text(desired_role)
    if not raw_role:
        return {
            "input": "",
            "normalized_role": "",
            "matched_catalog_role": None,
            "is_supported_catalog": False,
            "confidence": 0,
            "source": "empty",
            "interpretation": "Desired role is required.",
            "alternatives": [],
        }

    fallback = _heuristic_career_aim_resolution(raw_role, known_roles)
    known_role_payload = [
        {
            "label": item.get("label") or item.get("value"),
            "aliases": item.get("aliases", []),
            "description": item.get("description", ""),
        }
        for item in known_roles[:40]
    ]
    prompt = f"""
Return strict JSON only.
Resolve this typed career aim into the best professional target role.
Typed aim: {raw_role}
Known catalog roles: {json.dumps(known_role_payload, ensure_ascii=False)}
Learner context: {json.dumps(context or {}, ensure_ascii=False, default=str)[:3000]}

Rules:
- Expand abbreviations when clear, for example CA means Chartered Accountant.
- If it matches a catalog role or alias, set matched_catalog_role to that catalog label.
- If it is a legitimate role outside the catalog, create a concise normalized_role.
- If it is vague or unrealistic, normalize it to the closest real career direction and explain the interpretation.
- Do not force software/full-stack unless the typed aim actually means that.

Return keys:
input, normalized_role, matched_catalog_role, is_supported_catalog, confidence, interpretation, alternatives.
confidence must be a number from 0 to 1.
alternatives must be an array of up to 3 strings.
"""
    ai = await call_ai_json(
        settings,
        "You resolve career aims and abbreviations into practical professional target roles. Return JSON only.",
        prompt,
    )
    if not ai:
        return fallback

    matched_label = str(ai.get("matched_catalog_role") or "").strip()
    matched_role = _known_role_match(matched_label, known_roles) if matched_label else None
    if matched_role:
        normalized = str(matched_role.get("label") or matched_role.get("value") or matched_label).strip()
        is_supported = True
        matched_label = normalized
    else:
        normalized = _display_role_text(str(ai.get("normalized_role") or fallback["normalized_role"]))
        is_supported = False
        matched_label = ""

    if not normalized:
        normalized = str(fallback["normalized_role"])

    try:
        confidence = max(0.0, min(1.0, float(ai.get("confidence", fallback["confidence"]))))
    except Exception:
        confidence = float(fallback["confidence"])

    alternatives = ai.get("alternatives")
    if not isinstance(alternatives, list):
        alternatives = fallback.get("alternatives", [])

    return {
        "input": raw_role,
        "normalized_role": normalized,
        "matched_catalog_role": matched_label or None,
        "is_supported_catalog": is_supported,
        "confidence": round(confidence, 2),
        "source": "ai",
        "interpretation": str(ai.get("interpretation") or fallback["interpretation"]),
        "alternatives": [str(item) for item in alternatives if str(item).strip()][:3],
    }


def _meaningful_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z][a-zA-Z0-9+#.-]{2,}", value.lower())
        if token not in WRITTEN_STOPWORDS
    }


def _relevance_details(prompt: str, response: str, role_name: str) -> dict[str, Any]:
    prompt_terms = _meaningful_tokens(prompt)
    response_terms = _meaningful_tokens(response)
    lowered_response = response.lower()
    expected_terms = set(ROLE_KEYWORDS.get(normalize_role(role_name), ROLE_KEYWORDS["ai"]))
    expected_terms.update(term for item in expected_terms.copy() for term in _meaningful_tokens(item))
    overlap = prompt_terms & response_terms
    role_hits = {
        term
        for term in expected_terms
        if re.search(rf"\b{re.escape(term)}\b", lowered_response)
        or (len(term) > 3 and term in lowered_response)
    }
    denominator = max(1, min(len(prompt_terms), 14))
    return {
        "prompt_terms": prompt_terms,
        "response_terms": response_terms,
        "overlap": overlap,
        "role_hits": role_hits,
        "relevance_ratio": min(1.0, len(overlap) / denominator),
    }


def _cap_score(score: float, caps: list[tuple[int, str]]) -> tuple[int, int, list[str]]:
    score_cap = min((cap for cap, _ in caps), default=100)
    reasons = [reason for cap, reason in caps if cap == score_cap]
    return round(max(0, min(score, score_cap))), score_cap, reasons


def safe_json_from_text(value: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", value, flags=re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


async def call_ai_json(settings: Settings, system: str, user: str) -> dict[str, Any] | None:
    if not settings.openai_api_key:
        return None

    payload = {
        "model": settings.openai_chat_model,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
    }
    cache_key = _ai_cache_key("json", payload)
    cached = _ai_cache_get(settings, cache_key)
    if isinstance(cached, dict):
        return cached
    try:
        async with httpx.AsyncClient(timeout=settings.openai_timeout_seconds) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        parsed = safe_json_from_text(content)
        if parsed:
            _ai_cache_set(settings, cache_key, parsed)
        return parsed
    except Exception:
        return None


async def call_ai_text(settings: Settings, system: str, user: str) -> str | None:
    if not settings.openai_api_key:
        return None

    payload = {
        "model": settings.openai_chat_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.5,
    }
    cache_key = _ai_cache_key("text", payload)
    cached = _ai_cache_get(settings, cache_key)
    if isinstance(cached, str):
        return cached
    try:
        async with httpx.AsyncClient(timeout=settings.openai_timeout_seconds) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        response.raise_for_status()
        content = str(response.json()["choices"][0]["message"]["content"] or "").strip()
        if content:
            _ai_cache_set(settings, cache_key, content)
        return content
    except Exception:
        return None


def _image_media_type(filename: str) -> str | None:
    lowered = filename.lower()
    if lowered.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if lowered.endswith(".png"):
        return "image/png"
    if lowered.endswith(".webp"):
        return "image/webp"
    return None


async def extract_certificate_text_with_ai(settings: Settings, filename: str, content: bytes) -> str:
    media_type = _image_media_type(filename)
    if not settings.openai_api_key or not media_type or not content:
        return ""
    encoded = base64.b64encode(content[:8_000_000]).decode("ascii")
    payload = {
        "model": settings.openai_chat_model,
        "messages": [
            {
                "role": "system",
                "content": "You extract text from certificate images. Return only the visible text, issuer, credential id, dates, and skills. Do not invent missing details.",
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"Extract the credential text from this uploaded certificate image: {filename}"},
                    {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{encoded}"}},
                ],
            },
        ],
        "temperature": 0,
    }
    try:
        cache_key = _ai_cache_key("certificate-image-text", payload)
        cached = _ai_cache_get(settings, cache_key)
        if isinstance(cached, str):
            return cached
        async with httpx.AsyncClient(timeout=settings.openai_timeout_seconds) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        response.raise_for_status()
        extracted = str(response.json()["choices"][0]["message"]["content"] or "").strip()
        if extracted:
            _ai_cache_set(settings, cache_key, extracted)
        return extracted
    except Exception:
        return ""


def heuristic_resume_analysis(resume_text: str, target_role: str) -> dict[str, Any]:
    text = resume_text.lower()
    role_key = normalize_role(target_role)
    expected = ROLE_KEYWORDS[role_key]
    keyword_hits = [keyword for keyword in expected if keyword in text]
    has_links = any(token in text for token in ["github.com", "linkedin.com", "portfolio", "http"])
    has_dates = bool(re.search(r"(20[2-4][0-9]|expected graduation|graduation)", text))
    has_metrics = bool(re.search(r"\b\d+(\.\d+)?\s?%|\b\d+x\b|\b\d+\+", text))
    has_project = "project" in text or "built" in text or "developed" in text

    score = 42 + len(keyword_hits) * 6
    score += 8 if has_links else 0
    score += 8 if has_dates else 0
    score += 8 if has_metrics else 0
    score += 8 if has_project else 0
    score = max(15, min(92, score))

    red_flags = []
    if "estimated" in text:
        red_flags.append(
            {
                "title": '"Estimated" metrics undermine credibility',
                "reason": "Estimated impact numbers can look fabricated when a recruiter scans the document quickly.",
                "fix": "Use measured numbers, experiment targets, or remove the qualifier.",
            }
        )
    if not has_dates:
        red_flags.append(
            {
                "title": "No expected graduation date",
                "reason": "Internship recruiters need timeline clarity within a few seconds.",
                "fix": "Add expected graduation month and year next to the degree.",
            }
        )
    if not has_links:
        red_flags.append(
            {
                "title": "No visible proof links",
                "reason": "A hiring manager cannot quickly inspect GitHub, LinkedIn, publications, or portfolio evidence.",
                "fix": "Add visible URLs for GitHub, LinkedIn, portfolio, or top projects.",
            }
        )
    if len(red_flags) < 3 and not has_project:
        red_flags.append(
            {
                "title": "Projects are not obvious",
                "reason": "The resume does not make shipped work easy to find.",
                "fix": "Add 2-3 project bullets with problem, method, result, and link.",
            }
        )
    while len(red_flags) < 3:
        red_flags.append(
            {
                "title": "Generic role positioning",
                "reason": "The resume can be sharper for the exact target role.",
                "fix": f"Mirror the role title '{target_role}' and include role-specific evidence in the top half.",
            }
        )

    top_keywords = []
    for rank, keyword in enumerate(expected[:5], start=1):
        present = keyword in text
        top_keywords.append(
            {
                "rank": rank,
                "keyword": keyword.upper() if len(keyword) <= 4 else keyword.title(),
                "status": "Present" if present else "Missing",
                "detail": (
                    "Visible in the resume and useful for ATS matching."
                    if present
                    else "Add this explicitly with evidence, not only as a skill label."
                ),
                "badge": "Present" if present else "Missing",
            }
        )

    weak_points = [
        "Sharpen role-specific keywords in the top half of the resume",
        "Add proof links that remain readable outside embedded PDF hyperlinks",
        "Quantify project outcomes with measured numbers",
        "Connect coursework/projects to production or internship impact",
    ]
    strong_points = [
        "Clear technical foundation" if keyword_hits else "Academic foundation is usable",
        "Relevant projects are present" if has_project else "Can build a project-backed profile quickly",
        "Metrics are visible" if has_metrics else "Has room to add measurable impact",
        "Target role can be inferred from skills",
        "Profile can improve quickly with structured assessments",
    ]
    institute_help = [
        "Run resume clinics focused on visible proof links and role keywords",
        "Assign project mentors for deployable AI/ML portfolio work",
        "Create mock recruiter screen rounds with 10-second resume scans",
        "Map students to department-level skill labs based on weak dimensions",
    ]

    return {
        "match_score": round(score),
        "verdict": "Strong candidate - a few fixable gaps" if score >= 75 else "Developing candidate - needs sharper evidence",
        "summary": (
            f"The profile is viable for {target_role} tracks. The biggest improvement is to make proof, "
            "role keywords, and measurable outcomes visible in the first scan."
        ),
        "score_breakdown": [
            {"label": "Technical skills", "score": min(25, 10 + len(keyword_hits) * 3), "max": 25},
            {"label": "Project / internship proof", "score": 20 if has_project else 10, "max": 25},
            {"label": "Role keyword fit", "score": min(20, len(keyword_hits) * 3), "max": 20},
            {"label": "Presentation", "score": 14 if has_links else 8, "max": 15},
            {"label": "Impact clarity", "score": 15 if has_metrics else 8, "max": 15},
        ],
        "top_keywords": top_keywords,
        "red_flags": red_flags[:3],
        "full_breakdown": (
            f"Score: {round(score)}/100. The resume has {len(keyword_hits)} of the expected "
            f"{target_role} keyword signals. Improve recruiter confidence by making proof links, "
            "graduation timeline, and quantified outcomes explicit."
        ),
        "strong_points": strong_points[:5],
        "weak_points": weak_points[:4],
        "institute_help": institute_help,
    }


def normalize_score_breakdown(value: Any, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[Any]
    if isinstance(value, list):
        items = value
    elif isinstance(value, dict):
        items = []
        for label, raw in value.items():
            if isinstance(raw, dict):
                items.append({"label": raw.get("label") or label, **raw})
            else:
                items.append({"label": label, "score": raw, "max": 100})
    else:
        return fallback

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or item.get("name") or f"Area {index}").strip()
        try:
            score = float(item.get("score", item.get("value", 0)))
        except Exception:
            score = 0.0
        try:
            max_score = float(item.get("max", item.get("total", 100)))
        except Exception:
            max_score = 100.0
        if max_score <= 0:
            max_score = 100.0
        normalized.append({"label": label, "score": round(score, 2), "max": round(max_score, 2)})
    return normalized or fallback


def normalize_resume_list(value: Any, fallback: list[Any]) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return list(value.values())
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return fallback


def normalize_top_keywords(value: Any, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = normalize_resume_list(value, fallback)
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(rows, start=1):
        if isinstance(item, dict):
            keyword = str(
                item.get("keyword")
                or item.get("term")
                or item.get("name")
                or item.get("label")
                or item.get("title")
                or ""
            ).strip()
            status = str(item.get("status") or item.get("presence") or "").strip()
            detail = str(item.get("detail") or item.get("description") or item.get("reason") or "").strip()
            badge = str(item.get("badge") or status or "Keyword").strip()
            try:
                rank = int(item.get("rank") or index)
            except Exception:
                rank = index
        else:
            keyword = str(item).strip()
            status = "Review"
            detail = "Add this keyword only when it is supported by visible resume evidence."
            badge = "Keyword"
            rank = index
        if not keyword:
            continue
        normalized.append(
            {
                "rank": rank,
                "keyword": keyword,
                "status": status or "Review",
                "detail": detail or "Make this explicit with project, internship, or certification evidence.",
                "badge": badge,
            }
        )
    return normalized or fallback


def normalize_red_flags(value: Any, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = normalize_resume_list(value, fallback)
    normalized: list[dict[str, Any]] = []
    for item in rows:
        if isinstance(item, dict):
            title = str(item.get("title") or item.get("flag") or item.get("name") or item.get("label") or "").strip()
            reason = str(item.get("reason") or item.get("description") or item.get("detail") or "").strip()
            fix = str(item.get("fix") or item.get("recommendation") or item.get("solution") or "").strip()
        else:
            title = str(item).strip()
            reason = "A recruiter may notice this quickly during the first resume screen."
            fix = "Rewrite the section with concrete evidence, dates, links, or measured impact."
        if not title:
            continue
        normalized.append(
            {
                "title": title,
                "reason": reason or "This can weaken trust or role fit during a fast recruiter scan.",
                "fix": fix or "Add specific evidence and remove ambiguous wording.",
            }
        )
    return normalized or fallback


async def analyze_resume(settings: Settings, resume_text: str, target_role: str) -> dict[str, Any]:
    prompt = f"""
Return strict JSON only.
Act as a senior recruiter for the exact role of {target_role}.
Analyze my resume against the pointers crucial for an ideal candidate that has been going on as a candidate for this descriptio.
Give me a match score out of a 100. give the top five keywords and the 3 red flags that i shall not have in my resume that can be spotted by a hiring manager in 10 seconds.
Return keys: match_score, verdict, summary, score_breakdown, top_keywords, red_flags, full_breakdown, strong_points, weak_points, institute_help.
Resume:
{resume_text[:12000]}
"""
    ai = await call_ai_json(
        settings,
        "You are a precise recruiting evaluator. You return valid JSON and no markdown.",
        prompt,
    )
    fallback = heuristic_resume_analysis(resume_text, target_role)
    allow_fallback = _allow_heuristic_fallback(settings)
    if not ai:
        if not allow_fallback:
            _raise_analysis_unavailable("Resume")
        return fallback
    merged = {**(fallback if allow_fallback else {}), **ai}
    try:
        merged["match_score"] = max(0, min(100, round(float(merged["match_score"]))))
    except Exception:
        if not allow_fallback:
            _raise_analysis_unavailable("Resume")
        merged["match_score"] = fallback["match_score"]
    merged["score_breakdown"] = normalize_score_breakdown(merged.get("score_breakdown"), fallback["score_breakdown"] if allow_fallback else [])
    merged["top_keywords"] = normalize_top_keywords(merged.get("top_keywords"), fallback["top_keywords"] if allow_fallback else [])[:5]
    merged["red_flags"] = normalize_red_flags(merged.get("red_flags"), fallback["red_flags"] if allow_fallback else [])[:3]
    merged["strong_points"] = normalize_resume_list(merged.get("strong_points"), fallback["strong_points"] if allow_fallback else [])[:5]
    merged["weak_points"] = normalize_resume_list(merged.get("weak_points"), fallback["weak_points"] if allow_fallback else [])[:4]
    merged["institute_help"] = normalize_resume_list(merged.get("institute_help"), fallback["institute_help"] if allow_fallback else [])[:4]
    return merged


def infer_strengths_and_gaps(capability_profile: dict[str, float]) -> tuple[list[str], list[str]]:
    if not capability_profile:
        return ["Resume evidence"], ["Complete the first capability assessment"]
    ordered = sorted(capability_profile.items(), key=lambda item: item[1], reverse=True)
    strengths = [name for name, _ in ordered[:3]]
    gaps = [name for name, _ in ordered[-3:]]
    return strengths, gaps


async def analyze_aspiration(
    settings: Settings,
    desired_role: str,
    current_readiness: float,
    capability_profile: dict[str, float],
    resume_analysis: dict[str, Any] | None,
) -> dict[str, Any]:
    strengths, gaps = infer_strengths_and_gaps(capability_profile)
    prompt = f"""
Return strict JSON only.
The learner wants to become: {desired_role}.
Current readiness: {current_readiness}.
Capability profile: {json.dumps(capability_profile)}.
Resume analysis: {json.dumps(resume_analysis or {})[:5000]}.
Return keys desired_role, current_readiness, major_gaps, better_current_fit, roadmap, infographics, analysis.
major_gaps must be an array of strings (e.g., ["gap 1", "gap 2"]).
better_current_fit must be an array of strings (e.g., ["role 1", "role 2"]).
roadmap must contain roadmap_30_days, roadmap_60_days, roadmap_90_days arrays.
infographics must be an array of simple cards with label, value, helper.
"""
    ai = await call_ai_json(
        settings,
        "You are a career guidance engine. You return practical JSON and no markdown.",
        prompt,
    )
    if ai:
        return ai

    better_fit = ["AI Project Assistant", "Technical Support Analyst"]
    if normalize_role(desired_role) == "pilot":
        better_fit = ["Aviation Operations Analyst", "Drone Systems Trainee"]
    roadmap = {
        "roadmap_30_days": [
            f"Understand the entry requirements for {desired_role}",
            f"Close the first gap: {gaps[0] if gaps else 'foundation skills'}",
            "Build one proof artifact that shows commitment",
        ],
        "roadmap_60_days": [
            "Complete two capability assessments and compare improvement",
            "Find a mentor or department head for role-specific review",
            "Create a portfolio page with visible evidence",
        ],
        "roadmap_90_days": [
            "Attempt a role-based mock interview or selection test",
            "Collect feedback from institute/HOD and update the plan",
            "Apply to internships, training programs, or bridge courses",
        ],
    }
    return {
        "desired_role": desired_role,
        "current_readiness": round(current_readiness),
        "major_gaps": gaps[:3],
        "better_current_fit": better_fit,
        "roadmap": roadmap,
        "infographics": [
            {"label": "Current readiness", "value": f"{round(current_readiness)}%", "helper": "Updates after resume and assessments"},
            {"label": "Strongest area", "value": strengths[0] if strengths else "Pending", "helper": "Use this as your bridge"},
            {"label": "Primary gap", "value": gaps[0] if gaps else "Assessment pending", "helper": "Fix this first"},
        ],
        "analysis": {
            "summary": f"{desired_role} is possible with a staged transition plan. Start with proof, eligibility, and capability gaps.",
            "strengths": strengths,
            "gaps": gaps,
        },
    }


def heuristic_written_evaluation(prompt: str, response: str, role_name: str) -> dict[str, Any]:
    text = response.strip()
    lower = text.lower()
    word_count = len(re.findall(r"\b\w+\b", text))
    details = _relevance_details(prompt, text, role_name)
    has_structure = sum(
        1
        for token in [
            "first",
            "second",
            "because",
            "therefore",
            "risk",
            "tradeoff",
            "trade-off",
            "constraint",
            "evidence",
            "decision",
        ]
        if token in lower
    )
    has_evidence = bool(
        re.search(
            r"\b\d+(\.\d+)?\s?%|\bexample\b|\bmetric\b|\bevidence\b|\bdata\b|\blog\b|\bbenchmark\b|\btest\b",
            lower,
        )
    )
    has_conclusion = any(token in lower for token in ["therefore", "so ", "recommend", "next step", "conclusion"])
    upload_stub = "uploaded written evidence submitted through celtm upload flow" in lower or re.search(r"\bartifact\s*:", lower)
    overlap_count = len(details["overlap"])
    role_hit_count = len(details["role_hits"])

    score = 0
    score += min(14, word_count // 12)
    score += min(30, overlap_count * 5 + round(details["relevance_ratio"] * 10))
    score += min(18, has_structure * 3)
    score += 14 if has_evidence else 0
    score += min(12, role_hit_count * 4)
    score += 7 if has_conclusion else 0
    if word_count >= 120 and overlap_count >= 2:
        score += 5

    caps: list[tuple[int, str]] = []
    if word_count < 40:
        caps.append((15, "Answer is too short to evaluate beyond minimal credit."))
    if overlap_count == 0 and role_hit_count == 0:
        caps.append((10, "Submission is not connected to the written prompt."))
    elif overlap_count <= 1 and role_hit_count == 0:
        caps.append((22, "Submission has weak question relevance."))
    if upload_stub and not has_evidence and overlap_count <= 1:
        caps.append((12, "Uploaded-file metadata or notes do not answer the prompt."))
    if word_count < 80 and not has_evidence:
        caps.append((25, "Short answer without evidence cannot earn readiness credit."))
    score, score_cap, cap_reasons = _cap_score(score, caps)

    loopholes = []
    if cap_reasons:
        loopholes.extend(cap_reasons)
    if word_count < 80:
        loopholes.append("Response is too short to show reasoning depth.")
    if overlap_count <= 1:
        loopholes.append("The answer does not reuse enough of the problem context to prove relevance.")
    if not has_evidence:
        loopholes.append("No measurable evidence, concrete example, test, or benchmark is included.")
    if has_structure < 2:
        loopholes.append("Reasoning is not clearly sequenced into decision steps.")
    if role_hit_count == 0:
        loopholes.append(f"Answer does not connect explicitly to {role_name}.")
    while len(loopholes) < 3:
        loopholes.append("Conclusion needs a clearer link between action, risk, and outcome.")

    insights = [
        "Question relevance is visible" if overlap_count >= 2 else "Question relevance is weak or missing",
        "Shows usable written reasoning" if word_count >= 100 and has_structure >= 2 else "Needs deeper written reasoning",
        "Evidence is present" if has_evidence else "Evidence and metrics should be added",
    ]
    recommendations = [
        "Use a short structure: context, decision, evidence, risk, next action.",
        f"Name the {role_name} skill being demonstrated instead of implying it.",
        "Answer the exact prompt before adding general notes or uploaded evidence.",
        "Add one measured result, benchmark, or concrete example.",
    ]
    return {
        "score": round(score),
        "feedback": (
            f"Score: {round(score)}/100. The response is readable, but it needs clearer evidence, "
            "question relevance, role alignment, and a stronger decision path to pass a strict practice review."
        ),
        "insights": insights,
        "loopholes": loopholes[:4],
        "recommendations": recommendations,
        "plagiarism": {
            "risk_score": 0 if overlap_count >= 2 else 65,
            "risk_level": "low" if overlap_count >= 2 else "question-mismatch",
            "summary": (
                "No external similarity check is enabled in Phase 1. This score also flags whether "
                "the answer appears to address the asked prompt."
            ),
            "signals": [
                f"Prompt term overlap: {overlap_count}",
                f"Role evidence terms: {role_hit_count}",
                f"Score cap applied: {score_cap}",
            ],
        },
        "readiness_score": round(score),
        "quality_gate": {
            "score_cap": score_cap,
            "cap_reasons": cap_reasons,
            "prompt_overlap": overlap_count,
            "role_hits": role_hit_count,
            "word_count": word_count,
        },
    }


async def analyze_written_response(
    settings: Settings,
    prompt: str,
    response: str,
    evaluator_mode: str,
    role_name: str,
) -> dict[str, Any]:
    fallback = heuristic_written_evaluation(prompt, response, role_name)
    quality_gate = fallback.get("quality_gate") if isinstance(fallback.get("quality_gate"), dict) else {}
    score_cap = int(quality_gate.get("score_cap", 100))
    user_prompt = f"""
Return strict JSON only.
Evaluate this written assessment as a central unbiased CodeChef-style practice evaluator for {role_name}.
Ignore evaluator personalities and grade with one strict-but-fair standard.
Score only the answer to the asked question. Do not award sympathy marks for off-topic uploads, generic text, file names, or unrelated certificates.
Use 0-10 for responses that do not address the prompt, 10-25 for shallow or mostly irrelevant attempts, 25-55 for partially relevant reasoning, and higher scores only for clearly correct, evidenced, prompt-specific answers.
Return keys: score, feedback, insights, loopholes, recommendations, plagiarism, readiness_score.
plagiarism must be an object with risk and reason.

Question:
{prompt}

Student response:
{response[:12000]}
"""
    ai = await call_ai_json(
        settings,
        "You are a strict but fair written-practice evaluator. Return valid JSON only.",
        user_prompt,
    )
    allow_fallback = _allow_heuristic_fallback(settings)
    if not ai:
        if not allow_fallback:
            _raise_analysis_unavailable("Written assessment")
        return fallback
    merged = {**(fallback if allow_fallback else {}), **ai}
    try:
        raw_score = merged.get("score", fallback["score"] if allow_fallback else None)
        score = max(0, min(100, round(float(raw_score))))
    except Exception:
        if not allow_fallback:
            _raise_analysis_unavailable("Written assessment")
        score = fallback["score"]
    if score > score_cap:
        score = score_cap
        loopholes = merged.get("loopholes") if isinstance(merged.get("loopholes"), list) else []
        for reason in quality_gate.get("cap_reasons", []):
            if reason not in loopholes:
                loopholes.append(reason)
        merged["loopholes"] = loopholes
    merged["score"] = score
    try:
        readiness_score = max(0, min(100, round(float(merged.get("readiness_score", score)))))
    except Exception:
        readiness_score = score
    merged["readiness_score"] = min(readiness_score, score)
    merged["quality_gate"] = quality_gate
    for key in ("insights", "loopholes", "recommendations"):
        if not isinstance(merged.get(key), list):
            merged[key] = fallback[key] if allow_fallback else []
    if not isinstance(merged.get("plagiarism"), dict):
        merged["plagiarism"] = fallback["plagiarism"] if allow_fallback else {
            "risk_score": 0,
            "risk_level": "unavailable",
            "summary": "Plagiarism analysis is not available.",
            "signals": [],
        }
    else:
        plagiarism = merged["plagiarism"]
        if "risk_score" not in plagiarism:
            plagiarism["risk_score"] = 0
        if "risk_level" not in plagiarism:
            plagiarism["risk_level"] = str(plagiarism.get("risk") or "low")
        if "summary" not in plagiarism:
            plagiarism["summary"] = str(plagiarism.get("reason") or (fallback["plagiarism"]["summary"] if allow_fallback else "Plagiarism analysis is not available."))
        if "signals" not in plagiarism or not isinstance(plagiarism["signals"], list):
            plagiarism["signals"] = fallback["plagiarism"]["signals"] if allow_fallback else []
    if quality_gate.get("prompt_overlap", 0) <= 1 and score <= 22:
        plagiarism = merged.get("plagiarism") if isinstance(merged.get("plagiarism"), dict) else {}
        plagiarism["risk_score"] = max(float(plagiarism.get("risk_score", 0) or 0), 65)
        plagiarism["risk_level"] = "question-mismatch"
        plagiarism["summary"] = fallback["plagiarism"]["summary"] if allow_fallback else "The answer does not overlap enough with the prompt for a reliable plagiarism result."
        plagiarism["signals"] = fallback["plagiarism"]["signals"] if allow_fallback else []
        merged["plagiarism"] = plagiarism
    if not merged.get("feedback"):
        merged["feedback"] = fallback["feedback"] if allow_fallback else "Written feedback is not available from the AI evaluator."
    return merged


def capability_domain_breakdown_from_resume(score: float) -> dict[str, float]:
    base = max(25, min(90, score))
    return {dimension: round(max(10, min(100, base - (index * 3) + 6))) for index, dimension in enumerate(DIMENSIONS)}


def heuristic_certificate_evaluation(filename: str, extracted_text: str, role_name: str) -> dict[str, Any]:
    text = f"{filename}\n{extracted_text}".lower()
    role_key = normalize_role(role_name or "")
    expected = ROLE_KEYWORDS[role_key]
    hits = [keyword for keyword in expected if keyword in text]
    has_provider = any(
        token in text
        for token in [
            "coursera",
            "edx",
            "nptel",
            "aws",
            "google",
            "microsoft",
            "ibm",
            "oracle",
            "meta",
            "deeplearning.ai",
            "udemy",
            "linkedin learning",
        ]
    )
    has_verification = any(token in text for token in ["verify", "credential id", "certificate id", "issued", "license", "valid"])
    has_completion = any(token in text for token in ["certificate", "certification", "completed", "completion", "achieved"])
    has_project_signal = any(token in text for token in ["project", "capstone", "hands-on", "lab", "assignment"])
    has_readable_text = len(extracted_text.strip()) >= 40
    is_credential_like = has_provider or has_verification or has_completion

    score = 0
    score += 8 if has_readable_text else 0
    score += min(30, len(hits) * 10)
    score += 18 if has_provider else 0
    score += 16 if has_verification else 0
    score += 12 if has_completion else 0
    score += 8 if has_project_signal else 0
    caps: list[tuple[int, str]] = []
    if not has_readable_text:
        caps.append((8, "File text was not readable enough to verify relevance."))
    if not is_credential_like:
        caps.append((10, "Upload does not look like a verifiable certificate or credential."))
    if not hits:
        caps.append((35 if is_credential_like else 10, f"Credential is not aligned to {role_name}."))
    score, score_cap, cap_reasons = _cap_score(score, caps)

    primary_dimension = "Domain Foundation"
    if role_key in {"ai", "ml"}:
        primary_dimension = "AI Readiness"
    elif role_key == "data":
        primary_dimension = "Data Thinking"
    elif role_key == "software":
        primary_dimension = "Industry Application"
    elif role_key == "pilot":
        primary_dimension = "Domain Foundation"
    if "communication" in text or "presentation" in text:
        primary_dimension = "Communication"
    if "sql" in text or "analytics" in text or "statistics" in text:
        primary_dimension = "Data Thinking"

    base_dimension_score = 0 if score <= 10 else max(10, round(score - 12))
    domain_breakdown = {dimension: base_dimension_score for dimension in DIMENSIONS}
    domain_breakdown[primary_dimension] = score
    if "project" in text or "capstone" in text:
        domain_breakdown["Industry Application"] = max(domain_breakdown["Industry Application"], min(100, score + 5))
    if "communication" in text or "writing" in text or "presentation" in text:
        domain_breakdown["Communication"] = max(domain_breakdown["Communication"], score)

    reasons = []
    if cap_reasons:
        reasons.extend(cap_reasons)
    if hits:
        reasons.append(f"Role-relevant terms detected: {', '.join(hits[:4])}.")
    if has_provider:
        reasons.append("Issuer/provider signal detected.")
    if has_verification:
        reasons.append("Verification or credential-id signal detected.")
    if not has_readable_text:
        reasons.append("Readable text was weak, so the value is discounted.")
    if not reasons:
        reasons.append("Credential has limited visible evidence for the current role.")

    return {
        "score": round(score),
        "readiness_delta": round((score - 50) * 0.15, 2),
        "verdict": "strong" if score >= 75 else ("useful" if score >= 55 else ("irrelevant" if score <= 10 else "weak")),
        "credential_name": filename,
        "issuer": "Detected from document text" if has_provider else "Unknown",
        "detected_skills": hits[:6],
        "domain_breakdown": domain_breakdown,
        "reasons": reasons[:5],
        "risks": cap_reasons or ([] if has_readable_text else ["File text was not readable enough to verify the credential deeply."]),
        "recommendations": [
            "Add a public verification link or credential ID if available.",
            f"Connect the credential to a project or assessment in {primary_dimension}.",
        ],
        "quality_gate": {
            "score_cap": score_cap,
            "cap_reasons": cap_reasons,
            "role_hits": len(hits),
            "credential_like": is_credential_like,
            "readable_text": has_readable_text,
        },
    }


async def analyze_certificate_value(
    settings: Settings,
    filename: str,
    extracted_text: str,
    role_name: str,
) -> dict[str, Any]:
    fallback = heuristic_certificate_evaluation(filename, extracted_text, role_name)
    user_prompt = f"""
Return strict JSON only.
Evaluate this uploaded certificate/credential for role readiness.
Role: {role_name or "Unassigned"}.
Score the credential from 0 to 100 based on issuer credibility, relevance, verification signals, evidence depth, and role fit.
Return keys: score, readiness_delta, verdict, credential_name, issuer, detected_skills, domain_breakdown, reasons, risks, recommendations.
domain_breakdown must contain these six keys exactly: {", ".join(DIMENSIONS)}.
readiness_delta must be a small value between -8 and +8 that represents directional impact before product weighting.

Filename:
{filename}

Extracted credential text:
{extracted_text[:8000]}
"""
    ai = await call_ai_json(
        settings,
        "You are a strict credential evaluator for a career-readiness SaaS. Return valid JSON only.",
        user_prompt,
    )
    allow_fallback = _allow_heuristic_fallback(settings)
    if not ai:
        if not allow_fallback:
            _raise_analysis_unavailable("Credential")
        return fallback
    merged = {**(fallback if allow_fallback else {}), **ai}
    quality_gate = fallback.get("quality_gate") if isinstance(fallback.get("quality_gate"), dict) else {}
    score_cap = int(quality_gate.get("score_cap", 100))
    try:
        raw_score = merged.get("score", fallback["score"] if allow_fallback else None)
        score = max(0, min(100, round(float(raw_score))))
    except Exception:
        if not allow_fallback:
            _raise_analysis_unavailable("Credential")
        score = fallback["score"]
    score = min(score, score_cap)
    merged["score"] = score
    merged["readiness_delta"] = max(-8, min(8, round((score - 50) * 0.15, 2)))
    breakdown = merged.get("domain_breakdown")
    if not isinstance(breakdown, dict):
        breakdown = fallback["domain_breakdown"] if allow_fallback else {dimension: 0 for dimension in DIMENSIONS}
    dimension_cap = score if score < 50 else 100
    merged["domain_breakdown"] = {
        dimension: max(0, min(dimension_cap, round(float(breakdown.get(dimension, fallback["domain_breakdown"][dimension] if allow_fallback else 0)))))
        for dimension in DIMENSIONS
    }
    for key in ("detected_skills", "reasons", "risks", "recommendations"):
        if not isinstance(merged.get(key), list):
            merged[key] = fallback[key] if allow_fallback else []
    for key in ("verdict", "credential_name", "issuer"):
        if not merged.get(key):
            merged[key] = fallback[key] if allow_fallback else "Not available"
    merged["quality_gate"] = quality_gate
    return merged
