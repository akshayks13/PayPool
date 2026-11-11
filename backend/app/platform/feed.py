"""Discovery feed preparation; does not publish or enable partner checkout."""

from app.platform import service

SOURCE = "https://developers.openai.com/commerce/specs/file-upload/products"


def prepare(tx, seller):
    stock = service.available_stock(tx)
    records, rejected = [], []
    for product in tx.all("products"):
        if product["seller_id"] != seller["id"]:
            continue
        missing = [
            field
            for field, value in {
                "description": product.get("description"),
                "brand": product.get("attributes", {}).get("brand"),
                "image_url": product.get("image_url", "").startswith("https://"),
                "product_url": product.get("product_url"),
            }.items()
            if not value
        ]
        if missing:
            rejected.append(
                {
                    "id": product["id"],
                    "title": product["title"],
                    "missing_fields": missing,
                }
            )
            continue
        # Public discovery must not advertise a bulk discount that an
        # individual buyer has not earned. Shared freight is quote-dependent.
        base = next(
            t["unit_price_minor"]
            for t in product["tiers"]
            if t["minimum_quantity"] == 1
        )
        records.append(
            {
                "item_id": product["id"],
                "title": product["title"],
                "description": product["description"],
                "url": product["product_url"],
                "brand": product["attributes"]["brand"],
                "seller_name": seller["name"],
                "image_url": product["image_url"],
                "availability": "in_stock"
                if stock.get(product["id"], 0) > 0 and product.get("active", True)
                else "out_of_stock",
                "price": f"{base // 100}.{base % 100:02d} {product['currency']}",
                "is_eligible_search": product.get("active", True),
                "is_eligible_checkout": False,
            }
        )
    return {
        "products": records,
        "rejected": rejected,
        "source": SOURCE,
        "published": False,
        "note": "Private preparation/export only. Final freight, geographic eligibility and pooled prices require a PayPool quote; external checkout is disabled.",
    }
