# MarktPilot — Sync-Setup für 2 Geräte

Stand: 2026-06-28 — Repo lebt auf GitHub, Code + Doku + Prompts werden via Git synchronisiert.

## Architektur

```
┌──────────────────────────────┐         ┌──────────────────────────────┐
│  PC (Desktop, Windows)       │         │  Laptop (Windows)            │
│  C:\Repos\markt-pilot        │         │  C:\Repos\markt-pilot        │
│  ┌────────────────────────┐  │         │  ┌────────────────────────┐  │
│  │  Mavis (Workspace)     │  │  git    │  │  Mavis (Workspace)     │  │
│  │  liest/schreibt Code   │◄─┼──push──►┼──┤  liest/schreibt Code   │  │
│  │  + Prompts/Plan lokal  │  │  pull   │  │  + Prompts/Plan lokal  │  │
│  └────────────────────────┘  │         │  └────────────────────────┘  │
└──────────────────────────────┘         └──────────────────────────────┘
                  │                                       │
                  └──────────────► GitHub ◄───────────────┘
                          github.com/fakeochamp1357/markt-pilot
```

Jeder Commit enthält den aktuellen Stand. Mavis zeigt auf den lokalen Pfad und
"merkt" sich Git-Status automatisch — `git push` reicht, um die Arbeit zu teilen.

---

## Setup auf einem NEUEN Gerät (z.B. Laptop)

### 1) Tools installieren

PowerShell als Admin einmalig:

```powershell
winget install --id Git.Git        --accept-package-agreements --accept-source-agreements
# Mavis: siehe unten (MiniMax Code)
```

PATH refreshen (in derselben oder neuen Shell):

```powershell
$env:Path = [System.Environment]::GetEnvironmentVariable('Path','Machine') + ';' +
            [System.Environment]::GetEnvironmentVariable('Path','User')
git --version   # sollte "git version 2.x" zeigen
```

### 2) Git-Identity (einmalig pro Gerät)

```powershell
git config --global user.name  "fakeochamp1357"
git config --global user.email "fakeochamp1357@users.noreply.github.com"
git config --global init.defaultBranch main
```

### 3) Repo klonen

```powershell
New-Item -ItemType Directory -Path "C:\Repos" -Force
cd C:\Repos
git clone https://github.com/fakeochamp1357/markt-pilot.git
cd markt-pilot
```

### 4) Backend-Dependencies installieren + DB initialisieren

```powershell
cd C:\Repos\markt-pilot\backend
pip install -r requirements.txt
python -m alembic upgrade head
python seed.py                  # legt 5 Kategorien + 20 Beispiel-Produkte an
```

### 5) Frontend-Dependencies installieren

```powershell
cd C:\Repos\markt-pilot\frontend
npm install
```

### 6) Mavis (MiniMax Code) installieren + Workspace setzen

Mavis bekommst du hier: **<https://MiniMax.io/download>** (Windows-Installer).

Nach der Installation:
1. Mavis öffnen
2. "Open Workspace" oder `Cmd/Ctrl+K` → "Switch Workspace"
3. Pfad wählen: `C:\Repos\markt-pilot`
4. Mavis erkennt automatisch das Git-Repo und merkt sich den Workspace

---

## Täglicher Workflow

### Start auf dem PC

```powershell
cd C:\Repos\markt-pilot
git pull                    # holt neueste Änderungen vom Laptop
# dann mit Mavis arbeiten
git add .
git commit -m "Was hab ich gemacht"
git push
```

### Start auf dem Laptop

```powershell
cd C:\Repos\markt-pilot
git pull                    # holt PC-Änderungen
# dann mit Mavis arbeiten
git add .
git commit -m "Was hab ich gemacht"
git push
```

### Konflikt?

Wenn beide Geräte die gleiche Datei geändert haben, meckert `git pull`. Dann:

```powershell
git pull --rebase           # deine lokalen Commits obendrauf setzen
# Konflikte manuell lösen (VS Code zeigt sie rot)
git add <gelöste-dateien>
git rebase --continue
git push
```

Falls dir das zu heikel ist: einfach `git status` schauen, Mavis helfen lassen.

---

## Was läuft wo (App starten)

Auf **jedem** Gerät, auf dem du entwickeln willst:

```powershell
# Backend (Terminal 1)
cd C:\Repos\markt-pilot\backend
python -m uvicorn app.main:app --port 8000 --host 127.0.0.1

# Frontend (Terminal 2)
cd C:\Repos\markt-pilot\frontend
cmd /c npm run dev -- --host 127.0.0.1 --port 5173
```

Browser: <http://127.0.0.1:5173/>
API-Doku: <http://127.0.0.1:8000/docs>

> **Hinweis:** Die SQLite-DB (`backend/markt_pilot.db`) ist **nicht** im Git-Repo
> (siehe `.gitignore`). Jedes Gerät hat seine eigene DB. Für Multi-Device-Sync
> der **Daten** brauchen wir Phase 2 (Raspberry Pi Sync-Server).

---

## OneDrive-Falle (warum wir weg sind)

OneDrive + Git vertragen sich schlecht:
- OneDrive lockt Dateien beim Sync → Git-Operationen brechen ab
- `.pyc`/`node_modules`-Konflikte
- Locking-Fehler bei `git add`

→ Workspace **muss** außerhalb von OneDrive liegen. `C:\Repos\` ist der
empfohlene Pfad. OneDrive-Ordner können nach erfolgreichem Klon gelöscht werden.

---

## GitHub-Credentials (kein Token nötig)

Beim ersten `git push` fragt Windows automatisch nach dem Login. Einfach im
Browser "Sign in with your browser" wählen — Windows Credential Manager
speichert die Anmeldedaten, danach nie wieder gefragt.

Falls es hakt:
```powershell
git credential-manager clear     # falsche/alte Credentials löschen
# dann nochmal pushen, Browser-Login machen
```

---

## Was Mavis über Sync *automatisch* kann

- Mavis erkennt, ob ein Workspace ein Git-Repo ist
- Mavis erkennt Remote-URL und Tracking-Branch
- Mavis committed **nicht** automatisch (bewusst — du entscheidest, was rein
  kommt); aber es zeigt jederzeit `git status` und bietet "commit + push"-Helfer
- Mavis Sessions selbst sind **nicht** im Git, sondern im Mavis-Backend. Wenn
  du auf dem Laptop mit einer früheren Session weiterarbeiten willst, frag
  einfach Mavis: *"zeig mir meine letzten Sessions"* und nimm die richtige.

---

## Quick-Reference

| Aufgabe                              | Befehl                                         |
|--------------------------------------|------------------------------------------------|
| Stand vom anderen Gerät holen        | `git pull`                                     |
| Änderungen vormerken                 | `git add .`                                    |
| Änderungen festschreiben             | `git commit -m "..."`                          |
| Zum GitHub hochladen                 | `git push`                                     |
| In einem Schritt                     | `git add .; git commit -m "..."; git push`    |
| Status sehen                         | `git status`                                   |
| Letzte Commits                       | `git log --oneline -10`                        |
| Alles aufgeben & Remote-Stand holen  | `git fetch origin; git reset --hard origin/main` (Vorsicht!) |
