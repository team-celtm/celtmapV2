"""Quick probe: check if file_url column exists on uploaded_artifacts in Supabase."""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config.settings import get_settings
from app.integrations.supabase import get_supabase_client

settings = get_settings()
client = get_supabase_client(settings)

# Try inserting a dummy row that uses file_url to see if the column exists
# We'll do a SELECT introspection instead via Supabase information_schema
try:
    result = client.rpc("check_column_exists", {}).execute()
except Exception:
    pass

# Safer: just try to select file_url from the table
try:
    res = client.table("uploaded_artifacts").select("id, file_url").limit(1).execute()
    print("OK: file_url column EXISTS in uploaded_artifacts")
    print("Sample data:", res.data)
except Exception as exc:
    print("FAIL: file_url column DOES NOT EXIST or error:", exc)

# Also confirm what columns the table currently has
try:
    res2 = client.table("uploaded_artifacts").select("*").limit(1).execute()
    if res2.data:
        print("\nActual columns in table:", list(res2.data[0].keys()))
    else:
        print("\nTable exists but is empty")
except Exception as exc2:
    print("Could not probe table columns:", exc2)
