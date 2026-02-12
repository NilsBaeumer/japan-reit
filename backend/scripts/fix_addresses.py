"""Clean up addresses with newlines/tabs and backfill geocoding-friendly versions."""
import asyncio
from sqlalchemy import text
from app.database import async_session


async def fix():
    async with async_session() as s:
        # Count problematic addresses
        r = await s.execute(text(
            "SELECT count(*) FROM properties "
            "WHERE address_ja ~ E'[\\n\\r\\t]'"
        ))
        count = r.scalar()
        print(f"Addresses with whitespace chars: {count}")

        if count > 0:
            # Clean: replace newlines/tabs/multiple spaces with single space, trim
            r = await s.execute(text(
                "UPDATE properties "
                "SET address_ja = trim(regexp_replace(address_ja, E'[\\s]+', ' ', 'g')) "
                "WHERE address_ja ~ E'[\\n\\r\\t]'"
            ))
            await s.commit()
            print(f"Cleaned {r.rowcount} addresses")

        # Sample cleaned addresses
        r = await s.execute(text(
            "SELECT address_ja FROM properties "
            "WHERE address_ja IS NOT NULL AND address_ja != 'Unknown' "
            "ORDER BY id DESC LIMIT 5"
        ))
        print("\nSample addresses:")
        for row in r.fetchall():
            print(f"  {row[0][:80]}")


asyncio.run(fix())
