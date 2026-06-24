# MarktPilot — Phase 1 End-to-End Report

**Date:** 2026-06-24
**Phase:** 1 — Mobile-first Preisliste + Warenbestand
**Status:** ✅ ALL CHECKS PASS

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  iOS / Android / Windows / Linux Browser                    │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ React 18 + TypeScript + Tailwind (mobile-first)        │ │
│  │ Vite dev server :5173  (buildable to PWA / installable)│ │
│  │                                                        │ │
│  │  Dexie (IndexedDB)  ←────  Outbox queue                │ │
│  │   ↑ offline cache         ↑ mutations while offline   │ │
│  │   └── instant render ─────┘ ──── syncs when online ────┤ │
│  └─────────────────────────┬──────────────────────────────┘ │
│                            │ REST/JSON (axios)              │
└────────────────────────────┼────────────────────────────────┘
                             │ http://localhost:8000/api
┌────────────────────────────▼────────────────────────────────┐
│ FastAPI  +  SQLAlchemy 2.x  +  Pydantic v2  (uvicorn :8000) │
│  Routers:  /api/products   /api/categories                  │
│            /api/stock/movements  /api/stock/low             │
│            /api/stock/expiring  /api/products/barcode/{code}│
│            /api/products/export  /api/products/bulk          │
│            /docs   (Swagger UI / OpenAPI)                   │
└────────────────────────────┬────────────────────────────────┘
                             │ SQLAlchemy ORM
                             ▼
                       markt_pilot.db  (SQLite, lokal)
```

---

## Module 1 — Backend (`/workspace/markt-pilot/backend`)

| Endpoint | Status |
|---|---|
| `GET /healthz` | ✅ 200 |
| `GET /docs` | ✅ Swagger UI loads |
| `GET /api/products?q=cola` | ✅ Live search, 4 hits |
| `POST /api/products` | ✅ 201 + id |
| `PUT /api/products/{id}` | ✅ Decimal update works |
| `DELETE /api/products/{id}` | ✅ Soft-delete (is_active=false) |
| `GET /api/products/barcode/{code}` | ✅ Lookup in O(1) |
| `POST /api/products/bulk` | ✅ UPSERT on barcode/sku |
| `POST /api/stock/movements` | ✅ Atomic stock update |
| `GET /api/stock/low` | ✅ Returns deficit items |
| `GET /api/stock/expiring?days=N` | ✅ MHD filter |

**Tests:** 19/19 pytest green (`pytest_output.txt`)

---

## Module 2 — Frontend (`/workspace/markt-pilot/frontend`)

**Stack:** Vite 5 + React 18 + TypeScript + Tailwind + Zustand + Dexie + react-router v6 + react-hook-form + zod + @zxing/browser + vite-plugin-pwa

**TypeScript:** `tsc --noEmit` → 0 errors
**Dev server:** `npm run dev` → HTTP 200 on :5173

### Screens

| Tab | Path | Feature |
|---|---|---|
| Preisliste | `/` | Live search, filter chips, 6-way sort, product cards with category color stripe, big price, FAB |
| Warenbestand | `/inventory` | KPI cards (Produkte, Lagerwert, Niedriger Bestand, Läuft bald ab), Stock-Eingang sheet, Übersicht/Bewegungen tabs |
| Kategorien | `/categories` | Color picker, product count, add/rename/delete with confirm |
| Scanner | `/scanner` | Camera viewfinder (ZXing) + manual entry fallback, barcode lookup |
| Mehr | `/more` | Settings, Export (CSV/XLSX/PDF), About, Offline-Badge wenn offline |

### Design rules met
- ✅ Touch targets ≥ 44×44 px
- ✅ Body text ≥ 16 px, prices ≥ 20 px
- ✅ Hoher Kontrast, große Buttons
- ✅ Sprache komplett Deutsch

### Screenshots (iPhone 14 Pro, 390×844)
- `Preisliste` — 23 seed products, search/filter/sort, FAB, bottom tab bar
- `Warenbestand` — KPI cards + product list with low-stock warnings in red
- `Kategorien` — All categories with color stripes and product counts

(see `/workspace/markt-pilot/.references/screenshot-*.png`)

---

## End-to-End Smoke Test

Executed against running services:

| # | Step | Result |
|---|------|--------|
| 1 | GET `http://localhost:5173/` | ✅ 200, HTML contains `<div id="root">` |
| 2 | GET `/api/products` | ✅ 23 products loaded |
| 3 | GET `/api/products?q=cola` | ✅ 4 cola products |
| 4 | POST `/api/categories` (Getraenke-Test, #FF5733) | ✅ Created id=6 |
| 5 | POST `/api/products` (linked to category 6, barcode 9999999000001) | ✅ Created id=23 |
| 6 | PUT `/api/products/1` (Coca-Cola price 1.29 → 2.29) | ✅ Persisted |
| 7 | GET `/api/products/1` | ✅ Returns €2.29 |
| 8 | GET `/api/stock/low` | ✅ 2 items |
| 9 | GET `/api/stock/expiring?days=180` | ✅ 16 items |
| 10 | GET `/api/products/barcode/9999999000001` | ✅ Returns new product |
| 11 | DELETE `/api/products/23` (cleanup) | ✅ 200 |
| 12 | DELETE `/api/categories/6` (cleanup) | ✅ 204 |
| 13 | PUT restore Coca-Cola price | ✅ 1.29 restored |

---

## How to Run

### Backend
```bash
cd /workspace/markt-pilot/backend
pip install -r requirements.txt
alembic upgrade head              # apply migrations
python3 seed.py                   # load 20 sample products (optional)
uvicorn app.main:app --reload --port 8000
# → API docs at http://localhost:8000/docs
```

### Frontend
```bash
cd /workspace/markt-pilot/frontend
npm install
npm run dev                       # → http://localhost:5173
```

### Tests
```bash
cd /workspace/markt-pilot/backend
pytest                            # 19/19 should pass
```

---

## Next Steps (Phase 2+)

1. **Multi-Device Sync** — Raspberry Pi als zentraler Sync-Server, alle Geräte (Phone, Tablet, Pi-Touch, Windows-PC) verbinden sich zum LAN-Sync. Konfliktauflösung via `version`-Spalte (bereits implementiert).
2. **POS / Kasse** — Cart, Scan-to-cart, Cash/Card-Tender, ESC/POS Receipt-Printer Anbindung.
3. **Dashboard & Reports** — Tagesumsatz, Top-Seller, Marge pro Kategorie, Waste-Tracking.
4. **Image Upload** — Produktbilder lokal speichern (Phase 1: `image_url` Feld vorbereitet).
5. **Lieferanten-Modul** — Bestelllisten-Generierung bei Niedrigbestand.
