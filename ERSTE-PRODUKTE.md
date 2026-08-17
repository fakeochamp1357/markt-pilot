# MarktPilot — Die ersten Produkte anlegen

Stand: 2026-08-10
Ziel: 5–20 Produkte in die DB bekommen, sodass die Kassen was zu scannen haben.

> **Voraussetzung:** Laptop-Server läuft (siehe `LAPTOP-SETUP.md`), erreichbar
> auf `http://<LAPTOP-IP>:8000` (oder `http://localhost:8000` direkt am Laptop).

---

## Schritt 1 — Kategorien anlegen (5 Min)

Kategorien helfen beim Sortieren, Filtern und für die Farb-Streifen in der
Preisliste. Mindestens diese 6 anlegen:

| Name | Farbe (Hex) |
|---|---|
| Getränke | `#3B82F6` (Blau) |
| Snacks / Süßwaren | `#F59E0B` (Orange) |
| Obst & Gemüse | `#10B981` (Grün) |
| Milchprodukte | `#8B5CF6` (Lila) |
| Backwaren | `#D97706` (Braun-Orange) |
| Sonstiges | `#6B7280` (Grau) |

**In der UI** (Browser → `http://localhost:5173/` → Tab „Kategorien"):
- „+ Kategorie" → Name + Farbpicker → Speichern
- 6× wiederholen

**Oder per API** (Copy-Paste, jeweils anpassen):

```powershell
$base = "http://localhost:8000/api"

$categories = @(
    @{ name = "Getränke";     color = "#3B82F6" }
    @{ name = "Snacks";       color = "#F59E0B" }
    @{ name = "Obst & Gemüse"; color = "#10B981" }
    @{ name = "Milchprodukte"; color = "#8B5CF6" }
    @{ name = "Backwaren";     color = "#D97706" }
    @{ name = "Sonstiges";     color = "#6B7280" }
)

foreach ($cat in $categories) {
    Invoke-RestMethod -Method Post -Uri "$base/categories" `
        -ContentType "application/json" `
        -Body (ConvertTo-Json $cat)
}
```

---

## Schritt 2 — Produkte anlegen

### Option A: Manuelle Eingabe über die UI (gut für 5–10 Produkte)

Tab **„Preisliste"** → „+" Button (FAB unten rechts) → Formular ausfüllen:

| Feld | Beispiel | Hinweis |
|---|---|---|
| Name | Coca-Cola 0,33 L | Pflicht |
| Kategorie | Getränke | Dropdown |
| Barcode | 5449000000996 | Echte EAN scannen oder eintippen |
| SKU | COLA-033 | Optional, interne Artikelnummer |
| Einheit | Dose | „Stück" / „kg" / „Liter" / „Packung" |
| Verkaufspreis | 1,29 | In Euro, mit Komma |
| Einkaufspreis | 0,65 | Für Marge-Berechnung (Analytics) |
| Pfand | 0,25 | Falls Pfand-Flasche/-Dose |
| Bestand | 50 | Aktueller Lagerbestand |
| MHD | 2027-12-31 | Mindesthaltbarkeit (optional) |

Speichern → Produkt erscheint in der Liste.

### Option B: CSV-Bulk-Import (10–500 Produkte, EMPFOHLEN)

#### CSV-Format

Die Datei braucht **diese Spalten** (Reihenfolge egal, deutsche Kommas oder
englische Punkte für Dezimalzahlen — beides wird akzeptiert):

```csv
name,barcode,sku,category,unit,sell_price_eur,cost_price_eur,deposit_eur,stock,min_stock,expiry_date,supplier
Coca-Cola 0,33 L,5449000000996,COLA-033,Getränke,Dose,1.29,0.65,0.25,50,10,
Fanta 0,33 L,5449000000507,FANTA-033,Getränke,Dose,1.29,0.65,0.25,30,10,
Red Bull 0,25 L,9002490100070,RB-025,Getränke,Dose,1.79,0.95,0.25,40,10,
Vimto 0,33 L,5012345678900,VIM-033,Getränke,Dose,1.49,0.70,0.25,24,5,2027-06-30
Hohes C Orange 1 L,4001686301029,HC-O-1L,Getränke,Flasche,2.49,1.20,0.25,15,5,
Mars 50g,5000159461122,MARS-50,Snacks,Stück,1.19,0.55,0,80,20,
Snickers 50g,5000159459228,SNICK-50,Snacks,Stück,1.19,0.55,0,75,20,
Twix 50g,5000159459228,TWIX-50,Snacks,Stück,1.19,0.55,0,60,20,
Haribo Goldbären 100g,4001686301029,HAR-G-100,Snacks,Beutel,1.49,0.70,0,40,10,
Bananen,,BAN-1,Obst & Gemüse,kg,1.99,0.80,0,12,3,
Äpfel Elstar,,APF-ELS,Obst & Gemüse,kg,2.49,1.20,0,20,5,
Milch H-Milch 1 L,4001686301029,MIL-1L,Milchprodukte,Flasche,1.29,0.65,0,30,10,
Joghurt Müller 500g,4001686301029,JOG-M-500,Milchprodukte,Becher,1.99,1.00,0,25,8,
Brot Vollkorn 500g,4001686301029,BROT-VK,Backwaren,Stück,2.99,1.50,0,8,3,
Brötchen,,BROETCH,Backwaren,Stück,0.39,0.15,0,30,5,
```

> **Hinweise zu den Spalten:**
> - `barcode` und `sku` können leer sein (dann keine Doppel-Erkennung)
> - `category` muss **exakt** so heißen wie eine bestehende Kategorie
> - `expiry_date` im Format `JJJJ-MM-TT` oder leer
> - Dezimalzahlen: `1.29` ODER `1,29` — beides geht
> - `stock` und `min_stock`: `kg` werden mit 3 Nachkommastellen gespeichert (z.B. `1.250`)

Speichern als `C:\company\markt-pilot\produkte.csv` (oder wohin du willst).

#### Import via API

```powershell
$base = "http://localhost:8000/api"
$csv = Import-Csv "C:\company\markt-pilot\produkte.csv"

$payload = $csv | ForEach-Object {
    [PSCustomObject]@{
        name              = $_.name
        barcode           = if ($_.barcode) { $_.barcode } else { $null }
        sku               = if ($_.sku) { $_.sku } else { $null }
        category_name     = $_.category
        unit              = $_.unit
        size_weight       = $null
        sell_price_cents  = [int]([decimal]($_.sell_price_eur -replace ',', '.') * 100)
        cost_price_cents  = [int]([decimal]($_.cost_price_eur -replace ',', '.') * 100)
        deposit_cents     = [int]([decimal]($_.deposit_eur -replace ',', '.') * 100)
        stock_quantity    = [decimal]($_.stock -replace ',', '.')
        min_stock_level   = [decimal]($_.min_stock -replace ',', '.')
        expiry_date       = if ($_.expiry_date) { $_.expiry_date } else { $null }
        supplier          = if ($_.supplier) { $_.supplier } else { $null }
    }
}

$result = Invoke-RestMethod -Method Post -Uri "$base/products/bulk" `
    -ContentType "application/json" `
    -Body (ConvertTo-Json @{ items = $payload } -Depth 5)

Write-Host "Importiert: $($result.created.Count) | Aktualisiert: $($result.updated.Count) | Fehler: $($result.errors.Count)"
$result.errors | Format-Table
```

> **Wenn der Endpoint `category_name` noch nicht unterstützt**, vorher die
> `category_id` aus den Kategorien auflösen:
>
> ```powershell
> $categories = Invoke-RestMethod "$base/categories"
> $catMap = @{}
> $categories | ForEach-Object { $catMap[$_.name] = $_.id }
> # dann im Loop: category_id = $catMap[$_.category]
> ```

---

## Schritt 3 — Wareneingang erfassen (Bestand aufstocken)

Wenn du Produkte mit Anfangsbestand angelegt hast (Spalte `stock` in der CSV),
ist der Bestand direkt da. Wenn du nachträglich Ware reinbekommst:

### Über die UI

Tab **„Warenbestand"** → Produkt suchen → auf das Produkt tippen →
**„Wareneingang"** → Menge eingeben → Speichern.

### Über die API

```powershell
$base = "http://localhost:8000/api"

# 50 Coca-Cola dazubuchen
Invoke-RestMethod -Method Post -Uri "$base/stock/movements" `
    -ContentType "application/json" `
    -Body @{
        product_id = 1                  # ID deines Produkts
        change     = 50                 # +50 Stück
        reason     = "purchase"         # "purchase" | "sale" | "adjustment" | "waste" | "return"
        reference  = "Lieferschein #1234"
        created_by = "MarktPilot Setup"
    } | ConvertTo-Json
```

> Die `product_id` findest du in der UI unter „Warenbestand" → Produkt antippen
> → in der URL steht `/inventory/<id>`.

---

## Schritt 4 — Test-Verkauf auf einer Kasse

Bevor du das Ganze dem Mitarbeiter gibst:

1. Öffne auf einer Kasse (oder direkt am Laptop) die POS-Seite: `http://localhost:5173/pos` (oder Tab „Kasse" falls existent)
2. „Produkt suchen" → Coca-Cola antippen → 1× hinzugefügt
3. Noch 2 andere Produkte, Summe prüfen
4. „Bezahlen" → „Bargeld" → `5,00` eingeben → Bestätigen
5. → Bon erscheint auf dem Bildschirm (mit `print_requested=true` wird er in
   echt gedruckt, sobald Tauri-Drucker angebunden ist)
6. Im Kassenbuch prüfen: Tab **„Mehr" → „Bons"** oder `http://localhost:5173/receipts` → Bon sollte da sein

Wenn das klappt: **du hast eine funktionierende Kasse.** 🎉

---

## Schritt 5 — Backup nicht vergessen!

Bevor du weiterproduktiv gehst, schau in `LAPTOP-SETUP.md` Abschnitt „Phase 4 —
Backup einrichten". Sonst ist die ganze Arbeit bei einem Laptop-Crash weg.

---

## Schritt 6 — Auf den Kassen verifizieren

1. Kassen-PC starten → Browser öffnet sich automatisch (Kiosk-Mode)
2. Preisliste prüfen: sind die 15 Produkte sichtbar?
3. Test-Scan mit Kamera-Scanner (oder manuell Barcode eintippen)
4. Test-Verkauf
5. Auf dem Laptop: Kassenbuch prüfen — ist der Verkauf angekommen?

Falls etwas nicht ankommt: `http://<LAPTOP-IP>:8000/docs` öffnen, swagger-UI
zeigt alle Endpoints zum manuellen Debuggen.

---

## Quick-Reference

| Aufgabe | Pfad / URL |
|---|---|
| Preisliste | `http://localhost:5173/` (Tab Preisliste) |
| Warenbestand | `http://localhost:5173/inventory` |
| Kategorien | `http://localhost:5173/categories` |
| Kasse / POS | `http://localhost:5173/pos` |
| Kassenbuch | `http://localhost:5173/receipts` |
| Analytics | `http://localhost:5173/analytics` |
| API-Doku | `http://localhost:8000/docs` |
| Bulk-Import-Endpoint | `POST http://localhost:8000/api/products/bulk` |
| Wareneingang-Endpoint | `POST http://localhost:8000/api/stock/movements` |
| Beispiel-CSV | dieses Dokument, oben |
