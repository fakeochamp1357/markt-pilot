"""Tests für X-Client-Op-Id Idempotenz.

Garantiert: ein Retry mit derselben client_op_id erzeugt **kein** Duplikat
und liefert die ursprüngliche Antwort zurück — auch bei Stock-Bewegungen,
wo ein versehentlicher Doppel-Apply den Bestand ruinieren würde.
"""
from __future__ import annotations

from decimal import Decimal


def _create_category(client, name="Getränke"):
    resp = client.post(
        "/api/categories",
        json={"name": name, "color": "#3B82F6", "sort_order": 1},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_idempotent_product_create_returns_same_id(client):
    """POST /api/products mit derselben X-Client-Op-Id → 2× 201, gleiche ID."""
    cat_id = _create_category(client)
    payload = {
        "barcode": "4006381333931",
        "name": "Pilot Kugelschreiber",
        "category_id": cat_id,
        "sell_price": "1.49",
        "stock_quantity": "20",
    }
    headers = {"X-Client-Op-Id": "test-uuid-product-001"}

    r1 = client.post("/api/products", json=payload, headers=headers)
    assert r1.status_code == 201, r1.text
    pid_first = r1.json()["id"]

    # Retry — selbe ID, anderes WLAN, sollte kein Duplikat anlegen
    r2 = client.post("/api/products", json=payload, headers=headers)
    assert r2.status_code == 201, r2.text
    assert r2.json()["id"] == pid_first, "Retry muss dieselbe ID liefern"

    # DB hat tatsächlich nur 1 Eintrag
    r3 = client.get("/api/products", params={"q": "Pilot"})
    assert r3.json()["total"] == 1


def test_no_header_no_dedup(client):
    """Ohne X-Client-Op-Id verhält sich der Endpoint wie vorher (Legacy)."""
    cat_id = _create_category(client)
    payload = {
        "barcode": "5449000000996",
        "name": "Coca-Cola",
        "category_id": cat_id,
        "sell_price": "1.29",
        "stock_quantity": "10",
    }

    r1 = client.post("/api/products", json=payload)
    assert r1.status_code == 201

    # Selbes Payload, kein Header → neues Produkt? Nein, Barcode-Konflikt
    # (vermutetes Legacy-Verhalten). Was wir hier testen: KEIN Idempotenz-
    # Caching ohne Header.
    payload2 = {
        "barcode": "5449000000996",
        "name": "Coca-Cola (anderer Versuch)",
        "category_id": cat_id,
        "sell_price": "1.49",
        "stock_quantity": "5",
    }
    r2 = client.post("/api/products", json=payload2)
    # 409 weil Barcode schon existiert, aber WICHTIG: kein 2. Produkt
    # angelegt. Caching-Code wurde nicht getriggert.
    assert r2.status_code == 409


def test_idempotent_category_create(client):
    """POST /api/categories mit derselben X-Client-Op-Id → gleiche Antwort."""
    payload = {"name": "Snacks", "color": "#3B82F6", "sort_order": 2}
    headers = {"X-Client-Op-Id": "test-uuid-cat-001"}

    r1 = client.post("/api/categories", json=payload, headers=headers)
    assert r1.status_code == 201, r1.text
    cat_id = r1.json()["id"]

    r2 = client.post("/api/categories", json=payload, headers=headers)
    assert r2.status_code == 201
    assert r2.json()["id"] == cat_id

    r3 = client.get("/api/categories")
    names = [c["name"] for c in r3.json()]
    assert names.count("Snacks") == 1


def test_idempotent_4xx_replay(client):
    """Bei Konflikt wird 409 gecached — kein Retry-Sturm."""
    # Erstes Snacks anlegen
    r1 = client.post(
        "/api/categories", json={"name": "Snacks", "color": "#3B82F6"}
    )
    assert r1.status_code == 201

    # Jetzt mit X-Client-Op-Id erneut versuchen → 409
    headers = {"X-Client-Op-Id": "test-uuid-conflict-001"}
    r2 = client.post(
        "/api/categories",
        json={"name": "Snacks", "color": "#FF0000"},
        headers=headers,
    )
    assert r2.status_code == 409

    # Dritter Call mit selber ID → 409 (Replay aus Cache)
    r3 = client.post(
        "/api/categories",
        json={"name": "Snacks", "color": "#00FF00"},
        headers=headers,
    )
    assert r3.status_code == 409
    assert r3.json()["detail"] == r2.json()["detail"]


def test_idempotent_stock_movement_does_not_double_deduct(client):
    """DER KRITISCHE TEST: ein Retry einer Stock-Movement darf den Bestand
    nicht doppelt verändern."""
    cat_id = _create_category(client)
    r = client.post(
        "/api/products",
        json={
            "barcode": "90415465",
            "name": "Red Bull 250ml",
            "category_id": cat_id,
            "sell_price": "1.79",
            "stock_quantity": "100",
        },
    )
    assert r.status_code == 201
    pid = r.json()["id"]

    # Kasse: Verkauf -3
    sale_payload = {
        "product_id": pid,
        "change": "-3",
        "reason": "sale",
    }
    headers = {"X-Client-Op-Id": "sale-uuid-001"}

    r1 = client.post("/api/stock/movements", json=sale_payload, headers=headers)
    assert r1.status_code == 201, r1.text
    movement_id_1 = r1.json()["id"]

    # WLAN weg, Client sendet nochmal — selbe UUID
    r2 = client.post("/api/stock/movements", json=sale_payload, headers=headers)
    assert r2.status_code == 201, r2.text
    assert r2.json()["id"] == movement_id_1, "Bewegungs-ID muss identisch sein"

    # Bestand: 100 - 3 = 97. NICHT 100 - 6 = 94.
    r3 = client.get(f"/api/products/{pid}")
    assert r3.json()["stock_quantity"] == "97.000", (
        f"Stock doppelt abgebucht! Erwartet 97, bekommen {r3.json()['stock_quantity']}"
    )

    # Movements-Liste: nur 1 Eintrag für dieses Produkt
    r4 = client.get("/api/stock/movements", params={"product_id": pid})
    assert r4.json()["total"] == 1


def test_idempotent_stock_movement_409_replay(client):
    """Stock-Movement mit ungültiger product_id → 409 wird gecached."""
    headers = {"X-Client-Op-Id": "bad-movement-001"}
    payload = {"product_id": 99999, "change": "1", "reason": "purchase"}

    r1 = client.post("/api/stock/movements", json=payload, headers=headers)
    assert r1.status_code == 409

    r2 = client.post("/api/stock/movements", json=payload, headers=headers)
    assert r2.status_code == 409
    assert r2.json()["detail"] == r1.json()["detail"]


def test_different_client_op_ids_create_separate(client):
    """Verschiedene UUIDs → separate Einträge (kein überaggressiver Dedup)."""
    cat_id = _create_category(client)
    base = {
        "category_id": cat_id,
        "sell_price": "1.99",
        "stock_quantity": "5",
    }

    r1 = client.post(
        "/api/products",
        json={**base, "barcode": "111", "name": "Produkt A"},
        headers={"X-Client-Op-Id": "uuid-A"},
    )
    assert r1.status_code == 201

    r2 = client.post(
        "/api/products",
        json={**base, "barcode": "222", "name": "Produkt B"},
        headers={"X-Client-Op-Id": "uuid-B"},
    )
    assert r2.status_code == 201

    # Zwei verschiedene Produkte
    r3 = client.get("/api/products", params={"category": cat_id})
    assert r3.json()["total"] == 2


def test_oversized_client_op_id_rejected(client):
    """Header > 64 Zeichen → 400."""
    r = client.post(
        "/api/categories",
        json={"name": "X", "color": "#3B82F6"},
        headers={"X-Client-Op-Id": "x" * 65},
    )
    assert r.status_code == 400
    assert "X-Client-Op-Id" in r.json()["detail"]
