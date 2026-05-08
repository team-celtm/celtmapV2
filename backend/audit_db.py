import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(URL, KEY)

TABLES = [
    "learning_paths", "learning_modules", "trajectory_roles", "reports",
    "dashboard_projections", "schedule_events", "interview_sessions",
    "interview_questions", "interview_answers", "interview_evaluations",
    "subjects", "skills", "subskills", "user_skills", "user_hidden_skills",
    "roles", "role_requirements", "skill_requests", "profiles",
    "user_preferences", "uploaded_artifacts", "ai_call_logs", "job_failures"
]

results = {}

for table in TABLES:
    try:
        # Try to get columns by selecting all with limit 0
        res = supabase.table(table).select("*").limit(1).execute()
        columns = list(res.data[0].keys()) if res.data else "EXISTS BUT NO ROWS"
        results[table] = {"status": "EXISTS", "columns": columns}
    except Exception as e:
        err = str(e)
        if "PGRST205" in err:
            results[table] = {"status": "MISSING", "error": "Table not found"}
        elif "PGRST204" in err:
            # Column not found error during select *? Unlikely for select *
            results[table] = {"status": "ERROR", "error": err}
        else:
            results[table] = {"status": "ERROR", "error": err}

print("\n--- DATABASE AUDIT RESULTS ---")
for table, info in results.items():
    print(f"Table: {table:25} | Status: {info['status']:10} | Info: {info.get('columns') or info.get('error')}")
