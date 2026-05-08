import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(url, key)

def check_descriptive_questions():
    print("Checking 'questions' table for descriptive questions...")
    res = supabase.table("questions").select("*").eq("question_type", "descriptive").limit(10).execute()
    if res.data:
        for row in res.data:
            print(f"ID: {row.get('id')}, Category: {row.get('category')}, Skill: {row.get('skill_id')}")
            print(f"Question: {row.get('question_text')}")
            print("-" * 20)
    else:
        print("No descriptive questions found in 'questions' table.")

    print("\nChecking 'descriptive_questions' table...")
    try:
        res = supabase.table("descriptive_questions").select("*").limit(10).execute()
        if res.data:
            for row in res.data:
                print(f"ID: {row.get('id')}, Category: {row.get('category')}, Skill: {row.get('skill_id')}")
                print(f"Question: {row.get('question_text')}")
                print("-" * 20)
        else:
            print("No descriptive questions found in 'descriptive_questions' table.")
    except Exception as e:
        print(f"Error checking 'descriptive_questions' table: {e}")

if __name__ == "__main__":
    check_descriptive_questions()
