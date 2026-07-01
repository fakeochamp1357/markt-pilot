"""Tests für Produkt-Router: CRUD, Barcode, Bulk."""
from __future__ import annotations


def _create_category(client, name="Getränke"):
    resp = client.post(
        "/api/categories",
        json={"name": name, "color": "#3B82F6", "sort_order": 1},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_create_product_requires_category(client):
    """Wenn category_id gesetzt aber ungültig -> 400."""
    payload = {
        "name": "Test",
        "category_id": 9999,
        "sell_price": "1.99",
        "stock_quantity": "10",
    }
    resp = client.post("/api/products", json=payload)
    assert resp.status_code == 400


def test_product_crud_full_lifecycle(client):
    cat_id = _create_category(client)
    payload = {
        "sku": "TEST-001",
        "barcode": "4006381333931",
        "name": "Pilot Kugelschreiber",
        "category_id": cat_id,
        "unit": "Stück",
        "size_weight": "Standard",
        "cost_price": "0.50",
        "sell_price": "1.49",
        "currency": "EUR",
        "stock_quantity": "20",
        "min_stock_level": "5",
        "color_tag": "#3B82F6",
        "is_active": True,
    }

    # CREATE
    resp = client.post("/api/products", json=payload)
    assert resp.status_code == 201, resp.text
    created = resp.json()
    pid = created["id"]
    # Cent-Speicherung sichtbar: 1.49 EUR = 149 cents; API gibt Decimal zurück
    assert created["sell_price"] == "1.49"
    assert created["cost_price"] == "0.50"
    assert created["stock_quantity"] == "20.000"

    # READ
    resp = client.get(f"/api/products/{pid}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Pilot Kugelschreiber"

    # LIST (mit Suche)
    resp = client.get("/api/products", params={"q": "Pilot"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == pid

    # UPDATE
    resp = client.put(
        f"/api/products/{pid}",
        json={"sell_price": "1.79", "stock_quantity": "15"},
    )
    assert resp.status_code == 200
    upd = resp.json()
    assert upd["sell_price"] == "1.79"
    assert upd["stock_quantity"] == "15.000"

    # SOFT-DELETE
    resp = client.delete(f"/api/products/{pid}")
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False

    # Mit active=false wieder auffindbar
    resp = client.get("/api/products", params={"active": False})
    assert resp.json()["total"] == 1


def test_barcode_lookup(client):
    cat_id = _create_category(client)
    client.post(
        "/api/products",
        json={
            "barcode": "90415465",
            "name": "Red Bull 250ml",
            "category_id": cat_id,
            "sell_price": "1.79",
            "stock_quantity": "24",
        },
    )

    # Schneller Scanner-Pfad
    resp = client.get("/api/products/barcode/90415465")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Red Bull 250ml"

    # 404 für unbekannten Barcode
    resp = client.get("/api/products/barcode/99999999")
    assert resp.status_code == 404


def test_bulk_import_creates_and_updates(client):
    cat_id = _create_category(client, "Snacks")

    # Erstimport — 2 neue
    payload = {
        "items": [
            {
                "barcode": "7622210449283",
                "sku": "SS-MILKA-100",
                "name": "Milka Alpenmilch",
                "category_id": cat_id,
                "sell_price": "1.79",
                "stock_quantity": "40",
            },
            {
                "barcode": "0028400090054",
                "sku": "SS-LAYS-150",
                "name": "Lay's Classic Chips",
                "category_id": cat_id,
                "sell_price": "1.69",
                "stock_quantity": "28",
            },
        ]
    }
    resp = client.post("/api/products/bulk", json=payload)
    assert resp.status_code == 200
    result = resp.json()
    assert result["created"] == 2
    assert result["updated"] == 0
    assert result["skipped"] == 0

    # Update per barcode — Preis anheben, Name behalten
    payload2 = {
        "items": [
            {
                "barcode": "7622210449283",
                "sku": "SS-MILKA-100",
                "name": "Milka Alpenmilch (Aktion)",
                "category_id": cat_id,
                "sell_price": "1.49",
                "stock_quantity": "40",
            },
        ]
    }
    resp = client.post("/api/products/bulk", json=payload2)
    assert resp.status_code == 200
    result = resp.json()
    assert result["created"] == 0
    assert result["updated"] == 1

    # Verify update
    resp = client.get("/api/products/barcode/7622210449283")
    assert resp.json()["name"] == "Milka Alpenmilch (Aktion)"
    assert resp.json()["sell_price"] == "1.49"


def test_bulk_import_dedup_by_sku(client):
    cat_id = _create_category(client)
    payload = {
        "items": [
            {
                "sku": "DEDUP-001",
                "name": "Testprodukt",
                "category_id": cat_id,
                "sell_price": "9.99",
                "stock_quantity": "10",
            },
        ]
    }
    resp = client.post("/api/products/bulk", json=payload)
    assert resp.json()["created"] == 1

    # Nochmal mit gleichem SKU, neuem Namen -> Update
    payload["items"][0]["name"] = "Testprodukt NEU"
    resp = client.post("/api/products/bulk", json=payload)
    assert resp.json()["updated"] == 1
    assert resp.json()["created"] == 0


def test_barcode_uniqueness_conflict(client):
    _create_category(client)
    payload = {
        "barcode": "5449000000996",
        "name": "Erstes Produkt",
        "sell_price": "1.00",
        "stock_quantity": "1",
    }
    resp = client.post("/api/products", json=payload)
    assert resp.status_code == 201

    # Gleicher Barcode nochmal -> 409
    payload["name"] = "Zweites Produkt"
    resp = client.post("/api/products", json=payload)
    assert resp.status_code == 409


def test_export_csv(client):
    _create_category(client)
    client.post(
        "/api/products",
        json={
            "barcode": "123",
            "name": "Test A",
            "sell_price": "1.00",
            "stock_quantity": "5",
        },
    )
    resp = client.get("/api/products/export", params={"format": "csv"})
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    body = resp.text
    assert "Test A" in body
    assert "1.00" in body


def test_export_xlsx(client):
    _create_category(client)
    client.post(
        "/api/products",
        json={
            "name": "Excel Test",
            "sell_price": "2.50",
            "stock_quantity": "5",
        },
    )
    resp = client.get("/api/products/export", params={"format": "xlsx"})
    assert resp.status_code == 200
    assert (
        "spreadsheetml" in resp.headers["content-type"]
        or "octet-stream" in resp.headers["content-type"]
    )
    # Erste Bytes = ZIP-Magic (XLSX ist ein ZIP)
    assert resp.content[:2] == b"PK"


def test_export_pdf(client):
    _create_category(client)
    client.post(
        "/api/products",
        json={
            "name": "PDF Test",
            "sell_price": "3.99",
            "stock_quantity": "5",
        },
    )
    resp = client.get("/api/products/export", params={"format": "pdf"})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    # PDF-Magic
    assert resp.content[:4] == b"%PDF"
    # TODO: robustere Inhalts-Pruefung mit pypdf. Aktuell reicht der
    # Sanity-Check, dass die Datei erzeugt wird; reportlab packt die
    # Inhalte in komprimierte Streams, in denen Strings nicht einfach
    # greppbar sind.
    assert len(resp.content) > 1000