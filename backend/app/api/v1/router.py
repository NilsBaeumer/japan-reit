from fastapi import APIRouter

from app.api.v1 import locations, properties, scoring, hazards, financial, pipeline, scraping, demographics, export

api_router = APIRouter()

api_router.include_router(locations.router, prefix="/locations", tags=["locations"])
api_router.include_router(properties.router, prefix="/properties", tags=["properties"])
api_router.include_router(scoring.router, prefix="/scoring", tags=["scoring"])
api_router.include_router(hazards.router, prefix="/hazards", tags=["hazards"])
api_router.include_router(financial.router, prefix="/financial", tags=["financial"])
api_router.include_router(pipeline.router, prefix="/pipeline", tags=["pipeline"])
api_router.include_router(scraping.router, prefix="/scraping", tags=["scraping"])
api_router.include_router(demographics.router, prefix="/demographics", tags=["demographics"])
api_router.include_router(export.router, prefix="/export", tags=["export"])
