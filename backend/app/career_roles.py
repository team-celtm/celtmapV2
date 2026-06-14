from __future__ import annotations

import re
from typing import Any

from app.career_library import career_library_options


def normalize_role_key(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")


def compact_role_key(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def clean_role_label(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())[:80]


def display_role_label(value: str | None) -> str:
    raw = clean_role_label(value)
    if not raw:
        return ""
    if raw.isupper() and len(raw) <= 6:
        return raw
    small_words = {"and", "or", "of", "for", "to", "in", "as", "the"}
    words = re.split(r"(\s+)", raw)
    formatted: list[str] = []
    for index, word in enumerate(words):
        if not word.strip():
            formatted.append(word)
            continue
        lower = word.lower()
        if 0 < index < len(words) - 1 and lower in small_words:
            formatted.append(lower)
        elif len(word) <= 4 and word.isupper():
            formatted.append(word)
        else:
            formatted.append(word[:1].upper() + word[1:].lower())
    return "".join(formatted).strip()


def role_tokens(role: str | None) -> set[str]:
    return {token for token in re.split(r"[^a-z0-9]+", str(role or "").lower()) if len(token) > 1}


ROLE_PROFILES: list[dict[str, Any]] = [
    {
        "key": "data_analytics",
        "name": "Data Analytics",
        "keywords": {"data", "analytics", "analyst", "bi", "dashboard", "sql", "excel", "reporting"},
        "weights": {"Data Thinking": 0.34, "Problem Solving": 0.19, "Domain Foundation": 0.16, "Communication": 0.13, "Industry Application": 0.12, "AI Readiness": 0.06},
        "difficulty_penalty": 5.0,
        "certificates": ["Data analytics fundamentals", "SQL/dashboard certificate", "Excel or BI reporting project"],
        "practice": ["Dashboard interpretation drill", "SQL/data-cleaning practice", "Decision memo written practice"],
    },
    {
        "key": "ai_ml",
        "name": "AI / Machine Learning",
        "keywords": {"ai", "ml", "machine", "learning", "llm", "model", "models", "data", "scientist"},
        "weights": {"AI Readiness": 0.34, "Data Thinking": 0.25, "Problem Solving": 0.17, "Domain Foundation": 0.12, "Industry Application": 0.08, "Communication": 0.04},
        "difficulty_penalty": 6.5,
        "certificates": ["Machine learning fundamentals", "Python/data analysis certificate", "Responsible AI basics"],
        "practice": ["Model-evaluation case study", "Data-cleaning mini project", "AI concept written review"],
    },
    {
        "key": "cyber_security",
        "name": "Cyber Security",
        "keywords": {"cyber", "security", "soc", "analyst", "blue", "team", "incident", "threat"},
        "weights": {"Problem Solving": 0.26, "Industry Application": 0.22, "Domain Foundation": 0.20, "Data Thinking": 0.14, "Communication": 0.10, "AI Readiness": 0.08},
        "difficulty_penalty": 7.0,
        "certificates": ["Cybersecurity fundamentals", "Network security basics", "SOC analyst lab completion"],
        "practice": ["Incident triage drill", "Log-analysis practice", "Threat-model written case"],
    },
    {
        "key": "software_cloud",
        "name": "Software / Cloud Engineering",
        "keywords": {"cloud", "devops", "software", "backend", "frontend", "engineer", "developer", "fullstack", "api"},
        "weights": {"Industry Application": 0.27, "Problem Solving": 0.22, "Domain Foundation": 0.20, "Data Thinking": 0.12, "Communication": 0.11, "AI Readiness": 0.08},
        "difficulty_penalty": 5.5,
        "certificates": ["Cloud fundamentals", "Backend API project certificate", "Git/version-control practice"],
        "practice": ["Build and explain one API", "Debugging assessment block", "Deployment checklist exercise"],
    },
    {
        "key": "aviation",
        "name": "Aviation / Pilot",
        "keywords": {"pilot", "aviation", "airline", "aerospace", "drone", "flight", "atpl", "dgca"},
        "weights": {"Domain Foundation": 0.30, "Problem Solving": 0.23, "Communication": 0.19, "Data Thinking": 0.11, "Industry Application": 0.10, "AI Readiness": 0.07},
        "difficulty_penalty": 14.0,
        "certificates": ["Aviation aptitude foundation", "Communication and safety module", "Drone or simulator practice proof"],
        "practice": ["Aptitude and reasoning block", "Safety scenario written case", "Navigation fundamentals practice"],
    },
    {
        "key": "education_hr",
        "name": "Education / People Operations",
        "keywords": {"psychology", "therapist", "counselor", "hr", "human", "teacher", "educator", "trainer"},
        "weights": {"Communication": 0.30, "Domain Foundation": 0.24, "Problem Solving": 0.18, "Data Thinking": 0.10, "Industry Application": 0.10, "AI Readiness": 0.08},
        "difficulty_penalty": 5.0,
        "certificates": ["Communication practice certificate", "Counseling/teaching fundamentals", "Case-writing workshop"],
        "practice": ["Structured feedback exercise", "Learner/candidate scenario case", "Communication assessment block"],
    },
    {
        "key": "business_finance",
        "name": "Business / Finance / Product",
        "keywords": {"finance", "analyst", "business", "product", "manager", "consultant", "strategy", "marketing"},
        "weights": {"Data Thinking": 0.27, "Communication": 0.20, "Problem Solving": 0.19, "Industry Application": 0.17, "Domain Foundation": 0.10, "AI Readiness": 0.07},
        "difficulty_penalty": 5.5,
        "certificates": ["Business analytics basics", "Excel/SQL/data certificate", "Product case-study completion"],
        "practice": ["Market sizing case", "Dashboard interpretation drill", "Decision memo written practice"],
    },
    {
        "key": "chartered_accounting",
        "name": "Chartered Accounting",
        "keywords": {"ca", "chartered", "accountant", "accounting", "audit", "auditing", "tax", "taxation", "gst", "compliance", "finance", "financial"},
        "weights": {"Domain Foundation": 0.28, "Data Thinking": 0.23, "Problem Solving": 0.18, "Communication": 0.13, "Industry Application": 0.13, "AI Readiness": 0.05},
        "difficulty_penalty": 8.0,
        "certificates": ["Accounting fundamentals", "Taxation basics", "Auditing and compliance foundation"],
        "practice": ["Financial statement analysis", "Tax and compliance case practice", "Audit scenario review"],
    },
    {
        "key": "design_product",
        "name": "Design / Product Experience",
        "keywords": {"ux", "ui", "designer", "design", "figma", "research", "prototype", "product"},
        "weights": {"Communication": 0.24, "Problem Solving": 0.22, "Industry Application": 0.20, "Domain Foundation": 0.16, "Data Thinking": 0.11, "AI Readiness": 0.07},
        "difficulty_penalty": 5.5,
        "certificates": ["UX fundamentals", "Figma or prototyping proof", "User research case study"],
        "practice": ["User-flow critique", "Design case study", "Portfolio proof review"],
    },
    {
        "key": "culinary_hospitality",
        "name": "Culinary / Hospitality",
        "keywords": {"chef", "cook", "culinary", "kitchen", "food", "hospitality", "hotel", "restaurant", "catering"},
        "weights": {"Industry Application": 0.28, "Communication": 0.22, "Domain Foundation": 0.20, "Problem Solving": 0.16, "Data Thinking": 0.08, "AI Readiness": 0.06},
        "difficulty_penalty": 6.0,
        "certificates": ["Food safety certificate", "Culinary fundamentals proof", "Hospitality operations practice"],
        "practice": ["Kitchen operations scenario", "Customer-service written case", "Food safety foundations"],
    },
]

DEFAULT_ROLE_PROFILE: dict[str, Any] = {
    "key": "custom",
    "name": "Custom role",
    "keywords": set(),
    "weights": {"Problem Solving": 0.24, "Domain Foundation": 0.22, "Communication": 0.18, "Industry Application": 0.16, "Data Thinking": 0.12, "AI Readiness": 0.08},
    "difficulty_penalty": 8.0,
    "certificates": ["Role foundation certificate", "Project evidence review", "Communication or case-writing practice"],
    "practice": ["Role-specific written case", "Foundation assessment block", "Mentor-reviewed proof artifact"],
}

CUSTOM_SUBJECTS = [
    "English Communication",
    "Aptitude",
    "Logical Reasoning",
    "Programming Fundamentals",
    "Mathematics",
    "Data Analytics",
]

CAREER_ROLE_CATALOG: list[dict[str, Any]] = [
    {
        "label": "AI / Machine Learning Engineer",
        "profile_key": "ai_ml",
        "aliases": ["AI Engineer", "ML Engineer", "Machine Learning Engineer", "Data Scientist"],
        "description": "AI, ML, model evaluation, and applied data systems.",
        "subjects": ["Machine Learning", "Artificial Intelligence", "Python Fundamentals for ML", "ML Systems", "Data Analytics", "Mathematics", "Algorithms", "Data Structures"],
        "adjacent_roles": ["Data Analyst", "ML Intern", "AI Project Assistant"],
    },
    {
        "label": "Data Analyst",
        "profile_key": "data_analytics",
        "aliases": ["Data Analytics", "Business Intelligence Analyst", "BI Analyst"],
        "description": "SQL, dashboards, analytics, and data interpretation.",
        "subjects": ["Data Analytics", "Database Management Systems", "Mathematics", "Python Fundamentals for ML", "Logical Reasoning", "English Communication", "Business Analytics"],
        "adjacent_roles": ["BI Analyst", "Reporting Analyst", "Data Operations Associate"],
    },
    {
        "label": "SOC Analyst",
        "profile_key": "cyber_security",
        "aliases": ["Cyber Security Analyst", "Cybersecurity Analyst", "Security Analyst"],
        "description": "Security monitoring, networks, incidents, and threat triage.",
        "subjects": ["Cyber Security", "Computer Networks", "Operating Systems", "Cloud Computing", "Logical Reasoning", "English Communication"],
        "adjacent_roles": ["SOC Trainee", "Network Support Analyst", "IT Security Associate"],
    },
    {
        "label": "Full Stack Developer",
        "profile_key": "software_cloud",
        "aliases": ["Software Engineer", "Frontend Developer", "Backend Developer", "Cloud Engineer", "DevOps Engineer", "Full Stack Development"],
        "description": "Software, web, backend, cloud, and deployment practice.",
        "subjects": ["Cloud Computing", "DevOps", "Computer Networks", "Operating Systems", "Database Management Systems", "Software Engineering", "Programming Fundamentals", "Data Structures", "Algorithms", "Web Development"],
        "adjacent_roles": ["Frontend Developer", "Backend Developer", "Cloud Support Engineer"],
    },
    {
        "label": "Pilot / Aviation",
        "profile_key": "aviation",
        "aliases": ["Pilot", "Commercial Pilot", "Aviation", "Drone Pilot"],
        "description": "Aviation aptitude, navigation, safety, and communication.",
        "subjects": ["Aptitude", "Logical Reasoning", "Mathematics", "Physics", "English Communication", "Aviation Safety", "Navigation Fundamentals"],
        "adjacent_roles": ["Aviation Operations Analyst", "Drone Systems Trainee", "Ground Operations Trainee"],
    },
    {
        "label": "Teacher / HR",
        "profile_key": "education_hr",
        "aliases": ["Teacher", "Educator", "Trainer", "HR", "People Operations", "Counselor"],
        "description": "Teaching, training, counseling, and people operations.",
        "subjects": ["English Communication", "Social Science", "Logical Reasoning", "Aptitude", "Teaching Fundamentals", "People Operations"],
        "adjacent_roles": ["Training Coordinator", "HR Associate", "Teaching Assistant"],
    },
    {
        "label": "Product Manager",
        "profile_key": "business_finance",
        "aliases": ["Business Analyst", "Finance Analyst", "Product Analyst", "Consultant"],
        "description": "Product, business, finance, strategy, and case practice.",
        "subjects": ["Data Analytics", "Database Management Systems", "Mathematics", "English Communication", "Logical Reasoning", "Business Analytics", "Product Case Practice"],
        "adjacent_roles": ["Business Analyst", "Product Analyst", "Finance Analyst"],
    },
    {
        "label": "Chartered Accountant",
        "profile_key": "chartered_accounting",
        "aliases": ["CA", "C.A.", "Accountant", "Accounting", "Auditor", "Tax Consultant"],
        "description": "Accounting, taxation, auditing, compliance, and financial reporting.",
        "subjects": ["Accounting", "Financial Accounting", "Taxation", "Auditing", "Business Law", "Economics", "Mathematics", "Data Analytics", "English Communication", "Logical Reasoning"],
        "adjacent_roles": ["Accounting Trainee", "Audit Assistant", "Tax Associate"],
    },
    {
        "label": "UX/UI Designer",
        "profile_key": "design_product",
        "aliases": ["UI Designer", "UX Designer", "Product Designer"],
        "description": "Product thinking, communication, user research, and portfolio proof.",
        "subjects": ["Design Fundamentals", "User Research", "Product Case Practice", "English Communication", "Logical Reasoning", "Data Analytics"],
        "adjacent_roles": ["UX Research Assistant", "Product Design Intern", "UI Designer"],
    },
    {
        "label": "Chef / Hospitality",
        "profile_key": "culinary_hospitality",
        "aliases": ["Chef", "Culinary", "Hospitality", "Hotel Management"],
        "description": "Culinary fundamentals, food safety, and hospitality operations.",
        "subjects": ["English Communication", "Aptitude", "Chemistry", "Food Safety", "Culinary Fundamentals", "Hospitality Operations"],
        "adjacent_roles": ["Kitchen Operations Trainee", "Food Safety Assistant", "Hospitality Associate"],
    },
]


def career_role_options() -> list[dict[str, Any]]:
    options = [
        {
            "value": str(item["label"]),
            "label": str(item["label"]),
            "profile_key": str(item["profile_key"]),
            "aliases": list(item.get("aliases") or []),
            "description": str(item.get("description") or ""),
            "is_catalog": True,
        }
        for item in CAREER_ROLE_CATALOG
    ]
    seen = {compact_role_key(option["label"]) for option in options}
    for item in career_library_options():
        key = compact_role_key(str(item.get("label") or item.get("value") or ""))
        if not key or key in seen:
            continue
        seen.add(key)
        options.append({**item, "is_catalog": False})
        if len(options) >= 1000:
            break
    return options


def career_role_entry(value: str | None) -> dict[str, Any] | None:
    key = normalize_role_key(value)
    compact_key = compact_role_key(value)
    if not key and not compact_key:
        return None
    for item in CAREER_ROLE_CATALOG:
        candidates = [str(item["label"]), *[str(alias) for alias in item.get("aliases", [])]]
        normalized_candidates = {normalize_role_key(candidate) for candidate in candidates}
        compact_candidates = {compact_role_key(candidate) for candidate in candidates}
        if key in normalized_candidates or compact_key in compact_candidates:
            return item
    return None


def canonical_career_role(value: str | None, required: bool = True, allow_custom: bool = False) -> str | None:
    raw = clean_role_label(value)
    if not raw:
        if required:
            raise ValueError("Desired role is required")
        return None
    entry = career_role_entry(raw)
    if not entry:
        if allow_custom:
            return display_role_label(raw)
        raise ValueError("Choose a supported career role from the dropdown. This role is not available yet.")
    return str(entry["label"])


def profile_by_key(role_key: str | None) -> dict[str, Any]:
    for profile in ROLE_PROFILES:
        if profile["key"] == role_key:
            return profile
    return DEFAULT_ROLE_PROFILE


def pick_role_profile(tokens: set[str]) -> tuple[dict[str, Any], set[str]]:
    best_profile = DEFAULT_ROLE_PROFILE
    best_overlap: set[str] = set()
    best_score = 0
    for profile in ROLE_PROFILES:
        overlap = tokens & set(profile["keywords"])
        score = len(overlap) * 4
        if any(token in {"ai", "ml", "pilot", "aviation", "cyber", "security", "ca", "tax"} for token in overlap):
            score += 2
        if score > best_score:
            best_profile = profile
            best_overlap = overlap
            best_score = score
    return best_profile, best_overlap


def role_profile_for_label(role: str | None) -> tuple[dict[str, Any], set[str]]:
    tokens = role_tokens(role)
    entry = career_role_entry(role)
    if not entry:
        return pick_role_profile(tokens)
    profile = profile_by_key(str(entry.get("profile_key") or ""))
    matched_keywords = tokens & set(profile["keywords"])
    if not matched_keywords:
        matched_keywords = tokens & role_tokens(str(entry["label"]))
    return profile, matched_keywords


def role_candidate_names(desired_role: str | None, focus_role: str | None) -> list[str]:
    candidates: list[str] = []
    for role in [desired_role, focus_role]:
        entry = career_role_entry(role)
        if entry:
            candidates.append(str(entry["label"]))
        elif clean_role_label(role):
            candidates.append(display_role_label(role))
    candidates.extend(str(item["label"]) for item in CAREER_ROLE_CATALOG)
    seen: set[str] = set()
    unique: list[str] = []
    for candidate in candidates:
        key = normalize_role_key(candidate)
        if key and key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def subjects_for_role(focus_role: str | None) -> tuple[str, str, list[str]]:
    entry = career_role_entry(focus_role)
    role_label = str(entry["label"]) if entry else display_role_label(focus_role)
    if not role_label:
        return "custom", "your active career aim", CUSTOM_SUBJECTS
    if not entry:
        return "custom", role_label, CUSTOM_SUBJECTS
    return str(entry["profile_key"]), role_label, list(entry.get("subjects") or CUSTOM_SUBJECTS)


def adjacent_fits_for_role(role: str | None, role_profile_key: str | None = None) -> list[str]:
    entry = career_role_entry(role)
    if entry:
        return list(entry.get("adjacent_roles") or [])
    profile_key = str(role_profile_key or "custom")
    for item in CAREER_ROLE_CATALOG:
        if item.get("profile_key") == profile_key:
            return list(item.get("adjacent_roles") or [])
    return ["Foundation trainee role", "Assistant analyst role", "Entry-level operations role"]
