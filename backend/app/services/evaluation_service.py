from __future__ import annotations

import re
from collections.abc import Iterable
from statistics import mean
from typing import Any

from app.integrations.llm import EvaluationProvider
from app.utils.keywords import HIDDEN_SKILL_KEYWORDS


class EvaluationService:
    def __init__(self, provider: EvaluationProvider) -> None:
        self.provider = provider

    async def evaluate_transcript(self, transcript: str, context_documents: list[dict]) -> dict:
        prompt = {
            "task": "Evaluate interview transcript",
            "transcript": transcript,
            "context_documents": context_documents,
            "expected_output": {
                "score": "0-100",
                "feedback": "string",
                "detected_skills": [{"skill_name": "string", "confidence_score": "0-1"}],
                "hidden_skills": [
                    {
                        "skill_name": "string",
                        "confidence_score": "0-1",
                        "evidence": "string",
                    }
                ],
                "evaluation_metrics": {
                    "communication": "0-100",
                    "technical_accuracy": "0-100",
                    "problem_solving": "0-100",
                    "confidence": "0-100",
                },
                "question_answer_pairs": [
                    {
                        "question_text": "string",
                        "answer_text": "string",
                        "evaluation_metrics": {
                            "clarity": "0-100",
                            "depth": "0-100",
                            "relevance": "0-100",
                            "confidence": "0-100",
                        },
                        "evidence": "string",
                    }
                ],
            },
        }
        llm_response = await self.provider.evaluate(str(prompt))
        if llm_response.get("mode") == "heuristic":
            return self._heuristic_evaluation(transcript)
        return self._normalize_transcript_evaluation(llm_response, transcript)

    async def evaluate_written_submission(
        self,
        *,
        prompt_text: str,
        submission_text: str,
        rubric: dict,
        context_documents: list[dict],
        evaluator_mode: str = "teacher",
    ) -> dict:
        prompt = {
            "task": "Evaluate written assessment submission",
            "prompt": prompt_text,
            "submission_text": submission_text,
            "rubric": rubric,
            "context_documents": context_documents,
            "evaluator_mode": evaluator_mode,
            "grading_policy": self._written_policy_label(evaluator_mode),
            "expected_output": {
                "score": "0-100",
                "feedback": "string",
                "strengths": ["string"],
                "risks": ["string"],
                "recommendations": ["string"],
                "detected_skills": [{"skill_name": "string", "confidence_score": "0-1"}],
                "hidden_skills": [
                    {
                        "skill_name": "string",
                        "confidence_score": "0-1",
                        "evidence": "string",
                    }
                ],
                "plagiarism": {
                    "risk_score": "0-100",
                    "risk_level": "low|medium|high",
                    "summary": "string",
                    "signals": ["string"],
                },
            },
        }
        llm_response = await self.provider.evaluate(str(prompt))
        if llm_response.get("mode") == "heuristic":
            return self._heuristic_written_evaluation(
                prompt_text,
                submission_text,
                context_documents=context_documents,
                evaluator_mode=evaluator_mode,
            )
        return self._normalize_written_evaluation(
            llm_response,
            prompt_text,
            submission_text,
            context_documents=context_documents,
            evaluator_mode=evaluator_mode,
        )

    def _heuristic_evaluation(self, transcript: str) -> dict:
        lowered = transcript.lower()
        explicit_skills: list[dict[str, str | float]] = []
        hidden_skills: list[dict[str, str | float]] = []
        for skill_name, keywords in HIDDEN_SKILL_KEYWORDS.items():
            matches = [keyword for keyword in keywords if keyword in lowered]
            if not matches:
                continue
            score = min(0.95, 0.45 + len(matches) * 0.12)
            explicit_skills.append({"skill_name": skill_name, "confidence_score": round(score, 2)})
            hidden_skills.append(
                {
                    "skill_name": skill_name,
                    "confidence_score": round(score - 0.1, 2),
                    "evidence": ", ".join(matches),
                }
            )
        word_count = len([part for part in transcript.split() if part.strip()])
        score = min(94.0, max(48.0, word_count * 1.4))
        feedback_parts = [
            "Strong explanation depth." if word_count > 80 else "Add more detail and examples.",
            "Detected practical skill signals."
            if explicit_skills
            else "Skill evidence is still shallow.",
        ]
        confidence_values = [float(item["confidence_score"]) for item in explicit_skills] or [0.5]
        question_answer_pairs = self._extract_transcript_pairs(transcript)
        evaluation_metrics = self._build_session_metrics(question_answer_pairs, word_count)
        return {
            "score": round(score, 2),
            "feedback": " ".join(feedback_parts),
            "detected_skills": explicit_skills,
            "hidden_skills": hidden_skills,
            "confidence_score": round(mean(confidence_values), 2),
            "evaluation_metrics": evaluation_metrics,
            "question_answer_pairs": question_answer_pairs,
        }

    def _heuristic_written_evaluation(
        self,
        prompt_text: str,
        submission_text: str,
        *,
        context_documents: list[dict[str, Any]] | None = None,
        evaluator_mode: str = "teacher",
    ) -> dict:
        analysis = self._analyze_written_submission(
            prompt_text=prompt_text,
            submission_text=submission_text,
            context_documents=context_documents or [],
        )
        matched_terms = analysis["matched_prompt_terms"]
        word_count = analysis["word_count"]
        coverage_bonus = min(22.0, analysis["prompt_coverage_ratio"] * 28.0)
        depth_bonus = min(24.0, max(0, word_count - 120) * 0.08)
        structure_bonus = 8.0 if analysis["has_structure"] else 0.0
        evidence_bonus = min(12.0, analysis["evidence_marker_count"] * 2.5)
        example_bonus = 8.0 if analysis["example_marker_count"] else 0.0
        originality_bonus = 6.0 if analysis["lexical_diversity"] >= 0.52 else 0.0
        base_score = (
            36.0
            + coverage_bonus
            + depth_bonus
            + structure_bonus
            + evidence_bonus
            + example_bonus
            + originality_bonus
        )
        mode_adjustments = {
            "teacher": 0.0,
            "liberal_ai": 8.0,
            "strict_ai": -10.0,
        }
        minimum_thresholds = {
            "teacher": 65.0,
            "liberal_ai": 58.0,
            "strict_ai": 72.0,
        }
        evaluator_mode = evaluator_mode.strip().lower() or "teacher"
        score = min(96.0, max(25.0, base_score + mode_adjustments.get(evaluator_mode, 0.0)))
        strengths: list[str] = []
        if analysis["prompt_coverage_ratio"] >= 0.32:
            focus_terms = ", ".join(matched_terms[:3])
            strengths.append(
                f"Addresses the core prompt themes{f': {focus_terms}.' if focus_terms else '.'}"
            )
        if analysis["has_structure"]:
            strengths.append(
                "Presents the reasoning in a stepwise structure that is easy to follow."
            )
        if analysis["evidence_marker_count"] >= 2:
            strengths.append(
                "Includes validation, monitoring, or rollout checks alongside the fix."
            )
        if analysis["example_marker_count"]:
            strengths.append(
                "Supports the explanation with concrete examples or implementation detail."
            )
        if word_count >= 180:
            strengths.append(
                "Develops the answer beyond surface-level statements with useful depth."
            )

        risks: list[str] = []
        if word_count < 140:
            risks.append("The response is still short for a production-grade written evaluation.")
        if analysis["prompt_coverage_ratio"] < 0.25:
            risks.append("Several prompt requirements are not addressed directly enough.")
        if analysis["example_marker_count"] == 0:
            risks.append(
                "Claims are not grounded with concrete examples, metrics, or "
                "implementation detail."
            )
        if analysis["evidence_marker_count"] < 2:
            risks.append("Validation, testing, and rollout safeguards need more explicit detail.")
        if analysis["lexical_diversity"] < 0.36:
            risks.append("The phrasing is repetitive, which weakens clarity and originality.")
        if analysis["max_context_phrase_overlap"] >= 0.18:
            risks.append(
                "Some phrasing closely mirrors retrieved reference material and "
                "should be paraphrased."
            )
        if analysis["duplicate_sentence_count"] > 0:
            risks.append("Repeated sentences suggest copied or padded sections.")

        recommendations: list[str] = []
        if word_count < 140:
            recommendations.append(
                "Add one more paragraph covering tradeoffs, operational impact, "
                "and the final validation pass."
            )
        if analysis["example_marker_count"] == 0:
            recommendations.append(
                "Anchor the answer with a concrete case, implementation example, "
                "or measurable outcome."
            )
        if analysis["evidence_marker_count"] < 2:
            recommendations.append(
                "Spell out the verification plan: tests, telemetry, rollback "
                "guardrails, and success criteria."
            )
        if (
            analysis["max_context_phrase_overlap"] >= 0.18
            or analysis["lexical_diversity"] < 0.36
            or analysis["duplicate_sentence_count"] > 0
        ):
            recommendations.append(
                "Rewrite borrowed or repetitive phrasing in your own words and "
                "connect it back to the specific scenario."
            )

        if not strengths:
            strengths.append("Stays generally aligned with the written prompt.")

        plagiarism = self._build_plagiarism_report(analysis)
        feedback = self._build_written_feedback(
            score=round(score, 2),
            strengths=strengths,
            risks=risks,
            recommendations=recommendations,
            plagiarism=plagiarism,
            evaluator_mode=evaluator_mode,
        )
        return {
            "score": round(score, 2),
            "feedback": feedback,
            "strengths": strengths[:4],
            "risks": (
                []
                if score >= minimum_thresholds.get(evaluator_mode, 65.0) and not risks
                else risks[:4]
            ),
            "recommendations": recommendations[:3],
            "plagiarism": plagiarism,
            "metadata": {"evaluator_mode": evaluator_mode},
        }

    def _written_policy_label(self, evaluator_mode: str) -> str:
        normalized = evaluator_mode.strip().lower() or "teacher"
        return {
            "teacher": (
                "Standard balanced feedback. Look for technical accuracy, clarity, and "
                "practical reasoning. Grade fairly but expect professional-grade explanations."
            ),
            "liberal_ai": (
                "Supportive and encouraging feedback. Reward creative problem-solving and "
                "strong conceptual understanding even if specific syntax or minor details "
                "are slightly off. ADD A SCORE BONUS OF 5-10 POINTS for descriptive depth."
            ),
            "strict_ai": (
                "Rigorous and skeptical feedback. Penalize heavily for shallow answers, "
                "lack of concrete evidence, or missing validation/rollout details. "
                "SUBTRACT 10-15 POINTS from the score if the implementation plan is minimal."
            ),
        }.get(
            normalized,
            "Standard balanced feedback. Look for technical accuracy, clarity, and practical reasoning.",
        )

    def _written_policy_feedback(self, evaluator_mode: str, score: float) -> str:
        normalized = evaluator_mode.strip().lower() or "teacher"
        if normalized == "liberal_ai":
            return (
                "Liberal AI mode gives additional credit for reasonable intent and partial "
                "structure."
            )
        if normalized == "strict_ai":
            return (
                "Strict AI mode expects concrete evidence, stronger sequencing, and explicit "
                "validation."
            )
        return "Teacher mode balances structure, correctness, and practical reasoning."

    def _normalize_transcript_evaluation(self, payload: dict[str, Any], transcript: str) -> dict:
        heuristic = self._heuristic_evaluation(transcript)
        question_answer_pairs = payload.get("question_answer_pairs")
        if not isinstance(question_answer_pairs, list):
            question_answer_pairs = heuristic["question_answer_pairs"]

        normalized_pairs = []
        for pair in question_answer_pairs:
            if not isinstance(pair, dict):
                continue
            question_text = self._coerce_text(pair.get("question_text"))
            answer_text = self._coerce_text(pair.get("answer_text"))
            if not question_text and not answer_text:
                continue
            normalized_pairs.append(
                {
                    "question_text": question_text or "Interview follow-up",
                    "answer_text": answer_text or "",
                    "evaluation_metrics": self._normalize_metrics(
                        pair.get("evaluation_metrics"),
                        fallback=None,
                    ),
                    "evidence": self._coerce_text(pair.get("evidence")),
                }
            )

        if not normalized_pairs:
            normalized_pairs = heuristic["question_answer_pairs"]

        detected_skills = self._normalize_skill_entries(
            payload.get("detected_skills"),
            include_evidence=False,
        )
        hidden_skills = self._normalize_skill_entries(
            payload.get("hidden_skills"),
            include_evidence=True,
        )

        return {
            "score": self._coerce_number(payload.get("score"), fallback=heuristic["score"]),
            "feedback": self._coerce_text(payload.get("feedback")) or heuristic["feedback"],
            "detected_skills": detected_skills or heuristic["detected_skills"],
            "hidden_skills": hidden_skills or heuristic["hidden_skills"],
            "confidence_score": self._coerce_number(
                payload.get("confidence_score"),
                fallback=heuristic["confidence_score"],
            ),
            "evaluation_metrics": self._normalize_metrics(
                payload.get("evaluation_metrics"),
                fallback=heuristic["evaluation_metrics"],
            ),
            "question_answer_pairs": normalized_pairs,
        }

    def _normalize_written_evaluation(
        self,
        payload: dict[str, Any],
        prompt_text: str,
        submission_text: str,
        *,
        context_documents: list[dict[str, Any]] | None,
        evaluator_mode: str,
    ) -> dict[str, Any]:
        heuristic = self._heuristic_written_evaluation(
            prompt_text,
            submission_text,
            context_documents=context_documents,
            evaluator_mode=evaluator_mode,
        )
        metadata = dict(heuristic.get("metadata") or {})
        payload_metadata = payload.get("metadata")
        if isinstance(payload_metadata, dict):
            metadata.update(payload_metadata)
        metadata["evaluator_mode"] = evaluator_mode

        return {
            "score": self._coerce_number(payload.get("score"), fallback=heuristic["score"]),
            "feedback": self._coerce_text(payload.get("feedback")) or heuristic["feedback"],
            "strengths": self._coerce_text_list(payload.get("strengths"))
            or heuristic["strengths"],
            "risks": self._coerce_text_list(payload.get("risks")) or heuristic["risks"],
            "recommendations": self._coerce_text_list(payload.get("recommendations"))
            or heuristic["recommendations"],
            "detected_skills": self._normalize_skill_entries(
                payload.get("detected_skills"),
                include_evidence=False,
            ) or heuristic.get("detected_skills", []),
            "hidden_skills": self._normalize_skill_entries(
                payload.get("hidden_skills"),
                include_evidence=True,
            ) or heuristic.get("hidden_skills", []),
            "plagiarism": self._normalize_plagiarism(
                payload.get("plagiarism"),
                fallback=heuristic["plagiarism"],
            ),
            "metadata": metadata,
        }

    def _normalize_skill_entries(
        self,
        payload: Any,
        *,
        include_evidence: bool,
    ) -> list[dict[str, str | float]]:
        if not isinstance(payload, list):
            return []
        normalized: list[dict[str, str | float]] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            skill_name = self._coerce_text(item.get("skill_name"))
            if not skill_name:
                continue
            shaped: dict[str, str | float] = {
                "skill_name": skill_name,
                "confidence_score": round(
                    max(0.0, min(1.0, self._coerce_number(item.get("confidence_score"), 0.5))),
                    2,
                ),
            }
            if include_evidence:
                evidence = self._coerce_text(item.get("evidence"))
                if evidence:
                    shaped["evidence"] = evidence
            normalized.append(shaped)
        return normalized

    def _normalize_metrics(
        self,
        metrics: Any,
        *,
        fallback: dict[str, float] | None,
    ) -> dict[str, float]:
        baseline = dict(fallback or {})
        if not isinstance(metrics, dict):
            return baseline

        for key in ("communication", "technical_accuracy", "problem_solving", "confidence"):
            value = metrics.get(key)
            if value is None:
                continue
            baseline[key] = self._coerce_number(value, fallback=baseline.get(key, 0.0))

        for key in ("clarity", "depth", "relevance"):
            value = metrics.get(key)
            if value is None:
                continue
            baseline[key] = self._coerce_number(value, fallback=baseline.get(key, 0.0))

        return {key: round(value, 2) for key, value in baseline.items()}

    def _extract_transcript_pairs(self, transcript: str) -> list[dict[str, Any]]:
        segments = [segment.strip() for segment in transcript.splitlines() if segment.strip()]
        if not segments:
            return []

        pairs: list[dict[str, Any]] = []
        current_question: str | None = None

        for segment in segments:
            lowered = segment.lower()
            normalized_segment = self._strip_speaker_prefix(segment)
            if self._looks_like_question(segment, lowered):
                current_question = normalized_segment
                continue

            if current_question is None and "?" in normalized_segment:
                current_question = normalized_segment
                continue

            answer_text = normalized_segment
            if current_question is None:
                current_question = "Describe your approach."

            metrics = self._build_turn_metrics(answer_text)
            pairs.append(
                {
                    "question_text": current_question,
                    "answer_text": answer_text,
                    "evaluation_metrics": metrics,
                    "evidence": answer_text[:220],
                }
            )
            current_question = None

        if current_question is not None:
            pairs.append(
                {
                    "question_text": current_question,
                    "answer_text": "",
                    "evaluation_metrics": self._build_turn_metrics(""),
                    "evidence": current_question[:220],
                }
            )

        if pairs:
            return pairs

        chunks = [chunk.strip() for chunk in transcript.split("\n\n") if chunk.strip()]
        if not chunks:
            chunks = [transcript.strip()]

        fallback_pairs = []
        iterable_chunks = list(self._pair_chunks(chunks))
        for question_chunk, answer_chunk in iterable_chunks:
            fallback_pairs.append(
                {
                    "question_text": question_chunk or "Describe your experience.",
                    "answer_text": answer_chunk or "",
                    "evaluation_metrics": self._build_turn_metrics(answer_chunk or ""),
                    "evidence": (answer_chunk or question_chunk)[:220],
                }
            )
        return fallback_pairs

    def _pair_chunks(self, chunks: list[str]) -> Iterable[tuple[str, str]]:
        step = 2
        for index in range(0, len(chunks), step):
            question_chunk = chunks[index]
            answer_chunk = chunks[index + 1] if index + 1 < len(chunks) else ""
            yield question_chunk, answer_chunk

    def _looks_like_question(self, segment: str, lowered: str) -> bool:
        prefixes = ("interviewer:", "question:", "q:", "ai:")
        if lowered.startswith(prefixes):
            return True
        return "?" in segment and not lowered.startswith(("candidate:", "answer:", "a:", "user:"))

    def _strip_speaker_prefix(self, segment: str) -> str:
        prefixes = (
            "interviewer:",
            "question:",
            "q:",
            "candidate:",
            "answer:",
            "a:",
            "user:",
            "ai:",
        )
        lowered = segment.lower()
        for prefix in prefixes:
            if lowered.startswith(prefix):
                return segment[len(prefix) :].strip()
        return segment.strip()

    def _build_turn_metrics(self, answer_text: str) -> dict[str, float]:
        word_count = len([part for part in answer_text.split() if part.strip()])
        detail_score = min(95.0, 35.0 + (word_count * 1.2))
        clarity_score = min(95.0, 40.0 + (word_count * 0.9))
        relevance_score = 78.0 if answer_text else 25.0
        confidence_score = 72.0 if any(
            token in answer_text.lower()
            for token in ("built", "shipped", "measured", "improved", "designed", "debugged")
        ) else 58.0
        return {
            "clarity": round(clarity_score, 2),
            "depth": round(detail_score, 2),
            "relevance": round(relevance_score, 2),
            "confidence": round(confidence_score, 2),
        }

    def _build_session_metrics(
        self,
        question_answer_pairs: list[dict[str, Any]],
        word_count: int,
    ) -> dict[str, float]:
        if not question_answer_pairs:
            baseline = min(92.0, max(35.0, word_count * 1.1))
            return {
                "communication": round(baseline, 2),
                "technical_accuracy": round(baseline, 2),
                "problem_solving": round(baseline, 2),
                "confidence": 55.0,
            }

        clarity = mean(
            float(item.get("evaluation_metrics", {}).get("clarity", 0.0))
            for item in question_answer_pairs
        )
        depth = mean(
            float(item.get("evaluation_metrics", {}).get("depth", 0.0))
            for item in question_answer_pairs
        )
        relevance = mean(
            float(item.get("evaluation_metrics", {}).get("relevance", 0.0))
            for item in question_answer_pairs
        )
        confidence = mean(
            float(item.get("evaluation_metrics", {}).get("confidence", 0.0))
            for item in question_answer_pairs
        )
        return {
            "communication": round(clarity, 2),
            "technical_accuracy": round(depth, 2),
            "problem_solving": round(relevance, 2),
            "confidence": round(confidence, 2),
        }

    def _analyze_written_submission(
        self,
        *,
        prompt_text: str,
        submission_text: str,
        context_documents: list[dict[str, Any]],
    ) -> dict[str, Any]:
        prompt_terms = set(self._extract_meaningful_terms(prompt_text))
        submission_terms = self._extract_meaningful_terms(submission_text)
        submission_term_set = set(submission_terms)
        matched_prompt_terms = sorted(prompt_terms & submission_term_set)
        prompt_coverage_ratio = (
            len(matched_prompt_terms) / len(prompt_terms) if prompt_terms else 0.0
        )
        word_count = len([part for part in submission_text.split() if part.strip()])
        lexical_diversity = (
            len(submission_term_set) / len(submission_terms) if submission_terms else 0.0
        )
        lowered_submission = submission_text.lower()
        has_structure = any(
            marker in lowered_submission
            for marker in (
                "1.",
                "2.",
                "3.",
                "first",
                "second",
                "third",
                "finally",
                "because",
                "therefore",
            )
        )
        evidence_markers = [
            marker
            for marker in (
                "validate",
                "validation",
                "verify",
                "rollback",
                "monitor",
                "metrics",
                "logging",
                "telemetry",
                "test",
                "testing",
            )
            if marker in lowered_submission
        ]
        example_markers = [
            marker
            for marker in ("for example", "for instance", "such as", "e.g.", "case study")
            if marker in lowered_submission
        ]
        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+", submission_text)
            if sentence.strip()
        ]
        normalized_sentences = [
            re.sub(r"\s+", " ", sentence.lower()) for sentence in sentences if sentence.strip()
        ]
        duplicate_sentence_count = max(
            0, len(normalized_sentences) - len(set(normalized_sentences))
        )
        submission_four_grams = self._build_ngrams(submission_terms, size=4)
        prompt_four_grams = self._build_ngrams(self._extract_meaningful_terms(prompt_text), size=4)
        prompt_phrase_overlap = (
            len(prompt_four_grams & submission_four_grams) / len(prompt_four_grams)
            if prompt_four_grams
            else 0.0
        )

        max_context_term_overlap = 0.0
        max_context_phrase_overlap = 0.0
        for document in context_documents:
            raw_content = str(
                document.get("content") or document.get("text") or document.get("snippet") or ""
            ).strip()
            if not raw_content:
                continue
            document_terms = self._extract_meaningful_terms(raw_content)
            if document_terms:
                max_context_term_overlap = max(
                    max_context_term_overlap,
                    self._jaccard_similarity(submission_term_set, set(document_terms)),
                )
            document_four_grams = self._build_ngrams(document_terms, size=4)
            if document_four_grams and submission_four_grams:
                max_context_phrase_overlap = max(
                    max_context_phrase_overlap,
                    len(document_four_grams & submission_four_grams) / len(document_four_grams),
                )

        return {
            "matched_prompt_terms": matched_prompt_terms,
            "prompt_coverage_ratio": prompt_coverage_ratio,
            "word_count": word_count,
            "lexical_diversity": lexical_diversity,
            "has_structure": has_structure,
            "evidence_marker_count": len(evidence_markers),
            "example_marker_count": len(example_markers),
            "duplicate_sentence_count": duplicate_sentence_count,
            "prompt_phrase_overlap": prompt_phrase_overlap,
            "max_context_term_overlap": max_context_term_overlap,
            "max_context_phrase_overlap": max_context_phrase_overlap,
        }

    def _build_plagiarism_report(self, analysis: dict[str, Any]) -> dict[str, Any]:
        risk_score = 6.0
        risk_score += analysis["duplicate_sentence_count"] * 18.0
        risk_score += max(0.0, 0.42 - analysis["lexical_diversity"]) * 65.0
        risk_score += max(0.0, analysis["prompt_phrase_overlap"] - 0.18) * 55.0
        risk_score += max(0.0, analysis["max_context_term_overlap"] - 0.24) * 55.0
        risk_score += max(0.0, analysis["max_context_phrase_overlap"] - 0.12) * 95.0
        if analysis["word_count"] < 120 and analysis["prompt_phrase_overlap"] > 0.24:
            risk_score += 10.0
        bounded_score = round(min(100.0, max(0.0, risk_score)), 2)
        if bounded_score >= 70:
            risk_level = "high"
        elif bounded_score >= 40:
            risk_level = "medium"
        else:
            risk_level = "low"

        signals: list[str] = []
        if analysis["max_context_phrase_overlap"] >= 0.18:
            signals.append(
                "Multiple exact multi-word phrases overlap with retrieved reference material."
            )
        if analysis["prompt_phrase_overlap"] >= 0.32:
            signals.append("Large parts of the prompt wording were reused instead of paraphrased.")
        if analysis["duplicate_sentence_count"] > 0:
            signals.append("Repeated sentences or near-duplicate lines were detected.")
        if analysis["lexical_diversity"] < 0.36:
            signals.append("Low lexical diversity suggests heavy reuse of stock phrasing.")
        if not signals:
            signals.append("No strong copy-patterns were detected in the submitted text.")

        summary = (
            f"{risk_level.title()} plagiarism risk. "
            + (
                signals[0]
                if signals
                else "The response appears to rely on original phrasing."
            )
        )
        return {
            "risk_score": bounded_score,
            "risk_level": risk_level,
            "summary": summary,
            "signals": signals,
        }

    def _build_written_feedback(
        self,
        *,
        score: float,
        strengths: list[str],
        risks: list[str],
        recommendations: list[str],
        plagiarism: dict[str, Any],
        evaluator_mode: str,
    ) -> str:
        if score >= 85:
            opening = (
                "The submission is well-developed and demonstrates credible "
                "technical reasoning."
            )
        elif score >= 70:
            opening = (
                "The submission addresses the main task, but some parts still "
                "need stronger evidence."
            )
        else:
            opening = (
                "The submission only partially addresses the task and needs a "
                "more defensible technical explanation."
            )

        detail = (
            strengths[0]
            if strengths
            else "The response stays broadly aligned with the prompt."
        )
        improvement = risks[0] if risks else "No major evaluator gaps were identified."
        recommendation = (
            recommendations[0]
            if recommendations
            else "Continue tightening the answer with clearer validation details."
        )
        originality = ""
        if plagiarism.get("risk_level") in {"medium", "high"}:
            originality = f" {plagiarism.get('summary')}"
        return " ".join(
            [
                opening,
                detail,
                improvement,
                recommendation,
                self._written_policy_feedback(evaluator_mode, score) + originality,
            ]
        ).strip()

    def _extract_meaningful_terms(self, text: str) -> list[str]:
        return [
            token
            for token in re.findall(r"[a-zA-Z]{4,}", text.lower())
            if token not in {"that", "this", "with", "from", "into", "your", "have"}
        ]

    def _build_ngrams(self, tokens: list[str], *, size: int) -> set[str]:
        if len(tokens) < size:
            return set()
        return {" ".join(tokens[index : index + size]) for index in range(len(tokens) - size + 1)}

    def _jaccard_similarity(self, left: set[str], right: set[str]) -> float:
        if not left or not right:
            return 0.0
        union = left | right
        if not union:
            return 0.0
        return len(left & right) / len(union)

    def _normalize_plagiarism(
        self,
        payload: Any,
        *,
        fallback: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return fallback
        return {
            "risk_score": self._coerce_number(
                payload.get("risk_score"),
                fallback=self._coerce_number(fallback.get("risk_score"), 0.0),
            ),
            "risk_level": self._coerce_text(payload.get("risk_level"))
            or self._coerce_text(fallback.get("risk_level"))
            or "low",
            "summary": self._coerce_text(payload.get("summary"))
            or self._coerce_text(fallback.get("summary"))
            or "No plagiarism summary available.",
            "signals": self._coerce_text_list(payload.get("signals"))
            or self._coerce_text_list(fallback.get("signals")),
        }

    def _coerce_text(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _coerce_text_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [text for item in value if (text := self._coerce_text(item))]

    def _coerce_number(self, value: Any, fallback: float = 0.0) -> float:
        try:
            return round(float(value), 2)
        except (TypeError, ValueError):
            return round(float(fallback), 2)
