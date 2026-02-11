from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.demographics import TransactionHistory
from app.models.property import Property

router = APIRouter()


@router.get("/stats")
async def get_market_stats(db: AsyncSession = Depends(get_db)):
    """Aggregate market statistics from our property database."""
    # Total properties
    total_q = await db.execute(select(func.count()).select_from(Property))
    total = total_q.scalar() or 0

    # Active properties
    active_q = await db.execute(
        select(func.count()).select_from(
            select(Property).where(Property.status == "active").subquery()
        )
    )
    active = active_q.scalar() or 0

    # Average price
    avg_price_q = await db.execute(
        select(func.avg(Property.price)).where(Property.price.isnot(None), Property.status == "active")
    )
    avg_price = avg_price_q.scalar()

    # Average score
    avg_score_q = await db.execute(
        select(func.avg(Property.composite_score)).where(Property.composite_score.isnot(None))
    )
    avg_score = avg_score_q.scalar()

    # Price distribution buckets
    buckets = [
        (0, 500_000, "Under 50万"),
        (500_000, 1_000_000, "50-100万"),
        (1_000_000, 3_000_000, "100-300万"),
        (3_000_000, 5_000_000, "300-500万"),
        (5_000_000, 10_000_000, "500-1000万"),
        (10_000_000, 15_000_000, "1000-1500万"),
    ]
    price_distribution = []
    for low, high, label in buckets:
        count_q = await db.execute(
            select(func.count()).select_from(
                select(Property).where(
                    Property.price >= low,
                    Property.price < high,
                    Property.status == "active",
                ).subquery()
            )
        )
        count = count_q.scalar() or 0
        price_distribution.append({"label": label, "min": low, "max": high, "count": count})

    # Rebuild status
    rebuild_ok_q = await db.execute(
        select(func.count()).select_from(
            select(Property).where(Property.rebuild_possible.is_(True), Property.status == "active").subquery()
        )
    )
    rebuild_ok = rebuild_ok_q.scalar() or 0

    rebuild_ng_q = await db.execute(
        select(func.count()).select_from(
            select(Property).where(Property.rebuild_possible.is_(False), Property.status == "active").subquery()
        )
    )
    rebuild_ng = rebuild_ng_q.scalar() or 0

    return {
        "total_properties": total,
        "active_properties": active,
        "avg_price": round(avg_price) if avg_price else None,
        "avg_score": round(float(avg_score), 1) if avg_score else None,
        "price_distribution": price_distribution,
        "rebuild_ok": rebuild_ok,
        "rebuild_ng": rebuild_ng,
        "rebuild_unknown": active - rebuild_ok - rebuild_ng,
    }


@router.get("/municipality/{code}")
async def get_municipality_demographics(code: str, db: AsyncSession = Depends(get_db)):
    """Market stats for a specific municipality."""
    count_q = await db.execute(
        select(func.count()).select_from(
            select(Property).where(Property.municipality_code == code, Property.status == "active").subquery()
        )
    )
    avg_price_q = await db.execute(
        select(func.avg(Property.price)).where(
            Property.municipality_code == code, Property.price.isnot(None), Property.status == "active"
        )
    )
    avg_score_q = await db.execute(
        select(func.avg(Property.composite_score)).where(
            Property.municipality_code == code, Property.composite_score.isnot(None)
        )
    )

    return {
        "municipality_code": code,
        "property_count": count_q.scalar() or 0,
        "avg_price": round(avg_price_q.scalar() or 0),
        "avg_score": round(float(avg_score_q.scalar() or 0), 1) if avg_score_q.scalar() else None,
    }


@router.get("/transactions")
async def get_transactions(
    municipality_code: str | None = None,
    property_type: str | None = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    query = select(TransactionHistory).order_by(TransactionHistory.created_at.desc()).limit(limit)
    if municipality_code:
        query = query.where(TransactionHistory.municipality_code == municipality_code)
    if property_type:
        query = query.where(TransactionHistory.property_type == property_type)

    result = await db.execute(query)
    transactions = result.scalars().all()
    return [
        {
            "id": str(t.id),
            "municipality_code": t.municipality_code,
            "district_name": t.district_name,
            "property_type": t.property_type,
            "trade_price": t.trade_price,
            "price_per_sqm": t.price_per_sqm,
            "area_sqm": float(t.area_sqm) if t.area_sqm else None,
            "building_year": t.building_year,
            "structure": t.structure,
            "trade_quarter": t.trade_quarter,
        }
        for t in transactions
    ]
