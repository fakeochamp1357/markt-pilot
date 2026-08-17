# MarktPilot — Laptop als Server (Hauptplan)

Stand: 2026-08-17
Status: **HAUPTPLAN** — der Laptop ist der zentrale Backend-Server.
Datenbank + FastAPI laufen hier, alle Kassen-Clients (Pi #2, weitere PCs,
Tablets) zeigen mit ihrem Frontend auf diesen Laptop.

**Architektur:**
- **Laptop (diese Anleitung):** Server, läuft wenn gearbeitet wird
- **Kassen-Pi ([KASSE-PI-SETUP.md](KASSE-PI-SETUP.md)):** Touchscreen-Kasse mit USB-Hardware
- **PC/Verwaltung:** Browser auf `http://localhost:5173/` zum Warenbestand pflegen

**Schnellstart:**

1. Diese Datei komplett durchgehen (Architektur und Phasen)
2. Phase 1 + 3 + 4 (Backup!) reichen für „ich will heute noch produktiv arbeiten"
3. Phase 5 für spätere Updates

> **Hinweis:** Früher war eine dedizierte Server-Pi geplant (siehe
> [`PI-SETUP.md`](PI-SETUP.md)). Da der Laptop die nötige Leistung hat und
> sowieso immer läuft, ist er jetzt der primäre Server. Die Pi-Variante
> bleibt als Option dokumentiert, falls du später auf headless umsteigen
> willst.

> **Wichtig:** Die DB lebt nur hier. Wenn dieser Laptop abraucht **ohne Backup**, sind alle Bons, Produkte und Bestände weg. → Backup ist Pflicht, nicht Kür. Siehe unten.

---

## Architektur

```
┌─────────────────────────────────────────────────────────┐
│  Laptop (Windows) — dieser Setup                        │
│  ┌─────────────────────────────────────────────────┐    │
│  │  FastAPI-Backend auf 0.0.0.0:8000               │    │
│  │  SQLite  C:\company\markt-pilot\backend\        │    │
│  │          markt_pilot.db   ← EINE zentrale DB     │    │
│  └─────────────────────────────────────────────────┘    │
│  Feste IP im LAN (z.B. 192.168.2.30)                    │
└────────────┬──────────────────────┬─────────────────────┘
             │ LAN                  │ LAN
             ▼                      ▼
    ┌─────────────────┐    ┌─────────────────┐
    │ Kasse 1 (PC)    │    │ Kasse 2 (PC)    │
    │ Browser         │    │ Browser         │
    │ VITE_API_BASE   │    │ VITE_API_BASE   │
    │ → 192.168.2.30  │    │ → 192.168.2.30  │
    └─────────────────┘    └─────────────────┘
```

Du selbst arbeitest auch vom Laptop im Browser auf `http://localhost:5173/`
und kannst von überall im LAN auf `http://192.168.2.30:5173/` zugreifen.

---

## Phase 1 — Laptop startklar machen (einmalig, ~20 Min)

### 1.1 Voraussetzungen

- Windows 10 oder 11
- Python 3.11+ (https://www.python.org/downloads/)
- Node.js 20+ (https://nodejs.org/)
- Git (https://git-scm.com/)
- Im Router: Zugriff aufs Admin-Panel (für feste IP)
- Schreibzugriff auf `C:\company\` (oder wohin du das Repo legst)

### 1.2 Repo clonen / vorhandenes prüfen

```powershell
# Wenn noch nicht vorhanden:
cd C:\
New-Item -ItemType Directory -Path "C:\company" -Force
cd C:\company
git clone https://github.com/fakeochamp1357/markt-pilot.git .

# Wenn schon vorhanden:
cd C:\company\markt-pilot
git pull
```

> **Falls du das Repo woanders hin willst** (z.B. `D:\markt-pilot`): einfach den Pfad
> in allen folgenden Befehlen anpassen. Wichtig: **außerhalb von OneDrive** liegen
> (siehe SYNC.md, „OneDrive-Falle").

### 1.3 Backend-Dependencies installieren

```powershell
cd C:\company\markt-pilot\backend
python -m pip install -r requirements.txt
python -m alembic upgrade head
python seed.py          # 5 Kategorien + 20 Beispiel-Produkte (optional)
```

### 1.4 Backend testen (lokal)

```powershell
# In dieser Konsole — lassen wir offen für den Test
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

→ Du solltest sehen: `Uvicorn running on http://127.0.0.1:8000`

In **einer zweiten Konsole**:

```powershell
curl http://127.0.0.1:8000/healthz
# → {"status":"ok"}

curl http://127.0.0.1:8000/api/products | Select-Object -First 200
# → JSON-Liste der Seed-Produkte
```

Wenn das klappt, **Strg+C** in der ersten Konsole und weiter mit 1.5.

### 1.5 Backend ans LAN hängen

```powershell
# Mit 0.0.0.0 hört das Backend auf allen Netzwerk-Interfaces
cd C:\company\markt-pilot\backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

→ Du solltest sehen: `Uvicorn running on http://0.0.0.0:8000`

### 1.6 Windows-Firewall: Port 8000 öffnen

```powershell
# Nur nötig, wenn die Kassen den Laptop nicht erreichen
New-NetFirewallRule -DisplayName "MarktPilot Backend (8000)" `
    -Direction Inbound -Protocol TCP -LocalPort 8000 `
    -Action Allow -Profile Private,Domain
```

> **Wichtig:** Nur in privaten/Domänen-Netzwerken öffnen, **nicht** in „Public"!
> Zu Hause / im Laden-LAN: Profil sollte auf „Privat" stehen.

### 1.7 IP-Adresse des Laptops herausfinden

```powershell
ipconfig | Select-String -Pattern "IPv4"
# Beispielausgabe:
#   IPv4-Adresse  . . . . . . . . . : 192.168.2.30
```

Diese IP merken — die brauchen gleich die Kassen.

---

## Phase 2 — Feste IP im Router (einmalig)

Damit die IP nach Router-Reset nicht wechselt:

1. Im Router einloggen (Fritzbox z.B. `http://192.168.2.1`)
2. **Heimnetz → Geräte** (oder DHCP-Server)
3. Laptop in der Liste suchen → **„Diesem Gerät immer dieselbe IP zuweisen"**
4. IP bestätigen: `192.168.2.30` (oder was du in 1.7 gesehen hast)

> **Alternativ** (wenn der Router das nicht kann): Auf dem Laptop selbst eine
> statische IP setzen — Anleitung pro Router-Modell unterschiedlich, hier nicht
> abgedeckt. Sag Bescheid, wenn du das brauchst.

---

## Phase 3 — Autostart einrichten (damit du nicht jedes Mal starten musst)

Es gibt **drei Wege**, vom einfachsten bis zum „production-grade":

### 3.1 Windows-Aufgabenplanung (schnell, gut genug) ⭐ EMPFOHLEN

```powershell
# Aufgabe anlegen: Backend startet bei Login automatisch
$action = New-ScheduledTaskAction `
    -Execute "python" `
    -Argument "-m uvicorn app.main:app --host 0.0.0.0 --port 8000" `
    -WorkingDirectory "C:\company\markt-pilot\backend"

$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask -TaskName "MarktPilot Backend" `
    -Action $action -Trigger $trigger -Settings $settings `
    -RunLevel Highest `
    -User "$env:USERNAME" `
    -Description "MarktPilot FastAPI Server (laptop)"
```

**Was passiert:** Sobald du dich am Laptop einloggst, startet das Backend im
Hintergrund. Kein Konsolenfenster, kein Hand-Auflegen.

**Testen:** Aufgabenplanung öffnen (`taskschd.msc`) → Aufgabe „MarktPilot Backend"
→ Rechtsklick → „Ausführen". Im Browser `http://localhost:8000/healthz` → `ok`.

**Logs finden, wenn was klemmt:** Aufgabenplanung → Task auswählen →
„Verlauf" Tab.

### 3.2 NSSM als Windows-Dienst (production-grade, läuft auch ohne Login)

Für den Fall, dass der Laptop durchläuft, ohne dass sich jemand einloggt
(Display aus, niemand angemeldet, aber Strom da).

```powershell
# NSSM runterladen: https://nssm.cc/download
# nssm.exe nach C:\Windows\System32\ kopieren

nssm install MarktPilotBackend `
    "C:\Python311\python.exe" `   # Pfad anpassen!
    "-m uvicorn app.main:app --host 0.0.0.0 --port 8000"

# Working directory setzen
nssm set MarktPilotBackend AppDirectory "C:\company\markt-pilot\backend"

# Dienst starten + auf Auto-Start
nssm start MarktPilotBackend
nssm set MarktPilotBackend Start SERVICE_AUTO_START
```

**Status prüfen:** `services.msc` → „MarktPilot Backend" → sollte „Wird ausgeführt" sein.

### 3.3 Manueller Start (nur zum Testen, nicht für den Alltag)

Nicht für den Produktivbetrieb, aber wenn du schnell was ausprobieren willst:

```powershell
cd C:\company\markt-pilot\backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
# Konsole offen lassen
```

---

## Phase 4 — Backup einrichten (PFLICHT, nicht KÜR)

Die SQLite-Datei ist alles. Wenn der Laptop abraucht, ist ohne Backup alles weg.

### 4.1 Tägliches Datei-Backup (einfachste Variante)

```powershell
# Backup-Ordner anlegen
New-Item -ItemType Directory -Path "D:\markt-pilot-backups" -Force

# Tages-Backup via Aufgabenplanung (täglich 23:00)
$action = New-ScheduledTaskAction -Execute "powershell" `
    -Argument "-NoProfile -Command `"Copy-Item 'C:\company\markt-pilot\backend\markt_pilot.db' 'D:\markt-pilot-backups\markt_pilot_$(Get-Date -Format 'yyyy-MM-dd').db'`""
$trigger = New-ScheduledTaskTrigger -Daily -At "23:00"
Register-ScheduledTask -TaskName "MarktPilot DB Backup" `
    -Action $action -Trigger $trigger `
    -Description "Tägliches SQLite-Backup"
```

**Aufbewahrung:** Behalte die letzten 30 Tage, ältere löschen.

```powershell
# Einmalig: 30-Tage-Cleanup-Job anlegen
$action = New-ScheduledTaskAction -Execute "powershell" `
    -Argument "-NoProfile -Command `"Get-ChildItem 'D:\markt-pilot-backups\*.db' | Where-Object LastWriteTime -lt (Get-Date).AddDays(-30) | Remove-Item`""
$trigger = New-ScheduledTaskTrigger -Daily -At "23:30"
Register-ScheduledTask -TaskName "MarktPilot Backup Cleanup" `
    -Action $action -Trigger $trigger
```

### 4.2 Externe Synchronisation (sehr empfohlen)

Schieb die Backups zusätzlich auf einen USB-Stick, eine externe Platte oder
einen Cloud-Speicher (OneDrive ist OK für Backups, **nicht** für das Live-Repo).

---

## Phase 5 — Updates einspielen

```powershell
cd C:\company\markt-pilot
git pull
cd backend
python -m alembic upgrade head

# Backend neu starten (Aufgabenplanung / NSSM)
# Task: Rechtsklick → Beenden → Ausführen
# ODER: services.msc → MarktPilot Backend → Neu starten
```

Frontend: hat sich nichts geändert? Kassen holen sich die neue Version automatisch
beim nächsten Browser-Refresh.

---

## Was funktioniert, was nicht

✅ **Funktioniert jetzt:**
- Produkte auf Laptop anlegen → auf Kassen sichtbar (max 3s Verzögerung)
- Verkäufe auf Kasse → landen in DB (auch wenn Kasse kurz offline war)
- Bon-Duplikate sind ausgeschlossen (Idempotenz via `X-Client-Op-Id`)
- Storno auf Kasse → Bestand zurück
- Tagesabschluss / Kassenbuch auf Laptop einsehen

❌ **Funktioniert NICHT** (Phase 2 lt. Roadmap):
- Echtzeit-Push: wenn du auf dem Laptop ein Produkt umbenennst, sehen die
  Kassen es nicht sofort, sondern erst nach max 3 Sekunden (Cache-Refresh)
- Konfliktauflösung zwischen zwei Offline-Kassen, die das gleiche Produkt
  gleichzeitig bearbeiten → "last write wins" (einer gewinnt)
- Login / Mitarbeiter-Zuordnung: aktuell gibt es keine Auth

Für deinen aktuellen Use-Case (1–2 Kassen, wenige Mitarbeiter, ein Laptop als
Server) ist das **absolut ausreichend**. Multi-Device-Sync-Logik können wir
später bauen, wenn der Laden wächst.

---

## Troubleshooting

### Kasse erreicht den Laptop nicht

```powershell
# 1. Laptop: läuft das Backend?
curl http://127.0.0.1:8000/healthz
# → muss {"status":"ok"} liefern

# 2. Welche IP hat der Laptop?
ipconfig | Select-String "IPv4"

# 3. Kasse: kann sie den Laptop pingen?
# (auf der Kasse)
Test-NetConnection -ComputerName 192.168.2.30 -Port 8000
# → TcpTestSucceeded: True  ✓
# → TcpTestSucceeded: False ✗ → Firewall / IP falsch
```

### „Address already in use" auf Port 8000

```powershell
# Wer blockiert?
Get-NetTCPConnection -LocalPort 8000 | Select-Object OwningProcess, State
# Dann den Prozess beenden:
Stop-Process -Id <PID> -Force
```

### Backup-Job läuft nicht

Aufgabenplanung → „MarktPilot DB Backup" → Verlauf-Tab. Häufigste Ursachen:
- Pfad zum Backup-Ordner existiert nicht
- `Copy-Item` ohne `-Force`, und Datei ist gesperrt (sollte aber bei SQLite
  nicht passieren, weil das Backend nur liest/schreibt während es läuft)

### Frontend auf Kasse zeigt „Backend nicht erreichbar"

- `VITE_API_BASE` richtig gesetzt? (siehe KASSE-SETUP.md)
- Firewall auf Laptop blockt Port 8000?
- IP-Adresse vom Laptop hat sich geändert (kein DHCP-Fix im Router)?

---

## Quick-Reference

| Aufgabe | Befehl / Pfad |
|---|---|
| Backend manuell starten | `cd C:\company\markt-pilot\backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000` |
| Backend-Status (Task) | `taskschd.msc` → „MarktPilot Backend" |
| Backend-Status (NSSM) | `services.msc` → „MarktPilot Backend" |
| Backend-Health | `curl http://localhost:8000/healthz` |
| API-Doku | `http://localhost:8000/docs` |
| DB-Pfad | `C:\company\markt-pilot\backend\markt_pilot.db` |
| Backup-Ordner | `D:\markt-pilot-backups\` |
| Backend neu starten | Task beenden + starten, oder `nssm restart MarktPilotBackend` |
| Update einspielen | `git pull` + `alembic upgrade head` + Backend-Restart |
