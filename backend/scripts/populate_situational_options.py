from __future__ import annotations

import argparse
import hashlib
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import Database  # noqa: E402
from app.settings import get_settings  # noqa: E402
from app.supabase_bank import (  # noqa: E402
    _build_question_rows,
    _fetch_table,
    _supabase_write_key,
    sync_supabase_question_bank,
)


CORRECT_ANSWERS: dict[str, dict[str, str]] = {
    "Algorithms": {
        "real-time search on sorted data?": "Binary search",
        "need stable sorting?": "Merge sort",
        "graph traversal for path existence?": "BFS or DFS graph traversal",
        "massive dataset sorting external?": "External merge sort",
        "detect cycle in graph?": "DFS with visited and recursion-stack tracking",
        "fast approximate solution?": "Greedy or heuristic approximation",
        "you need shortest path with negative edges?": "Bellman-Ford algorithm",
        "memory constrained sorting?": "In-place sorting such as heap sort",
        "overlapping subproblems?": "Dynamic programming",
        "shortest path with heuristic?": "A* search",
    },
    "Artificial Intelligence": {
        "need optimal path with heuristic?": "A* search",
        "large labeled dataset available?": "Supervised learning",
        "unknown number of clusters?": "Clustering with model validation",
        "sequential decision making task?": "Reinforcement learning",
        "avoid overfitting in model?": "Regularization with validation",
        "processing natural language text?": "Natural language processing",
        "reduce high-dimensional features?": "Dimensionality reduction such as PCA",
        "need probabilistic classification?": "Naive Bayes or another probabilistic classifier",
        "model needs continuous output?": "Regression model",
        "high variance model indicates?": "Overfitting",
    },
    "Chemistry": {
        "disorder increases means?": "Entropy increases",
        "when does a reaction stop?": "Dynamic equilibrium is reached",
        "need faster reaction rate?": "Add a suitable catalyst",
        "identify acidic solution?": "pH below 7",
        "neutralization reaction?": "Acid reacts with base to form salt and water",
        "increase pressure effect on gas reaction?": "Equilibrium shifts toward fewer gas moles",
        "electron loss is called?": "Oxidation",
        "which is the ideal gas law?": "PV = nRT",
        "example of exothermic reaction?": "Combustion releasing heat",
        "identify the strong acid?": "Hydrochloric acid (HCl)",
    },
    "Cloud Computing": {
        "traffic spikes suddenly?": "Auto scaling",
        "global content delivery needed?": "Content delivery network",
        "need full infrastructure control?": "Infrastructure as a service",
        "run serverless function?": "Function as a service",
        "monitor application logs?": "Cloud logging and monitoring",
        "secure cloud network?": "VPC security groups and network controls",
        "ensure high availability?": "Multi-zone or multi-region deployment",
        "reduce global latency?": "Edge locations or CDN caching",
        "manage containers at scale?": "Kubernetes or container orchestration",
        "use private cloud?": "Dedicated private cloud environment",
    },
    "Cyber Security": {
        "user tricked via email?": "Phishing",
        "attacker targets database?": "SQL injection",
        "secure data in transit?": "TLS or HTTPS encryption",
        "store passwords securely?": "Salted password hashing",
        "defend network perimeter?": "Firewall rules",
        "attacker intercepts messages?": "Man-in-the-middle attack",
        "prevent xss on web app?": "Input validation and output encoding",
        "need secure remote access?": "VPN or zero-trust remote access",
        "ensure data integrity?": "Cryptographic hashing or digital signatures",
        "detect system vulnerabilities?": "Vulnerability scanning",
    },
    "Data Analytics": {
        "handle missing values?": "Imputation or context-aware removal",
        "find hidden patterns?": "Exploratory data analysis",
        "visualize data distribution?": "Histogram or box plot",
        "detect data outliers?": "IQR or z-score outlier detection",
        "predict future value?": "Regression or forecasting model",
        "summarize large dataset?": "Descriptive statistics",
        "process big data?": "Distributed processing such as Spark",
        "visualize business insights?": "Business intelligence dashboard",
        "build data pipeline?": "ETL or ELT pipeline",
        "find relationship between variables?": "Correlation or regression analysis",
    },
    "Data Structures": {
        "need lifo ordering?": "Stack",
        "need fifo ordering?": "Queue",
        "need fast key lookup?": "Hash table or map",
        "need dynamic resizing?": "Dynamic array or vector",
        "manage priority tasks?": "Priority queue or heap",
        "track recursive function calls?": "Call stack",
        "store hierarchical data?": "Tree",
        "model relationships in graph?": "Graph",
        "traversal using bfs?": "Queue",
        "traversal using dfs?": "Stack or recursion",
    },
    "Database Management Systems": {
        "need fast data lookup?": "Index",
        "avoid duplicate data?": "Normalization",
        "retrieve records from table?": "SELECT query",
        "ensure referential integrity?": "Foreign key constraint",
        "modify existing records?": "UPDATE statement",
        "handle transaction failure?": "Rollback",
        "filter specific rows?": "WHERE clause",
        "aggregate column values?": "Aggregate functions such as SUM or AVG",
        "prevent dirty reads?": "Transaction isolation level",
        "define database schema?": "DDL such as CREATE TABLE",
    },
    "DevOps": {
        "automate build process?": "CI build automation",
        "deploy application pipeline?": "CI/CD pipeline",
        "package application in container?": "Docker image",
        "scale application automatically?": "Auto scaling",
        "define infra as code?": "Infrastructure as code",
        "manage server configuration?": "Configuration management",
        "centralize application logs?": "Centralized logging",
        "store and manage secrets?": "Secrets manager",
        "track code changes?": "Version control with Git",
        "monitor system metrics?": "Monitoring and observability",
    },
    "English Communication": {
        "writing formal email?": "Use a clear subject, greeting, concise body, and closing",
        "fix grammar issue?": "Correct the grammar based on tense and agreement",
        "improve writing clarity?": "Use concise and specific wording",
        "fix incorrect spelling?": "Proofread and correct the spelling",
        "make writing professional?": "Use formal tone and precise wording",
        "avoid ambiguous writing?": "Add specific context and remove vague phrasing",
        "fix incorrect sentence?": "Correct grammar and word order",
        "correct plural of child?": "Children",
        "use correct article before apple?": "An apple",
        "when to use passive voice?": "Use passive voice when the action or receiver matters more than the actor",
    },
    "Machine Learning": {
        "model shows high variance?": "Overfitting",
        "data has no labels?": "Unsupervised learning",
        "assign categories to data?": "Classification",
        "minimize training error?": "Gradient descent or loss optimization",
        "reduce feature dimensions?": "Dimensionality reduction such as PCA",
        "prevent overfitting?": "Regularization and cross-validation",
        "standardize feature ranges?": "Feature scaling or standardization",
        "combine multiple models?": "Ensemble learning",
        "measure classification quality?": "Precision, recall, F1, or confusion matrix",
        "optimize the loss function?": "Gradient descent with backpropagation",
    },
    "Mathematics": {
        "find slope of a line?": "Change in y divided by change in x",
        "calculate area of a circle?": "pi r squared",
        "find rate of change?": "Derivative",
        "valid probability range?": "0 to 1 inclusive",
        "find distance between points?": "Distance formula",
        "solve quadratic equation?": "Quadratic formula",
        "find average of values?": "Arithmetic mean",
        "find magnitude of a vector?": "Square root of the sum of squared components",
        "evaluate a limit?": "Find the value approached by the function",
        "simplify logarithm?": "Use logarithm laws",
    },
    "Object-Oriented Programming": {
        "hide internal data?": "Encapsulation",
        "reuse parent class code?": "Inheritance",
        "method behaves differently by type?": "Polymorphism",
        "hide implementation details?": "Abstraction",
        "initialize a new object?": "Constructor",
        "free object memory?": "Destructor or garbage collection",
        "achieve runtime polymorphism?": "Method overriding with dynamic dispatch",
        "achieve compile-time polymorphism?": "Method overloading or operator overloading",
        "restrict data access?": "Access modifiers such as private or protected",
        "model object relationship?": "Association, aggregation, or composition",
    },
}


EXTRA_DISTRACTORS: dict[str, list[str]] = {
    "Algorithms": ["Linear scan", "Bubble sort", "Random search", "Brute force enumeration"],
    "Artificial Intelligence": ["Manual rule list", "Random guessing", "Static lookup table", "Unvalidated memorization"],
    "Chemistry": ["No chemical change occurs", "Only physical shape changes", "Pressure is ignored", "All acids are weak acids"],
    "Cloud Computing": ["Single local server", "Manual server restart", "Unmanaged spreadsheet tracking", "Public open network"],
    "Cyber Security": ["Plain-text storage", "Disable authentication", "Share passwords by email", "Ignore input handling"],
    "Data Analytics": ["Delete all columns", "Guess without checking data", "Use no visualization", "Ignore data quality"],
    "Data Structures": ["Plain text file only", "Unordered list for every case", "Random pointer access", "No structure required"],
    "Database Management Systems": ["Drop the table", "Ignore constraints", "Manual record copying", "No transaction control"],
    "DevOps": ["Manual copy to production", "No version tracking", "Hard-code secrets", "Ignore telemetry"],
    "English Communication": ["Use vague wording", "Ignore grammar", "Use informal slang", "Leave spelling unchecked"],
    "Machine Learning": ["Memorize every row manually", "Ignore validation", "Use labels that do not exist", "Skip feature preparation"],
    "Mathematics": ["Guess the value", "Ignore units and formulas", "Use an unrelated theorem", "Assume every result is negative"],
    "Object-Oriented Programming": ["Use only global variables", "Expose every field publicly", "Duplicate all class code", "Avoid methods entirely"],
}


LETTERS = ("A", "B", "C", "D")


def normalize_text(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def subject_name(row: dict[str, Any]) -> str:
    return str(row.get("subject_name") or row.get("category") or "").strip()


def answer_for(row: dict[str, Any]) -> str:
    subject = subject_name(row)
    question = normalize_text(row.get("question_text"))
    try:
        return CORRECT_ANSWERS[subject][question]
    except KeyError as exc:
        raise KeyError(f"No curated answer for {subject!r}: {question!r}") from exc


def decoys_for(subject: str, correct: str) -> list[str]:
    pool = list(CORRECT_ANSWERS.get(subject, {}).values()) + EXTRA_DISTRACTORS.get(subject, [])
    seen = {normalize_text(correct)}
    decoys: list[str] = []
    for item in pool:
        normalized = normalize_text(item)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        decoys.append(item)
        if len(decoys) == 3:
            return decoys
    raise ValueError(f"Not enough distractors for {subject!r}")


def option_payload(row: dict[str, Any]) -> dict[str, str]:
    subject = subject_name(row)
    correct = answer_for(row)
    choices = decoys_for(subject, correct)
    correct_index = int(hashlib.sha256(str(row["id"]).encode("utf-8")).hexdigest(), 16) % 4
    choices.insert(correct_index, correct)
    payload = {
        "question_id": str(row["id"]),
        "correct_option": LETTERS[correct_index],
    }
    for letter, text in zip(LETTERS, choices):
        payload[f"option_{letter.lower()}"] = f"{letter}. {text}"
    return payload


def load_live_rows(client: httpx.Client, base_url: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    questions = _fetch_table(client, base_url, "questions")
    options = _fetch_table(client, base_url, "mcq_questions")
    return questions, options


def situational_missing_options(
    questions: list[dict[str, Any]],
    options: list[dict[str, Any]],
    only_subject: str | None,
) -> list[dict[str, Any]]:
    option_ids = {str(row.get("question_id") or "") for row in options if row.get("question_id")}
    rows = [
        row
        for row in questions
        if row.get("is_active") is not False
        and "situational" in str(row.get("question_type") or "").lower()
        and str(row.get("id") or "") not in option_ids
    ]
    if only_subject:
        normalized_subject = normalize_text(only_subject)
        rows = [row for row in rows if normalize_text(subject_name(row)) == normalized_subject]
    rows.sort(key=lambda row: (subject_name(row), str(row.get("difficulty") or ""), str(row.get("question_text") or "")))
    return rows


def insert_option_rows(
    client: httpx.Client,
    base_url: str,
    rows: list[dict[str, str]],
) -> None:
    if not rows:
        return
    for start in range(0, len(rows), 100):
        chunk = rows[start : start + 100]
        response = client.post(
            f"{base_url}/rest/v1/mcq_questions",
            json=chunk,
            headers={"Prefer": "return=minimal"},
        )
        response.raise_for_status()


def print_status(label: str, questions: list[dict[str, Any]], options: list[dict[str, Any]]) -> None:
    rows, metadata = _build_question_rows(questions, options)
    usable = Counter(row[3] for row in rows)
    source = Counter(
        str(row.get("question_type") or "unknown").lower()
        for row in questions
        if row.get("is_active") is not False
    )
    print(f"{label}: source={dict(source)} usable={dict(usable)} skipped={metadata.get('skipped')}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Populate missing Supabase option rows for CELTM situational questions.")
    parser.add_argument("--dry-run", action="store_true", help="Validate generated rows without writing to Supabase.")
    parser.add_argument("--subject", help="Limit the repair to one subject name.")
    args = parser.parse_args()

    settings = get_settings()
    key = _supabase_write_key(settings)
    if not settings.supabase_url or not key:
        raise RuntimeError("Supabase URL and service key are required.")

    base_url = settings.supabase_url.rstrip("/")
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=30, headers=headers) as client:
        questions, options = load_live_rows(client, base_url)
        print_status("before", questions, options)
        missing = situational_missing_options(questions, options, args.subject)
        payloads = [option_payload(row) for row in missing]
        print(f"missing_situational_options={len(missing)}")
        print("missing_by_subject", dict(Counter(subject_name(row) for row in missing)))

        if args.dry_run:
            for payload in payloads[:5]:
                preview = {key: payload[key] for key in ("question_id", "correct_option", "option_a", "option_b", "option_c", "option_d")}
                print("preview", preview)
            return

        insert_option_rows(client, base_url, payloads)
        questions_after, options_after = load_live_rows(client, base_url)
        print_status("after", questions_after, options_after)

    database = Database(settings.database_target, postgres_schema=settings.postgres_schema)
    database.init()
    status = sync_supabase_question_bank(settings, database)
    print(
        "synced_status",
        {
            "total_questions": status.get("total_questions"),
            "mcq_count": status.get("mcq_count"),
            "descriptive_count": status.get("descriptive_count"),
            "situational_count": status.get("situational_count"),
            "status": status.get("status"),
        },
    )


if __name__ == "__main__":
    main()
