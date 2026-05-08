import asyncio
import csv
import hashlib
import sys
import uuid
from pathlib import Path
from datetime import datetime, UTC

# Add backend directory to path
backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

def get_checksum(content: str) -> str:
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

async def main():
    from app.config.settings import get_settings
    from app.integrations.supabase import get_supabase_client
    from app.repositories.assessment_repository import AssessmentRepository
    
    settings = get_settings()
    client = get_supabase_client(settings)
    repo = AssessmentRepository(client)
    
    csv_path = Path(str(backend_dir.parent)) / "CELTMIND" / "questions_optimized.csv"
    if not csv_path.exists():
        print(f"CSV not found: {csv_path}")
        return

    print(f"Reading {csv_path}...")
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Processing {len(rows)} questions...")
    
    inserted = 0
    skipped = 0
    
    for i, row in enumerate(rows):
        subject = row.get("subject", "General").strip()
        raw_type = row.get("type", "mcq").strip().lower()
        question_text = row.get("question", "").strip()
        
        if not question_text:
            continue
            
        # Map question type to schema allowed values
        if raw_type == "situational":
            q_type = "situational_mcq"
        elif raw_type == "descriptive":
            q_type = "descriptive"
        else:
            q_type = "mcq"
            
        # Create a stable source_question_id
        # We use a hash of the question text to keep it consistent if re-run
        text_hash = hashlib.md5(question_text.encode('utf-8')).hexdigest()[:12]
        source_id = f"opt_{subject.lower().replace(' ', '_')}_{text_hash}"
        
        # Difficulty normalization
        difficulty = row.get("difficulty", "medium").strip().lower()
        if difficulty not in ["easy", "medium", "hard"]:
            difficulty = "medium"
        
        # Metadata with IRT
        metadata = {
            "source": "questions_optimized.csv",
            "irt_a": row.get("irt_a"),
            "irt_b": row.get("irt_b"),
            "irt_c": row.get("irt_c"),
        }
        
        question_payload = {
            "source_question_id": source_id,
            "question_text": question_text,
            "question_text_normalized": question_text.lower(),
            "question_type": q_type,
            "difficulty": difficulty,
            "category": subject,
            "subject_name": subject,
            "metadata": metadata,
            "is_active": True,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        
        try:
            # Upsert question
            q_record = await repo.upsert_question(question_payload)
            q_id = q_record.get("id")
            
            if not q_id:
                print(f"Failed to get ID for question: {question_text[:50]}...")
                continue
                
            # Prepare options
            options_payload = []
            correct_ans = row.get("correct_answer", "").strip().upper()
            
            for key in ["a", "b", "c", "d"]:
                opt_text = row.get(f"option_{key}", "").strip()
                if opt_text:
                    options_payload.append({
                        "question_id": q_id,
                        "option_key": key.upper(),
                        "option_text": opt_text,
                        "is_correct": key.upper() == correct_ans
                    })
            
            if options_payload:
                await repo.upsert_options(options_payload)
            
            inserted += 1
            if i % 100 == 0:
                print(f"Processed {i} questions...")
                
        except Exception as e:
            print(f"Error processing row {i}: {e}")
            skipped += 1

    print(f"Success! Ingested {inserted} questions. Skipped {skipped}.")

if __name__ == "__main__":
    asyncio.run(main())
