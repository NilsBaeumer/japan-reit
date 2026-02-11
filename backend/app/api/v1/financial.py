from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class PurchaseCostRequest(BaseModel):
    purchase_price: int
    assessed_value: int | None = None
    is_land_only: bool = False


class ROIRequest(BaseModel):
    purchase_price: int
    assessed_value: int | None = None
    renovation_budget: int = 0
    target_sale_price: int = 0
    holding_months: int = 12
    annual_fixed_asset_tax: int | None = None


@router.post("/purchase-costs")
async def calculate_purchase_costs(req: PurchaseCostRequest):
    from app.services.financial_service import FinancialService

    svc = FinancialService()
    costs = svc.calculate_purchase_costs(
        price=req.purchase_price,
        assessed_value=req.assessed_value,
        is_land_only=req.is_land_only,
    )
    return costs


@router.post("/roi-projection")
async def calculate_roi(req: ROIRequest):
    from app.services.financial_service import FinancialService

    svc = FinancialService()
    projection = svc.calculate_roi_projection(
        purchase_price=req.purchase_price,
        assessed_value=req.assessed_value,
        renovation_budget=req.renovation_budget,
        target_sale_price=req.target_sale_price,
        holding_months=req.holding_months,
    )
    return projection


@router.get("/tax-rates")
async def get_tax_rates():
    return {
        "stamp_tax": {
            "1M_to_5M": 2000,
            "5M_to_10M": 5000,
            "10M_to_50M": 10000,
            "note": "Reduced rates through 2027-03-31",
        },
        "registration_tax": {
            "ownership_transfer_land": 0.015,
            "ownership_transfer_building": 0.02,
            "mortgage": 0.004,
            "note": "Land reduced rate 1.5% through 2026-03-31",
        },
        "acquisition_tax": {
            "land": 0.03,
            "building_residential": 0.03,
            "land_assessment_multiplier": 0.5,
        },
        "capital_gains": {
            "short_term_lte_5yr": 0.3963,
            "long_term_gt_5yr": 0.20315,
            "note": "5-year threshold: Jan 1 after acquisition to Jan 1 of sale year",
        },
        "annual_holding": {
            "fixed_asset_tax": 0.014,
            "city_planning_tax": 0.003,
        },
        "broker_commission": {
            "standard_pct_under_2M": 0.055,
            "standard_pct_2M_to_4M": 0.044,
            "standard_pct_over_4M": 0.033,
            "low_price_max_incl_tax": 330000,
            "low_price_threshold": 8000000,
            "note": "Low-price special rule since 2024-07-01: max ¥330,000 incl. tax per party for deals <= ¥8M",
        },
    }
