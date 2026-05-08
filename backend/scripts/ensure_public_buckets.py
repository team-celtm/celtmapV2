from __future__ import annotations

import asyncio

from supabase import create_client

from app.config.settings import get_settings


async def ensure_public_buckets():
    settings = get_settings()
    settings.require_supabase()
    supabase = create_client(settings.supabase_url, settings.resolved_supabase_service_role_key)
    
    buckets = ["profile-assets", "artifacts"]
    for bucket_id in buckets:
        try:
            print(f"Checking bucket: {bucket_id}")
            # Try to update to public if exists
            supabase.storage.update_bucket(bucket_id, options={"public": True})
            print(f"Bucket '{bucket_id}' is now Public.")
        except Exception as e:
            if "not found" in str(e).lower():
                print(f"Bucket '{bucket_id}' not found, creating as Public...")
                supabase.storage.create_bucket(bucket_id, options={"public": True})
                print(f"Bucket '{bucket_id}' created as Public.")
            else:
                print(f"Error ensuring bucket '{bucket_id}': {e}")

if __name__ == "__main__":
    asyncio.run(ensure_public_buckets())
