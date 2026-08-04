# MarktPilot auf dem Raspberry Pi 4

Stand: 2026-08-04 — Pi 4 mit **Fedora Workstation (ARM)**, getesteter Plan.
Ziel: zentraler Sync-Server **und** Kassen-Terminal in einem Gerät.

> **Wichtig:** Dieses Repo hat aktuell **keinen automatischen Daten-Sync** zwischen
> Clients. Der Pi als zentrales Backend heißt: alle Geräte sehen die gleichen
> Daten, **wenn** sie sich zum Pi verbinden. Phase 2 mit Konfliktauflösung
> steht noch aus (siehe Roadmap im README).

---

## Einkaufsliste

| Was | Wo | Preis (ca.) |
|---|---|---|
| Raspberry Pi 4 (4 oder 8 GB) | Reichelt, BerryBase, Amazon | 45–60 € |
| MicroSD mind. 32 GB, Class 10, A2 | überall | 8–12 € |
| USB-C Netzteil 5V/3A offiziell | Raspberry-Pi-Shop | 10 € |
| Gehäuse + Kühlkörper (Pi 4 wird warm) | Amazon, Reichelt | 8–15 € |
| Optional: 7"-Touchscreen (offiziell/SunFounder) | Reichelt, Amazon | 65–80 € |
| Optional: ESC/POS-Bondrucker USB (z.B. Epson TM-T20) | Amazon | 70–90 € |

HDMI-Kabel, Tastatur, Maus hast du vermutlich.

---

## Phase 1 — Pi startklar machen (einmalig, ~45 Min)

### 1.1 Fedora Workstation flashen

Am PC (Windows/macOS/Linux):

1. **Raspberry Pi Imager** installieren: <https://www.raspberrypi.com/software/>
2. SD-Karte rein (Pi aus!)
3. Imager öffnen:
   - **OS wählen:** "Other general-purpose OS" → **Fedora** → **Fedora Workstation ARM (aarch64) for Pi 4**
   - **Storage:** deine SD-Karte
4. ⚙️ **Erweiterte Optionen** (Zahnrad-Symbol):
   - Hostname: `marktpilot`
   - Username + Passwort setzen (z.B. `pi` / sicheres Passwort)
   - WLAN-SSID + Passwort eintragen (oder LAN benutzen)
   - SSH aktivieren: **"Enable SSH"** + "Use password authentication"
5. **Schreiben** klicken — dauert 5–15 Min

### 1.2 Erster Boot

1. SD-Karte in den Pi, Strom ran, Monitor+Tastatur optional
2. Fedora bootet durch, Desktop kommt nach 1–2 Min
3. Einloggen (User aus Imager)
4. Terminal öffnen (oder via SSH — siehe unten)

### 1.3 SSH-Zugriff (empfohlen, headless-Arbeit)

**Am Pi (einmalig):**
```bash
sudo systemctl enable --now sshd
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --reload
ip -4 addr show | grep inet   # IP-Adresse merken, z.B. 192.168.2.50
```

**Vom PC/Laptop:**
```bash
ssh pi@192.168.2.50
# Passwort wie im Imager gesetzt
```

### 1.4 Feste IP im Router (empfohlen)

Im Router-Admin (z.B. Fritzbox → Heimnetz → Gerät `marktpilot`):
- Diesem Gerät **immer dieselbe IP** zuweisen (z.B. `192.168.2.50`)
- Sonst ändert sich die IP nach jedem Router-Neustart und deine Geräte finden den Pi nicht mehr

### 1.5 System aktualisieren

```bash
sudo dnf update -y
sudo reboot
```

---

## Phase 2 — MarktPilot installieren (einmalig, ~20 Min)

### 2.1 Repo clonen

```bash
sudo dnf install -y git
mkdir -p ~/markt-pilot
cd ~/markt-pilot
git clone https://github.com/fakeochamp1357/markt-pilot.git .
```

### 2.2 Setup-Script laufen lassen

```bash
cd ~/markt-pilot
chmod +x scripts/setup-pi.sh
./scripts/setup-pi.sh
```

Das Script macht automatisch:

- Python 3.11 + venv + alle Backend-Deps (`pip install -r requirements.txt`)
- Node.js 20 (falls nicht da) + npm
- Alembic-Migrationen + Seed (20 Beispiel-Produkte)
- Build des Frontends (statisches Bundle)
- nginx installieren + als Reverse-Proxy konfigurieren
- `marktpilot-backend.service` installieren + aktivieren (auto-start)
- Firewall für Port 80 + 8000 öffnen

**Dauer:** 10–20 Min (je nach Internet).

### 2.3 Test

```bash
# Am Pi
sudo systemctl status marktpilot-backend
curl http://127.0.0.1:8000/healthz
# {"status":"ok"}

# Vom PC im Browser:
# http://192.168.2.50/         → MarktPilot UI
# http://192.168.2.50/docs     → API-Doku
```

---

## Phase 3 — Geräte umstellen (~5 Min pro Gerät)

### 3.1 PC (Windows)

Bisher lief dein Backend lokal. Jetzt zeigt der Browser auf den Pi:

1. **Backend auf PC stoppen** (falls du es gestartet hattest):
   ```powershell
   Get-NetTCPConnection -LocalPort 8000 | Select OwningProcess
   Stop-Process -Id <PID> -Force
   ```
2. **Frontend starten** mit neuer API-URL:
   ```powershell
   cd C:\Repos\markt-pilot\frontend
   # Vite-Proxy auf den Pi umstellen:
   $env:VITE_API_BASE="http://192.168.2.50:8000"
   cmd /c npm run dev -- --host 0.0.0.0 --port 5173
   ```
3. Browser: <http://localhost:5173/> → sollte Pi-Daten zeigen

### 3.2 Laptop

Genauso wie PC — Schritte 1–3 mit `C:\company\markt-pilot` statt `C:\Repos\markt-pilot`.

### 3.3 Smartphone

Einfach im Browser:
```
http://192.168.2.50/
```

(Direkt aufs Frontend auf dem Pi, kein Vite-Dev-Server nötig weil das Frontend auf dem Pi als statisches Bundle via nginx läuft.)

---

## Phase 4 — Updates & Wartung

### MarktPilot updaten

```bash
ssh pi@192.168.2.50
cd ~/markt-pilot
git pull
# Backend:
cd backend && source .venv/bin/activate && python -m alembic upgrade head
sudo systemctl restart marktpilot-backend
# Frontend neu bauen (falls sich Frontend geändert hat):
cd ../frontend && npm install && npm run build && sudo cp -r dist/* /var/www/marktpilot/
```

### Service-Status prüfen

```bash
sudo systemctl status marktpilot-backend
sudo journalctl -u marktpilot-backend -f   # Live-Logs
```

### Backup der Datenbank

```bash
ssh pi@192.168.2.50 "cp ~/markt-pilot/backend/markt_pilot.db ~/markt-pilot-$(date +%F).db"
# Datei dann per scp auf den PC ziehen:
scp pi@192.168.2.50:~/markt-pilot-*.db .
```

---

## Was bei der aktuellen Architektur **nicht** funktioniert

- **Gleichzeitiges Editieren** auf mehreren Geräten: kein Konflikt-Handling, "last write wins"
- **Offline-Edits + automatischer Sync**: Outbox-Queue speichert lokal, aber Sync geht nur wenn das **eigene** Backend erreichbar ist
- **Multi-User-Login**: aktuell keine Auth, alle Clients sehen alles

Diese Punkte sind Phase 2 in eurer Roadmap und noch nicht gebaut.

---

## Troubleshooting

### Service startet nicht

```bash
sudo journalctl -u marktpilot-backend -n 50
```

Häufigste Fehler:
- `port 8000 already in use` → `sudo lsof -i :8000` zeigt wer, dann killen
- `database is locked` → anderer Prozess hält die DB

### Frontend lädt Daten nicht

Im Browser DevTools → Network-Tab schauen:
- `/api/products` antwortet? Wenn nicht → Backend-URL im Frontend falsch
- CORS-Fehler? → Backend erlaubt standardmäßig alle Origins in Dev, im Prod nginx-Proxy nutzen

### nginx zeigt 502

```bash
sudo systemctl status nginx
sudo journalctl -u nginx -n 30
# FastAPI muss laufen:
sudo systemctl status marktpilot-backend
```

---

## Quick-Reference

| Aufgabe | Befehl (am Pi per SSH) |
|---|---|
| Backend-Status | `sudo systemctl status marktpilot-backend` |
| Backend-Logs | `sudo journalctl -u marktpilot-backend -f` |
| Backend neu starten | `sudo systemctl restart marktpilot-backend` |
| nginx-Status | `sudo systemctl status nginx` |
| Update ziehen | `cd ~/markt-pilot && git pull` |
| Pi neu starten | `sudo reboot` |
| Datenbank-Backup | `cp ~/markt-pilot/backend/markt_pilot.db ~/backup-$(date +%F).db` |
