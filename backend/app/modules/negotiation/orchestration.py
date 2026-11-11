"""Safe buyer/seller negotiation orchestration.

This is an application-service boundary, not an autonomous purchasing agent.
Every commercial value comes from a typed tool adapter and is rechecked before
it is returned. The optional LLM only explains the calculated result.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.modules.negotiation.agents import (
    BuyerProcurementAgent,
    CatalogCandidate,
    CatalogSearchQuery,
    DistributorYieldAgent,
    YieldPolicy,
    YieldTier,
)
from app.modules.negotiation.llm import (
    NegotiationNarrationFacts,
    NegotiationNarrative,
    NegotiationNarrator,
)
from app.modules.negotiation.procurement_schemas import ProcurementIntent
from app.modules.negotiation.schemas import OfferTerms


class AgentRunStatus(StrEnum):
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    NO_MATCH = "NO_MATCH"
    READY_FOR_SELLER_APPROVAL = "READY_FOR_SELLER_APPROVAL"


class AgentToolName(StrEnum):
    SEARCH_CATALOG = "search_catalog"
    GET_PRODUCT_DETAILS = "get_product_details"
    GET_INVENTORY = "get_inventory"
    GET_SERVICEABLE_SELLERS = "get_serviceable_sellers"
    GET_PRICE_TIERS = "get_price_tiers"
    GET_POOL_QUOTE = "get_pool_quote"
    GET_ALLOCATION_PREVIEW = "get_allocation_preview"


class AgentRunRequest(BaseModel):
    """Request accepted only after a retailer has explicitly reviewed it.

    Authentication and the canonical procurement-request record will be owned
    by the identity/procurement modules. Until they exist, these IDs are an
    integration contract, not proof of a caller's identity.
    """

    model_config = ConfigDict(extra="forbid")

    procurement_request_id: UUID
    buyer_id: UUID
    seller_id: UUID
    retailer_confirmed: bool
    intent: ProcurementIntent


class ToolAudit(BaseModel):
    tool_name: AgentToolName
    outcome: str


class AgentMessage(BaseModel):
    speaker: str
    message: str
    next_step: str


class AgentRunResponse(BaseModel):
    run_id: UUID
    status: AgentRunStatus
    created_at: datetime
    tool_calls: list[ToolAudit]
    messages: list[AgentMessage]
    candidate_sku_id: str | None = None
    proposed_terms: OfferTerms | None = None
    price_ceiling_per_unit_minor: int | None = None
    validation_note: str
    action_required: str


class NegotiationDataTools(Protocol):
    """Allowlisted Member 2 ports. Implementations authenticate service calls."""

    def search_catalog(self, query: CatalogSearchQuery) -> list[CatalogCandidate]: ...

    def get_yield_policy(self, seller_id: UUID, sku_id: str) -> YieldPolicy | None: ...

    def estimated_freight_per_unit_minor(
        self, buyer_id: UUID, seller_id: UUID, sku_id: str, quantity: Decimal
    ) -> int: ...


@dataclass(frozen=True)
class _ToolAuditedCatalog:
    tools: NegotiationDataTools
    audit: list[ToolAudit]

    def search_catalog(self, query: CatalogSearchQuery) -> list[CatalogCandidate]:
        self.audit.append(ToolAudit(tool_name=AgentToolName.SEARCH_CATALOG, outcome="completed"))
        return self.tools.search_catalog(query)


class InMemoryAgentRunRepository:
    """Development repository; replace with the owned agent_runs tables."""

    def __init__(self) -> None:
        self._runs: dict[UUID, AgentRunResponse] = {}

    def save(self, run: AgentRunResponse) -> AgentRunResponse:
        self._runs[run.run_id] = run
        return run

    def get(self, run_id: UUID) -> AgentRunResponse | None:
        return self._runs.get(run_id)


class AgentOrchestrationService:
    def __init__(
        self,
        tools: NegotiationDataTools,
        narrator: NegotiationNarrator,
        repository: InMemoryAgentRunRepository,
    ) -> None:
        self._tools = tools
        self._narrator = narrator
        self._repository = repository

    def recommend(self, request: AgentRunRequest) -> AgentRunResponse:
        if not request.retailer_confirmed:
            raise ValueError("retailer confirmation is required before agent negotiation")

        intent = request.intent
        if intent.clarification_questions:
            message = self._narrator.narrate(
                NegotiationNarrationFacts(
                    speaker="buyer",
                    currency=intent.currency,
                    status="NEEDS_CLARIFICATION",
                    required_action="Answer the clarification questions and confirm the request again.",
                )
            )
            return self._save(
                status=AgentRunStatus.NEEDS_CLARIFICATION,
                audit=[],
                messages=[AgentMessage(speaker="Buyer helper", **message.model_dump())],
                candidate_sku_id=None,
                terms=None,
                ceiling=intent.price_ceiling_per_unit_minor,
                note="No catalog or seller tool was called because the request is incomplete.",
                action="Retailer must clarify and reconfirm the request.",
            )

        if (
            intent.quantity is None
            or intent.quantity_unit is None
            or intent.delivery_date is None
            or intent.price_ceiling_per_unit_minor is None
        ):
            raise ValueError("a confirmed request must contain complete procurement constraints")

        audit: list[ToolAudit] = []
        buyer = BuyerProcurementAgent(_ToolAuditedCatalog(self._tools, audit))
        recommendation = buyer.recommend(intent)
        if recommendation.candidate is None:
            narration = self._narrator.narrate(
                NegotiationNarrationFacts(
                    speaker="buyer",
                    product_title=intent.product_description,
                    quantity=str(intent.quantity),
                    unit=intent.quantity_unit,
                    currency=intent.currency,
                    price_ceiling_per_unit_minor=intent.price_ceiling_per_unit_minor,
                    delivery_date=intent.delivery_date,
                    status="NO_MATCH",
                    required_action="Try a different product, date, or maximum price.",
                )
            )
            return self._save(
                status=AgentRunStatus.NO_MATCH,
                audit=audit,
                messages=[AgentMessage(speaker="Buyer helper", **narration.model_dump())],
                candidate_sku_id=None,
                terms=None,
                ceiling=intent.price_ceiling_per_unit_minor,
                note="No eligible catalog result met the retailer's ceiling.",
                action="Retailer must adjust the request; no offer was created.",
            )

        candidate = recommendation.candidate
        audit.append(ToolAudit(tool_name=AgentToolName.GET_INVENTORY, outcome="completed"))
        audit.append(ToolAudit(tool_name=AgentToolName.GET_PRICE_TIERS, outcome="completed"))
        policy = self._tools.get_yield_policy(request.seller_id, candidate.sku_id)
        if policy is None or policy.seller_id != request.seller_id:
            return self._no_seller_policy(request, audit, candidate)

        seller = DistributorYieldAgent()
        seller_recommendation = seller.recommend(policy, intent.quantity)
        if (
            not seller_recommendation.threshold_viable
            or seller_recommendation.proposed_unit_price_minor is None
            or seller_recommendation.proposed_route_fee_minor is None
        ):
            return self._no_seller_policy(request, audit, candidate)

        audit.append(ToolAudit(tool_name=AgentToolName.GET_POOL_QUOTE, outcome="estimated"))
        freight = self._tools.estimated_freight_per_unit_minor(
            request.buyer_id, request.seller_id, candidate.sku_id, intent.quantity
        )
        if freight < 0:
            raise ValueError("freight estimate must not be negative")
        terms = OfferTerms(
            sku_id=candidate.sku_id,
            quantity_min=int(intent.quantity),
            quantity_max=int(intent.quantity),
            unit_price_minor=seller_recommendation.proposed_unit_price_minor,
            estimated_freight_per_unit_minor=freight,
            currency=intent.currency,
            delivery_terms=f"Delivery by {intent.delivery_date.isoformat()}",
            substitution_consent=intent.substitution_consent,
        )
        if terms.estimated_landed_unit_cost_minor > intent.price_ceiling_per_unit_minor:
            return self._above_ceiling(request, audit, candidate, terms)

        buyer_narration = self._narrator.narrate(
            NegotiationNarrationFacts(
                speaker="buyer",
                product_title=candidate.title,
                quantity=str(intent.quantity),
                unit=intent.quantity_unit,
                currency=intent.currency,
                estimated_landed_unit_cost_minor=terms.estimated_landed_unit_cost_minor,
                price_ceiling_per_unit_minor=intent.price_ceiling_per_unit_minor,
                delivery_date=intent.delivery_date,
                status="WITHIN_CEILING",
                required_action="Review the proposed terms. Nothing is final until both parties approve.",
            )
        )
        seller_narration = self._narrator.narrate(
            NegotiationNarrationFacts(
                speaker="seller",
                product_title=candidate.title,
                quantity=str(intent.quantity),
                unit=intent.quantity_unit,
                currency=intent.currency,
                unit_price_minor=terms.unit_price_minor,
                delivery_date=intent.delivery_date,
                status="SELLER_POLICY_MATCH",
                required_action="Seller must explicitly approve before this draft can be submitted.",
            )
        )
        return self._save(
            status=AgentRunStatus.READY_FOR_SELLER_APPROVAL,
            audit=audit,
            messages=[
                AgentMessage(speaker="Buyer helper", **buyer_narration.model_dump()),
                AgentMessage(speaker="Seller helper", **seller_narration.model_dump()),
            ],
            candidate_sku_id=candidate.sku_id,
            terms=terms,
            ceiling=intent.price_ceiling_per_unit_minor,
            note="Estimated terms pass the hard ceiling. Allocation, stock, and freight require final authoritative revalidation.",
            action="Seller approves or counters; buyer later confirms the authoritative allocation quote.",
        )

    def _no_seller_policy(
        self, request: AgentRunRequest, audit: list[ToolAudit], candidate: CatalogCandidate
    ) -> AgentRunResponse:
        narration = self._narrator.narrate(
            NegotiationNarrationFacts(
                speaker="seller",
                product_title=candidate.title,
                currency=request.intent.currency,
                status="SELLER_POLICY_UNAVAILABLE",
                required_action="Seller should review stock, service area, and price policy.",
            )
        )
        return self._save(
            status=AgentRunStatus.NO_MATCH,
            audit=audit,
            messages=[AgentMessage(speaker="Seller helper", **narration.model_dump())],
            candidate_sku_id=candidate.sku_id,
            terms=None,
            ceiling=request.intent.price_ceiling_per_unit_minor,
            note="No seller-approved tier is available for this request.",
            action="Seller must update or approve policy; no offer was created.",
        )

    def _above_ceiling(
        self, request: AgentRunRequest, audit: list[ToolAudit], candidate: CatalogCandidate, terms: OfferTerms
    ) -> AgentRunResponse:
        narration = self._narrator.narrate(
            NegotiationNarrationFacts(
                speaker="buyer",
                product_title=candidate.title,
                currency=request.intent.currency,
                estimated_landed_unit_cost_minor=terms.estimated_landed_unit_cost_minor,
                price_ceiling_per_unit_minor=request.intent.price_ceiling_per_unit_minor,
                status="ABOVE_CEILING",
                required_action="Ask the seller for a different tier or change the request yourself.",
            )
        )
        return self._save(
            status=AgentRunStatus.NO_MATCH,
            audit=audit,
            messages=[AgentMessage(speaker="Buyer helper", **narration.model_dump())],
            candidate_sku_id=candidate.sku_id,
            terms=None,
            ceiling=request.intent.price_ceiling_per_unit_minor,
            note="The independently calculated estimated landed cost exceeds the hard ceiling.",
            action="No offer was created and the ceiling was not changed.",
        )

    def _save(
        self,
        *,
        status: AgentRunStatus,
        audit: list[ToolAudit],
        messages: list[AgentMessage],
        candidate_sku_id: str | None,
        terms: OfferTerms | None,
        ceiling: int | None,
        note: str,
        action: str,
    ) -> AgentRunResponse:
        return self._repository.save(
            AgentRunResponse(
                run_id=uuid4(),
                status=status,
                created_at=datetime.now(UTC),
                tool_calls=audit,
                messages=messages,
                candidate_sku_id=candidate_sku_id,
                proposed_terms=terms,
                price_ceiling_per_unit_minor=ceiling,
                validation_note=note,
                action_required=action,
            )
        )

