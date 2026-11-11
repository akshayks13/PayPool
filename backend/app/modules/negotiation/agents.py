"""Provider-neutral, typed agent orchestration.

This module deliberately contains no model SDK, database access, payment calls,
or mutable seller operations. An LLM adapter may later enrich extraction, but
the validated intent and allowlisted tools remain the security boundary.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID, uuid4

from app.modules.negotiation.procurement_schemas import ProcurementIntent


class AgentName(StrEnum):
    BUYER_PROCUREMENT = "BUYER_PROCUREMENT"
    DISTRIBUTOR_YIELD = "DISTRIBUTOR_YIELD"


class RecommendationStatus(StrEnum):
    RECOMMENDED = "RECOMMENDED"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    NO_ELIGIBLE_CATALOG_MATCH = "NO_ELIGIBLE_CATALOG_MATCH"


@dataclass(frozen=True)
class CatalogSearchQuery:
    product_query: str
    quantity: str
    unit: str
    delivery_date: str
    substitution_consent: bool


@dataclass(frozen=True)
class CatalogCandidate:
    sku_id: str
    title: str
    seller_id: UUID | str
    currency: str
    estimated_landed_unit_cost_minor: int
    available_quantity: str


class CatalogSearchTool(Protocol):
    """Member 2 adapter. It must apply stock and serviceability filters."""

    def search_catalog(self, query: CatalogSearchQuery) -> list[CatalogCandidate]: ...


@dataclass(frozen=True)
class AgentToolCallAudit:
    tool_name: str
    outcome: str


@dataclass(frozen=True)
class AgentRecommendation:
    run_id: UUID
    status: RecommendationStatus
    candidate: CatalogCandidate | None
    clarification_questions: tuple[str, ...]
    tool_calls: tuple[AgentToolCallAudit, ...]


@dataclass(frozen=True)
class YieldTier:
    minimum_quantity: Decimal
    unit_price_minor: int


@dataclass(frozen=True)
class YieldPolicy:
    seller_id: UUID | str
    sku_id: str
    available_quantity: Decimal
    route_fee_minor: int
    tiers: tuple[YieldTier, ...]


@dataclass(frozen=True)
class YieldRecommendation:
    run_id: UUID
    seller_id: UUID | str
    sku_id: str
    proposed_unit_price_minor: int | None
    proposed_route_fee_minor: int | None
    threshold_viable: bool
    reason: str


class BuyerProcurementAgent:
    """Produces a recommendation only; it cannot create or accept an order."""

    def __init__(self, catalog_search: CatalogSearchTool) -> None:
        self._catalog_search = catalog_search

    def recommend(self, intent: ProcurementIntent) -> AgentRecommendation:
        run_id = uuid4()
        if intent.clarification_questions:
            return AgentRecommendation(
                run_id=run_id,
                status=RecommendationStatus.NEEDS_CLARIFICATION,
                candidate=None,
                clarification_questions=tuple(intent.clarification_questions),
                tool_calls=(),
            )

        # Intent validation guarantees these values are present when there are
        # no clarification questions.
        query = CatalogSearchQuery(
            product_query=intent.product_description or "",
            quantity=str(intent.quantity),
            unit=intent.quantity_unit or "",
            delivery_date=intent.delivery_date.isoformat() if intent.delivery_date else "",
            substitution_consent=intent.substitution_consent,
        )
        candidates = self._catalog_search.search_catalog(query)
        eligible = [
            candidate
            for candidate in candidates
            if candidate.currency == intent.currency
            and candidate.estimated_landed_unit_cost_minor
            <= (intent.price_ceiling_per_unit_minor or -1)
        ]
        audit = (AgentToolCallAudit(tool_name="search_catalog", outcome="completed"),)
        if not eligible:
            return AgentRecommendation(
                run_id=run_id,
                status=RecommendationStatus.NO_ELIGIBLE_CATALOG_MATCH,
                candidate=None,
                clarification_questions=(),
                tool_calls=audit,
            )

        return AgentRecommendation(
            run_id=run_id,
            status=RecommendationStatus.RECOMMENDED,
            candidate=min(eligible, key=lambda item: item.estimated_landed_unit_cost_minor),
            clarification_questions=(),
            tool_calls=audit,
        )


class DistributorYieldAgent:
    """Advises from seller-approved policy; it never applies a price or stock change."""

    def recommend(self, policy: YieldPolicy, pool_demand_quantity: Decimal) -> YieldRecommendation:
        run_id = uuid4()
        if pool_demand_quantity <= 0:
            return YieldRecommendation(
                run_id=run_id,
                seller_id=policy.seller_id,
                sku_id=policy.sku_id,
                proposed_unit_price_minor=None,
                proposed_route_fee_minor=None,
                threshold_viable=False,
                reason="pool demand must be greater than zero",
            )
        if pool_demand_quantity > policy.available_quantity:
            return YieldRecommendation(
                run_id=run_id,
                seller_id=policy.seller_id,
                sku_id=policy.sku_id,
                proposed_unit_price_minor=None,
                proposed_route_fee_minor=None,
                threshold_viable=False,
                reason="pool demand exceeds seller-configured available quantity",
            )

        eligible_tiers = [tier for tier in policy.tiers if tier.minimum_quantity <= pool_demand_quantity]
        if not eligible_tiers:
            return YieldRecommendation(
                run_id=run_id,
                seller_id=policy.seller_id,
                sku_id=policy.sku_id,
                proposed_unit_price_minor=None,
                proposed_route_fee_minor=None,
                threshold_viable=False,
                reason="pool demand has not reached a configured volume tier",
            )

        selected = max(eligible_tiers, key=lambda tier: tier.minimum_quantity)
        return YieldRecommendation(
            run_id=run_id,
            seller_id=policy.seller_id,
            sku_id=policy.sku_id,
            proposed_unit_price_minor=selected.unit_price_minor,
            proposed_route_fee_minor=policy.route_fee_minor,
            threshold_viable=True,
            reason="recommendation is advisory and requires seller approval",
        )
