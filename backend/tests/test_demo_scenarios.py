import pytest

from app.platform.demo_scenarios import prepare
from app.platform.service import clear_pool, smart_receipt
from app.platform.store import Store


@pytest.fixture
def demo_store(tmp_path, monkeypatch):
    monkeypatch.setenv("PAYPOOL_DEMO_MODE", "true")
    monkeypatch.setenv("PAYPOOL_PAYMENT_PROVIDER", "demo")
    monkeypatch.setenv("PAYPOOL_POSTGIS", "false")
    return Store(f"sqlite:///{tmp_path / 'demo.db'}")


def test_recording_scenarios_are_ready_and_reruns_preserve_progress(demo_store):
    manifest = prepare(demo_store)
    scenes = manifest["scenarios"]
    with demo_store.transaction() as tx:
        assert len(tx.all("requests")) == 12
        assert len(tx.all("pools")) == 4
        first = tx.get("pools", scenes["ready_to_clear"]["pool_id"])
        assert first["status"] == "ACCUMULATING" and len(first["request_ids"]) == 3
        recovery = tx.get("pools", scenes["withdrawal_recovery"]["pool_id"])
        assert recovery["status"] == "CLEARED"
        assert [a["total_minor"] for a in recovery["allocations"]] == [4800] * 3
        for entry in scenes["withdrawal_recovery"]["orders"]:
            assert tx.get("orders", entry["order_id"])["payment_status"] == "AUTHORIZED"
        delivery = scenes["delivery_evidence"]
        assert tx.get("pools", delivery["pool_id"])["status"] == "DISPATCHED"
        for entry in delivery["orders"]:
            expected = "AUTHORIZED" if entry["buyer_id"] == "buyer-a" else "CAPTURED"
            assert tx.get("orders", entry["order_id"])["payment_status"] == expected
        for entry in scenes["matched_receipts"]["orders"]:
            assert (
                smart_receipt(tx.get("orders", entry["order_id"]))["status"]
                == "MATCHED"
            )
        first = clear_pool(tx, tx.get("users", "seller-demo"), first)
        assert first["status"] == "CLEARED"
        assert [a["total_minor"] for a in first["allocations"]] == [4800] * 3
        # A rerun must preserve rehearsal changes rather than reset the scene.
        first["note"] = "Rehearsal progress"
        tx.put("pools", first)
        count = len(tx.all("audit"))
    assert prepare(demo_store) == manifest
    with demo_store.transaction() as tx:
        assert tx.get("pools", first["id"])["note"] == "Rehearsal progress"
        assert len(tx.all("audit")) == count


def test_scenario_seed_refuses_existing_purchases(demo_store):
    with demo_store.transaction() as tx:
        tx.put("requests", {"id": "existing", "note": "Keep this"})
    with pytest.raises(ValueError, match="existing purchases"):
        prepare(demo_store)
    with demo_store.transaction() as tx:
        assert tx.get("requests", "existing")["note"] == "Keep this"
        assert not tx.all("pools")


@pytest.mark.parametrize(
    "setting,value",
    [("PAYPOOL_DEMO_MODE", "false"), ("PAYPOOL_PAYMENT_PROVIDER", "paypal_sandbox")],
)
def test_scenario_seed_refuses_non_simulated_environment(
    demo_store, monkeypatch, setting, value
):
    monkeypatch.setenv(setting, value)
    with pytest.raises(ValueError):
        prepare(demo_store)
    with demo_store.transaction() as tx:
        assert not tx.all("pools") and not tx.all("users")
