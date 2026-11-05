from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ProcurementParseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=2_000)
    currency: str = Field(default="INR", min_length=3, max_length=3)


class ProcurementIntent(BaseModel):
    """A retailer-confirmed intent is required before search or negotiation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_message: str
    product_description: str | None = None
    quantity: Decimal | None = Field(default=None, gt=0)
    quantity_unit: str | None = None
    delivery_date: date | None = None
    delivery_date_text: str | None = None
    price_ceiling_per_unit_minor: int | None = Field(default=None, ge=0)
    currency: str
    substitution_consent: bool = False
    protected_attributes: tuple[str, ...] = ()
    clarification_questions: tuple[str, ...] = ()
    confirmation_required: bool = True
