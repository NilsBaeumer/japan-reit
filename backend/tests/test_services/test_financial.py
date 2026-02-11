"""Tests for the financial service (Japanese tax calculations)."""

import pytest

from app.services.financial_service import FinancialService


@pytest.fixture
def svc():
    return FinancialService()


class TestBrokerCommission:
    def test_low_price_rule_applies_under_8m(self, svc):
        result = svc.calculate_broker_commission(1_500_000)
        assert result["low_price_rule_applies"] is True
        assert result["actual_commission_incl_tax"] == 330_000

    def test_low_price_rule_at_threshold(self, svc):
        result = svc.calculate_broker_commission(8_000_000)
        assert result["low_price_rule_applies"] is True

    def test_standard_rate_above_8m(self, svc):
        result = svc.calculate_broker_commission(10_000_000)
        assert result["low_price_rule_applies"] is False
        # 10M * 3% + 66,000 = 366,000 excl tax
        assert result["standard_excl_tax"] == 366_000

    def test_under_2m_rate(self, svc):
        result = svc.calculate_broker_commission(1_000_000)
        # 1M * 5% = 50,000
        assert result["standard_excl_tax"] == 50_000


class TestStampTax:
    def test_1_5m_stamp_tax(self, svc):
        assert svc.calculate_stamp_tax(1_500_000) == 1_000

    def test_5m_stamp_tax(self, svc):
        assert svc.calculate_stamp_tax(5_000_000) == 1_000

    def test_10m_stamp_tax(self, svc):
        assert svc.calculate_stamp_tax(10_000_000) == 5_000


class TestCapitalGains:
    def test_short_term_rate(self, svc):
        result = svc.calculate_capital_gains_tax(
            sale_price=3_000_000,
            acquisition_cost=2_000_000,
            sale_costs=330_000,
            holding_months=12,
        )
        assert result["is_short_term"] is True
        assert result["tax_rate"] == pytest.approx(0.3963)
        # Gain = 3M - 2M - 330k = 670k
        assert result["taxable_gain"] == 670_000

    def test_long_term_rate(self, svc):
        result = svc.calculate_capital_gains_tax(
            sale_price=3_000_000,
            acquisition_cost=2_000_000,
            sale_costs=330_000,
            holding_months=72,  # 6 years
        )
        assert result["is_short_term"] is False
        assert result["tax_rate"] == pytest.approx(0.20315)

    def test_no_gain_no_tax(self, svc):
        result = svc.calculate_capital_gains_tax(
            sale_price=1_000_000,
            acquisition_cost=2_000_000,
            sale_costs=100_000,
            holding_months=12,
        )
        assert result["tax_amount"] == 0


class TestPurchaseCosts:
    def test_1_5m_purchase_costs(self, svc):
        result = svc.calculate_purchase_costs(1_500_000)
        assert result["purchase_price"] == 1_500_000
        assert result["broker_commission"]["low_price_rule_applies"] is True
        assert result["total_purchase_costs"] > 0
        assert result["total_with_price"] > 1_500_000
        # Cost ratio should be significant for low-price properties
        assert result["cost_ratio"] > 20  # >20% costs on a 1.5M property

    def test_custom_assessed_value(self, svc):
        result = svc.calculate_purchase_costs(1_500_000, assessed_value=800_000)
        assert result["assessed_value_used"] == 800_000


class TestROIProjection:
    def test_basic_flip_scenario(self, svc):
        result = svc.calculate_roi_projection(
            purchase_price=1_500_000,
            renovation_budget=500_000,
            target_sale_price=3_500_000,
            holding_months=12,
        )
        assert result["investment_summary"]["purchase_price"] == 1_500_000
        assert result["investment_summary"]["renovation_budget"] == 500_000
        assert result["returns"]["breakeven_sale_price"] > 0
        # With these numbers, should be profitable
        assert result["returns"]["net_profit"] > 0
