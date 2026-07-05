"""Demo-Seeder für die Analytics-Vorschau.

Legt eine separate DB (``./demo_analytics.db``) an, füllt sie mit einem
realistischen Sortiment und simuliert Verkäufe der letzten ~120 Tage — so
dass jede Analytics-Sektion etwas Spannendes zu zeigen hat:

- Vimto & Wasser:        Bestseller (viele Sales, hohe Marge)
- Cola, Red Bull, Brot:  solide Verkäufe
- Bananen, Brötchen:     werden gekauft, aber Bestand geht zur Neige
- MHD-Warnungen:         Milch läuft in 2 Tagen ab, ein Joghurt ist alt
- Dead-Stock:            \"Spezialität Senf\" wurde seit 90 Tagen nicht verkauft
- Reorder:               Tomaten + Brötchen unter Mindestbestand

Nutzung:
    DATABASE_URL=sqlite:///./demo_analytics.db python -m scripts.demo_analytics
    uvicorn app.main:app --port 8765   # siehe ``scripts/run_demo.py``
"""
from __future__ import annotations

import os
import random
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

# DB-Override VOR allen app-Imports.
os.environ.setdefault(
    "DATABASE_URL", "sqlite:///./demo_analytics.db"
)
os.environ["MARKTPILOT_SKIP_AUTO_CREATE"] = "1"

from sqlalchemy import delete, select  # noqa: E402

from app.db.session import Base, SessionLocal, engine  # noqa: E402
from app.models import Category, Product, StockMovement  # noqa: E402
import app.models  # noqa: E402,F401

random.seed(42)
NOW = datetime.now(timezone.utc)


CATEGORIES = [
    {"name": "Getränke", "color": "#3B82F6", "sort_order": 1},
    {"name": "Backwaren", "color": "#A16207", "sort_order": 2},
    {"name": "Snacks & Süßes", "color": "#EF4444", "sort_order": 3},
    {"name": "Milchprodukte", "color": "#F59E0B", "sort_order": 4},
    {"name": "Spezialitäten", "color": "#7C3AED", "sort_order": 5},
]


PRODUCTS = [
    # Bestseller — viele Verkäufe in letzter Zeit.
    {
        "name": "Vimto Squash 1L",
        "sku": "GET-VIM-1L", "barcode": "5012345000011",
        "category": "Getränke", "unit": "Stück", "size_weight": "1L",
        "cost_price": Decimal("1.10"), "sell_price": Decimal("2.49"),
        "stock_quantity": Decimal("42"), "min_stock_level": Decimal("10"),
        "expiry_date": date.today() + timedelta(days=240),
        "supplier": "Vimto UK", "color_tag": "#9333EA",
    },
    {
        "name": "Vittel Mineralwasser 1,5L",
        "sku": "GET-VIT-15", "barcode": "3052671006050",
        "category": "Getränke", "unit": "Stück", "size_weight": "1.5L",
        "cost_price": Decimal("0.30"), "sell_price": Decimal("0.89"),
        "stock_quantity": Decimal("85"), "min_stock_level": Decimal("20"),
        "expiry_date": date.today() + timedelta(days=540),
        "supplier": "Vittel", "color_tag": "#0EA5E9",
    },
    # Solide Verkäufe.
    {
        "name": "Coca-Cola Original 500ml",
        "sku": "GET-COCA-05", "barcode": "5449000000996",
        "category": "Getränke", "unit": "Stück", "size_weight": "500ml",
        "cost_price": Decimal("0.55"), "sell_price": Decimal("1.29"),
        "stock_quantity": Decimal("60"), "min_stock_level": Decimal("15"),
        "expiry_date": date.today() + timedelta(days=180),
        "supplier": "Coca-Cola", "color_tag": "#EF4444",
    },
    {
        "name": "Red Bull Energy 250ml",
        "sku": "GET-RB-025", "barcode": "90415465",
        "category": "Getränke", "unit": "Stück", "size_weight": "250ml",
        "cost_price": Decimal("0.90"), "sell_price": Decimal("1.79"),
        "stock_quantity": Decimal("28"), "min_stock_level": Decimal("8"),
        "expiry_date": date.today() + timedelta(days=300),
        "supplier": "Red Bull", "color_tag": "#1E3A8A",
    },
    {
        "name": "Harry Brötchen 6er",
        "sku": "BW-BR-6", "barcode": "4008452001026",
        "category": "Backwaren", "unit": "Packung", "size_weight": "6 Stück",
        "cost_price": Decimal("0.95"), "sell_price": Decimal("1.79"),
        "stock_quantity": Decimal("3"), "min_stock_level": Decimal("8"),
        "expiry_date": date.today() + timedelta(days=1),
        "supplier": "Harry-Brot", "color_tag": "#D97706",
    },
    {
        "name": "Lieken Urkorn Brot 500g",
        "sku": "BW-BROT-500", "barcode": "4008452001019",
        "category": "Backwaren", "unit": "Stück", "size_weight": "500g",
        "cost_price": Decimal("1.20"), "sell_price": Decimal("2.29"),
        "stock_quantity": Decimal("18"), "min_stock_level": Decimal("6"),
        "expiry_date": date.today() + timedelta(days=3),
        "supplier": "Lieken", "color_tag": "#92400E",
    },
    # MHD-Warnungen.
    {
        "name": "Müller Milch 3,5% 1L",
        "sku": "MIL-MIL-1L", "barcode": "4025500011017",
        "category": "Milchprodukte", "unit": "Stück", "size_weight": "1L",
        "cost_price": Decimal("0.85"), "sell_price": Decimal("1.49"),
        "stock_quantity": Decimal("22"), "min_stock_level": Decimal("10"),
        "expiry_date": date.today() + timedelta(days=2),  # bald ablaufend
        "supplier": "Müller", "color_tag": "#FFFFFF",
    },
    {
        "name": "Ja! Naturjoghurt 500g",
        "sku": "MIL-JOG-500", "barcode": "4014400900060",
        "category": "Milchprodukte", "unit": "Stück", "size_weight": "500g",
        "cost_price": Decimal("0.45"), "sell_price": Decimal("0.89"),
        "stock_quantity": Decimal("8"), "min_stock_level": Decimal("6"),
        "expiry_date": date.today() - timedelta(days=3),  # abgelaufen
        "supplier": "REWE", "color_tag": "#FAFAF9",
    },
    # Niedriger Bestand / Reorder.
    {
        "name": "Tomaten Strauchtomaten",
        "sku": "OG-TOM-500", "barcode": "4015001000022",
        "category": "Backwaren", "unit": "kg", "size_weight": "500g",
        "cost_price": Decimal("1.40"), "sell_price": Decimal("2.89"),
        "stock_quantity": Decimal("2.5"), "min_stock_level": Decimal("5"),
        "expiry_date": date.today() + timedelta(days=6),
        "supplier": "Niederländische Erzeugergemeinschaft",
        "color_tag": "#B91C1C",
    },
    # Süßes — solide Verkäufe.
    {
        "name": "Milka Alpenmilch 100g",
        "sku": "SS-MILKA-100", "barcode": "7622210449283",
        "category": "Snacks & Süßes", "unit": "Stück", "size_weight": "100g",
        "cost_price": Decimal("0.95"), "sell_price": Decimal("1.79"),
        "stock_quantity": Decimal("38"), "min_stock_level": Decimal("10"),
        "expiry_date": date.today() + timedelta(days=120),
        "supplier": "Mondelez", "color_tag": "#7C3AED",
    },
    {
        "name": "Haribo Goldbären 200g",
        "sku": "SS-HAR-200", "barcode": "4001686301027",
        "category": "Snacks & Süßes", "unit": "Packung", "size_weight": "200g",
        "cost_price": Decimal("0.65"), "sell_price": Decimal("1.29"),
        "stock_quantity": Decimal("32"), "min_stock_level": Decimal("8"),
        "expiry_date": date.today() + timedelta(days=365),
        "supplier": "Haribo", "color_tag": "#FACC15",
    },
    # Ladenhüter — kein Sale in den letzten 90+ Tagen.
    {
        "name": "Spezialität Englischer Senf",
        "sku": "SP-SENF-200", "barcode": "5012345000999",
        "category": "Spezialitäten", "unit": "Stück", "size_weight": "200g",
        "cost_price": Decimal("2.80"), "sell_price": Decimal("4.99"),
        "stock_quantity": Decimal("14"), "min_stock_level": Decimal("0"),
        "expiry_date": date.today() + timedelta(days=400),
        "supplier": "Colman's", "color_tag": "#FBBF24",
    },
    {
        "name": "Salted Caramel Kekse (Premium)",
        "sku": "SP-CARA-150", "barcode": "5012345001002",
        "category": "Spezialitäten", "unit": "Packung", "size_weight": "150g",
        "cost_price": Decimal("3.20"), "sell_price": Decimal("5.49"),
        "stock_quantity": Decimal("9"), "min_stock_level": Decimal("0"),
        "expiry_date": date.today() + timedelta(days=60),
        "supplier": "Walkers Shortbread", "color_tag": "#92400E",
    },
]


def reset_db() -> None:
    """Löscht alle Tabellen und legt sie frisch an."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def seed_categories_and_products() -> dict[str, int]:
    """Schreibt Kategorien + Produkte in die DB. Returns: name → product_id."""
    product_ids: dict[str, int] = {}
    with SessionLocal() as db:
        for cat_data in CATEGORIES:
            db.add(Category(**cat_data))
        db.flush()

        for p in PRODUCTS:
            data = dict(p)
            cat_name = data.pop("category")
            cat = db.execute(
                select(Category).where(Category.name == cat_name)
            ).scalar_one()
            data["category_id"] = cat.id
            data["cost_price_cents"] = int(
                (data["cost_price"] * 100).quantize(Decimal("1"))
            )
            data["sell_price_cents"] = int(
                (data["sell_price"] * 100).quantize(Decimal("1"))
            )
            data["is_active"] = True
            del data["cost_price"]
            del data["sell_price"]
            prod = Product(**data)
            db.add(prod)
            db.flush()
            product_ids[prod.name] = prod.id
        db.commit()
    return product_ids


def seed_initial_purchase(product_ids: dict[str, int]) -> None:
    """Einmaliger Wareneingang, damit der Bestand stimmt."""
    with SessionLocal() as db:
        for name, pid in product_ids.items():
            product = db.get(Product, pid)
            db.add(
                StockMovement(
                    product_id=pid,
                    change=product.stock_quantity,
                    reason="purchase",
                    reference="INITIAL-STOCK",
                    created_at=NOW - timedelta(days=120),
                    created_by="demo",
                )
            )
        db.commit()


def seed_sales(product_ids: dict[str, int]) -> None:
    """Simuliert Verkäufe über die letzten 120 Tage."""
    # Profil: durschnittliche Sales pro Tag.
    profile = {
        "Vimto Squash 1L": 8,
        "Vittel Mineralwasser 1,5L": 12,
        "Coca-Cola Original 500ml": 6,
        "Red Bull Energy 250ml": 3,
        "Harry Brötchen 6er": 4,
        "Lieken Urkorn Brot 500g": 3,
        "Milka Alpenmilch 100g": 2,
        "Haribo Goldbären 200g": 2,
        "Müller Milch 3,5% 1L": 5,
        "Tomaten Strauchtomaten": 1,
    }
    with SessionLocal() as db:
        for name, per_day in profile.items():
            pid = product_ids[name]
            for day_offset in range(120, 0, -1):
                day = NOW - timedelta(days=day_offset)
                # Leichte Wochentags-Variation.
                weekday = day.weekday()
                weekend_factor = 1.5 if weekday >= 5 else 1.0
                qty = max(
                    0,
                    int(
                        round(
                            random.gauss(per_day * weekend_factor, per_day * 0.3)
                        )
                    ),
                )
                if qty == 0:
                    continue
                db.add(
                    StockMovement(
                        product_id=pid,
                        change=Decimal(-qty),
                        reason="sale",
                        reference=None,
                        created_at=day.replace(
                            hour=random.randint(8, 20), minute=random.randint(0, 59)
                        ),
                        created_by="kasse",
                    )
                )
        db.commit()


def main() -> None:
    print(f"→ Demo-DB: {os.environ['DATABASE_URL']}")
    reset_db()
    print("  Tabellen frisch angelegt.")
    pids = seed_categories_and_products()
    print(f"  {len(CATEGORIES)} Kategorien + {len(pids)} Produkte.")
    seed_initial_purchase(pids)
    print("  Anfangsbestand gebucht.")
    seed_sales(pids)
    print("  ~120 Tage simulierte Verkäufe.")
    print("Fertig. Starte das Backend jetzt mit:")
    print("  DATABASE_URL=sqlite:///./demo_analytics.db \\")
    print("    uvicorn app.main:app --port 8765 --reload")


if __name__ == "__main__":
    main()