import unittest
from tempfile import TemporaryDirectory

from app import main as main_app
from app.database import Database, now_iso, to_json


class SkillProfileTests(unittest.TestCase):
    def test_skill_rows_include_completed_assessment_and_written_practice_skills(self) -> None:
        previous_db = main_app.db
        try:
            with TemporaryDirectory() as temp_dir:
                db = Database(f"{temp_dir}/skill_profile.sqlite")
                db.init()
                main_app.db = db
                user_id = "user_skill_profile"
                completed_at = now_iso()

                db.execute(
                    """
                    INSERT INTO assessments (
                        id, user_id, status, mode, total_per_dimension, next_dimension_index,
                        assessment_type, question_type, category, score, capability_profile, metadata,
                        created_at, completed_at
                    )
                    VALUES (?, ?, 'completed', 'quick', 3, 0, 'capability', 'MCQ', 'Machine Learning',
                        82, ?, ?, ?, ?)
                    """,
                    (
                        "assess_skill_profile",
                        user_id,
                        to_json({"Data Thinking": 88, "AI Readiness": 76}),
                        to_json(
                            {
                                "target_dimensions": ["Data Thinking", "AI Readiness"],
                                "inference": {"hidden_skills": ["Model Evaluation"]},
                            }
                        ),
                        completed_at,
                        completed_at,
                    ),
                )
                db.execute(
                    """
                    INSERT INTO written_assessments (
                        id, user_id, assignment_id, skill_id, skill_request_id, prompt, rubric,
                        submission_text, score, feedback, status, metadata, created_at, updated_at
                    )
                    VALUES (?, ?, NULL, 'SQL Querying', NULL, 'Explain a query plan', '{}',
                        'Use indexes and joins carefully.', 74, 'Clear reasoning.', 'completed', ?, ?, ?)
                    """,
                    (
                        "written_skill_profile",
                        user_id,
                        to_json({"dimension": "SQL Querying", "insights": ["Query Optimization"]}),
                        completed_at,
                        completed_at,
                    ),
                )

                skills = {row["skill_id"]: row for row in main_app.skill_rows(user_id)}

                self.assertIn("machine-learning", skills)
                self.assertEqual(skills["machine-learning"]["assessment_score"], 82)
                self.assertEqual(skills["machine-learning"]["source"], "assessment_practice")
                self.assertIn("model-evaluation", skills)
                self.assertIn("sql-querying", skills)
                self.assertEqual(skills["sql-querying"]["written_score"], 74)
                self.assertEqual(skills["sql-querying"]["source"], "written_practice")
        finally:
            main_app.db = previous_db


if __name__ == "__main__":
    unittest.main()
