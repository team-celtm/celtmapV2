import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not URL or not KEY:
    print("Missing environment variables")
    exit(1)

supabase = create_client(URL, KEY)

def test_insert(payload):
    try:
        print(f"Testing insertion with columns: {list(payload.keys())}")
        res = supabase.table("uploaded_artifacts").insert(payload).execute()
        print("SUCCESS")
        return True
    except Exception as e:
        print(f"FAILED: {e}")
        return False

# Dummy base record
base = {
    "user_id": "ff7a75b5-7fc4-46cd-984f-b20acfca43f7", # Ullas's ID from logs
    "file_name": "test.txt",
    "file_type": "text/plain",
    "metadata": {"test": True}
}

# Test 1: Full superset (what current code does)
print("\n--- Test 1: Superset ---")
test_insert({
    **base,
    "bucket_name": "artifacts",
    "storage_path": "test/path",
    "file_url": "http://test.com"
})

# Test 2: Only supabase_schema columns
print("\n--- Test 2: Supabase Schema ---")
test_insert({
    **base,
    "bucket_name": "artifacts",
    "storage_path": "test/path/2"
})

# Test 3: Only patch_v2 columns
print("\n--- Test 3: Patch V2 ---")
test_insert({
    **base,
    "file_url": "http://test.com/2"
})
