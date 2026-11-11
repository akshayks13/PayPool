"""Bounded manifest optimization with independent monetary validation.

Freight ratios and volume-tier prices are nonlinear in membership. Enumerate
small feasible manifests first, then use CP-SAT to select the best manifest.
Quantity choices are the buyer's min/max and seller tier breakpoints, not an
unsubstantiated full nonlinear MILP. Large searches fail explicitly.
"""

from fractions import Fraction
from itertools import product as combinations
from math import asin, cos, radians, sin, sqrt

from ortools.constraint_solver import pywrapcp, routing_enums_pb2
from ortools.sat.python import cp_model


def inside(point, polygon):
    x, y = point
    result = False
    for (ax, ay), (bx, by) in zip(polygon, polygon[1:] + polygon[:1]):
        cross = (x - ax) * (by - ay) - (y - ay) * (bx - ax)
        if (
            abs(cross) < 1e-9
            and min(ax, bx) - 1e-9 <= x <= max(ax, bx) + 1e-9
            and min(ay, by) - 1e-9 <= y <= max(ay, by) + 1e-9
        ):
            return True
        if (ay > y) != (by > y) and x < (bx - ax) * (y - ay) / (by - ay) + ax:
            result = not result
    return result


def apportion(total, footprints, keys):
    denom = sum(footprints)
    if not denom:
        raise ValueError("Cannot split freight across zero demand")
    exact = [Fraction(total) * v / denom for v in footprints]
    shares = [int(v) for v in exact]
    # Largest remainder with stable request IDs breaks ties. Every cent is
    # allocated exactly once and the result does not depend on input order.
    order = sorted(range(len(keys)), key=lambda i: (-(exact[i] - shares[i]), keys[i]))
    for i in order[: total - sum(shares)]:
        shares[i] += 1
    return shares


def tier_price(item, quantity):
    return min(
        t["unit_price_minor"]
        for t in item["tiers"]
        if t["minimum_quantity"] <= quantity
    )


def evaluate(plan, zone, products, available):
    if not plan:
        return None
    demand = {}
    for r, sku, qty in plan:
        demand[sku] = demand.get(sku, 0) + qty
    if any(q > available.get(sku, 0) for sku, q in demand.items()):
        return None
    weights = [products[sku]["weight_grams"] * q for _, sku, q in plan]
    volumes = [products[sku]["volume_cm3"] * q for _, sku, q in plan]
    if (
        not zone["min_weight_grams"] <= sum(weights) <= zone["max_weight_grams"]
        or sum(volumes) > zone["max_volume_cm3"]
    ):
        return None
    footprints = [
        Fraction(w, zone["max_weight_grams"]) + Fraction(v, zone["max_volume_cm3"])
        for w, v in zip(weights, volumes)
    ]
    freight = zone["base_freight_minor"] + zone["stop_fee_minor"] * len(plan)
    shares = apportion(freight, footprints, [r["id"] for r, _, _ in plan])
    allocations = []
    for (r, sku, qty), share in zip(plan, shares):
        unit = tier_price(products[sku], demand[sku])
        total = unit * qty + share
        if total > r["ceiling_minor"] * qty:
            return None
        allocations.append(
            {
                "request_id": r["id"],
                "buyer_id": r["buyer_id"],
                "product_id": sku,
                "quantity": qty,
                "unit_price_minor": unit,
                "freight_minor": share,
                "total_minor": total,
                "ceiling_minor": r["ceiling_minor"],
                "currency": products[sku]["currency"],
                "substituted": sku != r["product_id"],
                "weight_grams": products[sku]["weight_grams"] * qty,
            }
        )
    return {
        "allocations": allocations,
        "freight_minor": freight,
        "weight_grams": sum(weights),
        "volume_cm3": sum(volumes),
        "demand": demand,
    }


def solve(requests, zone, products, users, available):
    choices = []
    for r in sorted(requests, key=lambda x: x["id"]):
        if not inside(users[r["buyer_id"]]["location"], zone["polygon"]):
            choices.append([None])
            continue
        options = [None]
        for sku in [r["product_id"], *r.get("substitute_product_ids", [])]:
            item = products[sku]
            quantities = {r["quantity_min"], r["quantity_max"]}
            quantities.update(
                t["minimum_quantity"]
                for t in item["tiers"]
                if r["quantity_min"] <= t["minimum_quantity"] <= r["quantity_max"]
            )
            options.extend((r, sku, q) for q in sorted(quantities))
        choices.append(options)
    count = 1
    for c in choices:
        count *= len(c)
    if count > 30000:
        raise ValueError(
            "This pool exceeds the MVP's 30,000 candidate-manifest limit; split the delivery run"
        )
    candidates = []
    for values in combinations(*choices):
        evaluated = evaluate(
            [v for v in values if v is not None], zone, products, available
        )
        if evaluated:
            candidates.append(evaluated)
    if not candidates:
        return None
    # Lexicographic: include most buyers, then most physical weight, then
    # minimize their total cost. Avoid silently dropping small shops for volume.
    best_count = max(len(c["allocations"]) for c in candidates)
    candidates = [c for c in candidates if len(c["allocations"]) == best_count]
    model = cp_model.CpModel()
    selected = [model.new_bool_var(f"manifest_{i}") for i in range(len(candidates))]
    model.add_exactly_one(selected)
    model.maximize(
        sum(selected[i] * c["weight_grams"] for i, c in enumerate(candidates))
    )
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 3
    solver.parameters.num_search_workers = 1
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise ValueError("Optimization did not find a valid manifest in time")
    optimum_weight = sum(
        c["weight_grams"] for i, c in enumerate(candidates) if solver.value(selected[i])
    )
    result = min(
        (c for c in candidates if c["weight_grams"] == optimum_weight),
        key=lambda c: (
            sum(a["total_minor"] for a in c["allocations"]),
            tuple(a["request_id"] for a in c["allocations"]),
        ),
    )
    # Independent recomputation from authoritative inputs, not solver fields.
    indexed = {r["id"]: r for r in requests}
    verified = evaluate(
        [
            (indexed[a["request_id"]], a["product_id"], a["quantity"])
            for a in result["allocations"]
        ],
        zone,
        products,
        available,
    )
    if (
        verified != result
        or sum(a["freight_minor"] for a in result["allocations"])
        != result["freight_minor"]
    ):
        raise ValueError("Independent allocation validation failed")
    result["excluded"] = [
        r["id"]
        for r in requests
        if r["id"] not in {a["request_id"] for a in result["allocations"]}
    ]
    result["solver"] = "OR-Tools CP-SAT · bounded manifest search"
    result["candidate_count"] = count
    return result


def route_order(depot, allocations, users):
    if not allocations:
        return []
    points = [depot] + [users[a["buyer_id"]]["location"] for a in allocations]

    def distance(a, b):
        lon1, lat1, lon2, lat2 = map(radians, [*a, *b])
        h = (
            sin((lat2 - lat1) / 2) ** 2
            + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
        )
        return int(12742000 * asin(min(1, sqrt(h))))

    manager = pywrapcp.RoutingIndexManager(len(points), 1, 0)
    model = pywrapcp.RoutingModel(manager)
    callback = model.RegisterTransitCallback(
        lambda a, b: distance(
            points[manager.IndexToNode(a)], points[manager.IndexToNode(b)]
        )
    )
    model.SetArcCostEvaluatorOfAllVehicles(callback)
    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    params.time_limit.seconds = 1
    solution = model.SolveWithParameters(params)
    if not solution:
        raise ValueError("No route was found")
    output, index = [], model.Start(0)
    while not model.IsEnd(index):
        node = manager.IndexToNode(index)
        if node:
            output.append(allocations[node - 1]["request_id"])
        index = solution.Value(model.NextVar(index))
    return output
