from datetime import date
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import create_app
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


def test_parse_extracts_intent_and_requires_confirmation() -> None:
    parser = DeterministicProcurementParser()
    intent = parser.parse(
        ProcurementParseRequest(
            message=(
                "30 kg Sona Masoori rice by 2026-11-13, landed price below "
                "₹52/kg; equivalent brands allowed but rice variety unchanged."
            )
        )
    )

    assert intent.product_description == "Sona Masoori rice"
    assert intent.quantity == Decimal("30")
    assert intent.delivery_date == date(2026, 11, 13)
    assert intent.price_ceiling_per_unit_minor == 5200
    assert intent.substitution_consent is True
    assert intent.protected_attributes == ("rice variety",)
    assert intent.clarification_questions == ()
    assert intent.confirmation_required is True


def test_parse_returns_clarification_for_ambiguous_weekday(monkeypatch) -> None:
    monkeypatch.setenv("PAYPOOL_LLM_PROVIDER", "deterministic")
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/v1/procurement/parse",
            json={"message": "30 kg rice by Friday, landed price below ₹52/kg"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["delivery_date"] is None
    assert "YYYY-MM-DD" in body["clarification_questions"][0]


class StubCatalogSearch:
    def search_catalog(self, query: CatalogSearchQuery) -> list[CatalogCandidate]:
        return [
            CatalogCandidate(
                sku_id="eligible-rice",
                title="Sona Masoori Rice",
                seller_id=uuid4(),
                currency="INR",
                estimated_landed_unit_cost_minor=5100,
                available_quantity="50",
            ),
            CatalogCandidate(
                sku_id="over-ceiling-rice",
                title="Premium Rice",
                seller_id=uuid4(),
                currency="INR",
                estimated_landed_unit_cost_minor=5400,
                available_quantity="50",
            ),
        ]


def test_buyer_agent_only_recommends_catalog_match_within_ceiling() -> None:
    intent = DeterministicProcurementParser().parse(
        ProcurementParseRequest(
            message="30 kg rice by 2026-11-13, landed price below ₹52/kg"
        )
    )
    recommendation = BuyerProcurementAgent(StubCatalogSearch()).recommend(intent)

    assert recommendation.status == "RECOMMENDED"
    assert recommendation.candidate is not None
    assert recommendation.candidate.sku_id == "eligible-rice"
    assert recommendation.tool_calls[0].tool_name == "search_catalog"


def test_yield_agent_selects_only_an_earned_seller_configured_tier() -> None:
    policy = YieldPolicy(
        seller_id=uuid4(),
        sku_id="rice-sona-masoori-25kg",
        available_quantity=Decimal("100"),
        route_fee_minor=2_000,
        tiers=(
            YieldTier(minimum_quantity=Decimal("10"), unit_price_minor=5_100),
            YieldTier(minimum_quantity=Decimal("30"), unit_price_minor=4_900),
        ),
    )

    recommendation = DistributorYieldAgent().recommend(policy, Decimal("35"))

    assert recommendation.threshold_viable is True
    assert recommendation.proposed_unit_price_minor == 4_900
    assert recommendation.proposed_route_fee_minor == 2_000
    assert "seller approval" in recommendation.reason
