#!/usr/bin/env python3
"""Detailed database check with breakdown by question type."""

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
    print("DETAILED DATABASE DATA CHECK")
    print("="*70 + "\n")

    # Get all questions
    questions_result = await repo.questions.list(limit=5000)
    total_questions = len(questions_result) if questions_result else 0
    
    # Get all options
    def direct_query():
        return client.table("options").select("id, question_id, option_text, is_correct").limit(5000).execute()
    result = await repo.options._run(direct_query)
    options_result = result.data if result.data else []
    total_options = len(options_result) if options_result else 0

    print(f"📊 TOTAL DATA:")
    print(f"   Questions: {total_questions}")
    print(f"   Options: {total_options}")
    print()

    # Breakdown by question type
    questions_by_type = defaultdict(list)
    for q in questions_result:
        questions_by_type[q.get("question_type", "UNKNOWN")].append(q)

    print(f"📋 BREAKDOWN BY QUESTION TYPE:")
    for qtype, questions in sorted(questions_by_type.items()):
        print(f"\n   {qtype}: {len(questions)} questions")

    # For MCQ questions specifically, check options
    print(f"\n\n🎯 MCQ QUESTIONS ANALYSIS:")
    mcq_questions = questions_by_type.get("MCQ", [])
    print(f"   Total MCQ Questions: {len(mcq_questions)}")
    
    if mcq_questions:
        # Count how many MCQ questions have options
        mcq_with_options = 0
        options_per_mcq = []
        
        for q in mcq_questions[:100]:  # Check first 100
            q_id = q["id"]
            q_options = [opt for opt in options_result if opt.get("question_id") == q_id]
            options_per_mcq.append(len(q_options))
            if len(q_options) > 0:
                mcq_with_options += 1

        print(f"   MCQ with Options (from first 100): {mcq_with_options}/100")
        if options_per_mcq:
            avg = sum(options_per_mcq) / len(options_per_mcq)
            print(f"   Avg Options per MCQ: {avg:.2f}")
            print(f"   Min Options: {min(options_per_mcq)}, Max: {max(options_per_mcq)}")

        # Show sample MCQ with options
        print(f"\n   ✅ SAMPLE MCQ WITH OPTIONS:")
        for q in mcq_questions[:5]:
            q_id = q["id"]
            q_options = [opt for opt in options_result if opt.get("question_id") == q_id]
            print(f"\n      Q: {q['question_text'][:60]}...")
            print(f"      ID: {q_id[:8]}...")
            print(f"      Options: {len(q_options)}")
            for i, opt in enumerate(q_options[:4], 1):
                correct = "✓" if opt.get("is_correct") else " "
                print(f"         [{correct}] {opt['option_text'][:50]}...")

    # For SITUATIONAL questions, check options
    print(f"\n\n🎯 SITUATIONAL QUESTIONS ANALYSIS:")
    situational_questions = questions_by_type.get("SITUATIONAL", [])
    print(f"   Total SITUATIONAL Questions: {len(situational_questions)}")
    
    if situational_questions:
        situational_with_options = 0
        for q in situational_questions[:10]:
            q_id = q["id"]
            q_options = [opt for opt in options_result if opt.get("question_id") == q_id]
            if len(q_options) > 0:
                situational_with_options += 1
        
        print(f"   SITUATIONAL with Options (from first 10): {situational_with_options}/10")

    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
