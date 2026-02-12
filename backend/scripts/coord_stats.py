"""Check coordinate and address stats."""
import asyncio
from sqlalchemy import text
from app.database import async_session


async def check():
    async with async_session() as s:
        # Source breakdown of missing coords
        r = await s.execute(text(
            "SELECT pl.source_id, "
            "count(*) as total, "
            "count(p.lat) as has_coords, "
            "count(*) - count(p.lat) as missing_coords "
            "FROM properties p "
            "JOIN property_listings pl ON pl.property_id = p.id "
            "WHERE p.status = 'active' "
            "GROUP BY pl.source_id"
        ))
        print("Source breakdown:")
        for row in r.fetchall():
            print(f"  {row[0]}: total={row[1]} has_coords={row[2]} missing={row[3]}")

        # Sample addresses without coords
        r = await s.execute(text(
            "SELECT address_ja FROM properties "
            "WHERE lat IS NULL AND address_ja IS NOT NULL "
            "AND address_ja != 'Unknown' LIMIT 5"
        ))
        print("\nSample addresses without coords:")
        for row in r.fetchall():
            print(f"  {row[0][:80]}")

        # Count unknowns
        r = await s.execute(text(
            "SELECT count(*) FROM properties "
            "WHERE address_ja = 'Unknown' OR address_ja IS NULL"
        ))
        print(f"\nProperties with Unknown/NULL address: {r.scalar()}")


asyncio.run(check())
