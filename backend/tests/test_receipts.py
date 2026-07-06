"""Tests fuer POS / Kassenbons."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal


def _today_compact() -> str:
    """YYYYMMDD für heute — die receipt_number wird so generiert."""
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _make_category(client, name="Getränke"):
    resp = client.post(
        "/api/categories", json={"name": name, "color": "#3B82F6", "sort_order": 1}
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _make_product(client, **overrides) -> dict:
    payload = {
        "barcode": "90415465",
        "name": "Red Bull 250ml",
        "sell_price": "1.79",
        "stock_quantity": "100",
        "deposit_cents": 25,
    }
    payload.update(overrides)
    resp = client.post("/api/products", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _price_cents(p: dict) -> int:
    """Sell-Preis in Cent (aus dem Decimal-String)."""
    return int((Decimal(p["sell_price"]) * 100).to_integral_value())


def _line(product: dict, qty: str = "1") -> dict:
    unit_price = _price_cents(product)
    qty_dec = Decimal(qty)
    return {
        "kind": "sale",
        "product_id": product["id"],
        "name_snapshot": product["name"],
        "unit_snapshot": product["unit"],
        "quantity": qty,
        "unit_price_cents": unit_price,
        "line_total_cents": int(qty_dec * unit_price),
    }


def _deposit_line(product: dict, qty: str = "1") -> dict:
    """Pfand-Position separat auf dem Bon."""
    qty_int = int(Decimal(qty))
    return {
        "kind": "deposit",
        "product_id": product["id"],
        "name_snapshot": "Pfand",
        "unit_snapshot": product["unit"],
        "quantity": qty,
        "unit_price_cents": product["deposit_cents"],
        "line_total_cents": product["deposit_cents"] * qty_int,
    }


def test_create_sale_basic_no_deposit(client):
    """Einfacher Verkauf ohne Pfand."""
    cat = _make_category(client)
    p = _make_product(client, category_id=cat, deposit_cents=0, barcode="1234")

    payload = {
        "cash_session": "2026-07-01",
        "payment_method": "cash",
        "tendered_cents": 500,
        "total_cents": 179,
        "lines": [_line(p, "1")],
    }
    resp = client.post("/api/receipts", json=payload)
    assert resp.status_code == 201, resp.text
    receipt = resp.json()
    assert receipt["receipt_number"].startswith(_today_compact() + "-")
    assert receipt["total_cents"] == 179
    assert receipt["kind"] == "sale"
    assert len(receipt["lines"]) == 1

    # Bestand wurde reduziert
    p2 = client.get(f"/api/products/{p['id']}").json()
    assert p2["stock_quantity"] == "99.000"


def test_create_sale_with_pfand(client):
    """Verkauf mit Pfand — Dose + Pfand als zwei getrennte Lines."""
    cat = _make_category(client)
    p = _make_product(client, category_id=cat, barcode="5678", deposit_cents=25)
    line = _line(p, "1")  # 179 cent
    deposit = _deposit_line(p, "1")  # 25 cent
    total = line["line_total_cents"] + deposit["line_total_cents"]

    payload = {
        "cash_session": "2026-07-01",
        "payment_method": "cash",
        "tendered_cents": 500,
        "total_cents": total,
        "lines": [line, deposit],
    }
    resp = client.post("/api/receipts", json=payload)
    assert resp.status_code == 201, resp.text
    receipt = resp.json()
    assert receipt["total_cents"] == 204

    # 3 Lines: sale + deposit + (Stock-Movement nur von sale)
    assert len(receipt["lines"]) == 2  # receipt_lines
    moves = client.get(
        "/api/stock/movements", params={"product_id": p["id"]}
    ).json()
    assert moves["total"] == 1, "Pfand darf KEINEN Stock-Movement erzeugen"
    assert Decimal(moves["items"][0]["change"]) == Decimal("-1.000")


def test_total_mismatch_409(client):
    """Wenn Client-total von Server-Berechnung abweicht -> 409."""
    cat = _make_category(client)
    p = _make_product(client, category_id=cat, barcode="9999", deposit_cents=0)
    payload = {
        "cash_session": "2026-07-01",
        "payment_method": "cash",
        "tendered_cents": 500,
        "total_cents": 9999,  # Luege
        "lines": [_line(p, "1")],  # eigentlich 179
    }
    resp = client.post("/api/receipts", json=payload)
    assert resp.status_code == 409
    assert "total_mismatch" in resp.json()["detail"]


def test_tendered_too_low_400(client):
    """Wenn weniger Geld uebergeben wird als total -> 400."""
    cat = _make_category(client)
    p = _make_product(client, category_id=cat, barcode="8888", deposit_cents=0)
    payload = {
        "cash_session": "2026-07-01",
        "payment_method": "cash",
        "tendered_cents": 50,  # weniger als 179
        "total_cents": 179,
        "lines": [_line(p, "1")],
    }
    resp = client.post("/api/receipts", json=payload)
    assert resp.status_code == 400


def test_idempotent_receipt_no_double_deduct(client):
    """WLAN-Crash waehrend Bezahl-vorgang: Retry mit selber UUID
    darf Bestand NICHT doppelt abbuchen."""
    cat = _make_category(client)
    p = _make_product(client, category_id=cat, barcode="1111", deposit_cents=0)
    payload = {
        "cash_session": "2026-07-01",
        "payment_method": "cash",
        "tendered_cents": 500,
        "total_cents": 179,
        "lines": [_line(p, "1")],
    }
    headers = {"X-Client-Op-Id": "receipt-sale-001"}

    r1 = client.post("/api/receipts", json=payload, headers=headers)
    assert r1.status_code == 201
    receipt_id = r1.json()["id"]

    r2 = client.post("/api/receipts", json=payload, headers=headers)
    assert r2.status_code == 201
    assert r2.json()["id"] == receipt_id, "Retry muss IDENTISCHE receipt_id liefern"

    # Bestand: 100 - 1 = 99 — NICHT 100 - 2 = 98
    p2 = client.get(f"/api/products/{p['id']}").json()
    assert p2["stock_quantity"] == "99.000", (
        f"Stock doppelt abgebucht! Erwartet 99, bekommen {p2['stock_quantity']}"
    )

    # Nur 1 Stock-Movement
    moves = client.get("/api/stock/movements", params={"product_id": p["id"]}).json()
    assert moves["total"] == 1


def test_receipt_void_restores_stock(client):
    """Storno-Bon stellt Bestand wieder her."""
    cat = _make_category(client)
    p = _make_product(client, category_id=cat, barcode="2222", deposit_cents=0)
    payload = {
        "cash_session": "2026-07-01",
        "payment_method": "cash",
        "tendered_cents": 500,
        "total_cents": 179,
        "lines": [_line(p, "1")],
    }
    r = client.post("/api/receipts", json=payload)
    assert r.status_code == 201
    rid = r.json()["id"]

    # Storno
    r2 = client.post(f"/api/receipts/{rid}/void")
    assert r2.status_code in (200, 201), r2.text
    storno = r2.json()
    assert storno["kind"] == "storno"
    assert storno["total_cents"] == -179

    # Bestand wieder bei 100
    p2 = client.get(f"/api/products/{p['id']}").json()
    assert p2["stock_quantity"] == "100.000"


def test_pieces_per_pack_on_product(client):
    """Vimto-Pack-Size: pieces_per_pack=24 wird am Produkt gespeichert."""
    cat = _make_category(client)
    resp = client.post(
        "/api/products",
        json={
            "barcode": "5000112637403",
            "name": "Vimto 0,33L",
            "category_id": cat,
            "sell_price": "1.00",
            "stock_quantity": "240",
            "deposit_cents": 25,
            "pieces_per_pack": 24,
            "pack_unit": "Tray",
            "pack_barcode": "5000112637410",
        },
    )
    assert resp.status_code == 201, resp.text
    p = resp.json()
    assert p["pieces_per_pack"] == 24
    assert p["pack_unit"] == "Tray"
    assert p["pack_barcode"] == "5000112637410"
    assert p["deposit_cents"] == 25

    # Update pflegt die Werte
    r2 = client.put(
        f"/api/products/{p['id']}",
        json={"pieces_per_pack": 30, "pack_unit": "Karton"},
    )
    assert r2.status_code == 200
    assert r2.json()["pieces_per_pack"] == 30
    assert r2.json()["pack_unit"] == "Karton"


def test_receipt_by_number_lookup(client):
    """Bon ist über seine menschenlesbare Nummer abrufbar (für Druck/Drucker)."""
    cat = _make_category(client)
    p = _make_product(client, category_id=cat, barcode="3333", deposit_cents=0)
    r = client.post(
        "/api/receipts",
        json={
            "cash_session": "2026-07-01",
            "payment_method": "cash",
            "tendered_cents": 200,
            "total_cents": 179,
            "lines": [_line(p, "1")],
        },
    )
    receipt_no = r.json()["receipt_number"]

    r2 = client.get(f"/api/receipts/by-number/{receipt_no}")
    assert r2.status_code == 200
    assert r2.json()["receipt_number"] == receipt_no
