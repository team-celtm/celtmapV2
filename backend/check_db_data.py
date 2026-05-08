#!/usr/bin/env python3
"""Quick script to check the current state of questions and options in the database."""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.config.settings import get_settings
from app.integrations.supabase import get_supabase_client
from app.repositories.assessment_repository import AssessmentRepository


async def main():
    settings = get_settings()
    client = get_supabase_client(settings)
    repo = AssessmentRepository(client)

    print("\n" + "="*60)
    print("DATABASE DATA CHECK")
    print("="*60 + "\n")

    # Count total questions
    questions_result = await repo.questions.list(limit=1000)
    total_questions = len(questions_result) if questions_result else 0
    print(f"📊 Total Questions in DB: {total_questions}")

    if total_questions > 0:
        # Show sample of questions with their categories
        categories = {}
        for q in questions_result[:20]:
            cat = q.get("category", "unknown")
            categories[cat] = categories.get(cat, 0) + 1

        print(f"\n📋 Question Categories (sample):")
        for cat, count in sorted(categories.items()):
            print(f"   - {cat}: ~{count} questions")

        # Show sample questions
        print(f"\n📝 Sample Questions:")
        for i, q in enumerate(questions_result[:3], 1):
            print(f"\n   {i}. ID: {q['id'][:8]}...")
            print(f"      Text: {q['question_text'][:60]}...")
            print(f"      Type: {q.get('question_type', 'N/A')}")
            print(f"      Category: {q.get('category', 'N/A')}")
            print(f"      Difficulty: {q.get('difficulty', 'N/A')}")

    # Count total options
    try:
        def direct_query():
            return client.table("options").select("id, question_id, option_text, is_correct").limit(5000).execute()
        result = await repo.options._run(direct_query)
        options_result = result.data if result.data else []
        total_options = len(options_result) if options_result else 0
        print(f"\n\n📊 Total Options in DB: {total_options}")

        if total_options > 0 and total_questions > 0:
            # Check options per question
            avg_options = total_options / total_questions
            print(f"⚡ Average Options per Question: {avg_options:.2f}")

            # Check a specific question's options
            if questions_result:
                q_id = questions_result[0]["id"]
                q_options = [opt for opt in options_result if opt.get("question_id") == q_id]
                print(f"\n✅ Sample Question (ID: {q_id[:8]}...)")
                print(f"   Question: {questions_result[0]['question_text'][:60]}...")
                print(f"   Options Count: {len(q_options)}")
                for j, opt in enumerate(q_options, 1):
                    correct = "✓ CORRECT" if opt.get("is_correct") else "  "
                    print(f"      {j}. {opt['option_text'][:50]}... {correct}")
    except Exception as e:
        print(f"\n\n⚠️  Error querying options: {e}")

    print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
