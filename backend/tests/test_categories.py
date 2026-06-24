"""Tests für Kategorien-Router."""
from __future__ import annotations


def test_health_check(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_openapi_docs_available(client):
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    spec = resp.json()
    assert spec["info"]["title"] == "MarktPilot API"
    assert "/api/products" in spec["paths"]
    assert "/api/categories" in spec["paths"]
    assert "/api/stock/movements" in spec["paths"]


def test_create_and_list_category(client):
    resp = client.post(
        "/api/categories",
        json={"name": "Getränke", "color": "#3B82F6", "sort_order": 1},
    )
    assert resp.status_code == 201, resp.text
    cat = resp.json()
    assert cat["id"] >= 1
    assert cat["name"] == "Getränke"
    assert cat["color"] == "#3B82F6"

    resp2 = client.get("/api/categories")
    assert resp2.status_code == 200
    items = resp2.json()
    assert len(items) == 1
    assert items[0]["name"] == "Getränke"


def test_category_unique_name_conflict(client):
    client.post("/api/categories", json={"name": "Snacks"})
    resp = client.post("/api/categories", json={"name": "Snacks"})
    assert resp.status_code == 409


def test_update_and_delete_category(client):
    create = client.post("/api/categories", json={"name": "Obst"})
    cat_id = create.json()["id"]

    upd = client.put(f"/api/categories/{cat_id}", json={"sort_order": 5})
    assert upd.status_code == 200
    assert upd.json()["sort_order"] == 5

    delete = client.delete(f"/api/categories/{cat_id}")
    assert delete.status_code == 204

    # Weg.
    resp = client.get("/api/categories")
    assert resp.json() == []