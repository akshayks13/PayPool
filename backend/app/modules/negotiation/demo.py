"""Local negotiation sandbox with Gemini intent extraction and fixed fixtures."""

from decimal import Decimal
import os
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.negotiation.agents import (
    BuyerProcurementAgent,
    CatalogCandidate,
    CatalogSearchQuery,
    DistributorYieldAgent,
    YieldPolicy,
    YieldTier,
)
from app.modules.negotiation.procurement_parser import DeterministicProcurementParser
from app.modules.negotiation.procurement_schemas import ProcurementParseRequest
from app.modules.negotiation.llm import GeminiProcurementExtractor, ProcurementIntentExtractor
from app.modules.negotiation.schemas import CreateOfferRequest, OfferResponse, OfferTerms
from app.modules.negotiation.service import OfferService

BUYER_ID = UUID("10000000-0000-0000-0000-000000000001")
SELLER_ID = UUID("20000000-0000-0000-0000-000000000001")
DEMO_REQUEST_ID = UUID("30000000-0000-0000-0000-000000000001")
DEMO_SKU = "rice-sona-masoori-25kg"


class DemoProfile(BaseModel):
    id: UUID
    role: str
    business_name: str
    display_name: str
    location_label: str


class DemoNegotiationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(
        default="I need 30 kg Sona Masoori rice by 2026-11-13, landed price below INR 52/kg.",
        min_length=1,
        max_length=1_000,
    )


class NegotiationMessage(BaseModel):
    speaker: str
    text: str


class DemoNegotiationResponse(BaseModel):
    ai_provider: str
    buyer: DemoProfile
    seller: DemoProfile
    parsed_intent: dict[str, object]
    messages: list[NegotiationMessage]
    offer: OfferResponse | None
    buyer_approval: str
    seller_approval: str
    next_step: str


BUYER = DemoProfile(
    id=BUYER_ID,
    role="RETAILER",
    business_name="GreenMart Kirana",
    display_name="Anika Shah",
    location_label="South Bengaluru",
)
SELLER = DemoProfile(
    id=SELLER_ID,
    role="SELLER",
    business_name="Sree Distributors",
    display_name="Ravi Menon",
    location_label="South Bengaluru",
)


class DemoCatalog:
    """A constrained fixture adapter, not a second catalog source of truth."""

    def search_catalog(self, query: CatalogSearchQuery) -> list[CatalogCandidate]:
        if "rice" not in query.product_query.lower():
            return []
        return [
            CatalogCandidate(
                sku_id=DEMO_SKU,
                title="Sona Masoori Rice · 25 kg bag",
                seller_id=SELLER_ID,
                currency="INR",
                estimated_landed_unit_cost_minor=5_100,
                available_quantity="120",
            )
        ]


class DemoNegotiationService:
    def __init__(
        self,
        offer_service: OfferService,
        extractor: ProcurementIntentExtractor,
        ai_provider: str,
    ) -> None:
        self._offer_service = offer_service
        self._extractor = extractor
        self._ai_provider = ai_provider
        self._buyer_agent = BuyerProcurementAgent(DemoCatalog())
        self._seller_agent = DistributorYieldAgent()

    def profiles(self) -> list[DemoProfile]:
        return [BUYER, SELLER]

    def run(self, request: DemoNegotiationRequest) -> DemoNegotiationResponse:
        intent = self._extractor.parse(ProcurementParseRequest(message=request.message))
        intent_data = intent.model_dump(mode="json")
        messages = [
            NegotiationMessage(
                speaker="Buyer helper",
                text="I read the retailer's request and checked the stated maximum price.",
            )
        ]
        if intent.clarification_questions:
            return DemoNegotiationResponse(
                ai_provider=self._ai_provider,
                buyer=BUYER,
                seller=SELLER,
                parsed_intent=intent_data,
                messages=messages + [
                    NegotiationMessage(
                        speaker="Buyer helper",
                        text="I need more information before I can ask the seller for an offer.",
                    )
                ],
                offer=None,
                buyer_approval="NOT_READY",
                seller_approval="NOT_READY",
                next_step="Answer the clarification questions, then run the negotiation again.",
            )

        buyer_recommendation = self._buyer_agent.recommend(intent)
        if buyer_recommendation.candidate is None:
            return DemoNegotiationResponse(
                ai_provider=self._ai_provider,
                buyer=BUYER,
                seller=SELLER,
                parsed_intent=intent_data,
                messages=messages + [
                    NegotiationMessage(
                        speaker="Buyer helper",
                        text="No suitable seller product is available for this request.",
                    )
                ],
                offer=None,
                buyer_approval="NOT_READY",
                seller_approval="NOT_READY",
                next_step="Try another product, delivery date, or price limit.",
            )

        seller_policy = YieldPolicy(
            seller_id=SELLER_ID,
            sku_id=DEMO_SKU,
            available_quantity=Decimal("120"),
            route_fee_minor=6_000,
            tiers=(
                YieldTier(minimum_quantity=Decimal("10"), unit_price_minor=4_950),
                YieldTier(minimum_quantity=Decimal("30"), unit_price_minor=4_900),
            ),
        )
        seller_recommendation = self._seller_agent.recommend(seller_policy, intent.quantity or Decimal("0"))
        if not seller_recommendation.threshold_viable or seller_recommendation.proposed_unit_price_minor is None:
            return DemoNegotiationResponse(
                ai_provider=self._ai_provider,
                buyer=BUYER,
                seller=SELLER,
                parsed_intent=intent_data,
                messages=messages + [
                    NegotiationMessage(speaker="Seller helper", text=seller_recommendation.reason)
                ],
                offer=None,
                buyer_approval="NOT_READY",
                seller_approval="NOT_READY",
                next_step="Seller needs more pool demand or stock before offering.",
            )

        quantity = int(intent.quantity or Decimal("0"))
        terms = OfferTerms(
            sku_id=DEMO_SKU,
            quantity_min=quantity,
            quantity_max=quantity,
            unit_price_minor=seller_recommendation.proposed_unit_price_minor,
            estimated_freight_per_unit_minor=200,
            currency=intent.currency,
            delivery_terms=f"Delivery by {intent.delivery_date.isoformat()}",
            substitution_consent=intent.substitution_consent,
        )
        offer = self._offer_service.create(
            CreateOfferRequest(
                procurement_request_id=DEMO_REQUEST_ID,
                buyer_id=BUYER_ID,
                seller_id=SELLER_ID,
                actor_id=SELLER_ID,
                price_ceiling_per_unit_minor=intent.price_ceiling_per_unit_minor or 0,
                terms=terms,
            )
        )
        landed_minor = terms.estimated_landed_unit_cost_minor
        messages.extend(
            [
                NegotiationMessage(
                    speaker="Seller helper",
                    text=f"Sree Distributors can offer {quantity} kg at ₹{terms.unit_price_minor / 100:.2f}/kg.",
                ),
                NegotiationMessage(
                    speaker="Buyer helper",
                    text=f"Estimated landed cost is ₹{landed_minor / 100:.2f}/kg, within the retailer's stated limit.",
                ),
            ]
        )
        return DemoNegotiationResponse(
            ai_provider=self._ai_provider,
            buyer=BUYER,
            seller=SELLER,
            parsed_intent=intent_data,
            messages=messages,
            offer=offer,
            buyer_approval="PENDING",
            seller_approval="PENDING",
            next_step="Both buyer and seller must approve. Final allocation and freight still require the pooling service.",
        )


def demo_intent_extractor() -> tuple[ProcurementIntentExtractor, str]:
    """Gemini is the runtime default; deterministic mode is exclusively for tests."""
    provider = os.getenv("PAYPOOL_DEMO_NEGOTIATION_PROVIDER", "gemini").lower()
    if provider == "deterministic":
        return DeterministicProcurementParser(), "deterministic-test-fixture"
    if provider == "gemini":
        return GeminiProcurementExtractor.from_environment(), "gemini"
    raise ValueError(f"unsupported demo negotiation provider: {provider}")
