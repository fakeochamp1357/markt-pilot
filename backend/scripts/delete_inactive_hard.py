"""MarktPilot — Hard-Delete aller inaktiven Produkte.

Loescht jede Zeile aus ``products`` mit ``is_active = 0`` direkt per SQL.
Foreign-Key-Constraints (ReceiptLine.product_id → SET NULL) werden sauber
behandelt — alte Bons bleiben durch ihren name_snapshot lesbar.

VOR dem Delete wird ein automatisches Backup der SQLite-Datei angelegt.
"""
from __future__ import annotations

import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "markt_pilot.db"


def main() -> int:
    if not DB_PATH.exists():
        print(f"DB nicht gefunden: {DB_PATH}", file=sys.stderr)
        return 1

    # ---- Backup ----
    backup = DB_PATH.with_suffix(
        DB_PATH.suffix + f".bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    )
    shutil.copy2(DB_PATH, backup)
    print(f"[backup] {backup}")

    # ---- Analyse ----
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")  # FK-Checks aktivieren
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM products WHERE is_active = 0")
    inactive_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM products WHERE is_active = 1")
    active_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM products")
    total = cur.fetchone()[0]

    print(f"[analyse] total={total}  aktiv={active_count}  inaktiv={inactive_count}")

    if inactive_count == 0:
        print("[ok] Keine inaktiven Produkte — nichts zu tun.")
        conn.close()
        return 0

    # ---- Vorschau ----
    cur.execute(
        "SELECT id, name, category_id, barcode FROM products "
        "WHERE is_active = 0 ORDER BY id"
    )
    print("\n[preview] Diese Produkte werden endgueltig geloescht:")
    print(f"  {'ID':>4}  {'Kat':>4}  Barcode         Name")
    print("  " + "-" * 70)
    for row in cur.fetchall():
        pid, name, cat, bc = row
        print(f"  {pid:>4}  {str(cat or '-'):>4}  {bc or '-':<14}  {name}")

    # ---- Bestaetigung ----
    print()
    answer = input("Wirklich loeschen? Tippe 'JA' (Grossbuchstaben): ")
    if answer.strip() != "JA":
        print("[abort] Abgebrochen.")
        conn.close()
        return 0

    # ---- Check: sind inaktive Produkte in Receipts referenziert? ----
    cur.execute(
        "SELECT DISTINCT rl.product_id FROM receipt_lines rl "
        "JOIN products p ON p.id = rl.product_id "
        "WHERE p.is_active = 0 AND rl.product_id IS NOT NULL"
    )
    refs = [r[0] for r in cur.fetchall()]
    if refs:
        print(
            f"\n[hinweis] {len(refs)} inaktive Produkte sind in Receipts "
            f"referenziert (product_id). Beim DELETE wird auf NULL gesetzt — "
            f"die name_snapshots in den Bons bleiben lesbar."
        )

    # ---- Hard-Delete ----
    cur.execute("DELETE FROM products WHERE is_active = 0")
    deleted = cur.rowcount
    conn.commit()

    cur.execute("VACUUM")  # DB-Datei physisch schrumpfen
    conn.close()

    print(f"\n[done] {deleted} Produkte geloescht.")
    print(f"[backup bleibt unter] {backup}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
