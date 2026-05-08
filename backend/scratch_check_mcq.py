
import asyncio
import os
from supabase import create_client
from dotenv import load_dotenv

async def check_mcq():
    load_dotenv()
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    supabase = create_client(url, key)
    
    # Check MCQ Questions
    mcqs = supabase.table("mcq_questions").select("*").limit(5).execute()
    print("\n--- MCQ QUESTIONS (Sample) ---")
    if mcqs.data:
        for q in mcqs.data:
            print(f"ID: {q.get('id')} | Question: {q.get('question_text')[:50]}...")
    else:
        print("mcq_questions table is empty.")

    # Check Written Assessments
    written = supabase.table("written_assessments").select("*").limit(5).execute()
    print("\n--- WRITTEN ASSESSMENTS (Sample) ---")
    if written.data:
        for w in written.data:
            print(f"ID: {w.get('id')} | Title: {w.get('title')}")
    else:
        print("written_assessments table is empty.")

    # Check if there are any assessment banks
    banks = supabase.table("assessment_banks").select("*").limit(5).execute()
    print("\n--- ASSESSMENT BANKS (Sample) ---")
    if banks.data:
        for b in banks.data:
            print(f"ID: {b.get('id')} | Name: {b.get('bank_name')}")
    else:
        print("assessment_banks table is empty.")

if __name__ == "__main__":
    asyncio.run(check_mcq())
