from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class OfferState(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    COUNTERED = "COUNTERED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class ValidationStatus(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    PENDING_AUTHORITATIVE_QUOTE = "PENDING_AUTHORITATIVE_QUOTE"


class OfferTerms(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku_id: str = Field(min_length=1, max_length=128)
    quantity_min: int = Field(gt=0)
    quantity_max: int = Field(gt=0)
    unit_price_minor: int = Field(ge=0)
    estimated_freight_per_unit_minor: int = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)
    delivery_terms: str = Field(min_length=1, max_length=500)
    substitution_consent: bool = False

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def validate_quantity_range(self) -> "OfferTerms":
        if self.quantity_min > self.quantity_max:
            raise ValueError("quantity_min must not exceed quantity_max")
        return self

    @property
    def estimated_landed_unit_cost_minor(self) -> int:
        return self.unit_price_minor + self.estimated_freight_per_unit_minor


class CreateOfferRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    procurement_request_id: UUID
    buyer_id: UUID
    seller_id: UUID
    actor_id: UUID
    price_ceiling_per_unit_minor: int = Field(ge=0)
    terms: OfferTerms


class CounterOfferRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor_id: UUID
    terms: OfferTerms


class AcceptanceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor_id: UUID


class OfferValidation(BaseModel):
    status: ValidationStatus
    reason: str | None = None


class OfferResponse(BaseModel):
    id: UUID
    procurement_request_id: UUID
    buyer_id: UUID
    seller_id: UUID
    actor_id: UUID
    version: int
    state: OfferState
    price_ceiling_per_unit_minor: int
    terms: OfferTerms
    validation: OfferValidation
    created_at: datetime
    updated_at: datetime


class OfferRecord(BaseModel):
    """Internal state. It stays independent of ORM or provider models."""

    id: UUID = Field(default_factory=uuid4)
    procurement_request_id: UUID
    buyer_id: UUID
    seller_id: UUID
    actor_id: UUID
    version: int = 1
    state: OfferState = OfferState.SUBMITTED
    price_ceiling_per_unit_minor: int
    terms: OfferTerms
    validation: OfferValidation
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def response(self) -> OfferResponse:
        return OfferResponse.model_validate(self.model_dump())
