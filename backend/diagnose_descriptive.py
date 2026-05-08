import os
import json
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

def check():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    supabase = create_client(url, key)

    print("Fetching descriptive questions...")
    res = supabase.table("questions").select("category,subject_id,skill_id,question_text,is_active").eq("question_type", "descriptive").execute()
    data = res.data or []
    
    print(f"Total descriptive questions: {len(data)}")
    active_count = sum(1 for d in data if d.get("is_active") is True)
    print(f"Active questions: {active_count}")
    
    stats = {}
    for d in data:
        cat = d.get("category") or "None"
        subj = d.get("subject_id") or "None"
        key = f"{cat} | {subj}"
        stats[key] = stats.get(key, 0) + 1
        
    print("\nBreakdown by Category | Subject:")
    for k, v in sorted(stats.items()):
        print(f" - {k}: {v}")

    if data:
        print("\nSample Question Text (First 5):")
        for d in data[:5]:
            print(f" - {d.get('question_text')[:100]}...")

if __name__ == "__main__":
    check()
