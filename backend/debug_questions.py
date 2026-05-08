#!/usr/bin/env python3
"""Debug script to check what data is stored for MCQ questions without options."""

import asyncio
import sys
from pathlib import Path
import json

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.config.settings import get_settings
from app.integrations.supabase import get_supabase_client
from app.repositories.assessment_repository import AssessmentRepository


async def main():
    settings = get_settings()
    client = get_supabase_client(settings)
    repo = AssessmentRepository(client)

    print("\n" + "="*70)
    print("DEBUG: INSPECTING MCQ QUESTIONS WITHOUT OPTIONS")
    print("="*70 + "\n")

    # Get all MCQ questions
    questions = await repo.questions.list(filters={"question_type": "MCQ"}, limit=5000)
    print(f"Total MCQ questions: {len(questions)}\n")

    # Get existing options
    def existing_options_query():
        return client.table("options").select("question_id").execute()
    
    result = await repo.options._run(existing_options_query)
    existing_option_q_ids = set(opt.get("question_id") for opt in result.data) if result.data else set()

    # Find questions without options
    questions_without_options = [q for q in questions if q["id"] not in existing_option_q_ids]
    print(f"MCQ questions WITHOUT options: {len(questions_without_options)}\n")

    # Show a few examples
    print("SAMPLE QUESTIONS WITHOUT OPTIONS:")
    for i, q in enumerate(questions_without_options[:3], 1):
        print(f"\n{i}. Question ID: {q['id']}")
        print(f"   Text: {q.get('question_text', 'N/A')[:80]}...")
        print(f"   Fields in DB:")
        for key in sorted(q.keys()):
            val = q[key]
            if key not in ['question_text', 'created_at', 'updated_at'] and val is not None:
                if isinstance(val, str) and len(val) > 80:
                    print(f"      {key}: {val[:80]}...")
                else:
                    print(f"      {key}: {val}")

    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
