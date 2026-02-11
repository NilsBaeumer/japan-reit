from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.location import Prefecture, Municipality

router = APIRouter()


@router.get("/prefectures")
async def list_prefectures(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Prefecture).order_by(Prefecture.code))
    prefectures = result.scalars().all()
    return [
        {
            "code": p.code,
            "name_ja": p.name_ja,
            "name_en": p.name_en,
            "region": p.region,
        }
        for p in prefectures
    ]


@router.get("/municipalities")
async def list_municipalities(
    prefecture_code: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Municipality).order_by(Municipality.code)
    if prefecture_code:
        query = query.where(Municipality.prefecture_code == prefecture_code)
    result = await db.execute(query)
    municipalities = result.scalars().all()
    return [
        {
            "code": m.code,
            "prefecture_code": m.prefecture_code,
            "name_ja": m.name_ja,
            "name_en": m.name_en,
        }
        for m in municipalities
    ]
