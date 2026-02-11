"""Celery tasks for property scoring."""

from app.celery_app import celery_app


@celery_app.task
def score_property(property_id: str):
    """Score a single property across all dimensions."""
    # TODO: Implement in Phase 5
    pass


@celery_app.task
def batch_score(property_ids: list[str] | None = None):
    """Batch score multiple properties. If None, score all unscored."""
    # TODO: Implement in Phase 5
    pass
