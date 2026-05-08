
import os
import json
from supabase import create_client
from dotenv import load_dotenv

# Load env from backend/.env
env_path = os.path.join('backend', '.env')
if not os.path.exists(env_path):
    # Try current directory if running from backend folder
    env_path = '.env'

load_dotenv(env_path)

url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
if not url or not key:
    print(f"Error: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not found in {env_path}")
    exit(1)

supabase = create_client(url, key)

def check_questions():
    print("--- QUESTIONS TABLE CONTENT ---")
    try:
        res = supabase.table('questions').select('id, subject_id, category, skill_id, question_text').limit(10).execute()
        print(json.dumps(res.data, indent=2))
        
        print("\n--- UNIQUE SUBJECTS (subject_id) ---")
        res = supabase.table('questions').select('subject_id').execute()
        subjects = list(set([r['subject_id'] for r in res.data if r['subject_id']]))
        print(subjects)
        
        print("\n--- UNIQUE CATEGORIES (category) ---")
        res = supabase.table('questions').select('category').execute()
        categories = list(set([r['category'] for r in res.data if r['category']]))
        print(categories)
    except Exception as e:
        print(f"Error querying table: {e}")

if __name__ == "__main__":
    check_questions()
