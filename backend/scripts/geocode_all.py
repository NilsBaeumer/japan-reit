"""Geocode all properties missing coordinates in batches.

Run inside the container: python3 geocode_all.py
"""
import asyncio
from app.database import async_session
from app.services.geocoding_service import get_geocoding_service

BATCH_SIZE = 200


async def main():
    service = get_geocoding_service()
    total_success = 0
    total_failed = 0
    batch_num = 0

    while True:
        batch_num += 1
        async with async_session() as session:
            stats = await service.geocode_properties_batch(session, limit=BATCH_SIZE)

        print(
            f"Batch {batch_num}: {stats['success']} success, "
            f"{stats['failed']} failed, {stats['skipped']} skipped "
            f"(total in batch: {stats['total']})"
        )
        total_success += stats["success"]
        total_failed += stats["failed"]

        if stats["total"] == 0:
            print(f"\nDone! Total: {total_success} geocoded, {total_failed} failed")
            break

        # Small pause between batches
        await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
