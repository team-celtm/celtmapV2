#!/usr/bin/env python3
"""Force re-ingest of all CELTMIND questions and options by clearing sync state."""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.config.settings import get_settings
from app.integrations.supabase import get_supabase_client
from app.repositories.sync_repository import SyncRepository


async def main():
    settings = get_settings()
    client = get_supabase_client(settings)
    sync_repo = SyncRepository(client)

    print("\n" + "="*70)
    print("CLEARING SYNC STATE FOR FORCE RE-INGEST")
    print("="*70 + "\n")

    # Get current file registry records - only select needed columns
    def list_registry():
        return client.table("celtmind_file_registry").select("file_name, checksum").execute()
    
    result = await sync_repo.file_registry._run(list_registry)
    records = result.data if result and result.data else []
    print(f"Found {len(records)} existing file registry records\n")

    # Show which files will be cleared
    for rec in records:
        print(f"  - {rec.get('file_name')}: checksum {rec.get('checksum')[:8]}...")

    # Delete all file registry records
    if records:
        print(f"\nDeleting {len(records)} file registry records to allow re-ingest...")
        for rec in records:
            await sync_repo.file_registry.delete(filters={"file_name": rec["file_name"]})
        print("✅ File registry cleared")

    print("\n" + "="*70)
    print("Now run: python scripts/ingest_mcq.py")
    print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
