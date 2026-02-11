from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.property import Property, PropertyListing

router = APIRouter()


@router.get("")
async def list_properties(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    search: str | None = None,
    price_min: int | None = None,
    price_max: int | None = None,
    prefecture_code: str | None = None,
    municipality_code: str | None = None,
    min_score: float | None = None,
    rebuild_possible: bool | None = None,
    status: str = "active",
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    db: AsyncSession = Depends(get_db),
):
    query = select(Property).where(Property.status == status)

    if search:
        query = query.where(Property.address_ja.ilike(f"%{search}%"))
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

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Sort
    sort_column = getattr(Property, sort_by, Property.created_at)
    if sort_dir == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    # Paginate
    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    properties = result.scalars().all()

    return {
        "items": [_property_to_dict(p) for p in properties],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
    }


@router.get("/geojson")
async def properties_geojson(
    search: str | None = None,
    price_min: int | None = None,
    price_max: int | None = None,
    municipality_code: str | None = None,
    min_score: float | None = None,
    rebuild_possible: bool | None = None,
    status: str = "active",
    db: AsyncSession = Depends(get_db),
):
    query = select(Property).where(
        Property.status == status,
        Property.latitude.isnot(None),
        Property.longitude.isnot(None),
    )

    if search:
        query = query.where(Property.address_ja.ilike(f"%{search}%"))
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

    result = await db.execute(query)
    properties = result.scalars().all()

    features = []
    for p in properties:
        if p.latitude is not None and p.longitude is not None:
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [p.longitude, p.latitude],
                },
                "properties": {
                    "id": str(p.id),
                    "price": p.price,
                    "score": float(p.composite_score) if p.composite_score else None,
                    "address": p.address_ja,
                    "floor_plan": p.floor_plan,
                    "land_area": float(p.land_area_sqm) if p.land_area_sqm else None,
                    "year_built": p.year_built,
                    "rebuild_possible": p.rebuild_possible,
                },
            })

    return {
        "type": "FeatureCollection",
        "features": features,
    }


@router.get("/{property_id}")
async def get_property(property_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Property).where(Property.id == property_id))
    prop = result.scalar_one_or_none()
    if not prop:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Property not found")

    # Get listings
    listings_result = await db.execute(
        select(PropertyListing).where(PropertyListing.property_id == property_id)
    )
    listings = listings_result.scalars().all()

    data = _property_to_dict(prop)
    data["listings"] = [
        {
            "id": str(l.id),
            "source": l.source,
            "source_url": l.source_url,
            "raw_price": l.raw_price,
            "raw_title": l.raw_title,
            "listing_status": l.listing_status,
            "first_scraped_at": l.first_scraped_at.isoformat() if l.first_scraped_at else None,
            "last_scraped_at": l.last_scraped_at.isoformat() if l.last_scraped_at else None,
        }
        for l in listings
    ]
    return data


@router.post("/geocode")
async def geocode_properties(
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Trigger geocoding for properties missing coordinates."""
    import asyncio
    from app.services.geocoding_service import get_geocoding_service

    service = get_geocoding_service()

    # Run in background
    async def _run():
        from app.database import async_session

        async with async_session() as session:
            return await service.geocode_properties_batch(session, limit=limit)

    task = asyncio.get_running_loop().create_task(_run())

    # Count how many need geocoding
    from sqlalchemy import func as sqlfunc

    count_result = await db.execute(
        select(sqlfunc.count())
        .select_from(
            select(Property)
            .where(Property.latitude.is_(None), Property.address_ja.isnot(None))
            .subquery()
        )
    )
    pending = count_result.scalar() or 0

    return {
        "status": "started",
        "pending_properties": pending,
        "batch_size": min(limit, pending),
        "message": f"Geocoding up to {min(limit, pending)} properties in background",
    }


def _property_to_dict(p: Property) -> dict:
    return {
        "id": str(p.id),
        "municipality_code": p.municipality_code,
        "address_ja": p.address_ja,
        "property_type": p.property_type,
        "latitude": p.latitude,
        "longitude": p.longitude,
        "price": p.price,
        "land_area_sqm": float(p.land_area_sqm) if p.land_area_sqm else None,
        "building_area_sqm": float(p.building_area_sqm) if p.building_area_sqm else None,
        "floor_plan": p.floor_plan,
        "year_built": p.year_built,
        "structure": p.structure,
        "floors": p.floors,
        "road_width_m": float(p.road_width_m) if p.road_width_m else None,
        "road_frontage_m": float(p.road_frontage_m) if p.road_frontage_m else None,
        "rebuild_possible": p.rebuild_possible,
        "city_planning_zone": p.city_planning_zone,
        "use_zone": p.use_zone,
        "coverage_ratio": float(p.coverage_ratio) if p.coverage_ratio else None,
        "floor_area_ratio": float(p.floor_area_ratio) if p.floor_area_ratio else None,
        "composite_score": float(p.composite_score) if p.composite_score else None,
        "status": p.status,
        "first_seen_at": p.first_seen_at.isoformat() if p.first_seen_at else None,
        "last_seen_at": p.last_seen_at.isoformat() if p.last_seen_at else None,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }
