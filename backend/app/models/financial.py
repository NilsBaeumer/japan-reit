import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid_str() -> str:
    return str(uuid.uuid4())


class Deal(Base):
    __tablename__ = "deals"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid_str
    )
    property_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("properties.id"), index=True
    )

    # Purchase
    purchase_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Costs
    broker_commission: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    stamp_tax: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    registration_tax: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    acquisition_tax: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    judicial_scrivener_fee: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    other_purchase_costs: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Renovation
    renovation_budget: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    renovation_actual: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    renovation_items: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Sale
    target_sale_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    actual_sale_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    sale_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    holding_period_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    capital_gains_tax_rate: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)

    # Pipeline
    stage: Mapped[str] = mapped_column(String(30), default="discovery", index=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    checklist_items: Mapped[list["DueDiligenceItem"]] = relationship(
        back_populates="deal", cascade="all, delete-orphan"
    )


class DueDiligenceItem(Base):
    __tablename__ = "due_diligence_items"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid_str
    )
    deal_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("deals.id", ondelete="CASCADE"), index=True
    )

    category: Mapped[str] = mapped_column(String(30))
    item_name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=0)

    deal: Mapped["Deal"] = relationship(back_populates="checklist_items")
