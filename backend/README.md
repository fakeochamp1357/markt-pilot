# MarktPilot — Backend (Phase 1 MVP)

Lokal-first Backend für **MarktPilot** — ein Supermarkt-POS / Warenbestand-System,
inspiriert von „Price List Maker" (ZerOnes) und SumUp.

Dieses Package implementiert die **Mobile-first Preisliste + Warenbestand**
API. Strikt lokal, eine SQLite-Datei, kein Cloud-Zwang.

---

## Tech-Stack

- **Python** 3.11+
- **FastAPI** 0.115 + Uvicorn
- **SQLAlchemy** 2.x ORM
- **Alembic** für Migrationen
- **Pydantic** v2 für Schema-Validierung
- **SQLite** (Datei-DB, läuft überall ohne Setup)
- **openpyxl** (XLSX) + **reportlab** (PDF) für Export

---

## Schnellstart

```bash
# 1. Dependencies installieren
cd markt-pilot/backend
pip install -r requirements.txt
# oder mit PEP 517/518:
# pip install -e .

# 2. DB migrieren (legt SQLite-Datei markt_pilot.db an)
alembic upgrade head

# 3. Beispieldaten seeden (5 Kategorien, 20 Produkte mit echten Barcodes)
python seed.py

# 4. Server starten
uvicorn app.main:app --reload --port 8000

# 5. Browser öffnen:
#    - Interaktive API-Doku:  http://localhost:8000/docs
#    - Alternative Doku:       http://localhost:8000/redoc
#    - OpenAPI-JSON:           http://localhost:8000/openapi.json
#    - Health-Check:           http://localhost:8000/healthz
```

> **Hinweis:** Wenn `alembic upgrade head` nicht ausgeführt wird, legt die App
> die Tabellen beim ersten Start automatisch an (per `Base.metadata.create_all`).
> In Production solltest du aber Alembic nutzen.

---

## Datenmodell

### Product (Herzstück der Preisliste)

| Feld             | Typ           | Beschreibung                                    |
| ---------------- | ------------- | ----------------------------------------------- |
| `id`             | int (PK)      |                                                 |
| `sku`            | str, unique   | Interne Artikelnummer                           |
| `barcode`        | str, indexed  | UPC/EAN — schneller Scanner-Lookup              |
| `name`           | str, indexed  |                                                 |
| `category_id`    | FK → Category |                                                 |
| `unit`           | str           | `Stück`, `kg`, `g`, `l`, `ml`, `m`, `Packung`, `Box` |
| `size_weight`    | str           | z.B. `500g`, `1L`                               |
| `cost_price`     | Decimal EUR   | **In DB als Integer-Cent** gespeichert          |
| `sell_price`     | Decimal EUR   | **In DB als Integer-Cent** gespeichert          |
| `currency`       | str (3)       | Default `EUR`                                   |
| `stock_quantity` | Decimal(14,3) | Bestand                                         |
| `min_stock_level`| Decimal(14,3) | Low-Stock-Schwelle                              |
| `expiry_date`    | date          | MHD                                             |
| `supplier`       | str           |                                                 |
| `notes`          | str           |                                                 |
| `image_url`      | str           |                                                 |
| `color_tag`      | str (HEX)     | Farbstreifen links in der UI                    |
| `is_active`      | bool          | Default `true` — Soft-Delete-Flag               |
| `version`        | int           | Optimistic-Lock für Stock-Updates               |
| `created_at` / `updated_at` | datetime | UTC                                       |

### Category
`id`, `name` (unique), `color` (HEX), `sort_order`, `parent_id` (FK self — für
Unterkategorien), `created_at`.

### StockMovement
`id`, `product_id` (FK), `change` (Decimal, +/-), `reason` (`purchase|sale|adjustment|waste|return`),
`reference` (z.B. Receipt-Nr), `created_by`, `created_at`.

---

## API-Endpoints

Alle Routen unter `/api/`. OpenAPI-Doku unter `/docs`.

### Produkte
| Method | Path                          | Beschreibung                          |
| ------ | ----------------------------- | ------------------------------------- |
| GET    | `/api/products`               | Liste, `?q=` Suche, `?category=`, `?active=`, Pagination (`limit`, `offset`) |
| GET    | `/api/products/{id}`          | Detail                                |
| POST   | `/api/products`               | Anlegen                               |
| PUT    | `/api/products/{id}`          | Aktualisieren                         |
| DELETE | `/api/products/{id}`          | **Soft-Delete** (`is_active=false`)   |
| GET    | `/api/products/barcode/{code}`| **Barcode-Lookup** — schneller Pfad   |
| POST   | `/api/products/bulk`          | Bulk-Import (JSON, dedup per barcode/sku) |
| POST   | `/api/products/bulk/upload`   | Bulk-Import (CSV-Datei-Upload)        |
| GET    | `/api/products/export`        | Export `?format=csv|xlsx|pdf|json`    |

### Kategorien
| Method | Path                       | Beschreibung      |
| ------ | -------------------------- | ----------------- |
| GET    | `/api/categories`          | Flache Liste      |
| POST   | `/api/categories`          | Anlegen           |
| PUT    | `/api/categories/{id}`     | Aktualisieren     |
| DELETE | `/api/categories/{id}`     | Löschen (Hard)    |

### Stock
| Method | Path                                          | Beschreibung                                  |
| ------ | --------------------------------------------- | --------------------------------------------- |
| POST   | `/api/stock/movements`                        | Wareneingang, Verkauf, Korrektur, …           |
| GET    | `/api/stock/movements?product_id=`            | Bewegungs-Historie                            |
| GET    | `/api/stock/low`                              | Produkte unter `min_stock_level`              |
| GET    | `/api/stock/expiring?days=30`                 | Produkte mit MHD in den nächsten N Tagen      |

### Meta
| Method | Path        | Beschreibung  |
| ------ | ----------- | ------------- |
| GET    | `/healthz`  | Health-Check  |
| GET    | `/docs`     | Swagger UI    |
| GET    | `/redoc`    | ReDoc         |

---

## Beispiel-Curl

```bash
# Kategorie anlegen
curl -X POST http://localhost:8000/api/categories \
  -H "Content-Type: application/json" \
  -d '{"name":"Getränke","color":"#3B82F6","sort_order":1}'

# Produkt anlegen (Cent-Preise werden in EUR eingegeben — die API konvertiert)
curl -X POST http://localhost:8000/api/products \
  -H "Content-Type: application/json" \
  -d '{
    "sku":"GET-COCA-05",
    "barcode":"5449000000996",
    "name":"Coca-Cola Original",
    "category_id":1,
    "unit":"Stück",
    "size_weight":"500ml",
    "cost_price":"0.55",
    "sell_price":"1.29",
    "stock_quantity":"48",
    "min_stock_level":"12",
    "color_tag":"#EF4444"
  }'

# Barcode-Lookup (schneller Scanner-Pfad)
curl http://localhost:8000/api/products/barcode/5449000000996

# Wareneingang +100 Stück
curl -X POST http://localhost:8000/api/stock/movements \
  -H "Content-Type: application/json" \
  -d '{"product_id":1,"change":"100","reason":"purchase","reference":"RE-2026-0001"}'

# Verkauf -3 Stück
curl -X POST http://localhost:8000/api/stock/movements \
  -H "Content-Type: application/json" \
  -d '{"product_id":1,"change":"-3","reason":"sale"}'

# Low-Stock-Liste
curl http://localhost:8000/api/stock/low

# Bald ablaufende Produkte (60 Tage)
curl "http://localhost:8000/api/stock/expiring?days=60"

# Export als Excel
curl -o preisliste.xlsx "http://localhost:8000/api/products/export?format=xlsx"

# Export als PDF
curl -o preisliste.pdf "http://localhost:8000/api/products/export?format=pdf"

# Suche
curl "http://localhost:8000/api/products?q=cola"
```

---

## Design-Entscheidungen

1. **Preise als Integer-Cent** — niemals Float für Geld. An der API-Grenze
   werden sie als Decimal (EUR) dargestellt (`Pydantic`/`Schemas`).
2. **Soft-Delete** — `DELETE /api/products/{id}` setzt nur `is_active=false`,
   die Daten bleiben für Reports erhalten.
3. **Optimistic Locking** auf Stock-Bewegungen: `UPDATE products SET stock_qty=…,
   version=version+1 WHERE id=? AND version=?`. Bei Konflikt gibt es einen
   409-Response (Retry-fähig).
4. **Bulk-Import Dedup-Strategie**: Existierendes Produkt wird per `barcode`
   (bevorzugt) oder `sku` gefunden und aktualisiert.
5. **CORS offen** für `*` (Development) — Phase 3 härten.
6. **Keine Auth** in Phase 1 — kommt später mit Multi-Device.

---

## Tests

```bash
pip install -r requirements.txt
pytest -v
```

19 Tests, alle grün:
- Health & OpenAPI
- Kategorie-CRUD
- Produkt-CRUD + Soft-Delete
- Barcode-Lookup
- Bulk-Import (JSON, dedup)
- Bulk-Import (CSV-Upload)
- Barcode-Konflikterkennung
- Export (CSV, XLSX, PDF)
- Stock-Movement-Happy-Path
- Low-Stock-Endpoint
- Expiring-Endpoint
- Stock-Movement bei unbekannter Product-ID

---

## Projektstruktur

```
backend/
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 20260623_2019_7180072e5311_initial_schema_*.py
├── alembic.ini
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI-App, CORS, Lifespan
│   ├── db/
│   │   └── session.py       # Engine, Session, get_db()
│   ├── models/
│   │   └── __init__.py      # Category, Product, StockMovement
│   ├── schemas/
│   │   └── __init__.py      # Pydantic v2 Schemas + Cent-Konvertierung
│   ├── routers/
│   │   ├── products.py      # CRUD + Barcode + Bulk + Export
│   │   ├── categories.py
│   │   └── stock.py
│   └── services/
│       └── __init__.py      # apply_stock_movement (Optimistic Lock)
├── tests/
│   ├── conftest.py
│   ├── test_categories.py
│   ├── test_products.py
│   └── test_stock.py
├── seed.py                  # 5 Kategorien, 20 Produkte mit echten Barcodes
├── pyproject.toml
├── requirements.txt
├── .env.example
└── README.md
```

---

## Phase-2 / Phase-3 Roadmap (was bewusst weggelassen wurde)

- **Auth** (Phase 3 multi-device): JWT, Rollen (Owner / Cashier)
- **POS-Flow**: Kassen-Bons, Tagesabschluss, Trinkgeld
- **WebSocket-Sync** für mehrere Geräte
- **Cloud-Backup**: opt-in, encrypted
- **Reporting**: Tages-/Wochenumsatz, Top-Seller
- **Hard-Delete-Purge** für GDPR-Compliance

---

## Lizenz

Proprietär — © 2026 MarktPilot