"""Connect the typed buyer and distributor agents to authoritative catalog facts.

The agents advise independently within their own authority. Only the domain
clearing and buyer-approval services can create executable agreements.
"""

from decimal import Decimal

from app.modules.negotiation.agents import (
    BuyerProcurementAgent,
    CatalogCandidate,
    DistributorYieldAgent,
    YieldPolicy,
    YieldTier,
)


class LiveCatalogTool:
    def __init__(self, candidates):
        self.candidates = candidates

    def search_catalog(self, query):
        # Candidates have already passed stock, currency, unit, requested
        # variety and service-zone filters for this exact parsed intent.
        return [
            CatalogCandidate(
                sku_id=c["product_id"],
                title=c["title"],
                seller_id=c["seller_id"],
                currency=c["currency"],
                available_quantity=str(c["available_stock"]),
                estimated_landed_unit_cost_minor=(
                    c["estimated_total_minor"] + c["quantity"] - 1
                )
                // c["quantity"],
            )
            for c in self.candidates
        ]


def coordinate(intent, candidates, products):
    supplier = DistributorYieldAgent()
    recommendations = []
    valid = []
    for candidate in candidates:
        product = products[candidate["product_id"]]
        result = supplier.recommend(
            YieldPolicy(
                seller_id=product["seller_id"],
                sku_id=product["id"],
                available_quantity=Decimal(candidate["available_stock"]),
                route_fee_minor=candidate["estimated_route_freight_minor"],
                tiers=tuple(
                    YieldTier(Decimal(t["minimum_quantity"]), t["unit_price_minor"])
                    for t in product["tiers"]
                ),
            ),
            Decimal(candidate["pool_quantity"]),
        )
        recommendations.append(
            {
                "agent": "DISTRIBUTOR_YIELD",
                "run_id": str(result.run_id),
                "product_id": result.sku_id,
                "status": "POLICY_APPROVED_ESTIMATE"
                if result.threshold_viable
                else "REJECTED",
                "unit_price_minor": result.proposed_unit_price_minor,
                "reason": result.reason,
                "tool": "read_seller_stock_and_tiers",
            }
        )
        if (
            result.threshold_viable
            and result.proposed_unit_price_minor == candidate["unit_price_minor"]
        ):
            valid.append(candidate)
    buyer = BuyerProcurementAgent(LiveCatalogTool(valid)).recommend(intent)
    return valid, {
        "buyer": {
            "agent": "BUYER_PROCUREMENT",
            "run_id": str(buyer.run_id),
            "status": str(buyer.status),
            "recommended_product_id": buyer.candidate.sku_id
            if buyer.candidate
            else None,
            "tools": [
                {"name": c.tool_name, "outcome": c.outcome} for c in buyer.tool_calls
            ],
        },
        "distributor": recommendations,
        "execution": "In-process advisory agents; final clearing and explicit consent remain mandatory",
    }
