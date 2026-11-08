from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.queue_manager import queue_manager

BENTO = {"shop_id": "tokyo-bento", "item_id": "tb-teriyaki"}      # 14 min
LATTE = {"shop_id": "brewlab", "item_id": "bl-spanish-latte"}     # 3 min


@pytest.fixture
def client():
    # No `with` block: the background tick loop is not started, tests advance time manually.
    queue_manager.reset()
    yield TestClient(app)
    queue_manager.reset()


def checkout(client, items, **extra):
    return client.post("/api/order/checkout", json={"student_name": "Test", "items": items, **extra})


# ---------- checkout / order splitting ----------
def test_multi_shop_checkout_splits_into_sub_tickets(client):
    r = checkout(client, [BENTO, LATTE], student_id="STU-1")
    assert r.status_code == 200
    order = r.json()
    assert order["id"] == "ORD-8801"
    assert order["student_id"] == "STU-1"
    assert order["total"] == 10.70
    assert {t["shop_id"] for t in order["sub_tickets"]} == {"tokyo-bento", "brewlab"}


def test_same_shop_items_share_one_sub_ticket(client):
    order = checkout(client, [BENTO, {"shop_id": "tokyo-bento", "item_id": "tb-gyoza", "quantity": 2}]).json()
    assert len(order["sub_tickets"]) == 1
    assert len(order["sub_tickets"][0]["lines"]) == 2


# ---------- Sync-Fire ----------
def test_sync_fire_staggers_and_finishes_together(client):
    tickets = {t["shop_id"]: t for t in checkout(client, [BENTO, LATTE]).json()["sub_tickets"]}
    assert tickets["tokyo-bento"]["fire_delay_seconds"] == 0
    assert tickets["tokyo-bento"]["status"] == "COOKING"
    assert tickets["brewlab"]["fire_delay_seconds"] == (14 - 3) * 60
    assert tickets["brewlab"]["status"] == "STAGED"
    assert tickets["tokyo-bento"]["ready_at"] == tickets["brewlab"]["ready_at"]


# ---------- validation (all 422) ----------
@pytest.mark.parametrize(
    "items",
    [
        [],
        [{**BENTO, "quantity": 0}],
        [{"shop_id": "shop_bento", "item_id": "tb-teriyaki"}],   # unknown shop
        [{"shop_id": "tokyo-bento", "item_id": "nope"}],         # unknown item
        [{"shop_id": "brewlab", "item_id": "tb-teriyaki"}],      # item belongs to another shop
    ],
)
def test_invalid_carts_return_422(client, items):
    assert checkout(client, items).status_code == 422


def test_missing_items_field_returns_422(client):
    assert client.post("/api/order/checkout", json={"student_name": "x"}).status_code == 422


def test_unknown_order_returns_404(client):
    assert client.get("/api/order/ORD-0000/status").status_code == 404


# ---------- ticket lifecycle ----------
def test_tickets_advance_with_time(client):
    order = checkout(client, [BENTO, LATTE]).json()
    created = datetime.fromisoformat(order["created_at"])

    queue_manager._refresh(created + timedelta(seconds=queue_manager_seconds(12)))
    statuses = {t["shop_id"]: t["status"] for t in client.get(f"/api/order/{order['id']}/status").json()["sub_tickets"]}
    assert statuses == {"tokyo-bento": "COOKING", "brewlab": "COOKING"}   # latte fired at minute 11

    queue_manager._refresh(created + timedelta(seconds=queue_manager_seconds(15)))
    final = client.get(f"/api/order/{order['id']}/status").json()
    assert final["status"] == "READY"
    assert all(t["status"] == "READY" for t in final["sub_tickets"])


def queue_manager_seconds(minutes: float) -> float:
    from backend.config import settings
    return minutes * settings.sim_seconds_per_minute


def test_vendor_can_mark_ticket_ready_early(client):
    order = checkout(client, [BENTO, LATTE]).json()
    latte = next(t for t in order["sub_tickets"] if t["shop_id"] == "brewlab")
    r = client.post(f"/api/queue/ticket/{latte['id']}/action", json={"status": "ready"})
    assert r.status_code == 200 and r.json()["status"] == "READY"
    board = client.get("/api/queue/vendor/brewlab").json()
    assert [t["id"] for t in board] == [latte["id"]]


def test_early_ready_fires_staged_siblings_and_updates_target(client):
    order = checkout(client, [BENTO, LATTE]).json()
    tickets = {t["shop_id"]: t for t in order["sub_tickets"]}
    assert tickets["brewlab"]["status"] == "STAGED"
    old_target = datetime.fromisoformat(order["target_ready_at"])

    # Bento kitchen finishes ~14 min early: the held latte must fire right away.
    before = datetime.now()
    r = client.post(f"/api/queue/ticket/{tickets['tokyo-bento']['id']}/action", json={"status": "READY"})
    after = datetime.now()
    assert r.status_code == 200

    updated = client.get(f"/api/order/{order['id']}/status").json()
    subs = {t["shop_id"]: t for t in updated["sub_tickets"]}
    latte = subs["brewlab"]
    assert subs["tokyo-bento"]["status"] == "READY"
    assert latte["status"] == "COOKING"
    assert latte["seconds_until_fire"] == 0
    fire_at = datetime.fromisoformat(latte["fire_at"])
    ready_at = datetime.fromisoformat(latte["ready_at"])
    assert before <= fire_at <= after
    assert ready_at - fire_at == timedelta(seconds=queue_manager_seconds(3))

    new_target = datetime.fromisoformat(updated["target_ready_at"])
    assert new_target == ready_at          # latest sibling ready_at
    assert new_target < old_target         # student sees the earlier pickup time
    assert updated["status"] == "COOKING"  # order waits for the latte


def test_early_ready_does_not_touch_cooking_siblings(client):
    order = checkout(client, [BENTO, LATTE]).json()
    tickets = {t["shop_id"]: t for t in order["sub_tickets"]}
    bento_before = tickets["tokyo-bento"]   # already COOKING
    client.post(f"/api/queue/ticket/{tickets['brewlab']['id']}/action", json={"status": "READY"})
    bento_after = next(t for t in client.get(f"/api/order/{order['id']}/status").json()["sub_tickets"]
                       if t["shop_id"] == "tokyo-bento")
    assert bento_after["status"] == "COOKING"
    assert bento_after["fire_at"] == bento_before["fire_at"]
    assert bento_after["ready_at"] == bento_before["ready_at"]


def test_cook_now_fires_held_ticket_immediately(client):
    order = checkout(client, [BENTO, LATTE]).json()
    tickets = {t["shop_id"]: t for t in order["sub_tickets"]}
    assert tickets["brewlab"]["status"] == "STAGED"

    before = datetime.now()
    r = client.post(f"/api/queue/ticket/{tickets['brewlab']['id']}/action", json={"status": "COOKING"})
    after = datetime.now()
    assert r.status_code == 200 and r.json()["status"] == "COOKING"

    updated = client.get(f"/api/order/{order['id']}/status").json()
    subs = {t["shop_id"]: t for t in updated["sub_tickets"]}
    latte = subs["brewlab"]
    fire_at = datetime.fromisoformat(latte["fire_at"])
    ready_at = datetime.fromisoformat(latte["ready_at"])
    assert before <= fire_at <= after
    assert ready_at - fire_at == timedelta(seconds=queue_manager_seconds(3))
    # Bento still takes longer, so the order's pickup time stays on the bento.
    assert updated["target_ready_at"] == subs["tokyo-bento"]["ready_at"]


def test_ticket_action_errors(client):
    order = checkout(client, [BENTO]).json()
    sid = order["sub_tickets"][0]["id"]
    assert client.post(f"/api/queue/ticket/{sid}/action", json={"status": "BOGUS"}).status_code == 422
    assert client.post("/api/queue/ticket/SUB-9999/action", json={"status": "READY"}).status_code == 404


# ---------- admin desk ----------
def test_admin_queue_join_and_validation(client):
    assert len(client.get("/api/queue/admin").json()) == 3   # seeded entries
    ok = client.post("/api/queue/admin/join", json={
        "counter_id": "it-helpdesk", "option_id": "it-license",
        "student_name": "Test", "matric_no": "A1"})
    assert ok.status_code == 200
    bad = client.post("/api/queue/admin/join", json={
        "counter_id": "nope", "option_id": "x", "student_name": "T", "matric_no": "A1"})
    assert bad.status_code == 422


# ---------- demo reset ----------
def test_demo_reset_clears_orders_and_restores_admin_queue(client):
    checkout(client, [BENTO])
    client.post("/api/queue/admin/join", json={
        "counter_id": "it-helpdesk", "option_id": "it-license", "student_name": "T", "matric_no": "A1"})
    assert client.post("/api/demo/reset").status_code == 200
    assert client.get("/api/order/ORD-8801/status").status_code == 404
    assert len(client.get("/api/queue/admin").json()) == 3
    assert checkout(client, [BENTO]).json()["id"] == "ORD-8801"   # counter restarted
