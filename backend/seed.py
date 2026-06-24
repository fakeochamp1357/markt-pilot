"""Seed-Skript für MarktPilot.

Legt 5 Beispiel-Kategorien und ~20 Beispiel-Produkte mit echten
Barcodes an, damit man sofort was sieht.

Nutzung:
    python -m seed
oder:
    python seed.py
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.db.session import Base, SessionLocal, engine
from app.models import Category, Product

# Modelle registrieren
import app.models  # noqa: F401

CATEGORIES = [
    {"name": "Getränke", "color": "#3B82F6", "sort_order": 1},
    {"name": "Obst & Gemüse", "color": "#10B981", "sort_order": 2},
    {"name": "Milchprodukte", "color": "#F59E0B", "sort_order": 3},
    {"name": "Backwaren", "color": "#A16207", "sort_order": 4},
    {"name": "Snacks & Süßes", "color": "#EF4444", "sort_order": 5},
]


PRODUCTS = [
    # Getränke — echte EANs
    {
        "name": "Coca-Cola Original",
        "barcode": "5449000000996",
        "sku": "GET-COCA-05",
        "category": "Getränke",
        "unit": "Stück",
        "size_weight": "500ml",
        "cost_price": Decimal("0.55"),
        "sell_price": Decimal("1.29"),
        "stock_quantity": Decimal("48"),
        "min_stock_level": Decimal("12"),
        "expiry_date": date.today() + timedelta(days=180),
        "supplier": "Coca-Cola Europacific Partners",
        "color_tag": "#EF4444",
    },
    {
        "name": "Coca-Cola Zero",
        "barcode": "5449000131836",
        "sku": "GET-COCAZ-05",
        "category": "Getränke",
        "unit": "Stück",
        "size_weight": "500ml",
        "cost_price": Decimal("0.55"),
        "sell_price": Decimal("1.29"),
        "stock_quantity": Decimal("36"),
        "min_stock_level": Decimal("12"),
        "expiry_date": date.today() + timedelta(days=240),
        "supplier": "Coca-Cola Europacific Partners",
        "color_tag": "#1F2937",
    },
    {
        "name": "Red Bull Energy Drink",
        "barcode": "90415465",
        "sku": "GET-RB-025",
        "category": "Getränke",
        "unit": "Stück",
        "size_weight": "250ml",
        "cost_price": Decimal("0.90"),
        "sell_price": Decimal("1.79"),
        "stock_quantity": Decimal("24"),
        "min_stock_level": Decimal("6"),
        "expiry_date": date.today() + timedelta(days=300),
        "supplier": "Red Bull Deutschland",
        "color_tag": "#1E3A8A",
    },
    {
        "name": "Vittel Mineralwasser",
        "barcode": "3052671006050",
        "sku": "GET-VIT-15",
        "category": "Getränke",
        "unit": "Stück",
        "size_weight": "1.5L",
        "cost_price": Decimal("0.30"),
        "sell_price": Decimal("0.89"),
        "stock_quantity": Decimal("60"),
        "min_stock_level": Decimal("15"),
        "expiry_date": date.today() + timedelta(days=540),
        "supplier": "Vittel / Nestlé Waters",
        "color_tag": "#0EA5E9",
    },
    {
        "name": "Beck's Pils",
        "barcode": "4100130992007",
        "sku": "GET-BEC-05",
        "category": "Getränke",
        "unit": "Stück",
        "size_weight": "500ml",
        "cost_price": Decimal("0.65"),
        "sell_price": Decimal("1.39"),
        "stock_quantity": Decimal("40"),
        "min_stock_level": Decimal("10"),
        "expiry_date": date.today() + timedelta(days=120),
        "supplier": "Brauerei Beck's",
        "color_tag": "#FACC15",
    },

    # Milchprodukte
    {
        "name": "Müller Milch 3,5%",
        "barcode": "4025500011017",
        "sku": "MIL-MIL-1L",
        "category": "Milchprodukte",
        "unit": "Stück",
        "size_weight": "1L",
        "cost_price": Decimal("0.85"),
        "sell_price": Decimal("1.49"),
        "stock_quantity": Decimal("30"),
        "min_stock_level": Decimal("10"),
        "expiry_date": date.today() + timedelta(days=7),
        "supplier": "Müller Milch",
        "color_tag": "#FFFFFF",
    },
    {
        "name": "Müller Milch fettarm 1,5%",
        "barcode": "4025500011031",
        "sku": "MIL-MILF-1L",
        "category": "Milchprodukte",
        "unit": "Stück",
        "size_weight": "1L",
        "cost_price": Decimal("0.85"),
        "sell_price": Decimal("1.49"),
        "stock_quantity": Decimal("24"),
        "min_stock_level": Decimal("10"),
        "expiry_date": date.today() + timedelta(days=5),
        "supplier": "Müller Milch",
        "color_tag": "#F0FDF4",
    },
    {
        "name": "Ja! Naturjoghurt 3,5%",
        "barcode": "4014400900060",
        "sku": "MIL-JOG-500",
        "category": "Milchprodukte",
        "unit": "Stück",
        "size_weight": "500g",
        "cost_price": Decimal("0.45"),
        "sell_price": Decimal("0.89"),
        "stock_quantity": Decimal("40"),
        "min_stock_level": Decimal("12"),
        "expiry_date": date.today() + timedelta(days=10),
        "supplier": "REWE",
        "color_tag": "#FAFAF9",
    },
    {
        "name": "Hirtenkäse / Feta",
        "barcode": "20064044",
        "sku": "MIL-FETA-200",
        "category": "Milchprodukte",
        "unit": "Stück",
        "size_weight": "200g",
        "cost_price": Decimal("1.40"),
        "sell_price": Decimal("2.79"),
        "stock_quantity": Decimal("18"),
        "min_stock_level": Decimal("6"),
        "expiry_date": date.today() + timedelta(days=14),
        "supplier": "Hochland",
        "color_tag": "#FEF3C7",
    },
    {
        "name": "Kerrygold Butter",
        "barcode": "5012345678900",
        "sku": "MIL-BUT-250",
        "category": "Milchprodukte",
        "unit": "Stück",
        "size_weight": "250g",
        "cost_price": Decimal("1.55"),
        "sell_price": Decimal("2.49"),
        "stock_quantity": Decimal("25"),
        "min_stock_level": Decimal("8"),
        "expiry_date": date.today() + timedelta(days=30),
        "supplier": "Kerrygold / Ornua",
        "color_tag": "#FDE68A",
    },

    # Obst & Gemüse
    {
        "name": "Bananen (Fairtrade)",
        "barcode": "4015001000008",
        "sku": "OG-BAN-1KG",
        "category": "Obst & Gemüse",
        "unit": "kg",
        "size_weight": "1kg",
        "cost_price": Decimal("1.10"),
        "sell_price": Decimal("1.99"),
        "stock_quantity": Decimal("15.5"),
        "min_stock_level": Decimal("5"),
        "expiry_date": date.today() + timedelta(days=5),
        "supplier": "Fairtrade-Bananen",
        "color_tag": "#FACC15",
    },
    {
        "name": "Äpfel Elstar (Kl. I)",
        "barcode": "4015001000015",
        "sku": "OG-APF-1KG",
        "category": "Obst & Gemüse",
        "unit": "kg",
        "size_weight": "1kg",
        "cost_price": Decimal("1.30"),
        "sell_price": Decimal("2.49"),
        "stock_quantity": Decimal("22.0"),
        "min_stock_level": Decimal("5"),
        "expiry_date": date.today() + timedelta(days=14),
        "supplier": "Altes Land",
        "color_tag": "#DC2626",
    },
    {
        "name": "Tomaten Strauchtomaten",
        "barcode": "4015001000022",
        "sku": "OG-TOM-500",
        "category": "Obst & Gemüse",
        "unit": "kg",
        "size_weight": "500g",
        "cost_price": Decimal("1.40"),
        "sell_price": Decimal("2.89"),
        "stock_quantity": Decimal("3.5"),  # unter min -> Low-Stock-Hit
        "min_stock_level": Decimal("5"),
        "expiry_date": date.today() + timedelta(days=6),
        "supplier": "Niederländische Erzeugergemeinschaft",
        "color_tag": "#B91C1C",
    },

    # Backwaren
    {
        "name": "Lieken Urkorn Brot",
        "barcode": "4008452001019",
        "sku": "BW-BROT-500",
        "category": "Backwaren",
        "unit": "Stück",
        "size_weight": "500g",
        "cost_price": Decimal("1.20"),
        "sell_price": Decimal("2.29"),
        "stock_quantity": Decimal("20"),
        "min_stock_level": Decimal("6"),
        "expiry_date": date.today() + timedelta(days=3),
        "supplier": "Lieken",
        "color_tag": "#92400E",
    },
    {
        "name": "Harry Brötchen (6 Stk.)",
        "barcode": "4008452001026",
        "sku": "BW-BR-6",
        "category": "Backwaren",
        "unit": "Packung",
        "size_weight": "6 Stück",
        "cost_price": Decimal("0.95"),
        "sell_price": Decimal("1.79"),
        "stock_quantity": Decimal("15"),
        "min_stock_level": Decimal("4"),
        "expiry_date": date.today() + timedelta(days=1),
        "supplier": "Harry-Brot",
        "color_tag": "#D97706",
    },

    # Snacks & Süßes
    {
        "name": "Milka Alpenmilch Schokolade",
        "barcode": "7622210449283",
        "sku": "SS-MILKA-100",
        "category": "Snacks & Süßes",
        "unit": "Stück",
        "size_weight": "100g",
        "cost_price": Decimal("0.95"),
        "sell_price": Decimal("1.79"),
        "stock_quantity": Decimal("40"),
        "min_stock_level": Decimal("10"),
        "expiry_date": date.today() + timedelta(days=120),
        "supplier": "Mondelez Deutschland",
        "color_tag": "#7C3AED",
    },
    {
        "name": "Prinzen Rolle Keks",
        "barcode": "4001686301010",
        "sku": "SS-PRINZ-200",
        "category": "Snacks & Süßes",
        "unit": "Packung",
        "size_weight": "200g",
        "cost_price": Decimal("0.75"),
        "sell_price": Decimal("1.49"),
        "stock_quantity": Decimal("22"),
        "min_stock_level": Decimal("6"),
        "expiry_date": date.today() + timedelta(days=150),
        "supplier": "Prinzen Rolle",
        "color_tag": "#FB923C",
    },
    {
        "name": "Lay's Classic Chips",
        "barcode": "0028400090054",
        "sku": "SS-LAYS-150",
        "category": "Snacks & Süßes",
        "unit": "Packung",
        "size_weight": "150g",
        "cost_price": Decimal("0.85"),
        "sell_price": Decimal("1.69"),
        "stock_quantity": Decimal("28"),
        "min_stock_level": Decimal("8"),
        "expiry_date": date.today() + timedelta(days=90),
        "supplier": "PepsiCo Deutschland",
        "color_tag": "#FDE047",
    },
    {
        "name": "Haribo Goldbären",
        "barcode": "4001686301027",
        "sku": "SS-HAR-200",
        "category": "Snacks & Süßes",
        "unit": "Packung",
        "size_weight": "200g",
        "cost_price": Decimal("0.65"),
        "sell_price": Decimal("1.29"),
        "stock_quantity": Decimal("35"),
        "min_stock_level": Decimal("10"),
        "expiry_date": date.today() + timedelta(days=365),
        "supplier": "Haribo",
        "color_tag": "#FACC15",
    },
    {
        "name": "Kinderschokolade",
        "barcode": "4014400900084",
        "sku": "SS-KIND-100",
        "category": "Snacks & Süßes",
        "unit": "Stück",
        "size_weight": "100g (8 Riegel)",
        "cost_price": Decimal("0.95"),
        "sell_price": Decimal("1.79"),
        "stock_quantity": Decimal("20"),
        "min_stock_level": Decimal("6"),
        "expiry_date": date.today() + timedelta(days=180),
        "supplier": "Ferrero",
        "color_tag": "#9333EA",
    },
]


def seed(*, force: bool = False) -> None:
    """Legt Kategorien + Produkte an. Idempotent (überspringt wenn vorhanden)."""
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        # Kategorien
        cat_by_name: dict[str, Category] = {}
        for cat_data in CATEGORIES:
            existing = db.execute(
                select(Category).where(Category.name == cat_data["name"])
            ).scalar_one_or_none()
            if existing is None:
                cat = Category(**cat_data)
                db.add(cat)
                db.flush()
                cat_by_name[cat.name] = cat
                print(f"  + Kategorie: {cat.name}")
            else:
                cat_by_name[existing.name] = existing
                if force:
                    for k, v in cat_data.items():
                        setattr(existing, k, v)

        # Produkte
        created = updated = 0
        for p in PRODUCTS:
            data = dict(p)
            cat_name = data.pop("category")
            cat = cat_by_name.get(cat_name)
            if cat is None:
                print(f"  ! Kategorie fehlt: {cat_name}")
                continue
            data["category_id"] = cat.id
            data["cost_price_cents"] = int(
                (data["cost_price"] * 100).quantize(Decimal("1"))
            )
            data["sell_price_cents"] = int(
                (data["sell_price"] * 100).quantize(Decimal("1"))
            )
            del data["cost_price"]
            del data["sell_price"]

            existing = None
            if data.get("barcode"):
                existing = db.execute(
                    select(Product).where(Product.barcode == data["barcode"])
                ).scalar_one_or_none()
            if existing is None and data.get("sku"):
                existing = db.execute(
                    select(Product).where(Product.sku == data["sku"])
                ).scalar_one_or_none()

            if existing is None:
                db.add(Product(**data))
                created += 1
                print(f"  + Produkt: {data['name']} ({data['barcode']})")
            elif force:
                for k, v in data.items():
                    setattr(existing, k, v)
                updated += 1
                print(f"  ~ Produkt aktualisiert: {data['name']}")

        db.commit()
        print(
            f"\nSeed fertig: {len(CATEGORIES)} Kategorien, "
            f"{created} neue Produkte, {updated} aktualisiert."
        )


if __name__ == "__main__":
    import sys
    force = "--force" in sys.argv
    seed(force=force)