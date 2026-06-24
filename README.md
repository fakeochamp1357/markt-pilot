# MarktPilot

Personal supermarket POS + inventory system. Mobile-first, offline-capable, multi-device sync (Phase 2).
Designed for self-hosted single-store use. Inspired by **Price List Maker** (ZerOnes iOS app) and **SumUp**.

> **Status:** Phase 1 MVP complete. Preisliste + Warenbestand + Kategorien + Scanner + Offline-Modus funktionieren auf iOS/Android/Windows/Linux-Browsern.

---

## Quick Start

### 1) Backend

```bash
cd backend
pip install -r requirements.txt
alembic upgrade head
python3 seed.py                       # lädt ~20 Beispiel-Produkte
uvicorn app.main:app --reload --port 8000
```

→ API läuft auf `http://localhost:8000`
→ Swagger-Doku: `http://localhost:8000/docs`

### 2) Frontend

```bash
cd frontend
npm install
npm run dev                           # → http://localhost:5173
```

Mobile testen: Browser auf `http://<deine-ip>:5173` öffnen oder via Chrome DevTools → Device Toolbar → iPhone 14 Pro.

---

## Architektur

```
Browser (iOS / Android / Win / Linux)
    │  React 18 + TS + Tailwind (mobile-first, PWA)
    │  Dexie (IndexedDB offline cache) + Outbox-Queue
    ▼
FastAPI (Python 3.11+)
    │  REST/JSON, OpenAPI auto-generiert
    ▼
SQLite (lokal-first, eine Datei)
```

Phase 2: Raspberry Pi als zentraler Server im LAN, mehrere Geräte syncen automatisch.

---

## Features (Phase 1)

- **Preisliste** mit Live-Suche, Filter-Chips, 6-Wege-Sortierung, Produkt-Karten mit Kategoriefarbe
- **Warenbestand** mit KPIs (Gesamtwert, Niedriger Bestand, Läuft bald ab), Stock-Eingang erfassen
- **Kategorien** mit Farbpicker, Produktanzahl, Add/Rename/Delete
- **Scanner** — Kamera (ZXing) + manueller Modus, Barcode-Lookup
- **Offline-First** — Dexie-Cache, Outbox-Queue, Service Worker (PWA), Offline-Badge
- **Bulk-Import** per CSV/JSON mit UPSERT auf barcode/SKU
- **Export** als CSV, XLSX, PDF
- **Mehr** — Settings, Export, About

---

## Tests

```bash
cd backend && pytest         # 19/19 grün
```

---

## Phase 2 Roadmap

- Multi-Device-Sync (LAN/Cloud)
- POS / Kasse mit Warenkorb, Bargeld, Receipt-Printer
- Dashboard (Tagesumsatz, Top-Seller, Marge)
- Lieferanten-Bestelllisten
- Produktbilder
