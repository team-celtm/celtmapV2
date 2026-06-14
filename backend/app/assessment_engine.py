from __future__ import annotations

import re
import random
from typing import Any

from fastapi import HTTPException

from app.database import (
    DIMENSIONS,
    LEVEL_WEIGHTS,
    Database,
    from_json,
    new_id,
    now_iso,
    to_json,
)


ASSESSMENT_LENGTHS = {"quick": 6, "standard": 9, "deep": 10}


def _difficulty_weight(difficulty: str) -> float:
    return float(LEVEL_WEIGHTS.get(difficulty, 1.0))


def _weighted_attempt_score(answers: list[dict[str, Any]]) -> tuple[float, float, float]:
    total_score = sum(float(answer.get("score_awarded") or 0.0) for answer in answers)
    max_score = sum(_difficulty_weight(str(answer.get("difficulty") or "")) for answer in answers)
    score = round((total_score / max_score) * 100, 2) if max_score > 0 else 0.0
    return score, round(total_score, 2), round(max_score, 2)


def _normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _target_dimensions(category: str) -> list[str]:
    normalized = _normalize_key(category or "")
    if normalized in {"", "capability", "capability-profile", "all"}:
        return DIMENSIONS
    for dimension in DIMENSIONS:
        if _normalize_key(dimension) == normalized:
            return [dimension]
    raise HTTPException(status_code=404, detail="Subject not available at the moment")


def _target_scope(category: str, question_pool: list[dict[str, Any]]) -> tuple[str, list[str]]:
    normalized = _normalize_key(category or "")
    if normalized in {"", "capability", "capability-profile", "all"}:
        return "dimension", DIMENSIONS

    subjects = sorted(
        {
            str(row.get("subject_name") or "").strip()
            for row in question_pool
            if str(row.get("subject_name") or "").strip()
        }
    )
    for subject in subjects:
        if _normalize_key(subject) == normalized:
            return "subject_name", [subject]

    for dimension in DIMENSIONS:
        if _normalize_key(dimension) == normalized:
            return "dimension", [dimension]

    raise HTTPException(status_code=404, detail="Subject not available at the moment")


def _question_type_order(question_type: str) -> list[str]:
    normalized = (question_type or "MIXED").upper()
    if normalized == "MCQ":
        return ["MCQ"]
    if normalized == "SITUATIONAL":
        return ["SITUATIONAL"]
    return ["MCQ", "SITUATIONAL"]


def public_question(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "question_id": row["id"],
        "id": row["id"],
        "dimension": row["dimension"],
        "category": row.get("subject_name") or row["dimension"],
        "subject_name": row.get("subject_name") or row["dimension"],
        "difficulty": row["difficulty"],
        "question_type": row["question_type"],
        "scenario": row["scenario"],
        "question_text": row["question_text"],
        "options": from_json(row["options"], []),
    }


def _question_snapshot(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "dimension": row["dimension"],
        "subject_name": row.get("subject_name") or row["dimension"],
        "difficulty": row["difficulty"],
        "question_type": row["question_type"],
        "scenario": row.get("scenario"),
        "question_text": row["question_text"],
        "options": row["options"],
        "correct_answer": row.get("correct_answer", ""),
        "explanation": row.get("explanation"),
    }


def _metadata_question(metadata: dict[str, Any], question_id: str) -> dict[str, Any] | None:
    snapshots = metadata.get("assigned_question_snapshots")
    if not isinstance(snapshots, list):
        return None
    for snapshot in snapshots:
        if isinstance(snapshot, dict) and snapshot.get("id") == question_id:
            return snapshot
    return None


def create_assessment(
    db: Database,
    user_id: str,
    mode: str = "quick",
    assessment_type: str = "capability",
    question_type: str = "MIXED",
    category: str = "capability-profile",
    assignment_id: str | None = None,
    question_ids: list[str] | None = None,
    question_pool: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if question_pool is None:
        raise HTTPException(status_code=503, detail="Supabase question bank is required for assessments")
    if not question_pool:
        raise HTTPException(status_code=503, detail="Supabase returned no usable assessment questions")

    normalized_mode = mode if mode in ASSESSMENT_LENGTHS else "quick"
    assessment_id = new_id("assess")
    total_per_dim = ASSESSMENT_LENGTHS[normalized_mode]
    question_type_order = _question_type_order(question_type)
    requested_ids = []
    seen_requested_ids = set()
    for question_id in question_ids or []:
        normalized_id = str(question_id or "").strip()
        if normalized_id and normalized_id not in seen_requested_ids:
            seen_requested_ids.add(normalized_id)
            requested_ids.append(normalized_id)

    # Fetch previously answered questions to avoid duplicates
    past_answers = db.query_all(
        "SELECT DISTINCT aa.question_id FROM assessment_answers aa JOIN assessments a ON aa.assessment_id = a.id WHERE a.user_id = ?",
        (user_id,)
    )
    seen_question_ids = {row["question_id"] for row in past_answers}

    # Pre-select questions to support a stable full-screen attempt with free navigation.
    assigned_questions = []
    assigned_snapshots: list[dict[str, Any]] = []
    if requested_ids:
        rows = [
            row
            for row in question_pool
            if row.get("id") in requested_ids
            and row.get("question_type") in question_type_order
            and str(row.get("options") or "[]") != "[]"
        ]
        id_to_row = {row["id"]: row for row in rows}
        ordered_rows = [id_to_row[question_id] for question_id in requested_ids if question_id in id_to_row]
        assigned_questions = [row["id"] for row in ordered_rows]
        assigned_snapshots = [_question_snapshot(row) for row in ordered_rows]
        target_dimensions = []
        for row in ordered_rows:
            if row["dimension"] not in target_dimensions:
                target_dimensions.append(row["dimension"])
        if not target_dimensions:
            target_dimensions = _target_dimensions(category)
    else:
        target_field, target_values = _target_scope(category, question_pool)
        for target_value in target_values:
            selected_for_dimension: list[str] = []
            for qtype in question_type_order:
                remaining = total_per_dim - len(selected_for_dimension)
                if remaining <= 0:
                    break
                all_candidates = [
                    row
                    for row in question_pool
                    if row.get(target_field) == target_value
                    and row.get("question_type") == qtype
                    and str(row.get("options") or "[]") != "[]"
                ]
                unseen_candidates = [row for row in all_candidates if row["id"] not in seen_question_ids]
                seen_candidates = [row for row in all_candidates if row["id"] in seen_question_ids]

                random.shuffle(unseen_candidates)
                random.shuffle(seen_candidates)
                candidates = unseen_candidates + seen_candidates

                rows = candidates[:remaining]
                selected_for_dimension.extend([row["id"] for row in rows])
                assigned_snapshots.extend(_question_snapshot(row) for row in rows)
            assigned_questions.extend(selected_for_dimension)
        target_dimensions = []
        for snapshot in assigned_snapshots:
            dimension = str(snapshot.get("dimension") or "").strip()
            if dimension and dimension not in target_dimensions:
                target_dimensions.append(dimension)

    if not assigned_questions:
        raise HTTPException(status_code=404, detail="Subject not available at the moment")

    db.execute(
        """
        INSERT INTO assessments (
            id, user_id, assignment_id, status, mode, total_per_dimension, next_dimension_index,
            assessment_type, question_type, category, metadata, created_at
        )
        VALUES (?, ?, ?, 'in_progress', ?, ?, 0, ?, ?, ?, ?, ?)
        """,
        (
            assessment_id,
            user_id,
            assignment_id,
            normalized_mode,
            total_per_dim,
            assessment_type,
            question_type,
            category,
            to_json(
                {
                    "assigned_questions": assigned_questions,
                    "target_dimensions": target_dimensions,
                    "requested_question_type": question_type,
                    "assignment_id": assignment_id,
                    "source_question_ids": requested_ids,
                    "assigned_question_snapshots": assigned_snapshots,
                    "question_source": "supabase_live",
                }
            ),
            now_iso(),
        ),
    )
    db.execute_many(
        """
        INSERT INTO assessment_dimension_state (
            assessment_id, dimension, current_level, updated_at
        )
        VALUES (?, ?, 'Basic', ?)
        """,
        [(assessment_id, dimension, now_iso()) for dimension in dict.fromkeys(target_dimensions)],
    )
    return read_assessment(db, assessment_id, user_id)


def read_assessment(db: Database, assessment_id: str, user_id: str | None = None) -> dict[str, Any]:
    if user_id:
        row = db.query_one("SELECT * FROM assessments WHERE id = ? AND user_id = ?", (assessment_id, user_id))
    else:
        row = db.query_one("SELECT * FROM assessments WHERE id = ?", (assessment_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "assignment_id": row.get("assignment_id"),
        "category": row["category"],
        "assessment_type": row["assessment_type"],
        "question_type": row["question_type"],
        "score": row["score"],
        "status": row["status"],
        "created_at": row["created_at"],
        "completed_at": row["completed_at"],
        "capability_profile": from_json(row["capability_profile"], {}),
        "metadata": from_json(row["metadata"], {}),
        "mode": row["mode"],
        "total_per_dimension": row["total_per_dimension"],
    }


def get_assigned_questions(db: Database, assessment_id: str, user_id: str) -> dict[str, Any]:
    assessment = db.query_one("SELECT * FROM assessments WHERE id = ? AND user_id = ?", (assessment_id, user_id))
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    metadata = from_json(assessment["metadata"], {})
    assigned_ids = metadata.get("assigned_questions", [])

    questions = []
    snapshots = metadata.get("assigned_question_snapshots")
    if isinstance(snapshots, list) and snapshots:
        id_to_row = {row.get("id"): row for row in snapshots if isinstance(row, dict)}
        questions = [id_to_row[qid] for qid in assigned_ids if qid in id_to_row]
    elif assigned_ids:
        raise HTTPException(
            status_code=409,
            detail="Assessment question snapshots are missing; restart the Supabase-backed assessment.",
        )

    # Fetch existing answers to populate state
    answers = db.query_all(
        "SELECT question_id, selected_answer FROM assessment_answers WHERE assessment_id = ?",
        (assessment_id,)
    )
    answer_map = {ans["question_id"]: ans["selected_answer"] for ans in answers}

    return {
        "status": assessment["status"],
        "assessment_id": assessment_id,
        "questions": [public_question(q) for q in questions],
        "answers": answer_map,
        "progress": progress_snapshot(db, assessment_id)
    }


def submit_answer(
    db: Database,
    assessment_id: str,
    user_id: str,
    question_id: str,
    selected_answer: str,
    time_taken_seconds: int | None,
) -> dict[str, Any]:
    assessment = db.query_one("SELECT * FROM assessments WHERE id = ? AND user_id = ?", (assessment_id, user_id))
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    if assessment["status"] == "completed":
        raise HTTPException(status_code=409, detail="Assessment is already completed")

    metadata = from_json(assessment["metadata"], {})
    question = _metadata_question(metadata, question_id)
    if not question:
        raise HTTPException(
            status_code=409,
            detail="Assessment question snapshot is missing; restart the Supabase-backed assessment.",
        )

    is_correct = selected_answer == question["correct_answer"]
    weight = LEVEL_WEIGHTS.get(question["difficulty"], 1.0)
    score_awarded = weight if is_correct else 0.0

    # Upsert answer (allow changing mind before submit)
    existing = db.query_one(
        "SELECT id FROM assessment_answers WHERE assessment_id = ? AND question_id = ?",
        (assessment_id, question_id),
    )

    if existing:
        db.execute(
            """
            UPDATE assessment_answers
            SET selected_answer = ?, is_correct = ?, score_awarded = ?, time_taken_seconds = ?, answered_at = ?
            WHERE id = ?
            """,
            (selected_answer, 1 if is_correct else 0, score_awarded, time_taken_seconds, now_iso(), existing["id"])
        )
    else:
        db.execute(
            """
            INSERT INTO assessment_answers (
                id, assessment_id, user_id, question_id, selected_answer,
                is_correct, score_awarded, time_taken_seconds, answered_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id("ans"),
                assessment_id,
                user_id,
                question_id,
                selected_answer,
                1 if is_correct else 0,
                score_awarded,
                time_taken_seconds,
                now_iso(),
            ),
        )

    return {
        "status": "recorded",
        "assessment_id": assessment_id,
        "question_id": question_id,
        "progress": progress_snapshot(db, assessment_id),
    }


def progress_snapshot(db: Database, assessment_id: str) -> dict[str, Any]:
    assessment = db.query_one("SELECT total_per_dimension, metadata FROM assessments WHERE id = ?", (assessment_id,))
    metadata = from_json(assessment["metadata"], {}) if assessment else {}
    assigned = metadata.get("assigned_questions", [])
    total = len(assigned) if isinstance(assigned, list) else 0
    if total == 0 and assessment:
        target_dimensions = metadata.get("target_dimensions")
        dimension_count = len(target_dimensions) if isinstance(target_dimensions, list) and target_dimensions else len(DIMENSIONS)
        total = int(assessment["total_per_dimension"]) * dimension_count
    answered_row = db.query_one(
        "SELECT COUNT(*) AS count FROM assessment_answers WHERE assessment_id = ?",
        (assessment_id,),
    )
    answered = int(answered_row["count"]) if answered_row else 0
    return {"answered": answered, "total_required": total, "percent": round((answered / total) * 100, 2) if total else 0}


async def complete_assessment(
    db: Database,
    assessment_id: str,
    user_id: str,
    force: bool = False,
) -> dict[str, Any]:
    assessment = db.query_one("SELECT * FROM assessments WHERE id = ? AND user_id = ?", (assessment_id, user_id))
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    if assessment["status"] == "completed":
        existing = read_assessment(db, assessment_id, user_id)
        answers = db.query_all("SELECT * FROM assessment_answers WHERE assessment_id = ?", (assessment_id,))
        return completion_payload(existing, answers)

    progress = progress_snapshot(db, assessment_id)
    if not force and progress["answered"] < progress["total_required"]:
        raise HTTPException(status_code=409, detail="Assessment is not complete yet")

    metadata = from_json(assessment["metadata"], {})
    snapshots = metadata.get("assigned_question_snapshots")
    snapshot_by_id = {
        row.get("id"): row
        for row in snapshots
        if isinstance(row, dict) and row.get("id")
    } if isinstance(snapshots, list) else {}

    raw_answers = db.query_all(
        "SELECT * FROM assessment_answers WHERE assessment_id = ?",
        (assessment_id,),
    )
    answers: list[dict[str, Any]] = []
    for answer in raw_answers:
        hydrated = dict(answer)
        question = snapshot_by_id.get(answer["question_id"])
        if not question:
            raise HTTPException(
                status_code=409,
                detail="Assessment question snapshots are missing; this attempt cannot be graded safely.",
            )
        hydrated["dimension"] = question["dimension"]
        hydrated["difficulty"] = question["difficulty"]
        hydrated["question_text"] = question["question_text"]
        answers.append(hydrated)

    target_dimensions = metadata.get("target_dimensions")
    scored_dimensions = (
        [dim for dim in target_dimensions if dim in DIMENSIONS]
        if isinstance(target_dimensions, list)
        else DIMENSIONS
    )
    dimension_scores = {dim: {"total_score": 0.0, "max_score": 0.0} for dim in scored_dimensions}
    for ans in answers:
        dim = ans["dimension"]
        if dim not in dimension_scores:
            dimension_scores[dim] = {"total_score": 0.0, "max_score": 0.0}
        weight = _difficulty_weight(ans["difficulty"])
        dimension_scores[dim]["total_score"] += ans["score_awarded"]
        dimension_scores[dim]["max_score"] += weight

    profile: dict[str, float] = {}
    highest: dict[str, str] = {dim: "Basic" for dim in dimension_scores}
    for dim in dimension_scores:
        max_s = dimension_scores[dim]["max_score"]
        tot_s = dimension_scores[dim]["total_score"]
        if max_s > 0:
            profile[dim] = round((tot_s / max_s) * 100, 2)
        db.execute(
            """
            UPDATE assessment_dimension_state
            SET total_score = ?, max_score = ?, updated_at = ?
            WHERE assessment_id = ? AND dimension = ?
            """,
            (tot_s, max_s, now_iso(), assessment_id, dim)
        )

    score, total_score, max_score = _weighted_attempt_score(answers)

    metadata["highest_level_reached"] = highest
    metadata["scoring"] = {
        "method": "difficulty_weighted_total",
        "total_score": total_score,
        "max_score": max_score,
        "weights": dict(LEVEL_WEIGHTS),
    }

    # Rule-based inference keeps MCQ/situational scoring deterministic and avoids LLM quota use.
    total = len(answers)
    correct = sum(1 for a in answers if a.get("is_correct", 0))
    wrong = total - correct

    wrong_topics = [a["question_text"][:50] for a in answers if not a.get("is_correct", 0)]
    inference = _rule_based_inference(profile, correct, total, wrong_topics)

    metadata["inference"] = inference
    metadata["analytics"] = {
        "correct": correct,
        "wrong": wrong,
        "total": total
    }

    db.execute(
        """
        UPDATE assessments
        SET status = 'completed',
            score = ?,
            capability_profile = ?,
            metadata = ?,
            completed_at = ?
        WHERE id = ?
        """,
        (
            score,
            to_json(profile),
            to_json(metadata),
            now_iso(),
            assessment_id,
        ),
    )

    profile_row = db.query_one("SELECT metadata FROM profiles WHERE user_id = ?", (user_id,))
    prof_metadata = from_json(profile_row["metadata"], {}) if profile_row else {}
    prof_metadata["last_capability_profile"] = profile
    prof_metadata["assessment_readiness"] = score
    db.execute(
        "UPDATE profiles SET metadata = ?, updated_at = ? WHERE user_id = ?",
        (to_json(prof_metadata), now_iso(), user_id),
    )

    completed = read_assessment(db, assessment_id, user_id)
    return completion_payload(completed, answers)


def completion_payload(assessment: dict[str, Any], answers: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(answers)
    correct = sum(1 for answer in answers if answer.get("is_correct", 0))
    raw_metadata = assessment.get("metadata", {})
    metadata = raw_metadata if isinstance(raw_metadata, dict) else from_json(raw_metadata, {})

    return {
        "assessment_id": assessment["id"],
        "score": assessment["score"] or 0,
        "correct_answers": correct,
        "total_questions": total,
        "status": assessment["status"],
        "capability_profile": assessment.get("capability_profile", {}),
        "detailed_feedback": [],
        "analytics": metadata.get("analytics", {"correct": correct, "wrong": total - correct, "total": total}),
        "inference": metadata.get("inference", {})
    }


def _rule_based_inference(
    profile: dict[str, float],
    correct: int,
    total: int,
    wrong_topics: list[str],
) -> dict[str, Any]:
    ordered = sorted(profile.items(), key=lambda item: item[1], reverse=True)
    strengths = [name for name, score in ordered if score >= 70][:3]
    if not strengths and ordered:
        strengths = [ordered[0][0]]
    weak = [name for name, score in sorted(profile.items(), key=lambda item: item[1]) if score < 70][:4]

    hidden_skills = [
        f"Applied {name}" for name, score in ordered if score >= 75
    ][:3]
    areas_of_betterment = weak or ["Practice consistency across the attempted subject"]

    recommendations = [
        f"Reattempt {areas_of_betterment[0]} after reviewing missed scenarios.",
        "Write one short explanation for every incorrect answer.",
        "Use the written protocol to prove reasoning depth for this subject.",
    ]
    if wrong_topics:
        recommendations.insert(0, f"Review missed topic: {wrong_topics[0]}")

    return {
        "insight": f"Rule-based scoring recorded {correct} correct answers out of {total}.",
        "strengths": strengths or ["Assessment attempt completed"],
        "risks": areas_of_betterment[:3],
        "recommendations": recommendations[:4],
        "hidden_skills": hidden_skills,
        "areas_of_betterment": areas_of_betterment,
    }
