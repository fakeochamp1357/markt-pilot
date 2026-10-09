"""Tests fuer Tagesabschluss / Z-Bericht."""
from __future__ import annotations

from datetime import datetime, timezone

SESSION = "2026-10-09"


def _product(client, barcode, price, vat_rate=19, deposit_cents=0):
    resp = client.post(
        "/api/products",
        json={
            "barcode": barcode,
            "name": f"Artikel {barcode}",
            "sell_price": price,
            "stock_quantity": "50",
            "deposit_cents": deposit_cents,
            "vat_rate": vat_rate,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _sell(client, lines, method="cash", session=SESSION):
    """lines: Liste von (product, qty) — Pfand wird automatisch angehaengt."""
    body = []
    for p, qty in lines:
        body.append({
            "kind": "sale",
            "product_id": p["id"],
            "name_snapshot": p["name"],
            "quantity": str(qty),
            "unit_price_cents": p["sell_price_cents"],
            "line_total_cents": p["sell_price_cents"] * qty,
        })
        if p["deposit_cents"]:
            body.append({
                "kind": "deposit",
                "product_id": p["id"],
                "name_snapshot": "Pfand",
                "quantity": str(qty),
                "unit_price_cents": p["deposit_cents"],
                "line_total_cents": p["deposit_cents"] * qty,
            })
    total = sum(line["line_total_cents"] for line in body)
    resp = client.post(
        "/api/receipts",
        json={
            "cash_session": session,
            "payment_method": method,
            "tendered_cents": total if method == "cash" else 0,
            "total_cents": total,
            "lines": body,
        },
    )
    return resp


def test_product_vat_rate_default_and_validation(client):
    p = _product(client, "111", "1.00")
    assert p["vat_rate"] == 19
    resp = client.post("/api/products", json={"name": "X", "vat_rate": 16})
    assert resp.status_code == 422
    resp = client.put(f"/api/products/{p['id']}", json={"vat_rate": 7})
    assert resp.json()["vat_rate"] == 7


def test_receipt_line_snapshots_vat_from_product(client):
    milk = _product(client, "222", "1.19", vat_rate=7)
    r = _sell(client, [(milk, 1)]).json()
    assert r["lines"][0]["vat_rate"] == 7
    # Spaetere Satz-Aenderung am Produkt aendert den gebuchten Bon nicht
    client.put(f"/api/products/{milk['id']}", json={"vat_rate": 19})
    again = client.get(f"/api/receipts/{r['id']}").json()
    assert again["lines"][0]["vat_rate"] == 7


def test_z_report_totals_by_payment_and_vat(client):
    milk = _product(client, "333", "1.07", vat_rate=7)
    cola = _product(client, "444", "1.19", vat_rate=19, deposit_cents=25)

    assert _sell(client, [(milk, 2), (cola, 1)], "cash").status_code == 201  # 214 + 144
    assert _sell(client, [(cola, 2)], "card").status_code == 201  # 288
    voided = _sell(client, [(milk, 1)], "cash").json()  # 107, wird storniert
    assert client.post(f"/api/receipts/{voided['id']}/void").status_code == 200
    # Anderer Tag zaehlt nicht mit
    assert _sell(client, [(milk, 5)], "cash", session="2026-10-08").status_code == 201

    rep = client.get(f"/api/day-close/{SESSION}").json()
    assert rep["closed"] is False
    assert rep["sale_count"] == 3
    assert rep["storno_count"] == 1
    assert rep["total_cents"] == 214 + 144 + 288
    assert rep["storno_total_cents"] == 107

    by_pay = {p["payment_method"]: p for p in rep["by_payment"]}
    assert by_pay["cash"]["total_cents"] == 358
    assert by_pay["cash"]["receipt_count"] == 2
    assert by_pay["card"]["total_cents"] == 288
    assert rep["cash_sales_cents"] == 358

    by_vat = {v["vat_rate"]: v for v in rep["by_vat"]}
    # 7 %: 2 Milch = 214 brutto -> 200 netto + 14 MwSt
    assert by_vat[7] == {"vat_rate": 7, "gross_cents": 214, "net_cents": 200, "vat_cents": 14}
    # 19 %: 3 Cola + 3 Pfand = 357 + 75 = 432 brutto -> 363 netto + 69 MwSt
    assert by_vat[19] == {"vat_rate": 19, "gross_cents": 432, "net_cents": 363, "vat_cents": 69}
    assert sum(v["gross_cents"] for v in rep["by_vat"]) == rep["total_cents"]


def test_close_day_cash_difference_and_lock(client):
    milk = _product(client, "555", "1.07", vat_rate=7)
    _sell(client, [(milk, 3)], "cash")  # 321
    _sell(client, [(milk, 1)], "card")  # 107

    resp = client.post(
        f"/api/day-close/{SESSION}",
        json={
            "opening_float_cents": 10000,
            "counted_cash_cents": 10300,
            "cashier_name": "Ali",
            "denominations": {"5000": 2, "200": 1, "100": 1},
        },
    )
    assert resp.status_code == 201, resp.text
    rep = resp.json()
    assert rep["closed"] is True
    assert rep["z_number"] == 1
    assert rep["expected_cash_cents"] == 10321
    assert rep["counted_cash_cents"] == 10300
    assert rep["difference_cents"] == -21
    assert rep["denominations"] == {"5000": 2, "200": 1, "100": 1}

    # Gesperrt: neue Bons werden abgelehnt
    blocked = _sell(client, [(milk, 1)], "cash")
    assert blocked.status_code == 409
    assert "abgeschlossen" in blocked.json()["detail"]

    # Zweiter Abschluss geht nicht
    again = client.post(f"/api/day-close/{SESSION}", json={"counted_cash_cents": 0})
    assert again.status_code == 409

    # Bericht bleibt eingefroren
    frozen = client.get(f"/api/day-close/{SESSION}").json()
    assert frozen == rep

    listing = client.get("/api/day-close").json()
    assert listing[0]["z_number"] == 1
    assert listing[0]["difference_cents"] == -21


def test_z_numbers_are_sequential(client):
    for i, day in enumerate(["2026-10-01", "2026-10-02"], start=1):
        r = client.post(f"/api/day-close/{day}", json={"counted_cash_cents": 0})
        assert r.status_code == 201
        assert r.json()["z_number"] == i
        assert r.json()["difference_cents"] == 0


def test_denominations_must_match_counted(client):
    resp = client.post(
        f"/api/day-close/{SESSION}",
        json={"counted_cash_cents": 1000, "denominations": {"500": 1}},
    )
    assert resp.status_code == 400
    resp = client.post(
        f"/api/day-close/{SESSION}",
        json={"counted_cash_cents": 300, "denominations": {"300": 1}},
    )
    assert resp.status_code == 400
    # Tag ist nach Fehlern noch offen
    assert client.get(f"/api/day-close/{SESSION}").json()["closed"] is False


def test_void_after_close_lands_in_today(client):
    milk = _product(client, "666", "1.07", vat_rate=7)
    sale = _sell(client, [(milk, 1)], "cash", session="2026-01-01").json()
    client.post("/api/day-close/2026-01-01", json={"counted_cash_cents": 107})

    storno = client.post(f"/api/receipts/{sale['id']}/void")
    assert storno.status_code == 200
    today = datetime.now(timezone.utc).date().isoformat()
    assert storno.json()["cash_session"] == today
    assert storno.json()["lines"][0]["vat_rate"] == 7

    # Der alte Z-Bericht bleibt unveraendert
    old = client.get("/api/day-close/2026-01-01").json()
    assert old["total_cents"] == 107
    assert old["storno_count"] == 0
