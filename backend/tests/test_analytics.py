"""Tests für den Analytics-Service und -Router.

Wir seeden eine kleine, deterministische Datenlage:
- 3 aktive Produkte (verschiedene Margen, Bestände, MHDs)
- Stock-Bewegungen über die letzten ~120 Tage
- 1 inaktives Produkt (sollte ignoriert werden)

Dann prüfen wir Top-Seller, Margins, Dead-Stock, MHD-Alerts, Reorder und
das aggregierte Dashboard.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_category(client, name: str = "Test") -> int:
    resp = client.post(
        "/api/categories",
        json={"name": name, "color": "#3B82F6", "sort_order": 1},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_product(client, *, name: str, cost: str, sell: str, **kw) -> int:
    payload: dict = {
        "name": name,
        "cost_price": cost,
        "sell_price": sell,
        "stock_quantity": "100",
        "min_stock_level": "10",
    }
    payload.update(kw)
    resp = client.post("/api/products", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_movement(
    client,
    product_id: int,
    change: str,
    reason: str,
    *,
    when: datetime | None = None,
) -> None:
    body: dict = {"product_id": product_id, "change": change, "reason": reason}
    if when is not None:
        # Direkter DB-Insert via Movement-Endpoint geht nur mit created_at
        # Override nicht. Wir nutzen unten stattdessen den Service direkt.
        raise NotImplementedError("Use _seed_movement for backdated moves.")
    resp = client.post("/api/stock/movements", json=body)
    assert resp.status_code == 201, resp.text


def _seed_movement(db_session, product_id: int, change: Decimal, reason: str, when: datetime) -> None:
    """Bewegung mit frei wählbarem created_at — direkt in die DB."""
    from app.models import StockMovement

    mv = StockMovement(
        product_id=product_id,
        change=change,
        reason=reason,
        reference=None,
        created_by="seed",
        created_at=when,
    )
    db_session.add(mv)
    db_session.commit()


# ---------------------------------------------------------------------------
# Top-Seller
# ---------------------------------------------------------------------------


def test_top_sellers_basic(client, db_session):
    cat = _create_category(client)
    p_a = _create_product(client, name="Apfelsaft", cost="0.80", sell="1.49", category_id=cat, barcode="1")
    p_b = _create_product(client, name="Brot", cost="1.10", sell="2.29", category_id=cat, barcode="2")
    p_c = _create_product(client, name="Kaugummi", cost="0.05", sell="0.30", category_id=cat, barcode="3")

    # In der aktuellen Stunde: wenige Sales.
    _create_movement(client, p_a, "-10", "sale")  # 10 Apfelsaft verkauft
    _create_movement(client, p_b, "-5", "sale")   # 5 Brot verkauft
    _create_movement(client, p_c, "-50", "sale")  # 50 Kaugummis verkauft

    resp = client.get("/api/analytics/top-sellers", params={"period": "all"})
    assert resp.status_code == 200, resp.text
    items = resp.json()
    assert len(items) == 3
    # Default sort=qty → Kaugummi (50) zuerst.
    assert items[0]["name"] == "Kaugummi"
    assert Decimal(items[0]["qty_sold"]) == Decimal("50")
    # Margen-Check: Kaugummi 50 × (0.30 - 0.05) = 12.50 EUR
    assert items[0]["margin"] == "12.50"


def test_top_sellers_period_cutoff(client, db_session):
    """Sale vor Cutoff darf NICHT in 'month' auftauchen, aber in 'year'."""
    cat = _create_category(client)
    p = _create_product(client, name="Alt-Verkauf", cost="1.00", sell="2.00", category_id=cat, barcode="9")

    # 120 Tage her: 5 Sales
    old = datetime.now(timezone.utc) - timedelta(days=120)
    _seed_movement(db_session, p, Decimal("-5"), "sale", old)

    resp = client.get("/api/analytics/top-sellers", params={"period": "month"})
    assert resp.status_code == 200
    assert resp.json() == []

    resp = client.get("/api/analytics/top-sellers", params={"period": "year"})
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["name"] == "Alt-Verkauf"


def test_top_sellers_excludes_inactive(client):
    cat = _create_category(client)
    p_active = _create_product(client, name="Aktiv", cost="1", sell="2", category_id=cat, barcode="11")
    p_inactive = _create_product(client, name="Inaktiv", cost="1", sell="2", category_id=cat, barcode="12", is_active=False)
    _create_movement(client, p_active, "-3", "sale")
    _create_movement(client, p_inactive, "-100", "sale")

    resp = client.get("/api/analytics/top-sellers")
    assert resp.status_code == 200
    items = resp.json()
    names = [i["name"] for i in items]
    assert "Aktiv" in names
    assert "Inaktiv" not in names


def test_top_sellers_sort_by_revenue(client):
    cat = _create_category(client)
    _create_product(client, name="Billig", cost="0.05", sell="0.10", category_id=cat, barcode="21")
    _create_product(client, name="Teuer", cost="5", sell="10", category_id=cat, barcode="22")
    # IDs sind fortlaufend; explizit abfragen.
    items = client.get("/api/products", params={"limit": 10}).json()["items"]
    billig = next(i for i in items if i["name"] == "Billig")["id"]
    teuer = next(i for i in items if i["name"] == "Teuer")["id"]

    _create_movement(client, billig, "-100", "sale")  # 10 EUR Revenue
    _create_movement(client, teuer, "-5", "sale")      # 50 EUR Revenue

    resp = client.get("/api/analytics/top-sellers", params={"sort_by": "revenue"})
    assert resp.status_code == 200
    items = resp.json()
    assert items[0]["name"] == "Teuer"


def test_top_sellers_invalid_period(client):
    resp = client.get("/api/analytics/top-sellers", params={"period": "decade"})
    assert resp.status_code == 422  # Pydantic regex schlägt zu


# ---------------------------------------------------------------------------
# Margins
# ---------------------------------------------------------------------------


def test_margins_with_sales(client):
    cat = _create_category(client)
    p_a = _create_product(client, name="Hohe Marge", cost="1", sell="3", category_id=cat, barcode="31")
    p_b = _create_product(client, name="Niedrige Marge", cost="1", sell="1.10", category_id=cat, barcode="32")
    _create_movement(client, p_a, "-10", "sale")
    _create_movement(client, p_b, "-50", "sale")

    resp = client.get("/api/analytics/margins", params={"period": "all"})
    assert resp.status_code == 200
    items = resp.json()
    # Hohe Marge: 10 × (3 - 1) = 20 EUR
    # Niedrige Marge: 50 × (1.10 - 1) = 5 EUR
    assert items[0]["name"] == "Hohe Marge"
    assert items[0]["margin"] == "20.00"
    assert items[0]["cost"] == "10.00"
    assert items[0]["revenue"] == "30.00"


def test_margins_only_with_sales_false_includes_zero(client):
    cat = _create_category(client)
    _create_product(client, name="Verkauft", cost="1", sell="2", category_id=cat, barcode="41")
    _create_product(client, name="Kein Sale", cost="1", sell="2", category_id=cat, barcode="42")

    items = client.get("/api/analytics/margins", params={"only_with_sales": "false"})
    assert items.status_code == 200
    items = items.json()
    names = [i["name"] for i in items]
    assert "Verkauft" in names
    assert "Kein Sale" in names


# ---------------------------------------------------------------------------
# Dead-Stock
# ---------------------------------------------------------------------------


def test_dead_stock_excludes_within_period_sales(client, db_session):
    cat = _create_category(client)
    p_hot = _create_product(client, name="Renner", cost="1", sell="2", category_id=cat, barcode="51")
    p_cold = _create_product(client, name="Ladenhüter", cost="1", sell="2", category_id=cat, barcode="52")

    # Renner hat 5 Sales HEUTE → kein Dead Stock.
    _create_movement(client, p_hot, "-5", "sale")

    resp = client.get("/api/analytics/dead-stock", params={"period": "month"})
    assert resp.status_code == 200
    names = [r["name"] for r in resp.json()]
    assert "Ladenhüter" in names
    assert "Renner" not in names


def test_dead_stock_excludes_with_old_sales(client, db_session):
    """Sale vor Cutoff → bei 'month' = Dead Stock, bei 'year' = nicht
    (wenn der Sale innerhalb des letzten Jahres liegt)."""
    cat = _create_category(client)
    p = _create_product(client, name="Einmal-verkauft", cost="1", sell="2", category_id=cat, barcode="61")

    # 200 Tage her: liegt im 'year' (365), aber NICHT im 'month' (30).
    old = datetime.now(timezone.utc) - timedelta(days=200)
    _seed_movement(db_session, p, Decimal("-3"), "sale", old)

    resp = client.get("/api/analytics/dead-stock", params={"period": "year"})
    items = resp.json()
    assert "Einmal-verkauft" not in [i["name"] for i in items]

    resp = client.get("/api/analytics/dead-stock", params={"period": "month"})
    items = resp.json()
    assert "Einmal-verkauft" in [i["name"] for i in items]

    # Und 'all' = nie Dead Stock.
    resp = client.get("/api/analytics/dead-stock", params={"period": "all"})
    items = resp.json()
    assert "Einmal-verkauft" not in [i["name"] for i in items]


def test_dead_stock_excludes_inactive(client):
    cat = _create_category(client)
    _create_product(client, name="Inaktiv und kalt", cost="1", sell="2", category_id=cat, barcode="71", is_active=False)
    resp = client.get("/api/analytics/dead-stock")
    assert resp.status_code == 200
    names = [r["name"] for r in resp.json()]
    assert "Inaktiv und kalt" not in names


# ---------------------------------------------------------------------------
# MHD-Alerts
# ---------------------------------------------------------------------------


def test_expiry_alerts_split_warn_and_danger(client):
    cat = _create_category(client)
    today = date.today()
    _create_product(
        client, name="Heute", cost="1", sell="2", category_id=cat,
        barcode="81", expiry_date=today.isoformat(),
    )
    _create_product(
        client, name="Bald", cost="1", sell="2", category_id=cat,
        barcode="82", expiry_date=(today + timedelta(days=3)).isoformat(),
    )
    _create_product(
        client, name="Abgelaufen", cost="1", sell="2", category_id=cat,
        barcode="83", expiry_date=(today - timedelta(days=2)).isoformat(),
    )
    _create_product(
        client, name="Frisch", cost="1", sell="2", category_id=cat,
        barcode="84", expiry_date=(today + timedelta(days=60)).isoformat(),
    )
    _create_product(
        client, name="Ohne MHD", cost="1", sell="2", category_id=cat,
        barcode="85",
    )

    resp = client.get("/api/analytics/expiry-alerts", params={"warn_days": 7})
    assert resp.status_code == 200
    items = resp.json()
    by_name = {i["name"]: i for i in items}

    assert by_name["Heute"]["severity"] == "warn"
    assert by_name["Heute"]["days_until_expiry"] == 0
    assert by_name["Bald"]["severity"] == "warn"
    assert by_name["Bald"]["days_until_expiry"] == 3
    assert by_name["Abgelaufen"]["severity"] == "danger"
    assert by_name["Abgelaufen"]["days_until_expiry"] == -2
    assert "Frisch" not in by_name
    assert "Ohne MHD" not in by_name


def test_expiry_alerts_exclude_expired(client):
    cat = _create_category(client)
    today = date.today()
    _create_product(
        client, name="Abgelaufen", cost="1", sell="2", category_id=cat,
        barcode="91", expiry_date=(today - timedelta(days=1)).isoformat(),
    )
    resp = client.get(
        "/api/analytics/expiry-alerts",
        params={"warn_days": 7, "include_expired": "false"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# Reorder
# ---------------------------------------------------------------------------


def test_reorder_alerts(client):
    cat = _create_category(client)
    _create_product(
        client, name="Leer", cost="1", sell="2", category_id=cat,
        barcode="101", stock_quantity="3", min_stock_level="10",
    )
    _create_product(
        client, name="Voll", cost="1", sell="2", category_id=cat,
        barcode="102", stock_quantity="50", min_stock_level="5",
    )
    _create_product(
        client, name="Min=0", cost="1", sell="2", category_id=cat,
        barcode="103", stock_quantity="0", min_stock_level="0",
    )

    resp = client.get("/api/analytics/reorder-alerts")
    assert resp.status_code == 200
    items = resp.json()
    by_name = {i["name"]: i for i in items}
    assert "Leer" in by_name
    assert "Voll" not in by_name
    assert "Min=0" not in by_name  # include_zero_min=False
    # Defizit bei "Leer": 10 - 3 = 7
    assert Decimal(by_name["Leer"]["deficit"]) == Decimal("7.000")


def test_reorder_alerts_include_zero_min(client):
    """Wenn min_stock_level=0, sollte das Produkt NICHT auftauchen
    (außer Bestand ist negativ — was wir nicht testen)."""
    cat = _create_category(client)
    _create_product(
        client, name="Min=0", cost="1", sell="2", category_id=cat,
        barcode="111", stock_quantity="0", min_stock_level="0",
    )
    resp = client.get("/api/analytics/reorder-alerts", params={"include_zero_min": "true"})
    items = resp.json()
    # Bestand 0 = nicht < 0 → kein Alert.
    assert all(i["name"] != "Min=0" for i in items)


# ---------------------------------------------------------------------------
# Dashboard & Notifications
# ---------------------------------------------------------------------------


def test_dashboard_summary(client):
    cat = _create_category(client)
    _create_product(client, name="X", cost="1", sell="2", category_id=cat, barcode="121")
    _create_product(client, name="Y", cost="1", sell="3", category_id=cat, barcode="122")
    _create_movement(client, _product_id(client, "X"), "-2", "sale")
    _create_movement(client, _product_id(client, "Y"), "-1", "sale")

    resp = client.get("/api/analytics/dashboard/summary", params={"period": "month"})
    assert resp.status_code == 200
    obj = resp.json()
    assert obj["total_active_products"] >= 2
    assert obj["period"] == "month"
    # Sales period: 2×2 + 1×3 = 7 EUR
    assert obj["total_sales_period"] == "7.00"
    # Marge: 2×1 + 1×2 = 4 EUR
    assert obj["total_margin_period"] == "4.00"


def test_notifications_aggregate(client):
    cat = _create_category(client)
    today = date.today()
    # MHD bald → severity=warn, type=expiry_soon
    _create_product(
        client, name="Bald", cost="1", sell="2", category_id=cat,
        barcode="131", expiry_date=(today + timedelta(days=2)).isoformat(),
        min_stock_level="0",
    )
    # MHD abgelaufen → type=expired, severity=danger
    _create_product(
        client, name="Alt", cost="1", sell="2", category_id=cat,
        barcode="132", expiry_date=(today - timedelta(days=3)).isoformat(),
        min_stock_level="0",
    )
    # Nachbestellung → type=reorder
    _create_product(
        client, name="Leer", cost="1", sell="2", category_id=cat,
        barcode="133", stock_quantity="1", min_stock_level="10",
    )

    resp = client.get("/api/analytics/notifications")
    assert resp.status_code == 200
    items = resp.json()
    types = {n["type"] for n in items}
    assert "expiry_soon" in types
    assert "expired" in types
    assert "reorder" in types

    # Erste Notification ist 'danger' (expired).
    assert items[0]["type"] == "expired"
    assert items[0]["severity"] == "danger"


def _product_id(client, name: str) -> int:
    items = client.get("/api/products", params={"limit": 500}).json()["items"]
    return next(i["id"] for i in items if i["name"] == name)