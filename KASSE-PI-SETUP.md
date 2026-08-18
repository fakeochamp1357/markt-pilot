# MarktPilot — Kassen-Pi einrichten (Pi #2)

Stand: 2026-08-18
Ziel: Eine Raspberry Pi 5 mit Touchscreen-Monitor und USB-Hardware (Drucker,
Scanner, Schublade) als autarkes Kassen-Terminal.

> **Voraussetzung:** Der Laptop-Server läuft und ist unter `http://192.168.2.76:8000`
> (oder der aktuellen Laptop-IP im LAN) erreichbar. Siehe [`LAPTOP-SETUP.md`](LAPTOP-SETUP.md).
>
> **Wichtig (Stand 2026-08-18):** Wir haben das Frontend auf **relative URLs**
> (`VITE_API_BASE = "/api"`) umgestellt. nginx auf der Pi proxt jetzt
> `/api/*` an den Laptop. Bei einem IP-Wechsel des Laptops muss nur **eine
> Zeile** in der nginx-Config angepasst werden — kein Re-Build.

---

## Was du brauchst (Einkaufsliste Kasse)

| Was | Hinweis | ca. Preis |
|---|---|---|
| Raspberry Pi 5 (4 oder 8 GB) | 4 GB reicht, 8 GB ist zukunftssicher | 60–80 € |
| microSD-Karte 32 GB, Class 10, A2 | SanDisk / Samsung | 8–12 € |
| USB-C-Netzteil 5V/5A | offizielles Pi-5-Netzteil (27 W) | 12–15 € |
| Aktiver Kühler für Pi 5 | offiziell oder Argon / Pimoroni | 8–15 € |
| Gehäuse mit Lüfter | optional, je nach Setup | 10–20 € |
| 7"- oder 10"-Touchscreen-Monitor | HDMI + USB-Touch, kapazitiv bevorzugt | 80–150 € |
| Micro-HDMI-Kabel | Pi 5 hat **micro-HDMI**, nicht mini oder full | 6–10 € |
| USB-Hub mit eigener Stromversorgung | falls Drucker+Scanner+Schublade mehr Strom brauchen als die Pi liefert | 15–25 € |
| **Vorhanden:** Epson TM-m30III USB, Scanner, Schublade | hast du schon | — |

**Optional für später (Tauri-Build):** Gehäuse + Kühlkörper reichen; für
Tauri-Apps brauchst du kein Touch-OS, kannst aber den Browser-Fallback
behalten.

---

## Phase 1 — Pi vorbereiten (einmalig, ~20 Min)

### 1.1 Raspberry Pi OS flashen

Am PC (Windows / macOS / Linux):

1. **Raspberry Pi Imager** installieren: <https://www.raspberrypi.com/software/>
2. SD-Karte rein (Pi aus!)
3. Imager öffnen:
   - **Gerät:** Raspberry Pi 5
   - **OS:** „Raspberry Pi OS (64-bit)" → die **Bookworm Desktop**-Variante
     (für Kiosk mit Chromium brauchst du den Desktop, nicht Lite)
   - **Storage:** deine SD-Karte
4. ⚙️ **Erweiterte Optionen** (Zahnrad-Symbol):
   - Hostname: `marktpilot-kasse` (oder behalte deinen Pi-Default)
   - Username + Passwort setzen (z.B. `globia1` / sicheres Passwort)
   - **WLAN-SSID + Passwort** eintragen ODER LAN benutzen
   - **SSH aktivieren:** „Enable SSH" + „Use password authentication"
5. **Schreiben** klicken — dauert 5–10 Min

### 1.2 Erster Boot

1. SD-Karte in die Pi, Strom ran, Touchscreen per HDMI + USB-Touch anstecken
2. Pi bootet durch, Desktop erscheint nach ~30 Sek
3. Einloggen, Terminal öffnen

### 1.3 SSH testen (vom PC aus)

Vom PC/Laptop im LAN:

```bash
ssh globia1@marktpilot-kasse.local
# oder, falls mDNS nicht klappt:
ssh globia1@<IP-der-Pi>   # findest du im Router oder mit `hostname -I` an der Pi
```

Ab jetzt kannst du alle weiteren Schritte **per SSH** machen — kein Monitor
nötig (außer du willst den Touchscreen für den Endspurt).

### 1.4 System aktualisieren

```bash
sudo apt update && sudo apt full-upgrade -y
sudo reboot
```

### 1.5 Feste IP im Router

Genau wie beim Laptop-Server (192.168.2.76): in der Router-Admin-Oberfläche der Kassen-Pi eine
**feste LAN-IP** geben (z.B. `192.168.2.51`). Sonst findet der Laptop-Server (192.168.2.76) die
Kasse später nicht zuverlässig.

---

## Phase 2 — Frontend bauen und deployen (~15 Min)

Das Frontend läuft im Browser der Kassen-Pi. Wir bauen es **am PC** und
kopieren nur das fertige Bundle auf die Pi — schneller als alles auf der
kleinen Pi zu kompilieren.

### 2.1 Am PC: Frontend production-builden (mit relativen URLs)

Wir bauen das Frontend so, dass es **nicht** die Laptop-IP kennt. Stattdessen
gehen alle API-Calls über den nginx-Proxy auf der Kassen-Pi. Vorteil: wenn
du den Laptop in einen anderen Markt umziehst und eine neue IP bekommst,
musst du nur **eine** Zeile in der nginx-Config auf der Pi ändern — kein
Re-Build, kein Re-Deploy.

```powershell
cd C:\Repos\markt-pilot\frontend

# "/" als Base: Frontend ruft /api/products, nginx schickt's ans Backend
$env:VITE_API_BASE = "/api"
cmd /c npm run build
# → erzeugt dist/ Ordner
```

### 2.2 Bundle auf die Kassen-Pi schieben

```powershell
# Vom PC aus
scp -r C:\Repos\markt-pilot\frontend\dist\* globia1@192.168.2.51:~/markt-pilot-frontend/
```

Falls `scp` auf Windows nicht klappt (PowerShell hat es erst ab Windows 10
1809+ stabil), nutze `rsync` falls vorhanden, oder WinSCP / FileZilla.

### 2.3 Auf der Pi: nginx installieren (serviert das Frontend)

```bash
sudo apt install -y nginx
```

Konfiguration `sudo nano /etc/nginx/sites-available/marktpilot`:

```nginx
server {
    listen 8080;
    server_name _;

    root /home/globia1/marktpilot-frontend;

    # KEIN "index index.html;" — würde zusammen mit try_files eine
    # Endlosschleife auslösen (rewrite cycle).

    location / {
        try_files $uri $uri/ /index.html;
    }

    # Pflicht: API-Proxy. Frontend ruft /api/... (relativ) und nginx
    # schickt's an den Laptop. Laptop-IP bei IP-Wechsel hier anpassen.
    location /api/ {
        proxy_pass http://192.168.2.76:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

> **Wenn die Laptop-IP sich ändert** (neuer Standort, neuer Router): nur
> diese eine Zeile ändern und nginx reloaden:
>
> ```bash
> sudo sed -i 's#192.168.2.76#NEUE_LAPTOP_IP#g' /etc/nginx/sites-available/marktpilot
> sudo nginx -t && sudo systemctl reload nginx
> ```

Aktivieren:

```bash
sudo ln -s /etc/nginx/sites-available/marktpilot /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

Test im Browser: `http://192.168.2.51:8080/` → deine MarktPilot-UI mit
Daten vom Laptop-Server (192.168.2.76).

---

## Phase 3 — Kiosk-Mode (Browser im Vollbild, Auto-Start + Auto-Restart) (~15 Min)

Wir benutzen **systemd** statt GNOME-Autostart, weil systemd den Browser
aktiv überwacht: wenn Chromium crasht oder jemand es per SSH killt, startet
es innerhalb von 5 Sekunden automatisch neu. Für eine Kasse, die einfach
durchlaufen soll, essentiell.

### 3.1 systemd-Service-Datei installieren

Die Service-Datei liegt im Repo unter `scripts/marktpilot-kiosk.service`.
Sie enthält die richtigen Pfade + Flags für Chromium im Kiosk-Mode.

```bash
# Service-Datei aufs Pi holen (vom Laptop aus, oder per git pull auf der Pi)
scp scripts/marktpilot-kiosk.service globia1@192.168.2.51:/tmp/

# Auf der Pi:
sudo mv /tmp/marktpilot-kiosk.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now marktpilot-kiosk.service
```

Alten GNOME-Autostart löschen, falls noch vorhanden (sonst startet Chromium doppelt):

```bash
rm -f ~/.config/autostart/marktpilot-kiosk.desktop
```

### 3.2 Status checken

```bash
systemctl status marktpilot-kiosk.service
# Sollte "active (running)" zeigen
```

Falls der Service nicht startet, ins Log schauen:

```bash
sudo journalctl -u marktpilot-kiosk.service -f
```

### 3.3 TTY-Notfall-Workflow

Wenn das Kassen-Display hängt, der Browser aber nicht reagiert:

| Shortcut | Wirkung |
|---|---|
| `Ctrl+Alt+F7` | zurück zur graphischen Oberfläche (wo Chromium läuft) |
| `Ctrl+Alt+F1` | Text-Login (TTY1) — bash zum Debuggen |
| `pkill -f chromium` (in TTY1) | killt Chromium → systemd startet sofort neu |
| `sudo systemctl restart marktpilot-kiosk.service` | sauberer Restart |
| `sudo reboot` | kompletter Neustart |

> **Wichtig:** Die URL ist `http://localhost:8080/`, **nicht** die
> Laptop-IP. nginx auf der Kassen-Pi selbst bedient das Frontend und
> proxiet `/api/` an den Laptop.

### 3.2 Touchscreen kalibrieren (optional)

Die meisten kapazitiven Touchscreens brauchen keine Kalibrierung. Falls
deiner ungenau ist:

```bash
sudo apt install -y xinput-calibrator
# Dann auf dem Desktop:
xinput_calibrator
```

Folge den Anweisungen, trage die Werte in `/usr/share/X11/xorg.conf.d/99-calibration.conf` ein.

### 3.3 Touchscreen-Rotation (falls der Bildschirm hochkant montiert ist)

```bash
sudo nano /boot/firmware/config.txt
```

Am Ende hinzufügen:

```
# Display drehen (1 = 90°, 2 = 180°, 3 = 270°)
display_rotate=1
```

Oder nur den Touch drehen (wenn das Bild richtig ist, aber Touch gespiegelt):

```bash
sudo nano /usr/share/X11/xorg.conf.d/99-touch-rotate.conf
```

Inhalt:

```
Section "InputClass"
    Identifier "rotate-touch"
    MatchProduct "your-touchscreen-name"   # mit `xinput list` rausfinden
    Option "TransformationMatrix" "0 1 0 -1 0 1 0 0 1"
EndSection
```

### 3.4 Reboot-Test

```bash
sudo reboot
```

→ Beim Hochfahren:
1. Desktop erscheint
2. Browser öffnet sich automatisch im Vollbild
3. MarktPilot-UI lädt
4. Du siehst die Produkte vom Laptop-Server (192.168.2.76)

Wenn das klappt: **Kasse läuft!** 🎉

---

## Phase 4 — USB-Hardware anschließen (Drucker/Scanner/Schublade)

> **Wichtig:** Schließ die Geräte erst an, NACHDEM die Pi gebootet hat.
> USB-Hotplug funktioniert bei den meisten Geräten, aber für eine saubere
> udev-Regel ist es besser, die Pi neu zu starten, nachdem alles dranhängt.

### 4.1 udev-Regel für den Drucker (Epson TM-m30III)

Der Epson wird bei USB als generisches Drucker- oder Vendor-Device erkannt.
Damit dein User (nicht root) drauf zugreifen darf:

```bash
# Drucker-USB-ID rausfinden
lsusb
# Beispielausgabe:
#   Bus 001 Device 004: ID 04b8:0e28 Seiko Epson Corp. TM-m30III
```

Regel anlegen:

```bash
sudo nano /etc/udev/rules.d/99-epson-printer.rules
```

Inhalt (USB-ID anpassen, falls abweichend):

```
# Epson TM-m30III
SUBSYSTEM=="usb", ATTR{idVendor}=="04b8", ATTR{idProduct}=="0e28", MODE="0666", GROUP="plugdev"
```

Neu laden:

```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
```

### 4.2 Scanner

USB-HID-Scanner werden als Tastatur erkannt — keine extra Konfiguration
nötig. Sie senden Tastendrücke + Enter. Im MarktPilot-Frontend einfach das
Suchfeld fokussieren, Barcode scannen, fertig.

Falls der Scanner **nicht** als HID erkannt wird (manche Modelle brauchen
einen speziellen Mode), schau in die Scanner-Doku — meist gibt's einen
Barcode zum Scannen, der den Scanner auf „HID Keyboard" umschaltet.

### 4.3 Kassenschublade

Die Schublade hängt am **Drucker** (RJ12-Kabel). Sie wird per
ESC/POS-Pulse-Befehl vom Drucker geöffnet — kein direkter Strom-Anschluss
an die Pi nötig. Das passiert automatisch, sobald wir die Drucker-Anbindung
programmiert haben (kommt mit Tauri).

---

## Phase 5 — Update-Workflow

Wenn du Änderungen am Frontend machst (auf dem PC), willst du die auf die
Kassen-Pi kriegen:

```powershell
# Am PC
cd C:\Repos\markt-pilot\frontend
$env:VITE_API_BASE = "http://192.168.2.76:8000"
cmd /c npm run build

scp -r dist\* globia1@192.168.2.51:~/markt-pilot-frontend/
```

Die Pi braucht keinen Neustart — Chromium lädt die Seite beim nächsten
Refresh neu. Oder: `F5` auf dem Touchscreen drücken.

Für ein richtiges Update-Skript (das den Reload automatisch macht), kann
ich dir später ein `deploy-kasse.ps1` schreiben.

---

## Was funktioniert, was (noch) nicht

✅ **Funktioniert jetzt:**
- Touchscreen-Kasse im Browser, autark
- Liest Produkte vom Laptop-Server (192.168.2.76)
- Verkäufe, Storno, Kassenbuch, Analytics
- Offline-Modus: Cart läuft lokal, Outbox synct wenn Laptop-Server (192.168.2.76) wieder da

❌ **Noch nicht (kommt mit Tauri-Schritt):**
- Drucker druckt die Bons noch nicht (nur Bildschirm-Anzeige)
- Schublade öffnet noch nicht
- Tastatur-Scanner funktioniert in Browser-App, aber Fokus-Management ist
  bei Touch-Kassen manchmal fummelig — Tauri löst das

Für die ersten Tage / Wochen kannst du mit der Browser-Kasse problemlos
arbeiten und Bons auf dem Bildschirm zeigen lassen. Kunden ohne Bon sind
okay (deutsches Recht: Pflicht nur, wenn Kunde es wünscht). Drucken und
Schublade kommen, wenn wir Tauri angehen.

---

## Troubleshooting

### Touchscreen reagiert nicht

```bash
# Touch-Gerät erkennen
xinput list
# Sollte einen Eintrag mit "touch" oder deinem Display-Namen haben

# Test, ob Touch-Events ankommen
xinput test <id>
# Dann den Finger über den Bildschirm ziehen — sollten Events kommen
```

Falls gar nichts: USB-Touch-Kabel prüfen, anderes USB-Kabel probieren, oder
den Touchscreen hat einen Knopf / Hotkey zum Aktivieren.

### Browser bleibt nicht im Vollbild

Oft liegt's am `--kiosk`-Flag in Kombination mit Wayland (Pi 5 Default).
Workaround: in der systemd-Service-Datei einen kurzen Sleep einbauen
(`ExecStartPre=/bin/sleep 5`).

### nginx zeigt 502

```bash
sudo systemctl status nginx
# Falls nginx läuft aber 502: ist das dist/ Verzeichnis da?
ls -la /home/globia1/marktpilot-frontend/
# Index.html muss da sein
```

### Frontend zeigt „Backend nicht erreichbar"

- Hat der Laptop-Server die richtige IP? (vom Browser aus `http://<LAPTOP-IP>:8000/healthz` testen)
- Firewall auf Laptop: Port 8000 offen? (siehe `LAPTOP-SETUP.md`)
- Stimmt die IP in der nginx-Config auf der Pi? (`grep proxy_pass /etc/nginx/sites-available/marktpilot`)
- Stimmt die Kasse-URL im Chromium? Sollte `http://localhost:8080/` sein (nicht die Laptop-IP)

---

## Quick-Reference

| Aufgabe | Befehl |
|---|---|
| Per SSH verbinden | `ssh globia1@<PI-IP>` |
| nginx-Status | `sudo systemctl status nginx` |
| nginx-Logs | `sudo journalctl -u nginx -f` |
| nginx reload (nach Config-Änderung) | `sudo nginx -t && sudo systemctl reload nginx` |
| Kiosk-Service-Status | `systemctl status marktpilot-kiosk.service` |
| Kiosk-Service-Restart | `sudo systemctl restart marktpilot-kiosk.service` |
| Kiosk-Logs | `sudo journalctl -u marktpilot-kiosk.service -f` |
| Chromium killen (Systemd startet neu) | `pkill -f chromium` |
| IP-Wechsel Laptop → nginx updaten | `sudo sed -i 's#ALT_IP#NEU_IP#g' /etc/nginx/sites-available/marktpilot && sudo nginx -t && sudo systemctl reload nginx` |
| Pi neu starten | `sudo reboot` |
| Pi ausschalten | `sudo shutdown -h now` |
| Frontend-Verzeichnis | `/home/globia1/marktpilot-frontend/` |
| API-URL im Frontend | **relativ** (`/api/...`) — nginx proxt zum Laptop |
| Kiosk-Browser-URL | `http://localhost:8080/` (lokaler nginx) |
