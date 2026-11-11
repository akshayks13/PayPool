from app.platform.auth import password_hash

DEMO_PASSWORD = "PayPool-demo-2026!"
ACCOUNTS = [
    (
        "buyer-a",
        "ananya@paypool.demo",
        "Ananya · GreenMart",
        ["RETAILER"],
        [77.59, 12.96],
    ),
    (
        "buyer-b",
        "rahul@paypool.demo",
        "Rahul · Corner Store",
        ["RETAILER"],
        [77.61, 12.97],
    ),
    (
        "buyer-c",
        "meera@paypool.demo",
        "Meera · Fresh Basket",
        ["RETAILER"],
        [77.60, 12.99],
    ),
    (
        "seller-demo",
        "seller@paypool.demo",
        "Sree Distributors",
        ["SELLER"],
        [77.58, 12.95],
    ),
    (
        "driver-demo",
        "driver@paypool.demo",
        "Kiran · Delivery",
        ["DRIVER"],
        [77.58, 12.95],
    ),
    (
        "admin-demo",
        "admin@paypool.demo",
        "PayPool Operations",
        ["ADMIN"],
        [77.58, 12.95],
    ),
]


def seed(store):
    with store.transaction() as tx:
        if tx.get("meta", "seed-v1"):
            upgrade(tx)
            return
        for key, email, name, roles, location in ACCOUNTS:
            tx.put(
                "users",
                {
                    "id": key,
                    "email": email,
                    "name": name,
                    "roles": roles,
                    "location": location,
                    "active": True,
                    "verified": True,
                    "demo_account": True,
                    "password_hash": password_hash(DEMO_PASSWORD),
                },
            )
        tx.put(
            "zones",
            {
                "id": "south-zone",
                "seller_id": "seller-demo",
                "name": "South Bengaluru · shared delivery",
                "currency": "USD",
                "polygon": [
                    [77.50, 12.90],
                    [77.70, 12.90],
                    [77.70, 13.05],
                    [77.50, 13.05],
                ],
                "depot": [77.58, 12.95],
                "base_freight_minor": 600,
                "stop_fee_minor": 100,
                "min_weight_grams": 50000,
                "max_weight_grams": 200000,
                "max_volume_cm3": 400000,
            },
        )
        for key, title, attributes, tiers in [
            (
                "rice-sona",
                "Sona Masoori rice",
                {"variety": "Sona Masoori", "brand": "Harvest"},
                [(1, 180), (60, 150), (100, 140)],
            ),
            (
                "rice-sona-alt",
                "Sona Masoori rice · alternative brand",
                {"variety": "Sona Masoori", "brand": "Field"},
                [(1, 175), (60, 145), (100, 135)],
            ),
            (
                "rice-basmati",
                "Basmati rice",
                {"variety": "Basmati", "brand": "Harvest"},
                [(1, 240), (60, 220), (100, 200)],
            ),
        ]:
            tx.put(
                "products",
                {
                    "id": key,
                    "seller_id": "seller-demo",
                    "title": title,
                    "unit": "kg",
                    "currency": "USD",
                    "stock": 500,
                    "weight_grams": 1000,
                    "volume_cm3": 1500,
                    "attributes": attributes,
                    "tiers": [
                        {"minimum_quantity": q, "unit_price_minor": p} for q, p in tiers
                    ],
                },
            )
        upgrade(tx)
        tx.put(
            "meta",
            {
                "id": "seed-v1",
                "description": "Fictional businesses, inventory and USD pricing; not real supplier offers",
            },
        )


def upgrade(tx):
    if tx.get("meta", "seed-v2-fleet"):
        return
    tx.put(
        "vehicles",
        {
            "id": "demo-van",
            "seller_id": "seller-demo",
            "name": "Shared delivery van",
            "registration": "DEMO-VAN-01",
            "max_weight_grams": 200000,
            "max_volume_cm3": 400000,
            "active": True,
        },
    )
    tx.put("meta", {"id": "seed-v2-fleet", "description": "Fictional vehicle record"})
