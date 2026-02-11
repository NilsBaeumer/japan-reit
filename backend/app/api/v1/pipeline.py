from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.financial import Deal, DueDiligenceItem

router = APIRouter()

VALID_STAGES = [
    "discovery", "analysis", "due_diligence", "negotiation",
    "purchase", "renovation", "listing", "sale", "completed", "abandoned",
]


class CreateDealRequest(BaseModel):
    property_id: str
    purchase_price: int | None = None
    notes: str | None = None


class UpdateDealRequest(BaseModel):
    stage: str | None = None
    purchase_price: int | None = None
    renovation_budget: int | None = None
    target_sale_price: int | None = None
    notes: str | None = None


@router.get("/deals")
async def list_deals(
    stage: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Deal).order_by(Deal.updated_at.desc())
    if stage:
        query = query.where(Deal.stage == stage)
    result = await db.execute(query)
    deals = result.scalars().all()
    return [_deal_to_dict(d) for d in deals]


@router.post("/deals")
async def create_deal(req: CreateDealRequest, db: AsyncSession = Depends(get_db)):
    deal = Deal(
        property_id=req.property_id,
        purchase_price=req.purchase_price,
        notes=req.notes,
        stage="discovery",
    )
    db.add(deal)
    await db.flush()

    # Create default due diligence items
    default_items = [
        ("legal", "fefta_report_filed", "File FEFTA report within 20 days of acquisition"),
        ("legal", "tax_agent_appointed", "Appoint tax agent (required for non-residents)"),
        ("legal", "domestic_contact_arranged", "Arrange domestic contact (国内連絡先)"),
        ("legal", "title_search", "Verify property title and encumbrances"),
        ("regulatory", "rebuild_check_confirmed", "Confirm rebuild capability (2m/4m road rule)"),
        ("regulatory", "road_width_verified", "Verify road classification with municipality"),
        ("regulatory", "zoning_confirmed", "Confirm zoning and building restrictions"),
        ("financial", "broker_commission_agreed", "Agree broker commission (check low-price rule)"),
        ("financial", "cost_sheet_prepared", "Prepare full transaction cost sheet"),
        ("physical", "building_inspection", "Conduct building inspection"),
        ("physical", "renovation_quote", "Obtain renovation quotes"),
    ]

    for i, (category, name, description) in enumerate(default_items):
        item = DueDiligenceItem(
            deal_id=deal.id,
            category=category,
            item_name=name,
            description=description,
            sort_order=i,
        )
        db.add(item)

    await db.flush()
    return _deal_to_dict(deal)


@router.patch("/deals/{deal_id}")
async def update_deal(
    deal_id: str,
    req: UpdateDealRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Deal).where(Deal.id == deal_id))
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    if req.stage is not None:
        if req.stage not in VALID_STAGES:
            raise HTTPException(status_code=400, detail=f"Invalid stage: {req.stage}")
        deal.stage = req.stage
    if req.purchase_price is not None:
        deal.purchase_price = req.purchase_price
    if req.renovation_budget is not None:
        deal.renovation_budget = req.renovation_budget
    if req.target_sale_price is not None:
        deal.target_sale_price = req.target_sale_price
    if req.notes is not None:
        deal.notes = req.notes

    await db.flush()
    return _deal_to_dict(deal)


@router.get("/deals/{deal_id}/checklist")
async def get_deal_checklist(deal_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(DueDiligenceItem)
        .where(DueDiligenceItem.deal_id == deal_id)
        .order_by(DueDiligenceItem.sort_order)
    )
    items = result.scalars().all()
    return [
        {
            "id": str(item.id),
            "category": item.category,
            "item_name": item.item_name,
            "description": item.description,
            "is_completed": item.is_completed,
            "completed_at": item.completed_at.isoformat() if item.completed_at else None,
            "due_date": item.due_date.isoformat() if item.due_date else None,
            "notes": item.notes,
        }
        for item in items
    ]


@router.patch("/checklist/{item_id}")
async def toggle_checklist_item(
    item_id: str,
    is_completed: bool,
    notes: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DueDiligenceItem).where(DueDiligenceItem.id == item_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Checklist item not found")

    item.is_completed = is_completed
    if is_completed:
        from datetime import datetime, timezone

        item.completed_at = datetime.now(timezone.utc)
    else:
        item.completed_at = None
    if notes is not None:
        item.notes = notes

    await db.flush()
    return {"status": "updated"}


def _deal_to_dict(d: Deal) -> dict:
    return {
        "id": str(d.id),
        "property_id": str(d.property_id),
        "purchase_price": d.purchase_price,
        "stage": d.stage,
        "renovation_budget": d.renovation_budget,
        "target_sale_price": d.target_sale_price,
        "notes": d.notes,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "updated_at": d.updated_at.isoformat() if d.updated_at else None,
    }
