/**
 * Kassenbuch: Übersicht über alle Bons einer Schicht.
 *
 * Aktuell:
 *  - "Heute"-Karte mit Stueckzahl, Gesamtumsatz, Bar/Karte-Aufteilung
 *  - Liste aller Bons von heute (neueste zuerst)
 *  - Tap auf eine Zeile oeffnet den vollen Bildschirm-Bon (re-use)
 *  - Storno-Button im Detail-Sheet
 *
 * Vorgemerkt fuer spaeter (Phase B):
 *  - Filter: "Heute / Gestern / Diese Woche / Alle"
 *  - Z-Bericht (Tagesabschluss) am Listenende
 *  - Filter nach Bediener
 */
import { useEffect, useMemo, useState } from 'react';
import { Receipt as ReceiptIcon, ListChecks, Trash2 } from 'lucide-react';
import { BottomSheet } from '@/components/BottomSheet';
import { listReceipts, voidReceipt } from '@/api/client';
import { formatPriceCents } from '@/utils/format';
import type { Receipt, PaymentMethod } from '@/types/api';

function todaySession(): string {
  return new Date().toISOString().slice(0, 10);
}

function fmtTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString('de-DE', {
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return '';
  }
}

const PAYMENT_LABEL: Record<PaymentMethod, string> = {
  cash: 'Bar',
  card: 'Karte',
  mixed: 'Gemischt',
};

const PAYMENT_BADGE: Record<PaymentMethod, string> = {
  cash: 'bg-amber-500/20 text-amber-200',
  card: 'bg-emerald-500/20 text-emerald-200',
  mixed: 'bg-blue-500/20 text-blue-200',
};

export function ReceiptsPage() {
  const [receipts, setReceipts] = useState<Receipt[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [openReceipt, setOpenReceipt] = useState<Receipt | null>(null);
  const [voiding, setVoiding] = useState(false);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      // Heute filtern ueber cash_session
      const data = await listReceipts({ cash_session: todaySession() });
      setReceipts(data);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : 'Bons konnten nicht geladen werden.'
      );
      setReceipts([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const stats = useMemo(() => {
    if (!receipts) return null;
    // Nur sales zaehlen, Stornos / Retouren raus (sind eh negativ)
    const sales = receipts.filter((r) => r.kind === 'sale');
    const voids = receipts.filter((r) => r.kind === 'storno');
    const total = sales.reduce((s, r) => s + r.total_cents, 0);
    const stornoTotal = voids.reduce((s, r) => s + Math.abs(r.total_cents), 0);
    const byMethod: Record<PaymentMethod, number> = {
      cash: 0,
      card: 0,
      mixed: 0,
    };
    sales.forEach((r) => {
      byMethod[r.payment_method] += r.total_cents;
    });
    return { count: sales.length, total, stornoTotal, voidsCount: voids.length, byMethod };
  }, [receipts]);

  const onVoid = async (r: Receipt) => {
    if (!window.confirm(`Bon ${r.receipt_number} wirklich stornieren?`)) return;
    setVoiding(true);
    try {
      await voidReceipt(r.id);
      await load();
      setOpenReceipt(null);
    } catch (e) {
      window.alert(
        e instanceof Error ? e.message : 'Storno fehlgeschlagen.'
      );
    } finally {
      setVoiding(false);
    }
  };

  return (
    <div className="px-4 pt-3 pb-8 space-y-3">
      {/* Heute-Zusammenfassung */}
      <section className="card p-3">
        <div className="flex items-center gap-2 text-[color:var(--text-secondary)]">
          <ListChecks size={16} />
          <h3 className="text-xs font-semibold uppercase tracking-wide">
            Heute ({todaySession()})
          </h3>
        </div>
        {stats && (
          <div className="mt-2 grid grid-cols-3 gap-2">
            <Stat
              label="Bons"
              value={String(stats.count)}
              tone="default"
            />
            <Stat
              label="Umsatz"
              value={formatPriceCents(stats.total)}
              tone="default"
            />
            <Stat
              label="Stornos"
              value={String(stats.voidsCount)}
              tone={stats.voidsCount > 0 ? 'warn' : 'default'}
            />
          </div>
        )}
        {stats && (stats.byMethod.cash > 0 || stats.byMethod.card > 0) && (
          <div className="mt-2 flex gap-2 text-xs">
            {stats.byMethod.cash > 0 && (
              <span className="rounded-full bg-amber-500/20 px-2 py-0.5 text-amber-200">
                Bar: {formatPriceCents(stats.byMethod.cash)}
              </span>
            )}
            {stats.byMethod.card > 0 && (
              <span className="rounded-full bg-emerald-500/20 px-2 py-0.5 text-emerald-200">
                Karte: {formatPriceCents(stats.byMethod.card)}
              </span>
            )}
            {stats.byMethod.mixed > 0 && (
              <span className="rounded-full bg-blue-500/20 px-2 py-0.5 text-blue-200">
                Mix: {formatPriceCents(stats.byMethod.mixed)}
              </span>
            )}
          </div>
        )}
        {stats && stats.stornoTotal > 0 && (
          <p className="mt-2 text-xs text-[color:var(--text-muted)]">
            Storno-Volumen: {formatPriceCents(stats.stornoTotal)} (vom Umsatz bereits abgezogen)
          </p>
        )}
      </section>

      {/* Liste */}
      {loading && (
        <p className="text-center text-sm text-[color:var(--text-muted)] py-8">
          Lade Bons …
        </p>
      )}
      {error && (
        <p className="rounded-xl border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-200">
          {error}
        </p>
      )}
      {!loading && !error && receipts && receipts.length === 0 && (
        <div className="card p-6 text-center text-sm text-[color:var(--text-muted)]">
          Heute noch keine Bons.
        </div>
      )}
      {!loading && receipts && receipts.length > 0 && (
        <ul className="space-y-2">
          {receipts.map((r) => {
            const isVoid = r.kind === 'storno';
            return (
              <li key={r.id}>
                <button
                  type="button"
                  onClick={() => setOpenReceipt(r)}
                  className="card flex w-full items-center gap-3 p-3 text-left active:bg-[color:var(--bg-hover)]"
                  aria-label={`Bon ${r.receipt_number} anzeigen`}
                >
                  <span className="shrink-0">
                    <ReceiptIcon
                      size={18}
                      className={
                        isVoid
                          ? 'text-red-500'
                          : 'text-[color:var(--text-secondary)]'
                      }
                    />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <p className="font-mono text-sm font-semibold">
                        {r.receipt_number}
                      </p>
                      {isVoid && (
                        <span className="rounded-full bg-red-500/20 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-red-200">
                          Storno
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-[color:var(--text-muted)]">
                      {fmtTime(r.created_at)} · {r.lines.length}{' '}
                      {r.lines.length === 1 ? 'Position' : 'Positionen'}
                    </p>
                  </div>
                  <div className="shrink-0 text-right">
                    <p
                      className={`text-base font-bold ${
                        isVoid ? 'text-red-500' : ''
                      }`}
                    >
                      {formatPriceCents(r.total_cents)}
                    </p>
                    <span
                      className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                        PAYMENT_BADGE[r.payment_method]
                      }`}
                    >
                      {PAYMENT_LABEL[r.payment_method]}
                    </span>
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
      )}

      {/* Detail-Sheet */}
      <ReceiptDetail
        receipt={openReceipt}
        onClose={() => setOpenReceipt(null)}
        onVoid={onVoid}
        voiding={voiding}
      />
    </div>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: 'default' | 'warn';
}) {
  return (
    <div className="rounded-xl bg-[color:var(--bg-page)] p-2 text-center">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-[color:var(--text-muted)]">
        {label}
      </p>
      <p
        className={`mt-0.5 text-lg font-bold ${
          tone === 'warn' ? 'text-amber-500' : ''
        }`}
      >
        {value}
      </p>
    </div>
  );
}

// -------------------------------------------------------------
// Detail-Sheet (re-use logic aus POSPage, mit Void-Button)
// -------------------------------------------------------------

interface ReceiptDetailProps {
  receipt: Receipt | null;
  onClose: () => void;
  onVoid: (r: Receipt) => Promise<void>;
  voiding: boolean;
}

function ReceiptDetail({ receipt, onClose, onVoid, voiding }: ReceiptDetailProps) {
  if (!receipt) return null;
  const isVoid = receipt.kind === 'storno';
  return (
    <BottomSheet
      open
      onClose={onClose}
      title={`Bon ${receipt.receipt_number}${isVoid ? ' (Storno)' : ''}`}
      maxHeight="92vh"
    >
      <div className="rounded-xl border border-[color:var(--border-strong)] bg-[color:var(--bg-page)] p-3 text-sm">
        <div className="flex justify-between">
          <span>Datum</span>
          <span>{new Date(receipt.created_at).toLocaleString('de-DE')}</span>
        </div>
        <div className="flex justify-between">
          <span>Zahlung</span>
          <span>{PAYMENT_LABEL[receipt.payment_method]}</span>
        </div>
        {receipt.payment_method === 'cash' && (
          <>
            <div className="flex justify-between">
              <span>Gegeben</span>
              <span>{formatPriceCents(receipt.tendered_cents)}</span>
            </div>
            <div className="flex justify-between">
              <span>Rückgeld</span>
              <span>{formatPriceCents(receipt.change_cents)}</span>
            </div>
          </>
        )}
        {receipt.print_requested && (
          <p className="mt-2 text-xs text-[color:var(--text-muted)]">
            ✓ Bon für Kunde gewünscht
          </p>
        )}
      </div>

      <ul className="mt-4 space-y-1 font-mono text-sm">
        {receipt.lines.map((l) => (
          <li key={l.id} className="flex justify-between gap-2">
            <span className="flex-1 truncate">
              {l.quantity}× {l.name_snapshot}
              {l.kind === 'deposit' && (
                <span className="ml-1 text-[color:var(--text-faint)]">(Pfand)</span>
              )}
              {l.kind === 'storno' && (
                <span className="ml-1 text-[color:var(--text-faint)]">(Storno)</span>
              )}
            </span>
            <span className="shrink-0">{formatPriceCents(l.line_total_cents)}</span>
          </li>
        ))}
      </ul>

      <div className="mt-4 flex items-center justify-between border-t-2 border-dashed border-[color:var(--border-strong)] pt-3 text-lg font-bold">
        <span>Summe</span>
        <span className={isVoid ? 'text-red-500' : ''}>
          {formatPriceCents(receipt.total_cents)}
        </span>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2">
        <button type="button" onClick={onClose} className="btn btn-secondary">
          Schließen
        </button>
        {!isVoid && (
          <button
            type="button"
            onClick={() => onVoid(receipt)}
            disabled={voiding}
            className="btn btn-danger"
          >
            <Trash2 size={14} />
            {voiding ? 'Storniere …' : 'Stornieren'}
          </button>
        )}
      </div>
    </BottomSheet>
  );
}
