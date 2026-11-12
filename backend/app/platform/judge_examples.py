"""Daily, labelled purchasing examples. Never fabricate payment or delivery states."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.platform import service
from app.platform.models import Request
from app.platform.seed import seed
from app.platform.store import now


def prepare(store):
    day = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    key = "judge-buying-examples:" + day.isoformat()
    with store.transaction() as tx:
        if tx.get("meta", key):
            return tx.get("meta", key)
    seed(store)
    with store.transaction() as tx:
        if tx.get("meta", key):
            return tx.get("meta", key)
        seller = service.must(tx, "users", "seller-demo")
        occupied = {p["dispatch_date"] for p in tx.all("pools")}
        scenes = []
        for offset, buyers, label, clear in [
            (
                2,
                ["buyer-a", "buyer-b", "buyer-c"],
                "Judge example: three shops ready to pool",
                False,
            ),
            (
                3,
                ["buyer-a", "buyer-b"],
                "Judge example: two-shop delivered-price quote",
                True,
            ),
        ]:
            target = day + timedelta(days=offset)
            while target.isoformat() in occupied:
                target += timedelta(days=1)
            occupied.add(target.isoformat())
            for buyer_id in buyers:
                data = Request(
                    product_id="rice-sona",
                    zone_id="south-zone",
                    dispatch_date=target,
                    quantity_min=30,
                    quantity_max=30,
                    ceiling_minor=170,
                    note=label,
                ).model_dump(mode="json")
                request = service.submit_request(
                    tx, service.must(tx, "users", buyer_id), data
                )
            pool = service.must(tx, "pools", request["pool_id"])
            if clear:
                pool = service.clear_pool(tx, seller, pool)
            pool["example_label"] = label
            tx.put("pools", pool)
            scenes.append(
                {"pool_id": pool["id"], "date": target.isoformat(), "label": label}
            )
        return tx.put("meta", {"id": key, "created_at": now(), "scenes": scenes})
