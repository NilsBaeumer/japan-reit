import csv
import io

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.property import Property

router = APIRouter()


@router.get("/properties/csv")
async def export_properties_csv(
    price_min: int | None = None,
    price_max: int | None = None,
    municipality_code: str | None = None,
    min_score: float | None = None,
    rebuild_possible: bool | None = None,
    status: str = "active",
    db: AsyncSession = Depends(get_db),
):
    """Export filtered properties as CSV."""
    query = select(Property).where(Property.status == status)

    if price_min is not None:
        query = query.where(Property.price >= price_min)
    if price_max is not None:
        query = query.where(Property.price <= price_max)
    if municipality_code:
        query = query.where(Property.municipality_code == municipality_code)
    if min_score is not None:
        query = query.where(Property.composite_score >= min_score)
    if rebuild_possible is not None:
        query = query.where(Property.rebuild_possible == rebuild_possible)

    query = query.order_by(Property.created_at.desc()).limit(5000)
    result = await db.execute(query)
    properties = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "id", "address", "price", "land_area_sqm", "building_area_sqm",
        "floor_plan", "year_built", "structure", "road_width_m",
        "rebuild_possible", "composite_score", "city_planning_zone",
        "use_zone", "latitude", "longitude", "status", "created_at",
    ])

    for p in properties:
        writer.writerow([
            p.id, p.address_ja, p.price,
            float(p.land_area_sqm) if p.land_area_sqm else "",
            float(p.building_area_sqm) if p.building_area_sqm else "",
            p.floor_plan or "", p.year_built or "", p.structure or "",
            float(p.road_width_m) if p.road_width_m else "",
            "true" if p.rebuild_possible else "false" if p.rebuild_possible is False else "",
            float(p.composite_score) if p.composite_score else "",
            p.city_planning_zone or "", p.use_zone or "",
            p.latitude or "", p.longitude or "",
            p.status, p.created_at.isoformat() if p.created_at else "",
        ])

    csv_content = output.getvalue()
    output.close()

    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=properties.csv"},
    )


@router.get("/deals/csv")
async def export_deals_csv(db: AsyncSession = Depends(get_db)):
    """Export all pipeline deals as CSV."""
    from app.models.financial import Deal

    result = await db.execute(select(Deal).order_by(Deal.created_at.desc()))
    deals = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "id", "property_id", "stage", "purchase_price", "renovation_budget",
        "target_sale_price", "notes", "created_at", "updated_at",
    ])

    for d in deals:
        writer.writerow([
            d.id, d.property_id, d.stage, d.purchase_price or "",
            d.renovation_budget or "", d.target_sale_price or "",
            d.notes or "", d.created_at.isoformat() if d.created_at else "",
            d.updated_at.isoformat() if d.updated_at else "",
        ])

    csv_content = output.getvalue()
    output.close()

    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=deals.csv"},
    )
