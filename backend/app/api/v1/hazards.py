from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.hazard import HazardAssessment
from app.clients.hazard_map import HazardMapClient, HAZARD_TILE_LAYERS

router = APIRouter()

_tile_client: HazardMapClient | None = None

def _get_tile_client() -> HazardMapClient:
    global _tile_client
    if _tile_client is None:
        _tile_client = HazardMapClient()
    return _tile_client


@router.get("/{property_id}")
async def get_property_hazards(property_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(HazardAssessment).where(HazardAssessment.property_id == property_id)
    )
    hazard = result.scalar_one_or_none()
    if not hazard:
        return {"detail": "No hazard assessment available"}
    return {
        "property_id": str(hazard.property_id),
        "seismic_intensity_prob": hazard.seismic_intensity_prob,
        "pga_475yr": float(hazard.pga_475yr) if hazard.pga_475yr else None,
        "liquefaction_risk": hazard.liquefaction_risk,
        "flood_depth_max_m": float(hazard.flood_depth_max_m) if hazard.flood_depth_max_m else None,
        "flood_zone": hazard.flood_zone,
        "tsunami_risk": hazard.tsunami_risk,
        "tsunami_depth_max_m": float(hazard.tsunami_depth_max_m) if hazard.tsunami_depth_max_m else None,
        "landslide_risk": hazard.landslide_risk,
        "steep_slope_zone": hazard.steep_slope_zone,
        "landslide_prevention_zone": hazard.landslide_prevention_zone,
        "mesh_code": hazard.mesh_code,
        "assessed_at": hazard.assessed_at.isoformat() if hazard.assessed_at else None,
    }


@router.post("/enrich")
async def enrich_hazards(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Trigger hazard assessment for properties missing assessments."""
    import asyncio
    from app.services.hazard_service import HazardService
    from app.database import async_session

    async def _run():
        async with async_session() as session:
            service = HazardService(session)
            return await service.assess_properties_batch(limit=limit)

    asyncio.get_running_loop().create_task(_run())
    return {"status": "started", "message": f"Enriching up to {limit} properties with hazard data"}


@router.get("/layers")
async def list_hazard_layers():
    """List available hazard map overlay layers with tile URLs."""
    from app.clients.hazard_map import HazardMapClient
    layers = HazardMapClient.get_available_layers()
    for layer in layers:
        layer["tile_url"] = HAZARD_TILE_LAYERS.get(layer["id"])
    return {"layers": layers}


@router.get("/tiles/{layer}/{z}/{x}/{y}.png")
async def get_hazard_tile(layer: str, z: int, x: int, y: int):
    """Proxy hazard map tiles from GSI to avoid CORS issues."""
    client = _get_tile_client()
    tile_data = await client.get_tile(layer, z, x, y)
    if tile_data is None:
        return Response(content=b"", media_type="image/png", status_code=204)
    return Response(content=tile_data, media_type="image/png")
