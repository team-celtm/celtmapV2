from __future__ import annotations

import pytest

from app.services.evaluation_service import EvaluationService


class FakeEvaluationProvider:
    async def evaluate(self, prompt: str) -> dict:
        return {"mode": "heuristic", "prompt": prompt}


class PartialEvaluationProvider:
    async def evaluate(self, prompt: str) -> dict:
        return {
            "feedback": "Covers the main remediation path.",
            "strengths": ["Clear sequencing"],
        }


@pytest.mark.asyncio
async def test_written_evaluation_modes_change_scores() -> None:
    service = EvaluationService(FakeEvaluationProvider())  # type: ignore[arg-type]
    prompt = "Explain how you would diagnose the outage, fix it, and validate the rollout."
    submission = (
        "1. I would identify the failing service, confirm the root cause, and stabilize the "
        "highest-risk dependency first. 2. I would implement the smallest safe fix, explain "
        "tradeoffs, and define validation checks for logs, metrics, and user impact."
    )

    liberal = await service.evaluate_written_submission(
        prompt_text=prompt,
        submission_text=submission,
        rubric={},
        context_documents=[],
        evaluator_mode="liberal_ai",
    )
    teacher = await service.evaluate_written_submission(
        prompt_text=prompt,
        submission_text=submission,
        rubric={},
        context_documents=[],
        evaluator_mode="teacher",
    )
    strict = await service.evaluate_written_submission(
        prompt_text=prompt,
        submission_text=submission,
        rubric={},
        context_documents=[],
        evaluator_mode="strict_ai",
    )

    assert liberal["score"] > teacher["score"] > strict["score"]
    assert liberal["metadata"]["evaluator_mode"] == "liberal_ai"
    assert strict["metadata"]["evaluator_mode"] == "strict_ai"
    assert isinstance(teacher["recommendations"], list)
    assert teacher["plagiarism"]["risk_level"] in {"low", "medium", "high"}


@pytest.mark.asyncio
async def test_written_evaluation_normalizes_partial_llm_payloads() -> None:
    service = EvaluationService(PartialEvaluationProvider())  # type: ignore[arg-type]
    result = await service.evaluate_written_submission(
        prompt_text="Explain the failure, the fix, and the validation plan.",
        submission_text=(
            "First, isolate the auth bug and confirm the failing guard. "
            "Second, patch issuer and audience validation. "
            "Third, verify expiry, replay prevention, and telemetry coverage."
        ),
        rubric={},
        context_documents=[],
        evaluator_mode="teacher",
    )

    assert result["score"] > 0
    assert result["feedback"] == "Covers the main remediation path."
    assert result["strengths"] == ["Clear sequencing"]
    assert result["metadata"]["evaluator_mode"] == "teacher"
    assert isinstance(result["risks"], list)
    assert isinstance(result["recommendations"], list)
    assert result["plagiarism"]["summary"]


@pytest.mark.asyncio
async def test_written_evaluation_flags_copy_like_patterns() -> None:
    service = EvaluationService(FakeEvaluationProvider())  # type: ignore[arg-type]
    prompt = "Explain the migration plan, rollout validation, and rollback strategy."
    copied_reference = (
        "The migration plan must include rollout validation and rollback strategy. "
        "The migration plan must include rollout validation and rollback strategy. "
        "The migration plan must include rollout validation and rollback strategy."
    )

    result = await service.evaluate_written_submission(
        prompt_text=prompt,
        submission_text=copied_reference,
        rubric={},
        context_documents=[
            {
                "content": (
                    "The migration plan must include rollout validation and rollback strategy."
                )
            }
        ],
        evaluator_mode="teacher",
    )

    assert result["plagiarism"]["risk_score"] >= 40
    assert result["plagiarism"]["risk_level"] in {"medium", "high"}
