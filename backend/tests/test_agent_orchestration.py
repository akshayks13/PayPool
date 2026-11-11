from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.modules.negotiation.agents import (
    CatalogCandidate,
    CatalogSearchQuery,
    YieldPolicy,
    YieldTier,
)
from app.modules.negotiation.llm import DeterministicNegotiationNarrator
from app.modules.negotiation.orchestration import (
    AgentOrchestrationService,
    AgentRunRequest,
    AgentRunStatus,
    InMemoryAgentRunRepository,
)
from app.modules.negotiation.procurement_parser import DeterministicProcurementParser
from app.modules.negotiation.procurement_schemas import ProcurementParseRequest

SELLER_ID = UUID("20000000-0000-0000-0000-000000000001")


class StubTools:
    def __init__(self, freight_minor: int = 200, policy: YieldPolicy | None = None) -> None:
        self.freight_minor = freight_minor
        self.policy = policy or YieldPolicy(
            seller_id=SELLER_ID,
            sku_id="rice-sona-masoori-25kg",
            available_quantity=Decimal("120"),
            route_fee_minor=6_000,
            tiers=(YieldTier(minimum_quantity=Decimal("30"), unit_price_minor=4_900),),
        )

    def search_catalog(self, query: CatalogSearchQuery) -> list[CatalogCandidate]:
        return [
            CatalogCandidate(
                sku_id="rice-sona-masoori-25kg",
                title="Sona Masoori Rice",
                seller_id=SELLER_ID,
                currency="INR",
                estimated_landed_unit_cost_minor=5_100,
                available_quantity="120",
            )
        ]

    def get_yield_policy(self, seller_id: UUID, sku_id: str) -> YieldPolicy | None:
        return self.policy if seller_id == SELLER_ID and sku_id == self.policy.sku_id else None

    def estimated_freight_per_unit_minor(
        self, buyer_id: UUID, seller_id: UUID, sku_id: str, quantity: Decimal
    ) -> int:
        return self.freight_minor


def _request(*, confirmed: bool = True) -> AgentRunRequest:
    intent = DeterministicProcurementParser().parse(
        ProcurementParseRequest(message="30 kg Sona Masoori rice by 2026-11-13, landed price below INR 52/kg")
    )
    return AgentRunRequest(
        procurement_request_id=uuid4(),
        buyer_id=uuid4(),
        seller_id=SELLER_ID,
        retailer_confirmed=confirmed,
        intent=intent,
    )


def _service(tools: StubTools) -> AgentOrchestrationService:
    return AgentOrchestrationService(tools, DeterministicNegotiationNarrator(), InMemoryAgentRunRepository())


def test_agent_returns_only_a_draft_recommendation_within_hard_ceiling() -> None:
    result = _service(StubTools()).recommend(_request())

    assert result.status == AgentRunStatus.READY_FOR_SELLER_APPROVAL
    assert result.proposed_terms is not None
    assert result.proposed_terms.estimated_landed_unit_cost_minor == 5_100
    assert result.price_ceiling_per_unit_minor == 5_200
    assert [call.tool_name for call in result.tool_calls] == [
        "search_catalog",
        "get_inventory",
        "get_price_tiers",
        "get_pool_quote",
    ]
    assert "Nothing is final" in result.messages[0].next_step


def test_agent_requires_explicit_retailer_confirmation_before_tools_run() -> None:
    with pytest.raises(ValueError, match="retailer confirmation"):
        _service(StubTools()).recommend(_request(confirmed=False))


def test_agent_rejects_offer_when_freight_breaks_hard_ceiling() -> None:
    result = _service(StubTools(freight_minor=400)).recommend(_request())

    assert result.status == AgentRunStatus.NO_MATCH
    assert result.proposed_terms is None
    assert "ceiling was not changed" in result.action_required


def test_agent_does_not_offer_when_seller_tier_is_not_earned() -> None:
    policy = YieldPolicy(
        seller_id=SELLER_ID,
        sku_id="rice-sona-masoori-25kg",
        available_quantity=Decimal("120"),
        route_fee_minor=6_000,
        tiers=(YieldTier(minimum_quantity=Decimal("40"), unit_price_minor=4_900),),
    )
    result = _service(StubTools(policy=policy)).recommend(_request())

    assert result.status == AgentRunStatus.NO_MATCH
    assert result.proposed_terms is None
    assert "No seller-approved tier" in result.validation_note


def test_agent_endpoint_uses_llm_narrator_boundary_in_deterministic_test_mode(monkeypatch) -> None:
    monkeypatch.setenv("PAYPOOL_AGENT_NARRATOR_PROVIDER", "deterministic")
    request = _request().model_dump(mode="json")
    with TestClient(create_app()) as client:
        response = client.post("/api/v1/agents/negotiations/recommend", json=request)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "READY_FOR_SELLER_APPROVAL"
    assert body["proposed_terms"]["estimated_freight_per_unit_minor"] == 200
    assert body["action_required"].startswith("Seller approves")
