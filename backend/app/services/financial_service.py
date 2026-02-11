"""
Japanese Real Estate Financial Calculator.

Implements all tax, commission, and cost rules for Japanese real estate transactions.
All amounts in Japanese Yen (JPY).
"""

import math


class FinancialService:
    # Consumption tax rate
    CONSUMPTION_TAX = 0.10

    # Stamp tax table (reduced rates through 2027-03-31 for real estate contracts)
    STAMP_TAX_TABLE = [
        (0, 10_000, 200),
        (10_001, 500_000, 200),
        (500_001, 1_000_000, 500),
        (1_000_001, 5_000_000, 1_000),
        (5_000_001, 10_000_000, 5_000),
        (10_000_001, 50_000_000, 10_000),
        (50_000_001, 100_000_000, 30_000),
        (100_000_001, 500_000_000, 60_000),
        (500_000_001, float("inf"), 320_000),
    ]

    # Registration license tax rates
    REG_TAX_LAND_TRANSFER = 0.015  # Reduced rate through 2026-03-31 (normally 2.0%)
    REG_TAX_BUILDING_TRANSFER = 0.020
    REG_TAX_MORTGAGE = 0.004

    # Acquisition tax rates
    ACQ_TAX_LAND_RATE = 0.03
    ACQ_TAX_LAND_ASSESSMENT_MULTIPLIER = 0.5  # Land assessed * 1/2 * rate
    ACQ_TAX_BUILDING_RESIDENTIAL_RATE = 0.03

    # Capital gains tax
    SHORT_TERM_RATE = 0.3963  # income 30% + resident 9% + special 0.63%
    LONG_TERM_RATE = 0.20315  # income 15% + resident 5% + special 0.315%
    LONG_TERM_THRESHOLD_YEARS = 5

    # Annual holding
    FIXED_ASSET_TAX_RATE = 0.014
    CITY_PLANNING_TAX_RATE = 0.003

    # Broker commission - low-price special rule (since 2024-07-01)
    LOW_PRICE_MAX_COMMISSION_INCL_TAX = 330_000
    LOW_PRICE_THRESHOLD = 8_000_000

    def calculate_broker_commission(self, price: int) -> dict:
        """
        Calculate broker commission with low-price special rule.

        Standard tiers (max per side, excl. tax):
        - Under ¥2M: 5% of price
        - ¥2M-¥4M: 4% + ¥22,000
        - Over ¥4M: 3% + ¥66,000

        Low-price special rule (since 2024-07-01):
        For properties <= ¥8M, max ¥330,000 incl. tax per party.
        """
        # Standard calculation
        if price <= 2_000_000:
            standard_excl = price * 0.05
        elif price <= 4_000_000:
            standard_excl = price * 0.04 + 22_000
        else:
            standard_excl = price * 0.03 + 66_000

        standard_incl = math.floor(standard_excl * (1 + self.CONSUMPTION_TAX))

        # Low-price special rule check
        low_price_applies = price <= self.LOW_PRICE_THRESHOLD
        if low_price_applies:
            actual_commission = min(standard_incl, self.LOW_PRICE_MAX_COMMISSION_INCL_TAX)
            # Under the special rule, up to ¥330,000 incl. tax can be charged
            actual_commission = self.LOW_PRICE_MAX_COMMISSION_INCL_TAX
        else:
            actual_commission = standard_incl

        return {
            "standard_excl_tax": math.floor(standard_excl),
            "standard_incl_tax": standard_incl,
            "low_price_rule_applies": low_price_applies,
            "actual_commission_incl_tax": actual_commission,
            "note": (
                "Low-price special rule: max ¥330,000 incl. tax per party (since 2024-07-01)"
                if low_price_applies
                else "Standard commission rate applied"
            ),
        }

    def calculate_stamp_tax(self, contract_amount: int) -> int:
        """Stamp tax based on contract amount (reduced rates through 2027-03-31)."""
        for lower, upper, tax in self.STAMP_TAX_TABLE:
            if lower <= contract_amount <= upper:
                return tax
        return 0

    def calculate_registration_tax(
        self,
        assessed_value: int,
        is_land_only: bool = False,
    ) -> dict:
        """
        Registration license tax.
        Based on assessed value (固定資産税評価額), NOT purchase price.
        Assessed value is typically 50-70% of market value.
        """
        if is_land_only:
            land_tax = math.floor(assessed_value * self.REG_TAX_LAND_TRANSFER)
            return {
                "land_transfer": land_tax,
                "building_transfer": 0,
                "total": land_tax,
                "rate_land": self.REG_TAX_LAND_TRANSFER,
                "rate_building": 0,
                "note": "Land reduced rate 1.5% through 2026-03-31",
            }

        # Split assumed 40% land, 60% building for mixed properties
        land_value = math.floor(assessed_value * 0.4)
        building_value = assessed_value - land_value

        land_tax = math.floor(land_value * self.REG_TAX_LAND_TRANSFER)
        building_tax = math.floor(building_value * self.REG_TAX_BUILDING_TRANSFER)

        return {
            "land_transfer": land_tax,
            "building_transfer": building_tax,
            "total": land_tax + building_tax,
            "assessed_land_value": land_value,
            "assessed_building_value": building_value,
            "rate_land": self.REG_TAX_LAND_TRANSFER,
            "rate_building": self.REG_TAX_BUILDING_TRANSFER,
            "note": "Land reduced rate 1.5% through 2026-03-31",
        }

    def calculate_acquisition_tax(self, assessed_value: int, is_land_only: bool = False) -> dict:
        """
        Real estate acquisition tax (不動産取得税).
        Land: assessed * 1/2 * 3%
        Building (residential): assessed * 3%
        """
        if is_land_only:
            land_tax = math.floor(
                assessed_value * self.ACQ_TAX_LAND_ASSESSMENT_MULTIPLIER * self.ACQ_TAX_LAND_RATE
            )
            return {"land": land_tax, "building": 0, "total": land_tax}

        land_value = math.floor(assessed_value * 0.4)
        building_value = assessed_value - land_value

        land_tax = math.floor(
            land_value * self.ACQ_TAX_LAND_ASSESSMENT_MULTIPLIER * self.ACQ_TAX_LAND_RATE
        )
        building_tax = math.floor(building_value * self.ACQ_TAX_BUILDING_RESIDENTIAL_RATE)

        return {
            "land": land_tax,
            "building": building_tax,
            "total": land_tax + building_tax,
        }

    def calculate_annual_holding_cost(self, assessed_value: int) -> dict:
        """Annual fixed asset tax + city planning tax."""
        fixed_asset = math.floor(assessed_value * self.FIXED_ASSET_TAX_RATE)
        city_planning = math.floor(assessed_value * self.CITY_PLANNING_TAX_RATE)
        return {
            "fixed_asset_tax": fixed_asset,
            "city_planning_tax": city_planning,
            "total_annual": fixed_asset + city_planning,
            "monthly": math.floor((fixed_asset + city_planning) / 12),
        }

    def calculate_capital_gains_tax(
        self,
        sale_price: int,
        acquisition_cost: int,
        sale_costs: int,
        holding_months: int,
    ) -> dict:
        """
        Capital gains tax on property sale.

        Short-term (<=5 years from Jan 1 after acquisition to Jan 1 of sale year): 39.63%
        Long-term (>5 years): 20.315%

        Taxable gain = sale_price - acquisition_cost - sale_costs
        """
        gain = sale_price - acquisition_cost - sale_costs
        if gain <= 0:
            return {
                "taxable_gain": max(0, gain),
                "tax_rate": 0,
                "tax_amount": 0,
                "is_short_term": holding_months <= 60,
                "net_after_tax": sale_price - sale_costs,
            }

        # Approximate: <=60 months is short-term
        is_short_term = holding_months <= 60
        rate = self.SHORT_TERM_RATE if is_short_term else self.LONG_TERM_RATE
        tax = math.floor(gain * rate)

        return {
            "taxable_gain": gain,
            "tax_rate": rate,
            "tax_rate_label": "short_term (39.63%)" if is_short_term else "long_term (20.315%)",
            "tax_amount": tax,
            "is_short_term": is_short_term,
            "net_after_tax": sale_price - sale_costs - tax,
            "note": "5-year threshold: Jan 1 after acquisition to Jan 1 of sale year",
        }

    def calculate_purchase_costs(
        self,
        price: int,
        assessed_value: int | None = None,
        is_land_only: bool = False,
    ) -> dict:
        """Full purchase cost breakdown."""
        # Default assessed value to 70% of price if not provided
        if assessed_value is None:
            assessed_value = math.floor(price * 0.7)

        commission = self.calculate_broker_commission(price)
        stamp = self.calculate_stamp_tax(price)
        registration = self.calculate_registration_tax(assessed_value, is_land_only)
        acquisition = self.calculate_acquisition_tax(assessed_value, is_land_only)

        # Estimated judicial scrivener fee
        scrivener_fee = 50_000  # Typical range: ¥30,000-¥80,000

        total_costs = (
            commission["actual_commission_incl_tax"]
            + stamp
            + registration["total"]
            + acquisition["total"]
            + scrivener_fee
        )

        return {
            "purchase_price": price,
            "assessed_value_used": assessed_value,
            "broker_commission": commission,
            "stamp_tax": stamp,
            "registration_tax": registration,
            "acquisition_tax": acquisition,
            "judicial_scrivener_fee": scrivener_fee,
            "total_purchase_costs": total_costs,
            "total_with_price": price + total_costs,
            "cost_ratio": round(total_costs / price * 100, 1) if price > 0 else 0,
        }

    def calculate_roi_projection(
        self,
        purchase_price: int,
        assessed_value: int | None = None,
        renovation_budget: int = 0,
        target_sale_price: int = 0,
        holding_months: int = 12,
    ) -> dict:
        """Full ROI projection for buy-renovate-sell scenario."""
        purchase = self.calculate_purchase_costs(purchase_price, assessed_value)
        holding = self.calculate_annual_holding_cost(
            assessed_value or math.floor(purchase_price * 0.7)
        )

        total_invested = purchase["total_with_price"] + renovation_budget
        holding_cost = math.floor(holding["monthly"] * holding_months)
        total_invested_with_holding = total_invested + holding_cost

        # Sale costs
        sale_commission = self.calculate_broker_commission(target_sale_price)
        sale_costs = sale_commission["actual_commission_incl_tax"]

        # Capital gains
        acquisition_cost = purchase_price + purchase["total_purchase_costs"] + renovation_budget
        cap_gains = self.calculate_capital_gains_tax(
            sale_price=target_sale_price,
            acquisition_cost=acquisition_cost,
            sale_costs=sale_costs,
            holding_months=holding_months,
        )

        net_proceeds = target_sale_price - sale_costs - cap_gains["tax_amount"]
        net_profit = net_proceeds - total_invested_with_holding

        roi_pct = round(net_profit / total_invested_with_holding * 100, 1) if total_invested_with_holding > 0 else 0
        annualized_roi = round(roi_pct / max(holding_months, 1) * 12, 1)

        # Break-even sale price
        breakeven = math.ceil(
            (total_invested_with_holding + sale_costs)
            / (1 - cap_gains["tax_rate"])
        ) if cap_gains["tax_rate"] < 1 else 0

        return {
            "investment_summary": {
                "purchase_price": purchase_price,
                "purchase_costs": purchase["total_purchase_costs"],
                "renovation_budget": renovation_budget,
                "holding_costs": holding_cost,
                "total_invested": total_invested_with_holding,
            },
            "sale_summary": {
                "target_sale_price": target_sale_price,
                "sale_commission": sale_costs,
                "capital_gains_tax": cap_gains["tax_amount"],
                "net_proceeds": net_proceeds,
            },
            "returns": {
                "net_profit": net_profit,
                "roi_percent": roi_pct,
                "annualized_roi_percent": annualized_roi,
                "breakeven_sale_price": breakeven,
            },
            "tax_detail": cap_gains,
            "holding_detail": {
                "months": holding_months,
                "monthly_cost": holding["monthly"],
                "total_holding_cost": holding_cost,
            },
            "cost_breakdown": purchase,
        }
