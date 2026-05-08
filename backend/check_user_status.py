import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(URL, KEY)

user_id = "ff7a75b5-7fc4-46cd-984f-b20acfca43f7" # Ullas ID

def check_status():
    print(f"Checking status for user: {user_id}")
    
    profile = supabase.table("profiles").select("*").eq("id", user_id).single().execute()
    print("\nPROFILE:")
    print(profile.data)
    
    skills = supabase.table("user_skills").select("*").eq("user_id", user_id).execute()
    print(f"\nSKILLS: {len(skills.data)}")
    
    learning_path = supabase.table("learning_paths").select("*").eq("user_id", user_id).execute()
    print(f"\nLEARNING PATHS: {len(learning_path.data)}")
    
    # Check if there are ANY questions in the DB
    questions = supabase.table("questions").select("subject", count="exact").execute()
    print(f"\nTOTAL QUESTIONS: {questions.count}")
    
    if questions.data:
        subjects = set(q['subject'] for q in questions.data)
        print(f"SUBJECTS IN DB: {subjects}")

if __name__ == "__main__":
    check_status()
