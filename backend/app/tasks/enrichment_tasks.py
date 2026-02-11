"""Celery tasks for property enrichment (geocoding, hazard, demographics)."""

from app.celery_app import celery_app


@celery_app.task(bind=True, rate_limit="10/m")
def enrich_property(self, property_id: str):
    """
    Enrich a property with external data:
    1. Geocoding (if no coordinates yet)
    2. Hazard data from J-SHIS + Hazard Map
    3. Infrastructure proximity from reinfolib XKT*
    4. Demographic data from population mesh
    5. Comparable transactions from XIT001
    6. Trigger scoring after enrichment
    """
    # TODO: Implement in Phase 4
    pass


@celery_app.task
def enrich_batch(property_ids: list[str]):
    """Fan out individual enrichment tasks with staggered delays."""
    for i, pid in enumerate(property_ids):
        enrich_property.apply_async(args=[pid], countdown=i * 6)
