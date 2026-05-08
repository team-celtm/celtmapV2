import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(url, key)

def audit_descriptive_questions():
    print("Checking descriptive question categories...")
    res = supabase.table("questions").select("category").eq("question_type", "descriptive").execute()
    if res.data:
        categories = {}
        for row in res.data:
            cat = row.get("category")
            categories[cat] = categories.get(cat, 0) + 1
        print("Categories found in 'descriptive' type:")
        for cat, count in categories.items():
            print(f" - {cat}: {count}")
    else:
        print("No descriptive questions found.")

if __name__ == "__main__":
    audit_descriptive_questions()
