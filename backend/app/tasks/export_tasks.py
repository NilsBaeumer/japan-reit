"""Celery tasks for report generation."""

from app.celery_app import celery_app


@celery_app.task
def generate_property_pdf(property_id: str):
    """Generate PDF report for a property."""
    # TODO: Implement in Phase 7
    pass


@celery_app.task
def generate_properties_csv(filter_params: dict):
    """Generate CSV export of filtered properties."""
    # TODO: Implement in Phase 7
    pass
