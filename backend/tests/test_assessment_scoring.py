import asyncio
import gc
import unittest
from tempfile import TemporaryDirectory

from app.assessment_engine import _weighted_attempt_score, complete_assessment
from app.database import LEVEL_WEIGHTS, Database, now_iso, to_json


def _answer(difficulty: str, correct: bool) -> dict:
    return {
        "difficulty": difficulty,
        "score_awarded": LEVEL_WEIGHTS[difficulty] if correct else 0.0,
    }


class AssessmentScoringTests(unittest.TestCase):
    def test_weighted_score_for_advanced_only_passed_case(self) -> None:
        answers = [
            _answer("Basic", False),
            _answer("Basic", False),
            _answer("Intermediate", False),
            _answer("Intermediate", False),
            _answer("Intermediate", False),
            _answer("Advanced", True),
        ]

        score, total_score, max_score = _weighted_attempt_score(answers)

        self.assertEqual(total_score, 2.0)
        self.assertEqual(max_score, 8.5)
        self.assertEqual(round(score), 24)
        self.assertEqual(score, 23.53)

    def test_weighted_score_for_three_intermediate_passed_case(self) -> None:
        answers = [
            _answer("Basic", False),
            _answer("Basic", False),
            _answer("Intermediate", True),
            _answer("Intermediate", True),
            _answer("Intermediate", True),
            _answer("Advanced", False),
        ]

        score, total_score, max_score = _weighted_attempt_score(answers)

        self.assertEqual(total_score, 4.5)
        self.assertEqual(max_score, 8.5)
        self.assertEqual(round(score), 53)
        self.assertEqual(score, 52.94)

    def test_completion_uses_attempt_weighted_score_not_dimension_average(self) -> None:
        with TemporaryDirectory() as temp_dir:
            db = Database(f"{temp_dir}/assessment.sqlite")
            db.init()
            assessment_id = "assess_weighted_case"
            user_id = "user_weighted_case"
            snapshots = [
                _question("q_basic_1", "Communication", "Basic", "a"),
                _question("q_basic_2", "Communication", "Basic", "a"),
                _question("q_int_1", "Communication", "Intermediate", "b"),
                _question("q_int_2", "Problem Solving", "Intermediate", "b"),
                _question("q_int_3", "Problem Solving", "Intermediate", "b"),
                _question("q_adv_1", "Problem Solving", "Advanced", "c"),
            ]
            db.execute(
                """
                INSERT INTO assessments (
                    id, user_id, status, mode, total_per_dimension, next_dimension_index,
                    assessment_type, question_type, category, metadata, created_at
                )
                VALUES (?, ?, 'in_progress', 'quick', 6, 0, 'capability', 'MCQ', 'Machine Learning', ?, ?)
                """,
                (
                    assessment_id,
                    user_id,
                    to_json(
                        {
                            "assigned_questions": [item["id"] for item in snapshots],
                            "target_dimensions": ["Communication", "Problem Solving"],
                            "assigned_question_snapshots": snapshots,
                        }
                    ),
                    now_iso(),
                ),
            )
            db.execute_many(
                """
                INSERT INTO assessment_dimension_state (assessment_id, dimension, updated_at)
                VALUES (?, ?, ?)
                """,
                [
                    (assessment_id, "Communication", now_iso()),
                    (assessment_id, "Problem Solving", now_iso()),
                ],
            )
            for snapshot in snapshots:
                selected = snapshot["correct_answer"] if snapshot["difficulty"] == "Intermediate" else "wrong"
                correct = selected == snapshot["correct_answer"]
                db.execute(
                    """
                    INSERT INTO assessment_answers (
                        id, assessment_id, user_id, question_id, selected_answer,
                        is_correct, score_awarded, answered_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"answer_{snapshot['id']}",
                        assessment_id,
                        user_id,
                        snapshot["id"],
                        selected,
                        1 if correct else 0,
                        LEVEL_WEIGHTS[snapshot["difficulty"]] if correct else 0.0,
                        now_iso(),
                    ),
                )

            result = asyncio.run(complete_assessment(db, assessment_id, user_id, force=True))

            self.assertEqual(result["score"], 52.94)
            gc.collect()


def _question(question_id: str, dimension: str, difficulty: str, correct_answer: str) -> dict:
    return {
        "id": question_id,
        "dimension": dimension,
        "subject_name": "Machine Learning",
        "difficulty": difficulty,
        "question_type": "MCQ",
        "scenario": "",
        "question_text": f"{difficulty} {question_id}",
        "options": to_json(
            [
                {"id": "a", "text": "A"},
                {"id": "b", "text": "B"},
                {"id": "c", "text": "C"},
            ]
        ),
        "correct_answer": correct_answer,
        "explanation": "",
    }


if __name__ == "__main__":
    unittest.main()
