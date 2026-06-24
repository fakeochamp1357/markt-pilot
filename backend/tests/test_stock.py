"""Tests für Stock-Bewegungen, Low-Stock und Expiring."""
from __future__ import annotations

from datetime import date, timedelta


def _create_category(client):
    resp = client.post(
        "/api/categories",
        json={"name": "Getränke", "color": "#3B82F6", "sort_order": 1},
    )
    return resp.json()["id"]


def _create_product(client, **overrides):
    payload = {
        "barcode": "4006381333931",
        "name": "Testprodukt",
        "sell_price": "1.49",
        "stock_quantity": "10",
        "min_stock_level": "5",
    }
    payload.update(overrides)
    resp = client.post("/api/products", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_stock_movement_happy_path(client):
    """Wareneingang erhöht Bestand; Verkauf reduziert."""
    cat_id = _create_category(client)
    pid = _create_product(client, category_id=cat_id, stock_quantity="10")

    # Wareneingang +50
    resp = client.post(
        "/api/stock/movements",
        json={
            "product_id": pid,
            "change": "50",
            "reason": "purchase",
            "reference": "RE-2026-0001",
            "created_by": "anna",
        },
    )
    assert resp.status_code == 201, resp.text
    movement = resp.json()
    assert movement["change"] == "50.000"
    assert movement["reason"] == "purchase"

    # Verify Bestand
    resp = client.get(f"/api/products/{pid}")
    assert resp.json()["stock_quantity"] == "60.000"

    # Verkauf -3
    resp = client.post(
        "/api/stock/movements",
        json={"product_id": pid, "change": "-3", "reason": "sale"},
    )
    assert resp.status_code == 201

    resp = client.get(f"/api/products/{pid}")
    assert resp.json()["stock_quantity"] == "57.000"

    # Movements-Liste
    resp = client.get("/api/stock/movements", params={"product_id": pid})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2


def test_low_stock_endpoint(client):
    cat_id = _create_category(client)
    # Produkt unter Mindestbestand
    _create_product(
        client,
        category_id=cat_id,
        name="Leerer Bestand",
        stock_quantity="2",
        min_stock_level="10",
        barcode="111",
    )
    # Produkt mit ausreichend Bestand
    _create_product(
        client,
        category_id=cat_id,
        name="Voller Bestand",
        stock_quantity="50",
        min_stock_level="5",
        barcode="222",
    )

    resp = client.get("/api/stock/low")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["name"] == "Leerer Bestand"
    assert float(items[0]["deficit"]) == 8.0


def test_expiring_endpoint(client):
    cat_id = _create_category(client)
    today = date.today()
    # Bald ablaufend (in 5 Tagen)
    _create_product(
        client,
        category_id=cat_id,
        name="Frischer Joghurt",
        stock_quantity="10",
        min_stock_level="1",
        expiry_date=(today + timedelta(days=5)).isoformat(),
        barcode="333",
    )
    # Noch haltbar (in 60 Tagen) — sollte NICHT auftauchen bei days=30
    _create_product(
        client,
        category_id=cat_id,
        name="Haltbares",
        stock_quantity="10",
        min_stock_level="1",
        expiry_date=(today + timedelta(days=60)).isoformat(),
        barcode="444",
    )
    # Bereits abgelaufen (gestern) -> taucht auf bei days>=1
    _create_product(
        client,
        category_id=cat_id,
        name="Abgelaufen",
        stock_quantity="5",
        min_stock_level="1",
        expiry_date=(today - timedelta(days=1)).isoformat(),
        barcode="555",
    )

    resp = client.get("/api/stock/expiring", params={"days": 30})
    assert resp.status_code == 200
    items = resp.json()
    names = {i["name"] for i in items}
    assert "Frischer Joghurt" in names
    assert "Abgelaufen" in names
    assert "Haltbares" not in names
    # days_until_expiry ist korrekt
    joghurt = next(i for i in items if i["name"] == "Frischer Joghurt")
    assert joghurt["days_until_expiry"] == 5


def test_stock_movement_invalid_product(client):
    resp = client.post(
        "/api/stock/movements",
        json={"product_id": 9999, "change": "1", "reason": "purchase"},
    )
    assert resp.status_code == 409


def test_bulk_csv_upload(client, tmp_path):
    """Upload-Pfad für CSV-Datei."""
    csv_content = (
        "barcode,sku,name,category,unit,size_weight,cost_price,sell_price,"
        "currency,stock_quantity,min_stock_level,expiry_date,supplier,"
        "notes,color_tag,is_active\n"
        "1234567890,CSV-001,CSV Brot,Backwaren,Stück,500g,1.10,2.29,EUR,"
        "10,3,,REWE,,#A16207,true\n"
        "1234567891,CSV-002,CSV Butter,Milchprodukte,Stück,250g,1.55,2.49,"
        "EUR,5,2,,Kerrygold,,#FDE68A,true\n"
    )
    csv_file = tmp_path / "import.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    # Kategorien vorher anlegen
    client.post("/api/categories", json={"name": "Backwaren", "sort_order": 4})
    client.post("/api/categories", json={"name": "Milchprodukte", "sort_order": 3})

    with open(csv_file, "rb") as f:
        resp = client.post(
            "/api/products/bulk/upload",
            files={"file": ("import.csv", f, "text/csv")},
        )
    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert result["created"] == 2
    assert result["skipped"] == 0
    assert result["errors"] == []