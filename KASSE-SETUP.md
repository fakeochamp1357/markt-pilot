# MarktPilot — Kassen-PC einrichten

Stand: 2026-08-10
Ziel: Ein Kassen-PC zeigt im Browser auf den Laptop-Server, öffnet beim
Hochfahren automatisch die Kassen-Ansicht im Vollbild.

> **Voraussetzung:** Der Laptop-Server läuft und ist unter `http://<LAPTOP-IP>:8000`
> erreichbar. Siehe `LAPTOP-SETUP.md`.

---

## Architektur pro Kasse

```
Kassen-PC (Windows)
    │
    │  Chrome / Edge im Kiosk-Modus
    │  http://localhost:5173/  (Vite-Dev)
    │       ODER
    │  http://localhost:8080/  (Production-Build + nginx)
    │       ODER
    │  MarktPilot-PWA (installiert)
    │
    │  VITE_API_BASE → http://<LAPTOP-IP>:8000
    │
    └── kein lokales Backend, keine lokale DB
        (nur Browser-Cache + Outbox für Offline-Verkäufe)
```

**Drei Optionen** für die Kasse, vom einfachsten zum professionellsten:

| Option | Aufwand | Vorteil | Nachteil |
|---|---|---|---|
| **A) Vite-Dev** | 5 Min | Sofort testen, Hot-Reload | Dev-Mode ist langsam, Console-Fehler sichtbar |
| **B) Production-Build + nginx** | 30 Min | Schnell, stabil, wie Laptop-Setup | Mehr Konfig |
| **C) PWA installieren** | 5 Min | Echte App, kein Browser-UI, Offline-Icon im Startmenü | Braucht HTTPS für manche Features (bei LAN ok) |

Für **jetzt** nimm **A**, um zu testen, ob alles läuft. Danach **B** für echt.

---

## Option A — Vite-Dev (zum Testen)

### 1. Repo clonen

```powershell
cd C:\
New-Item -ItemType Directory -Path "C:\Repos" -Force   # oder D:\Repos
cd C:\Repos
git clone https://github.com/fakeochamp1357/markt-pilot.git
cd markt-pilot\frontend
npm install
```

### 2. Frontend auf den Laptop zeigen lassen

```powershell
# Wichtig: VITE_API_BASE MUSS vor dem Start gesetzt sein
$env:VITE_API_BASE = "http://192.168.2.30:8000"
cmd /c npm run dev -- --host 0.0.0.0 --port 5173
```

Browser: `http://localhost:5173/` → sollte die Produkte vom Laptop zeigen.

### 3. Auto-Start beim Hochfahren

Browser-Verknüpfung in den Autostart-Ordner legen:

```powershell
# Chrome-Beispiel (Edge analog mit msedge.exe)
$shell = New-Object -COM WScript.Shell
$shortcut = $shell.CreateShortcut("$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\MarktPilot Kasse.lnk")
$shortcut.TargetPath = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$shortcut.Arguments = "--kiosk http://localhost:5173/"
$shortcut.WorkingDirectory = "C:\"
$shortcut.Save()
```

→ Beim nächsten Login öffnet sich Chrome automatisch im Vollbild auf der Kasse.

> **Wichtig:** Vite-Dev muss vorher laufen! Am einfachsten: das `npm run dev`
> auch in den Autostart (siehe unten).

### Vite-Dev in den Autostart

```powershell
# Frontend-Auto-Start-Task
$action = New-ScheduledTaskAction `
    -Execute "cmd" `
    -Argument "/c set VITE_API_BASE=http://192.168.2.30:8000 && npm run dev -- --host 0.0.0.0 --port 5173" `
    -WorkingDirectory "C:\Repos\markt-pilot\frontend"

$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName "MarktPilot Kasse Frontend (Dev)" `
    -Action $action -Trigger $trigger -Settings $settings `
    -RunLevel Highest -User "$env:USERNAME"
```

---

## Option B — Production-Build + nginx (EMPFOHLEN für Echtbetrieb)

### 1. Repo clonen + bauen

```powershell
cd C:\Repos\markt-pilot\frontend

# API-URL für den Build fest einkompilieren
$env:VITE_API_BASE = "http://192.168.2.30:8000"
cmd /c npm run build
# → erzeugt dist/ Ordner
```

### 2. nginx installieren

```powershell
# nginx für Windows herunterladen: https://nginx.org/en/download.html
# ZIP entpacken nach C:\nginx
```

`C:\nginx\conf\nginx.conf` editieren, **innerhalb des `http { ... }`-Blocks**:

```nginx
server {
    listen 8080;
    server_name _;

    root C:/Repos/markt-pilot/frontend/dist;
    index index.html;

    # SPA: alle unbekannten Routen → index.html
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API-Proxy: Frontend ruft /api/... auf, nginx leitet weiter
    location /api/ {
        proxy_pass http://192.168.2.30:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Backend-Health via nginx
    location /healthz {
        proxy_pass http://192.168.2.30:8000/healthz;
    }
}
```

> **Trick:** Wenn der nginx-Proxy `/api/` an den Laptop weiterleitet, **muss im
> Frontend** `VITE_API_BASE` leer oder auf den nginx-Host zeigen, damit die
> relativen `/api/...`-Pfade passen. Setz beim Bauen:
>
> ```powershell
> $env:VITE_API_BASE = ""   # leer → Frontend ruft relative Pfade
> cmd /c npm run build
> ```

### 3. nginx starten

```powershell
cd C:\nginx
Start-Process nginx.exe
# Browser: http://localhost:8080/ → Kasse läuft
```

In den Autostart (Verknüpfung in `shell:startup`):

```powershell
$shell = New-Object -COM WScript.Shell
$shortcut = $shell.CreateShortcut("$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\MarktPilot Kasse.lnk")
$shortcut.TargetPath = "C:\nginx\nginx.exe"
$shortcut.WorkingDirectory = "C:\nginx"
$shortcut.Save()
```

### 4. Browser-Kiosk-Verknüpfung

```powershell
$shell = New-Object -COM WScript.Shell
$shortcut = $shell.CreateShortcut("$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\MarktPilot Kiosk.lnk")
$shortcut.TargetPath = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$shortcut.Arguments = "--kiosk --noerrdialogs --disable-infobars --disable-pinch --overscroll-history-navigation=0 http://localhost:8080/"
$shortcut.Save()
```

**Was die Flags tun:**
- `--kiosk` → Vollbild ohne Browser-UI
- `--noerrdialogs` → keine nervigen „Diese Seite ist nicht sicher"-Dialoge
- `--disable-infobars` → keine Info-Leisten
- `--disable-pinch` → Touchscreen-Zoom aus
- `--overscroll-history-navigation=0` → kein „Wische nach links für History"

### 5. Kasse verlassen / entsperren

Im echten Kiosk-Modus kommt man mit Strg+Alt+Entf oder Alt+F4 raus. Für den
Alltag reicht das. Für Updates: per RDP/RDP-in auf den Kassen-PC, Alt+F4,
`git pull`, `npm run build`, nginx reloaden.

---

## Option C — Als PWA installieren (schneller Mittelweg)

Wenn ihr nur den Browser nehmt und „MarktPilot installieren" klickt:

1. Im Browser auf `http://localhost:5173/` (Dev) oder `http://localhost:8080/` (nginx)
2. Rechts oben in der URL-Bar → **„App installieren"**-Icon (Chrome/Edge)
3. Bestätigen → MarktPilot liegt jetzt im Startmenü wie eine native App
4. Verknüpfung in den Autostart legen (siehe oben, aber mit dem PWA-Pfad)

Vorteil: einfacher Offline-Indikator, fühlt sich mehr nach App an.
Nachteil: muss einmal pro Kasse installiert werden, läuft trotzdem im Browser.

---

## Offline-Verhalten an der Kasse

Wichtig zu verstehen, was passiert, wenn das LAN weg ist:

| Was passiert? | Verhalten |
|---|---|
| Laptop-Server weg, Kasse online | Kasse zeigt gecachte Produkte, Outbox sammelt Mutationen |
| Kasse verkauft während Laptop weg | Verkauf wird lokal in Dexie gespeichert, Outbox pusht wenn Laptop wieder da |
| Kasse bekommt LAN zurück | Innerhalb 3s wird Outbox abgearbeitet (`useOutboxSync` tick alle 3s) |
| Mehrere Offline-Verkäufe | Jeder hat eigene UUID → kein Doppel-Buch auf Backend |
| Laptop kommt mit **anderer** DB zurück | Outbox-Einträge mit nicht existierender `product_id` → 4xx-Fehler → dauerhaft „failed" |

**Heißt:** Solange dein Laptop-Server nur **up- oder down-** ist (nicht überschrieben
wird), funktioniert alles automatisch. Wenn du aber den Laptop neu aufsetzt und
eine leere DB startest, dann haben die Offline-Verkäufe der Kassen plötzlich
kein `product_id` mehr → 4xx → landen in „failed" und müssen manuell gelöst
werden.

**Faustregel:** Wenn der Laptop crasht, vorher das letzte DB-Backup
einspielen. Nicht die Kassen weiterlaufen lassen ohne intaktes Backend.

---

## Quick-Reference

| Aufgabe | Pfad / Befehl |
|---|---|
| Frontend-Dev starten | `cd frontend && $env:VITE_API_BASE="http://192.168.2.30:8000" && npm run dev` |
| Frontend bauen | `cd frontend && $env:VITE_API_BASE="" && npm run build` |
| nginx config | `C:\nginx\conf\nginx.conf` |
| Kiosk-Verknüpfung | `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\MarktPilot Kiosk.lnk` |
| Backend-Health prüfen | Browser → `http://192.168.2.30:8000/healthz` |
| API-Doku | Browser → `http://192.168.2.30:8000/docs` |
| Kasse verlassen | `Alt+F4` (im Kiosk-Modus) |
