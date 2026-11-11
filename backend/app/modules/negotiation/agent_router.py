"""HTTP boundary for constrained agent recommendations."""

import os
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.modules.negotiation.agents import CatalogCandidate, CatalogSearchQuery, YieldPolicy, YieldTier
from app.modules.negotiation.llm import (
    DeterministicNegotiationNarrator,
    GeminiNegotiationNarrator,
    LLMUnavailableError,
    NegotiationNarrator,
)
from app.modules.negotiation.orchestration import (
    AgentOrchestrationService,
    AgentRunRequest,
    AgentRunResponse,
    InMemoryAgentRunRepository,
    NegotiationDataTools,
)

router = APIRouter(prefix="/agents", tags=["agents"])


class DevelopmentNegotiationTools:
    """Demo-only Member 2 adapter; it is never a catalog source of truth."""

    DEMO_SELLER_ID = UUID("20000000-0000-0000-0000-000000000001")

    def search_catalog(self, query: CatalogSearchQuery) -> list[CatalogCandidate]:
        if "rice" not in query.product_query.lower():
            return []
        return [
            CatalogCandidate(
                sku_id="rice-sona-masoori-25kg",
                title="Sona Masoori Rice, 25 kg bag",
                seller_id=self.DEMO_SELLER_ID,
                currency="INR",
                estimated_landed_unit_cost_minor=5_100,
                available_quantity="120",
            )
        ]

    def get_yield_policy(self, seller_id: UUID, sku_id: str) -> YieldPolicy | None:
        if seller_id != self.DEMO_SELLER_ID or sku_id != "rice-sona-masoori-25kg":
            return None
        return YieldPolicy(
            seller_id=seller_id,
            sku_id=sku_id,
            available_quantity=Decimal("120"),
            route_fee_minor=6_000,
            tiers=(
                YieldTier(minimum_quantity=Decimal("10"), unit_price_minor=4_950),
                YieldTier(minimum_quantity=Decimal("30"), unit_price_minor=4_900),
            ),
        )

    def estimated_freight_per_unit_minor(
        self, buyer_id: UUID, seller_id: UUID, sku_id: str, quantity: Decimal
    ) -> int:
        return 200


_repository = InMemoryAgentRunRepository()
_tools: NegotiationDataTools = DevelopmentNegotiationTools()


def get_narrator() -> NegotiationNarrator:
    provider = os.getenv("PAYPOOL_AGENT_NARRATOR_PROVIDER", os.getenv("PAYPOOL_LLM_PROVIDER", "gemini")).lower()
    if provider == "deterministic":
        return DeterministicNegotiationNarrator()
    if provider == "gemini":
        return GeminiNegotiationNarrator.from_environment()
    raise LLMUnavailableError(f"unsupported agent narrator provider: {provider}")


def get_agent_service() -> AgentOrchestrationService:
    return AgentOrchestrationService(_tools, get_narrator(), _repository)


AgentServiceDependency = Annotated[AgentOrchestrationService, Depends(get_agent_service)]


@router.post("/negotiations/recommend", response_model=AgentRunResponse, status_code=status.HTTP_200_OK)
def recommend_negotiation(
    request: AgentRunRequest, service: AgentServiceDependency
) -> AgentRunResponse:
    try:
        return service.recommend(request)
    except LLMUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "LLM_UNAVAILABLE", "message": str(error)},
        ) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
