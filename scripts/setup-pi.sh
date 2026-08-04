#!/usr/bin/env bash
# =============================================================================
# MarktPilot — Raspberry Pi Setup-Script
# -----------------------------------------------------------------------------
# Wird EINMAL auf einem frisch geflashten Fedora-Workstation-Pi ausgefuehrt.
# Installiert: Python venv + Backend-Deps, Node + npm, baut das Frontend,
# richtet nginx als Reverse-Proxy ein und installiert den Backend-Service.
#
# Aufruf:  ./scripts/setup-pi.sh
# Laufzeit: 10-20 Min (je nach Internet-Geschwindigkeit)
# =============================================================================

set -euo pipefail

# --- Farben fuer Output -----------------------------------------------------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log()  { echo -e "${BLUE}==>${NC} $*"; }
ok()   { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}!${NC} $*"; }
fail() { echo -e "${RED}✗${NC} $*"; exit 1; }

# --- Sanity-Checks ----------------------------------------------------------
[[ "$(id -u)" -ne 0 ]] || fail "Bitte NICHT als root ausfuehren — als normaler User mit sudo-Rechten."
[[ -f "backend/requirements.txt" ]] || fail "backend/requirements.txt nicht gefunden. Bist du im Repo-Root?"
[[ -f "frontend/package.json" ]]   || fail "frontend/package.json nicht gefunden. Bist du im Repo-Root?"

log "MarktPilot Setup-Script — fuer Raspberry Pi 4 (Fedora Workstation ARM)"
echo

# -----------------------------------------------------------------------------
# 1) System-Pakete
# -----------------------------------------------------------------------------
log "Installiere System-Pakete (python3, venv, nginx, firewalld-Tools)..."
sudo dnf install -y python3 python3-pip python3-virtualenv nginx git firewalld || fail "dnf install fehlgeschlagen"
ok "System-Pakete installiert"

# -----------------------------------------------------------------------------
# 2) Python venv + Backend-Deps
# -----------------------------------------------------------------------------
log "Erstelle Python venv..."
python3 -m venv backend/.venv
source backend/.venv/bin/activate
log "Installiere Backend-Dependencies..."
pip install --upgrade pip wheel setuptools | tail -1
pip install -r backend/requirements.txt
ok "Backend-Dependencies installiert"

# -----------------------------------------------------------------------------
# 3) Datenbank-Migrationen + Seed
# -----------------------------------------------------------------------------
log "Fuehre Alembic-Migrationen aus..."
(cd backend && alembic upgrade head) || fail "Alembic fehlgeschlagen"
if [[ ! -f backend/markt_pilot.db ]]; then
  log "Lege Datenbank mit Seed-Daten an..."
  (cd backend && python seed.py) || warn "Seed fehlgeschlagen — App laeuft trotzdem, nur ohne Beispieldaten"
else
  warn "Datenbank existiert bereits — Seed wird uebersprungen"
fi
ok "Datenbank ready"

deactivate

# -----------------------------------------------------------------------------
# 4) Node.js 20 (via NodeSource wenn noetig)
# -----------------------------------------------------------------------------
if ! command -v node >/dev/null 2>&1 || [[ "$(node -v | sed 's/v//' | cut -d. -f1)" -lt 20 ]]; then
  log "Installiere Node.js 20..."
  curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo bash -
  sudo dnf install -y nodejs
fi
ok "Node.js $(node -v) + npm $(npm -v)"

# -----------------------------------------------------------------------------
# 5) Frontend bauen
# -----------------------------------------------------------------------------
log "Baue Frontend (das dauert 1-3 Min)..."
(cd frontend && npm install --no-audit --no-fund && npm run build) || fail "Frontend-Build fehlgeschlagen"
ok "Frontend gebaut in frontend/dist/"

# -----------------------------------------------------------------------------
# 6) Frontend nach /var/www/marktpilot deployen
# -----------------------------------------------------------------------------
log "Deploye Frontend nach /var/www/marktpilot..."
sudo mkdir -p /var/www/marktpilot
sudo cp -r frontend/dist/* /var/www/marktpilot/
sudo chown -R nginx:nginx /var/www/marktpilot
ok "Frontend deployed"

# -----------------------------------------------------------------------------
# 7) systemd-Service installieren
# -----------------------------------------------------------------------------
log "Installiere Backend-Service marktpilot-backend..."
# Service-File: WorkingDirectory relativ zum User-Home. Wir installieren
# das Service-File mit absolutem Pfad.
REAL_USER="${SUDO_USER:-$(logname)}"
REAL_HOME="$(getent passwd "$REAL_USER" | cut -d: -f6)"
REPO_DIR="$REAL_HOME/markt-pilot"

sudo tee /etc/systemd/system/marktpilot-backend.service > /dev/null <<EOF
[Unit]
Description=MarktPilot Backend (FastAPI)
After=network.target

[Service]
Type=simple
User=$REAL_USER
WorkingDirectory=$REPO_DIR/backend
Environment=PATH=$REPO_DIR/backend/.venv/bin:/usr/bin:/bin
ExecStart=$REPO_DIR/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable marktpilot-backend
sudo systemctl restart marktpilot-backend
sleep 2
sudo systemctl is-active --quiet marktpilot-backend && ok "Backend-Service laeuft" || fail "Backend-Service startet nicht — journalctl -u marktpilot-backend"
ok "Backend-Service installiert + aktiviert (auto-start bei Boot)"

# -----------------------------------------------------------------------------
# 8) nginx Reverse-Proxy
# -----------------------------------------------------------------------------
log "Konfiguriere nginx als Reverse-Proxy..."
sudo tee /etc/nginx/conf.d/marktpilot.conf > /dev/null 'EOF'
server {
    listen 80 default_server;
    server_name _;
    root /var/www/marktpilot;
    index index.html;

    # Frontend — alles was nicht /api ist, faellt auf die index.html
    # (React Router History-Mode)
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Backend-API proxien
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Health-Check
    location /healthz {
        proxy_pass http://127.0.0.1:8000/healthz;
    }
}
EOF

# Default-Server-Block deaktivieren (unser marktpilot.conf ist jetzt default)
sudo sed -i 's|listen       80 default_server;|# listen       80 default_server;|' /etc/nginx/nginx.conf 2>/dev/null || true

sudo nginx -t || fail "nginx-Config ungueltig"
sudo systemctl enable --now nginx
sudo systemctl restart nginx
ok "nginx laeuft"

# -----------------------------------------------------------------------------
# 9) Firewall
# -----------------------------------------------------------------------------
log "Oeffne Ports 80 (HTTP) und 22 (SSH) in der Firewall..."
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --reload
ok "Firewall konfiguriert"

# -----------------------------------------------------------------------------
# 10) Smoke-Tests
# -----------------------------------------------------------------------------
log "Smoke-Tests..."
sleep 2
if curl -sf http://127.0.0.1:8000/healthz >/dev/null; then
  ok "Backend  /healthz antwortet"
else
  fail "Backend /healthz antwortet NICHT"
fi
if curl -sf http://127.0.0.1:80/ | grep -q '<div id="root"'; then
  ok "Frontend wird via nginx ausgeliefert"
else
  warn "Frontend liefert kein <div id=\"root\"> — siehe /var/log/nginx/error.log"
fi

# IP-Adresse(n) anzeigen
echo
log "Fertig! Dein Pi ist erreichbar unter:"
ip -4 addr show | grep -E "inet " | grep -v 127.0.0.1 | awk '{print "  - http://" $2 "/"}' | sed 's|/[0-9]*||'
echo
log "Im Browser auf einem GLEICHEN WLAN-Geraet:"
echo "  http://<obige-ip>/"
echo
ok "MarktPilot laeuft. Bei Problemen: sudo journalctl -u marktpilot-backend -f"
