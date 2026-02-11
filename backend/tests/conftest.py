"""Test configuration and fixtures."""

import pytest


@pytest.fixture
def financial_service():
    from app.services.financial_service import FinancialService
    return FinancialService()
