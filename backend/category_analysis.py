#!/usr/bin/env python3
"""Analyze which questions have options and which don't, by category."""

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
    print("QUESTIONS WITH/WITHOUT OPTIONS BY CATEGORY")
    print("="*70 + "\n")

    # Get all questions
    questions_result = await repo.questions.list(limit=5000)
    
    # Get all options
    def direct_query():
        return client.table("options").select("id, question_id, option_text, is_correct").limit(5000).execute()
    result = await repo.options._run(direct_query)
    options_result = result.data if result.data else []

    # Map question_id to options
    options_by_question_id = defaultdict(list)
    for opt in options_result:
        q_id = opt.get("question_id")
        options_by_question_id[q_id].append(opt)

    # Analyze by category
    category_analysis = defaultdict(lambda: {"with_options": 0, "without_options": 0, "total": 0, "types": set()})
    
    for q in questions_result:
        cat = q.get("category", "UNKNOWN")
        q_type = q.get("question_type", "UNKNOWN")
        has_options = len(options_by_question_id.get(q["id"], [])) > 0
        
        category_analysis[cat]["total"] += 1
        category_analysis[cat]["types"].add(q_type)
        
        if has_options:
            category_analysis[cat]["with_options"] += 1
        else:
            category_analysis[cat]["without_options"] += 1

    print("CATEGORY BREAKDOWN:\n")
    for cat in sorted(category_analysis.keys()):
        data = category_analysis[cat]
        with_opts = data["with_options"]
        total = data["total"]
        pct = (with_opts / total * 100) if total > 0 else 0
        types = ", ".join(sorted(data["types"]))
        
        print(f"{cat}:")
        print(f"  Total: {total} questions")
        print(f"  With options: {with_opts} ({pct:.0f}%)")
        print(f"  Without options: {data['without_options']}")
        print(f"  Types: {types}")
        print()

    print("="*70)
    print("\nSUMMARY:")
    total_all = sum(d["total"] for d in category_analysis.values())
    total_with_opts = sum(d["with_options"] for d in category_analysis.values())
    total_without_opts = sum(d["without_options"] for d in category_analysis.values())
    
    print(f"Total questions: {total_all}")
    print(f"With options: {total_with_opts} ({total_with_opts/total_all*100:.0f}%)")
    print(f"Without options: {total_without_opts} ({total_without_opts/total_all*100:.0f}%)")
    print()

    # Show sample from each category
    print("\nSAMPLE QUESTIONS BY CATEGORY:\n")
    shown_cats = set()
    for q in questions_result:
        cat = q.get("category", "UNKNOWN")
        if cat in shown_cats:
            continue
        shown_cats.add(cat)
        
        has_opts = len(options_by_question_id.get(q["id"], [])) > 0
        opts_str = "HAS options" if has_opts else "NO options"
        
        print(f"{cat}: {opts_str}")
        print(f"  Q: {q['question_text'][:70]}...")
        print(f"  Type: {q.get('question_type', 'N/A')}, Difficulty: {q.get('difficulty', 'N/A')}")
        print()

    print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
