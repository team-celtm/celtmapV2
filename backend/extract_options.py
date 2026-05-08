#!/usr/bin/env python3
"""Extract options from question data and populate the options table."""

import asyncio
import sys
from pathlib import Path
import uuid

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
    print("EXTRACTING AND LOADING OPTIONS FROM QUESTION DATA")
    print("="*70 + "\n")

    # Get all MCQ questions
    questions = await repo.questions.list(filters={"question_type": "MCQ"}, limit=5000)
    print(f"Found {len(questions)} MCQ questions\n")

    # Get existing options
    def existing_options_query():
        return client.table("options").select("question_id").execute()
    
    result = await repo.options._run(existing_options_query)
    existing_option_q_ids = set(opt.get("question_id") for opt in result.data) if result.data else set()
    print(f"Existing options for {len(existing_option_q_ids)} questions\n")

    # Extract options from questions that don't have them yet
    options_to_insert = []
    options_map_fields = ["option_a", "option_b", "option_c", "option_d"]
    correct_field = "correct_answer"

    for q in questions:
        q_id = q["id"]
        
        # Skip if already has options
        if q_id in existing_option_q_ids:
            continue
        
        # Check if question has the option fields
        has_options = any(field in q for field in options_map_fields if q.get(field))
        if not has_options:
            continue
        
        # Extract options
        correct = q.get(correct_field, "").upper()  # e.g., "A", "B", "C", "D"
        option_index = {"A": 0, "B": 1, "C": 2, "D": 3}.get(correct)
        
        for idx, field in enumerate(options_map_fields):
            option_text = q.get(field)
            if option_text:
                is_correct = (idx == option_index) if option_index is not None else False
                
                options_to_insert.append({
                    "id": str(uuid.uuid4()),
                    "question_id": q_id,
                    "option_text": str(option_text),
                    "is_correct": is_correct,
                })

    print(f"Extracted {len(options_to_insert)} options to insert\n")

    if options_to_insert:
        print("Inserting options...")
        # Insert in batches of 500
        batch_size = 500
        for i in range(0, len(options_to_insert), batch_size):
            batch = options_to_insert[i : i + batch_size]
            try:
                await repo.options.upsert(batch, on_conflict="question_id,option_text")
                print(f"  ✅ Inserted batch {i//batch_size + 1} ({len(batch)} options)")
            except Exception as e:
                print(f"  ❌ Error inserting batch {i//batch_size + 1}: {e}")

    print("\n" + "="*70)
    print("DONE! Now run: python category_analysis.py")
    print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
