from __future__ import annotations

import re
from functools import lru_cache
from typing import Any


DESCRIPTION_BY_PROFILE = {
    "ai_ml": "AI, machine learning, automation, model systems, and applied research.",
    "data_analytics": "Data, reporting, business intelligence, analytics, and decision support.",
    "software_cloud": "Software, cloud, product engineering, platform, and deployment work.",
    "cyber_security": "Security operations, risk, networks, incidents, and digital trust.",
    "design_product": "Design, product experience, user research, and creative technology.",
    "business_finance": "Business, finance, operations, strategy, and commercial analysis.",
    "education_hr": "Teaching, training, counseling, HR, and people development.",
    "aviation": "Aviation, aerospace operations, flight, safety, and transport systems.",
    "culinary_hospitality": "Food, hospitality, tourism, service, and guest operations.",
    "custom": "Role-specific pathway. CELTM can use AI if this needs deeper normalization.",
}


PRIORITY_CAREERS: list[dict[str, Any]] = [
    {"label": "Career Analyst", "profile_key": "business_finance", "aliases": ["CA"], "description": "Career research, advisory analytics, and learner pathway planning."},
    {"label": "Career Advisor", "profile_key": "education_hr", "aliases": ["CA"], "description": "Career guidance, counseling, planning, and student support."},
    {"label": "Compliance Analyst", "profile_key": "business_finance", "aliases": ["CA"], "description": "Compliance monitoring, controls, reporting, and audit coordination."},
    {"label": "Company Secretary", "profile_key": "business_finance", "aliases": ["CS"], "description": "Corporate governance, filings, compliance, and company law."},
    {"label": "Certified Public Accountant", "profile_key": "business_finance", "aliases": ["CPA"], "description": "Accounting, audit, tax, and financial reporting."},
    {"label": "Cost and Management Accountant", "profile_key": "business_finance", "aliases": ["CMA"], "description": "Costing, management accounting, analysis, and controls."},
    {"label": "Civil Services Officer", "profile_key": "business_finance", "aliases": ["IAS", "IPS", "IFS", "UPSC"], "description": "Public administration, governance, policy, and field leadership."},
    {"label": "Indian Administrative Service Officer", "profile_key": "business_finance", "aliases": ["IAS"], "description": "Administration, policy, governance, and public service leadership."},
    {"label": "Indian Police Service Officer", "profile_key": "business_finance", "aliases": ["IPS"], "description": "Law enforcement leadership, public safety, and administration."},
    {"label": "Indian Foreign Service Officer", "profile_key": "business_finance", "aliases": ["IFS"], "description": "Diplomacy, international relations, policy, and public service."},
    {"label": "Product Manager", "profile_key": "business_finance", "aliases": ["PM"], "description": "Product strategy, discovery, roadmap, metrics, and delivery."},
    {"label": "Project Manager", "profile_key": "business_finance", "aliases": ["PM"], "description": "Project planning, delivery, risk, stakeholders, and execution."},
    {"label": "Program Manager", "profile_key": "business_finance", "aliases": ["PM"], "description": "Cross-functional program delivery, planning, and operating rhythm."},
    {"label": "Business Analyst", "profile_key": "business_finance", "aliases": ["BA"], "description": "Requirements, process analysis, reporting, and business cases."},
    {"label": "Brand Analyst", "profile_key": "business_finance", "aliases": ["BA"], "description": "Brand performance, market signals, campaigns, and consumer insight."},
    {"label": "Quality Analyst", "profile_key": "software_cloud", "aliases": ["QA"], "description": "Quality testing, defect analysis, QA workflows, and release checks."},
    {"label": "Quality Assurance Engineer", "profile_key": "software_cloud", "aliases": ["QA Engineer", "QA"], "description": "Test automation, quality systems, and release confidence."},
    {"label": "Human Resources Manager", "profile_key": "education_hr", "aliases": ["HR Manager", "HR"], "description": "Talent, people operations, hiring, engagement, and HR processes."},
    {"label": "User Experience Designer", "profile_key": "design_product", "aliases": ["UX Designer", "UX"], "description": "Research, flows, prototyping, usability, and product experience."},
    {"label": "User Interface Designer", "profile_key": "design_product", "aliases": ["UI Designer", "UI"], "description": "Interface design, visual systems, interaction patterns, and UI craft."},
    {"label": "Software Development Engineer", "profile_key": "software_cloud", "aliases": ["SDE", "Software Engineer"], "description": "Software design, coding, debugging, testing, and delivery."},
    {"label": "Machine Learning Engineer", "profile_key": "ai_ml", "aliases": ["ML Engineer", "MLE"], "description": "ML models, data pipelines, training, evaluation, and deployment."},
    {"label": "Artificial Intelligence Engineer", "profile_key": "ai_ml", "aliases": ["AI Engineer", "AIE"], "description": "AI systems, LLM apps, automation, agents, and model integration."},
]


CATEGORY_DOMAINS: dict[str, list[str]] = {
    "business_finance": [
        "Accounting", "Audit", "Tax", "GST", "Finance", "Financial Planning", "Investment", "Equity Research",
        "Wealth Management", "Banking", "Retail Banking", "Corporate Banking", "Insurance", "Actuarial",
        "Risk Management", "Compliance", "Legal Operations", "Corporate Governance", "Business", "Business Operations",
        "Sales", "Enterprise Sales", "Marketing", "Digital Marketing", "Growth", "Brand", "Market Research",
        "Product", "Project", "Program", "Strategy", "Consulting", "Operations", "Supply Chain", "Procurement",
        "Logistics", "Inventory", "Retail", "Ecommerce", "Customer Success", "Client Relations", "Public Policy",
        "Public Administration", "Economics", "Entrepreneurship", "Startup Operations", "Venture Capital",
        "Private Equity", "Real Estate", "Facilities", "Event Management", "Sports Management", "Media Business",
        "Content Strategy", "Partnerships", "Revenue Operations", "Commercial", "Merchandising", "Import Export",
    ],
    "data_analytics": [
        "Data", "Business Intelligence", "Analytics", "Product Analytics", "Marketing Analytics", "People Analytics",
        "Sales Analytics", "Finance Analytics", "Risk Analytics", "Healthcare Analytics", "Sports Analytics",
        "Learning Analytics", "Operations Analytics", "Customer Analytics", "Web Analytics", "Data Governance",
        "Data Quality", "Data Visualization", "Reporting", "Dashboard", "SQL", "Database", "Data Engineering",
        "Cloud Data", "Big Data", "Research Data", "Statistics", "Decision Science", "Experimentation",
        "Data Product", "Geospatial Data", "Fraud Analytics", "Credit Analytics", "Consumer Insights",
    ],
    "software_cloud": [
        "Software", "Frontend", "Backend", "Full Stack", "Mobile App", "Android", "iOS", "Web", "Cloud",
        "DevOps", "Site Reliability", "Platform", "Infrastructure", "Database", "API", "Microservices",
        "Distributed Systems", "Game", "Embedded Systems", "IoT", "Robotics Software", "AR VR", "Blockchain",
        "Fintech Software", "Healthtech Software", "Edtech Software", "Enterprise Software", "CRM", "ERP",
        "Automation", "No Code", "Low Code", "Technical Support", "IT Support", "Systems", "Network",
        "Release", "QA Automation", "Performance Testing", "Solutions", "Technical Program",
    ],
    "ai_ml": [
        "Artificial Intelligence", "Machine Learning", "Deep Learning", "Generative AI", "LLM", "NLP",
        "Computer Vision", "MLOps", "AI Product", "AI Research", "AI Safety", "Responsible AI", "Data Science",
        "Recommendation Systems", "Speech AI", "Robotics AI", "Predictive Modeling", "AI Automation",
        "Prompt Engineering", "AI Governance", "Knowledge Graph", "Agentic AI",
    ],
    "cyber_security": [
        "Cyber Security", "Information Security", "SOC", "Threat Intelligence", "Incident Response",
        "Cloud Security", "Application Security", "Network Security", "Endpoint Security", "Identity Security",
        "Security Compliance", "GRC", "Penetration Testing", "Digital Forensics", "Fraud Prevention",
        "Data Privacy", "Security Engineering", "Vulnerability Management", "Risk Assurance", "DevSecOps",
    ],
    "design_product": [
        "UX", "UI", "Product Design", "Interaction Design", "Visual Design", "Graphic Design", "Motion Design",
        "Brand Design", "Design Systems", "User Research", "Service Design", "Content Design", "Game Design",
        "Industrial Design", "Interior Design", "Fashion Design", "Creative Direction", "Video Production",
        "Animation", "3D Design", "Illustration", "Photography", "Digital Media", "Publishing",
    ],
    "education_hr": [
        "Teaching", "English Teaching", "Mathematics Teaching", "Science Teaching", "Computer Science Teaching",
        "Instructional Design", "Learning Experience", "Curriculum", "Academic Counseling", "Career Counseling",
        "Psychology", "Clinical Psychology", "Counseling Psychology", "Social Work", "Human Resources",
        "Talent Acquisition", "Learning and Development", "People Operations", "Employee Engagement",
        "Training", "Coaching", "Corporate Training", "Student Success", "Admissions", "Placement",
        "Community Management", "Public Speaking", "Communication",
    ],
    "aviation": [
        "Aviation", "Commercial Pilot", "Airline", "Airport Operations", "Flight Operations", "Cabin Crew",
        "Aircraft Maintenance", "Aerospace", "Drone", "Air Traffic", "Navigation", "Aviation Safety",
        "Ground Operations", "Logistics Aviation", "Travel Operations",
    ],
    "culinary_hospitality": [
        "Culinary", "Chef", "Bakery", "Pastry", "Food Safety", "Food Production", "Restaurant",
        "Hotel Management", "Hospitality", "Tourism", "Travel", "Guest Relations", "Front Office",
        "Housekeeping", "Catering", "Event Hospitality", "Food and Beverage", "Kitchen Operations",
        "Resort Operations", "Cruise Hospitality",
    ],
    "custom": [
        "Medicine", "Nursing", "Pharmacy", "Physiotherapy", "Dentistry", "Veterinary", "Nutrition",
        "Public Health", "Biomedical", "Biotechnology", "Chemistry", "Physics", "Mathematics", "Civil Engineering",
        "Mechanical Engineering", "Electrical Engineering", "Electronics", "Chemical Engineering", "Automobile",
        "Architecture", "Urban Planning", "Law", "Criminal Law", "Corporate Law", "Journalism", "Broadcast Media",
        "Civil Services", "Defense", "Army", "Navy", "Air Force", "Sports Coaching", "Fitness Training",
        "Environmental Science", "Sustainability", "Agriculture", "Marine", "Mining", "Petroleum",
    ],
}


CATEGORY_TITLES: dict[str, list[str]] = {
    "business_finance": ["Analyst", "Associate", "Specialist", "Consultant", "Manager", "Coordinator", "Strategist", "Advisor", "Auditor", "Planner", "Officer", "Lead"],
    "data_analytics": ["Analyst", "Scientist", "Engineer", "Specialist", "Consultant", "Architect", "Manager", "Developer", "Researcher"],
    "software_cloud": ["Engineer", "Developer", "Architect", "Consultant", "Specialist", "Manager", "Lead", "Tester", "Administrator"],
    "ai_ml": ["Engineer", "Scientist", "Researcher", "Specialist", "Consultant", "Developer", "Architect", "Product Manager"],
    "cyber_security": ["Analyst", "Engineer", "Specialist", "Consultant", "Architect", "Manager", "Auditor", "Responder"],
    "design_product": ["Designer", "Researcher", "Strategist", "Specialist", "Manager", "Consultant", "Producer", "Architect"],
    "education_hr": ["Teacher", "Trainer", "Specialist", "Counselor", "Coordinator", "Manager", "Consultant", "Advisor"],
    "aviation": ["Pilot", "Engineer", "Specialist", "Coordinator", "Analyst", "Instructor", "Manager", "Officer"],
    "culinary_hospitality": ["Chef", "Manager", "Specialist", "Coordinator", "Consultant", "Supervisor", "Associate"],
    "custom": ["Specialist", "Analyst", "Consultant", "Researcher", "Engineer", "Manager", "Advisor", "Coordinator"],
}


DOMAIN_ABBREVIATIONS = {
    "Artificial Intelligence": ["AI"],
    "Machine Learning": ["ML"],
    "Generative AI": ["GenAI"],
    "Business Intelligence": ["BI"],
    "Human Resources": ["HR"],
    "User Experience": ["UX"],
    "User Interface": ["UI"],
    "Cyber Security": ["CS"],
    "Information Security": ["IS"],
    "Quality Assurance": ["QA"],
    "Site Reliability": ["SRE"],
    "Search Engine Optimization": ["SEO"],
    "Customer Success": ["CSM"],
    "Civil Services": ["UPSC"],
    "Air Traffic": ["ATC"],
    "Food and Beverage": ["F&B"],
}


SIGNIFICANT_WORDS = {
    "and", "of", "for", "the", "to", "in", "with", "or", "on", "at",
}


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def _compact(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _acronym(value: str) -> str:
    words = [word for word in re.findall(r"[A-Za-z0-9]+", value) if word.lower() not in SIGNIFICANT_WORDS]
    return "".join(word[0].upper() for word in words if word)


def _aliases(label: str, domain: str, title: str, explicit_aliases: list[str] | None = None) -> list[str]:
    aliases = list(explicit_aliases or [])
    acronym = _acronym(label)
    if 2 <= len(acronym) <= 5:
        aliases.append(acronym)
        if len(acronym) <= 4:
            aliases.append(".".join(acronym) + ".")
    for domain_alias in DOMAIN_ABBREVIATIONS.get(domain, []):
        aliases.append(f"{domain_alias} {title}")
        title_acronym = _acronym(title)
        if title_acronym and len(title_acronym) <= 3:
            aliases.append(f"{domain_alias}{title_acronym}")
    unique: list[str] = []
    seen: set[str] = set()
    for alias in aliases:
        clean_alias = _clean(alias)
        key = _compact(clean_alias)
        if key and key != _compact(label) and key not in seen:
            seen.add(key)
            unique.append(clean_alias)
    return unique[:8]


def _make_label(domain: str, title: str) -> str:
    clean_domain = _clean(domain)
    clean_title = _clean(title)
    if clean_domain.lower().endswith(clean_title.lower()):
        return clean_domain
    return f"{clean_domain} {clean_title}"


def _option(label: str, profile_key: str, aliases: list[str] | None = None, description: str | None = None) -> dict[str, Any]:
    return {
        "value": label,
        "label": label,
        "profile_key": profile_key,
        "aliases": aliases or [],
        "description": description or DESCRIPTION_BY_PROFILE.get(profile_key, DESCRIPTION_BY_PROFILE["custom"]),
    }


@lru_cache(maxsize=1)
def career_library_options() -> tuple[dict[str, Any], ...]:
    options: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(option: dict[str, Any]) -> None:
        label = _clean(str(option.get("label") or option.get("value") or ""))
        key = _compact(label)
        if not key or key in seen:
            return
        seen.add(key)
        options.append(
            _option(
                label,
                str(option.get("profile_key") or "custom"),
                [str(alias) for alias in option.get("aliases", []) if str(alias).strip()],
                str(option.get("description") or ""),
            )
        )

    for item in PRIORITY_CAREERS:
        add(item)

    for profile_key, domains in CATEGORY_DOMAINS.items():
        for domain in domains:
            for title in CATEGORY_TITLES[profile_key]:
                label = _make_label(domain, title)
                add(
                    _option(
                        label,
                        profile_key,
                        _aliases(label, domain, title),
                        DESCRIPTION_BY_PROFILE.get(profile_key, DESCRIPTION_BY_PROFILE["custom"]),
                    )
                )

    return tuple(options)
