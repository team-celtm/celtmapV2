#!/usr/bin/env python3
"""Check what question_ids the options are actually referencing."""

import asyncio
import sys
from pathlib import Path
from collections import defaultdict

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
    print("OPTIONS TABLE ANALYSIS")
    print("="*70 + "\n")

    # Get all questions
    questions_result = await repo.questions.list(limit=5000)
    question_ids = {q["id"]: q.get("question_text", "")[:60] for q in questions_result}
    
    # Get all options
    def direct_query():
        return client.table("options").select("id, question_id, option_text, is_correct").limit(5000).execute()
    result = await repo.options._run(direct_query)
    options_result = result.data if result.data else []

    print(f"Total questions in DB: {len(question_ids)}")
    print(f"Total options in DB: {len(options_result)}\n")

    # Check which question_ids the options reference
    options_by_question_id = defaultdict(list)
    orphaned_options = []
    
    for opt in options_result:
        q_id = opt.get("question_id")
        if q_id in question_ids:
            options_by_question_id[q_id].append(opt)
        else:
            orphaned_options.append({
                "option_id": opt.get("id", ""),
                "question_id": q_id,
                "option_text": opt.get("option_text", "")[:60]
            })

    print(f"✅ Options with matching questions: {sum(len(opts) for opts in options_by_question_id.values())}")
    print(f"❌ Orphaned options (no matching question): {len(orphaned_options)}\n")

    if orphaned_options:
        print(f"Sample orphaned options (first 10):")
        for i, orphan in enumerate(orphaned_options[:10], 1):
            print(f"   {i}. Question ID: {orphan['question_id']}")
            print(f"      Option: {orphan['option_text']}")

    # Show distribution
    print(f"\n\n📊 DISTRIBUTION OF OPTIONS PER QUESTION:")
    distribution = defaultdict(int)
    for q_id, opts in options_by_question_id.items():
        distribution[len(opts)] += 1
    
    for count in sorted(distribution.keys()):
        num_questions = distribution[count]
        print(f"   Questions with {count} options: {num_questions}")

    # Show some questions with options
    print(f"\n\n✅ SAMPLE QUESTIONS WITH OPTIONS:")
    questions_with_options = [q_id for q_id in options_by_question_id.keys()][:5]
    for q_id in questions_with_options:
        print(f"\n   Q: {question_ids[q_id]}")
        print(f"   ID: {q_id[:8]}...")
        opts = options_by_question_id[q_id]
        print(f"   Options: {len(opts)}")
        for i, opt in enumerate(opts, 1):
            correct = "✓" if opt.get("is_correct") else " "
            print(f"      [{correct}] {opt['option_text'][:50]}...")

    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
