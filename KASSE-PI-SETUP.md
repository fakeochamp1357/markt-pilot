# MarktPilot — Kassen-Pi einrichten (Pi #2)

Stand: 2026-08-10
Ziel: Eine Raspberry Pi 5 mit Touchscreen-Monitor und USB-Hardware (Drucker,
Scanner, Schublade) als autarkes Kassen-Terminal.

> **Voraussetzung:** Der Laptop-Server läuft und ist unter `http://192.168.2.196:8000`
> erreichbar. Siehe [`LAPTOP-SETUP.md`](LAPTOP-SETUP.md).
> `http://<PI-SERVER-IP>:8000` erreichbar. Siehe `PI-SETUP.md`.

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
   - Hostname: `marktpilot-kasse`
   - Username + Passwort setzen (z.B. `kasse` / sicheres Passwort)
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
ssh kasse@marktpilot-kasse.local
# oder, falls mDNS nicht klappt:
ssh kasse@<IP-der-Pi>   # findest du im Router oder mit `hostname -I` an der Pi
```

Ab jetzt kannst du alle weiteren Schritte **per SSH** machen — kein Monitor
nötig (außer du willst den Touchscreen für den Endspurt).

### 1.4 System aktualisieren

```bash
sudo apt update && sudo apt full-upgrade -y
sudo reboot
```

### 1.5 Feste IP im Router

Genau wie beim Laptop-Server (192.168.2.196): in der Router-Admin-Oberfläche der Kassen-Pi eine
**feste LAN-IP** geben (z.B. `192.168.2.51`). Sonst findet der Laptop-Server (192.168.2.196) die
Kasse später nicht zuverlässig.

---

## Phase 2 — Frontend bauen und deployen (~15 Min)

Das Frontend läuft im Browser der Kassen-Pi. Wir bauen es **am PC** und
kopieren nur das fertige Bundle auf die Pi — schneller als alles auf der
kleinen Pi zu kompilieren.

### 2.1 Am PC: Frontend production-builden

```powershell
cd C:\Repos\markt-pilot\frontend

# API-URL auf den SERVER-Pi setzen (nicht die Kassen-Pi!)
$env:VITE_API_BASE = "http://192.168.2.196:8000"
cmd /c npm run build
# → erzeugt dist/ Ordner
```

### 2.2 Bundle auf die Kassen-Pi schieben

```powershell
# Vom PC aus
scp -r C:\Repos\markt-pilot\frontend\dist\* kasse@192.168.2.51:~/markt-pilot-frontend/
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

    root /home/kasse/marktpilot-frontend;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # Optional: API-Proxy — wenn du /api/ statt VITE_API_BASE nutzen willst
    location /api/ {
        proxy_pass http://192.168.2.196:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

Aktivieren:

```bash
sudo ln -s /etc/nginx/sites-available/marktpilot /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

Test im Browser: `http://192.168.2.51:8080/` → deine MarktPilot-UI mit
Daten vom Laptop-Server (192.168.2.196).

---

## Phase 3 — Kiosk-Mode (Browser im Vollbild, Auto-Start) (~15 Min)

### 3.1 Chromium für Kiosk konfigurieren

```bash
mkdir -p ~/.config/autostart
nano ~/.config/autostart/marktpilot-kiosk.desktop
```

Inhalt:

```ini
[Desktop Entry]
Type=Application
Name=MarktPilot Kasse
Exec=/usr/bin/chromium --kiosk --noerrdialogs --disable-infobars --disable-pinch --overscroll-history-navigation=0 --check-for-update-interval=31536000 http://localhost:8080/
X-GNOME-Autostart-enabled=true
```

> **Wichtig:** Die URL ist `http://localhost:8080/`, **nicht** die
> Laptop-Server (192.168.2.196)-IP. nginx auf der Kassen-Pi selbst bedient das Frontend und
> proxiet `/api/` an die Laptop-Server (192.168.2.196).

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
4. Du siehst die Produkte vom Laptop-Server (192.168.2.196)

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
$env:VITE_API_BASE = "http://192.168.2.196:8000"
cmd /c npm run build

scp -r dist\* kasse@192.168.2.51:~/markt-pilot-frontend/
```

Die Pi braucht keinen Neustart — Chromium lädt die Seite beim nächsten
Refresh neu. Oder: `F5` auf dem Touchscreen drücken.

Für ein richtiges Update-Skript (das den Reload automatisch macht), kann
ich dir später ein `deploy-kasse.ps1` schreiben.

---

## Was funktioniert, was (noch) nicht

✅ **Funktioniert jetzt:**
- Touchscreen-Kasse im Browser, autark
- Liest Produkte vom Laptop-Server (192.168.2.196)
- Verkäufe, Storno, Kassenbuch, Analytics
- Offline-Modus: Cart läuft lokal, Outbox synct wenn Laptop-Server (192.168.2.196) wieder da

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
Workaround: in den Autostart-Desktop-File einen kurzen Sleep + Restart einbauen:

```ini
Exec=/bin/sh -c "sleep 5 && /usr/bin/chromium --kiosk http://localhost:8080/"
```

### nginx zeigt 502

```bash
sudo systemctl status nginx
# Falls nginx läuft aber 502: ist das dist/ Verzeichnis da?
ls -la /home/kasse/marktpilot-frontend/
# Index.html muss da sein
```

### Frontend zeigt „Backend nicht erreichbar"

- Hat der Laptop-Server (192.168.2.196) die richtige IP? (vom Browser aus `http://192.168.2.196:8000/healthz` testen)
- Firewall auf Laptop-Server (192.168.2.196): Port 8000 offen? (siehe `PI-SETUP.md`)
- Korrekter `VITE_API_BASE` beim Bauen gesetzt?

---

## Quick-Reference

| Aufgabe | Befehl |
|---|---|
| Per SSH verbinden | `ssh kasse@192.168.2.51` |
| nginx-Status | `sudo systemctl status nginx` |
| nginx-Logs | `sudo journalctl -u nginx -f` |
| nginx reload | `sudo systemctl reload nginx` |
| Pi neu starten | `sudo reboot` |
| Pi ausschalten | `sudo shutdown -h now` |
| Frontend-Verzeichnis | `/home/kasse/marktpilot-frontend/` |
| API-URL im Frontend | `http://192.168.2.196:8000` (Laptop-Server (192.168.2.196)!) |
| Kiosk-Browser-URL | `http://localhost:8080/` (lokaler nginx) |
