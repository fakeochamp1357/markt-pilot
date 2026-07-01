/**
 * Kassen-Modul (Phase A): Bon zusammenstellen + bezahlen.
 *
 * Aufbau bewusst leichtgewichtig fuer Raspberry Pi:
 * - flache Liste, kein Virtual-Scrolling (Warenkoerbe sind kurz)
 * - keine schweren Animationen
 * - Total wird lokal gerundet, Server validiert nochmal
 */
import { useEffect, useMemo, useState } from 'react';
import { Plus, Minus, Trash2, ShoppingCart, ScanLine, X, Search } from 'lucide-react';
import { BottomSheet } from '@/components/BottomSheet';
import { useMarketData } from '@/hooks/useData';
import { useCartStore } from '@/store/cart';
import { createReceipt, voidReceipt } from '@/api/client';
import type { Product, Receipt } from '@/types/api';
import { formatPriceCents } from '@/utils/format';

function todaySession(): string {
  return new Date().toISOString().slice(0, 10); // YYYY-MM-DD
}

export function POSPage() {
  const { products, categories, refresh } = useMarketData();
  const lines = useCartStore((s) => s.lines);
  const addProduct = useCartStore((s) => s.addProduct);
  const setQuantity = useCartStore((s) => s.setQuantity);
  const removeLine = useCartStore((s) => s.removeLine);
  const totalCents = useCartStore((s) => s.totalCents);
  const totalDepositCents = useCartStore((s) => s.totalDepositCents);
  const grandTotalCents = useCartStore((s) => s.grandTotalCents);
  const clearCart = useCartStore((s) => s.clear);
  const newCheckoutOpId = useCartStore((s) => s.newCheckoutOpId);
  const checkoutClientOpId = useCartStore((s) => s.checkoutClientOpId);

  const [pickerOpen, setPickerOpen] = useState(false);
  const [pickerQ, setPickerQ] = useState('');
  const [payOpen, setPayOpen] = useState(false);
  const [lastReceipt, setLastReceipt] = useState<Receipt | null>(null);
  const [busy, setBusy] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const lineCount = lines.length;
  const grandTotal = grandTotalCents();

  const filteredProducts = useMemo(() => {
    const q = pickerQ.trim().toLowerCase();
    let list = products.filter((p) => p.is_active);
    if (q) {
      list = list.filter((p) =>
        `${p.name} ${p.barcode ?? ''} ${p.sku ?? ''}`.toLowerCase().includes(q)
      );
    }
    return list.slice(0, 60);
  }, [products, pickerQ]);

  const onPickProduct = (p: Product) => {
    addProduct(p, '1');
    setPickerOpen(false);
    setPickerQ('');
  };

  const onConfirmCheckout = async (
    payment: { method: 'cash' | 'card'; tendered_cents: number }
  ) => {
    setBusy(true);
    setErrorMsg(null);
    try {
      const payload = {
        cash_session: todaySession(),
        payment_method: payment.method,
        tendered_cents: payment.tendered_cents,
        change_cents: Math.max(0, payment.tendered_cents - grandTotal),
        total_cents: grandTotal,
        cashier_name: null,
        notes: null,
        lines: lines.map((l) => ({
          kind: l.kind,
          product_id: l.productId,
          name_snapshot: l.nameSnapshot,
          unit_snapshot: l.unitSnapshot,
          quantity: l.quantity.replace(',', '.'),
          unit_price_cents: l.unitPriceCents,
          line_total_cents: Math.round(
            parseFloat(l.quantity.replace(',', '.')) * l.unitPriceCents
          ),
          comment: null,
        })),
      };

      const opId = checkoutClientOpId ?? newCheckoutOpId();
      // eslint-disable-next-line no-console
      console.log('[POS] checkout start', { totalCents: payload.total_cents, lines: payload.lines.length, opId });
      const receipt = await createReceipt(payload, opId);
      // eslint-disable-next-line no-console
      console.log('[POS] checkout success', receipt.receipt_number, 'id=', receipt.id);
      setLastReceipt(receipt);
      setPayOpen(false);
      clearCart();
      await refresh();
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error('[POS] checkout failed', e);
      const msg =
        e instanceof Error ? e.message : 'Bezahlvorgang fehlgeschlagen.';
      setErrorMsg(`${msg} (Bon wurde NICHT gebucht — versuche es erneut oder pruefe das Backend.)`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="px-4 pt-3 pb-32">
      {/* Leerer Warenkorb-Hint */}
      {lineCount === 0 && (
        <div className="card mt-8 p-8 text-center">
          <ShoppingCart size={48} className="mx-auto text-ink-400" />
          <p className="mt-3 text-lg font-semibold">Warenkorb ist leer</p>
          <p className="mt-1 text-sm text-ink-500">
            Scanne ein Produkt oder tippe unten auf „Produkt suchen".
          </p>
        </div>
      )}

      {/* Cart Lines */}
      {lineCount > 0 && (
        <ul className="space-y-2">
          {lines.map((l) => {
            const qNum = parseFloat(l.quantity.replace(',', '.')) || 0;
            const lineTotal = Math.round(qNum * l.unitPriceCents);
            const cat =
              l.productId !== null
                ? products.find((p) => p.id === l.productId)?.category_id
                : null;
            const stripe = l.colorTag;
            return (
              <li
                key={l.id}
                className="card flex items-center gap-2 p-2 overflow-hidden"
              >
                <span
                  aria-hidden
                  className="block w-1.5 self-stretch shrink-0"
                  style={{ backgroundColor: stripe }}
                />
                <div className="flex-1 min-w-0">
                  <p className="font-semibold truncate">{l.nameSnapshot}</p>
                  <p className="text-xs text-ink-500">
                    {formatPriceCents(l.unitPriceCents)} / {l.unitSnapshot}
                    {l.kind === 'deposit' && (
                      <span className="ml-1 text-ink-400">· Pfand</span>
                    )}
                  </p>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  <button
                    type="button"
                    aria-label="Menge verringern"
                    onClick={() => {
                      const next = Math.max(0, qNum - 1);
                      if (next === 0) removeLine(l.id);
                      else setQuantity(l.id, String(next).replace('.', ','));
                    }}
                    className="btn btn-secondary btn-sm !min-h-[36px] !min-w-[36px] !px-2"
                  >
                    <Minus size={14} />
                  </button>
                  <input
                    aria-label="Menge"
                    className="input !min-h-[36px] !w-14 !px-1 !py-1 text-center text-sm"
                    value={l.quantity}
                    onChange={(e) => setQuantity(l.id, e.target.value)}
                  />
                  <button
                    type="button"
                    aria-label="Menge erhöhen"
                    onClick={() => setQuantity(l.id, String(qNum + 1).replace('.', ','))}
                    className="btn btn-secondary btn-sm !min-h-[36px] !min-w-[36px] !px-2"
                  >
                    <Plus size={14} />
                  </button>
                </div>
                <div className="shrink-0 w-16 text-right text-sm font-bold">
                  {formatPriceCents(lineTotal)}
                </div>
                <button
                  type="button"
                  aria-label="Position entfernen"
                  onClick={() => removeLine(l.id)}
                  className="btn btn-ghost btn-sm !min-h-[36px] !min-w-[36px] !px-2 text-red-500"
                >
                  <Trash2 size={14} />
                </button>
              </li>
            );
          })}
        </ul>
      )}

      {/* Subtotal-Zeile */}
      {lineCount > 0 && totalDepositCents() > 0 && (
        <div className="mt-3 space-y-1 px-1 text-sm text-ink-500">
          <div className="flex justify-between">
            <span>Zwischensumme Ware</span>
            <span>{formatPriceCents(totalCents())}</span>
          </div>
          <div className="flex justify-between">
            <span>Pfand</span>
            <span>{formatPriceCents(totalDepositCents())}</span>
          </div>
        </div>
      )}

      {/* Aktions-Buttons */}
      <div className="mt-4 grid grid-cols-2 gap-2">
        <button
          type="button"
          onClick={() => setPickerOpen(true)}
          className="btn btn-secondary"
        >
          <Search size={16} />
          Produkt suchen
        </button>
        <button
          type="button"
          onClick={() => setPayOpen(true)}
          disabled={lineCount === 0 || busy}
          className="btn btn-primary"
        >
          Bezahlen
        </button>
      </div>
      {errorMsg && (
        <p className="mt-2 text-sm text-red-500 border-l-2 border-red-500 pl-2">
          {errorMsg}
        </p>
      )}

      {/* Sticky Total-Bar */}
      {lineCount > 0 && (
        <div className="fixed bottom-[68px] inset-x-0 z-20 border-t border-[color:var(--border-strong)] bg-[color:var(--bg-card)] px-4 py-3 shadow-sheet">
          <div className="mx-auto flex max-w-screen-sm items-center justify-between">
            <span className="text-sm uppercase tracking-wide text-ink-500">
              Summe ({lineCount} Pos.)
            </span>
            <span className="text-xl font-bold">{formatPriceCents(grandTotal)}</span>
          </div>
        </div>
      )}

      {/* Produkt-Picker (BottomSheet) */}
      <BottomSheet
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        title="Produkt suchen"
        maxHeight="85vh"
      >
        <div className="relative">
          <Search
            size={18}
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-500"
          />
          <input
            autoFocus
            className="input pl-9"
            placeholder="Name oder Barcode eingeben..."
            value={pickerQ}
            onChange={(e) => setPickerQ(e.target.value)}
          />
        </div>
        <ul className="mt-3 space-y-1">
          {filteredProducts.map((p) => {
            const cat = categories.find((c) => c.id === p.category_id);
            return (
              <li key={p.id}>
                <button
                  type="button"
                  onClick={() => onPickProduct(p)}
                  className="card flex w-full items-center gap-3 p-2 text-left active:bg-gray-50"
                  aria-label={`${p.name} zum Warenkorb hinzufügen`}
                >
                  <span
                    aria-hidden
                    className="block h-10 w-1.5 rounded-full"
                    style={{ backgroundColor: cat?.color ?? p.color_tag }}
                  />
                  <div className="min-w-0 flex-1">
                    <p className="font-semibold truncate">{p.name}</p>
                    <p className="text-xs text-ink-500 truncate">
                      {p.unit}
                      {p.size_weight ? ` · ${p.size_weight}` : ''}
                      {p.barcode ? ` · ${p.barcode}` : ''}
                      {p.deposit_cents > 0 && (
                        <span className="ml-1 text-ink-400">
                          · +{formatPriceCents(p.deposit_cents)} Pfand
                        </span>
                      )}
                    </p>
                  </div>
                  <span className="shrink-0 font-bold">
                    {formatPriceCents(p.sell_price_cents)}
                  </span>
                </button>
              </li>
            );
          })}
          {filteredProducts.length === 0 && (
            <li className="card p-6 text-center text-ink-500">
              Kein Produkt gefunden.
            </li>
          )}
        </ul>
      </BottomSheet>

      {/* Payment Sheet */}
      <PaymentSheet
        open={payOpen}
        onClose={() => !busy && setPayOpen(false)}
        onConfirm={onConfirmCheckout}
        totalCents={grandTotal}
        busy={busy}
        errorMsg={errorMsg}
        onClearError={() => setErrorMsg(null)}
      />

      {/* Receipt View (nach erfolgreichem Checkout) */}
      {lastReceipt && (
        <ReceiptSheet receipt={lastReceipt} onClose={() => setLastReceipt(null)} />
      )}
    </div>
  );
}

// -------------------------------------------------------------
// PaymentSheet
// -------------------------------------------------------------

interface PaymentSheetProps {
  open: boolean;
  onClose: () => void;
  onConfirm: (payment: {
    method: 'cash' | 'card';
    tendered_cents: number;
  }) => Promise<void> | void;
  totalCents: number;
  busy: boolean;
  errorMsg: string | null;
  onClearError: () => void;
}

function PaymentSheet({ open, onClose, onConfirm, totalCents, busy, errorMsg, onClearError }: PaymentSheetProps) {
  const [method, setMethod] = useState<'cash' | 'card'>('cash');
  const [tendered, setTendered] = useState(''); // EUR-Betrag, "5,00"
  const tenderedCents = useMemo(() => {
    const n = parseFloat(tendered.replace(',', '.'));
    return isFinite(n) ? Math.round(n * 100) : 0;
  }, [tendered]);

  const change = Math.max(0, tenderedCents - totalCents);
  const enough = method === 'card' || tenderedCents >= totalCents;

  const quickAdd = (cents: number) => {
    setTendered(((parseFloat(tendered.replace(',', '.') || '0') + cents / 100).toFixed(2)).replace('.', ','));
  };

  const submit = () => {
    if (!enough) return;
    onClearError();
    onConfirm({ method, tendered_cents: method === 'card' ? totalCents : tenderedCents });
  };

  // Beim Schliessen / Method-Wechsel alten Error wegräumen.
  useEffect(() => {
    if (!open) onClearError();
  }, [open, onClearError]);

  return (
    <BottomSheet open={open} onClose={onClose} title="Bezahlen" maxHeight="90vh">
      {errorMsg && (
        <div
          className="mb-3 rounded-xl border border-red-300 bg-red-500/10 p-3 text-sm text-red-200 dark:border-red-500/40"
          role="alert"
          aria-live="polite"
        >
          <p className="font-semibold">Bezahlung fehlgeschlagen</p>
          <p className="mt-1 break-words text-xs">{errorMsg}</p>
          <p className="mt-1 text-xs text-[color:var(--text-muted)]">
            Der Warenkorb ist noch da — du kannst es nochmal versuchen.
          </p>
        </div>
      )}
      <div className="rounded-xl bg-[color:var(--bg-page)] p-4 text-center">
        <p className="text-sm uppercase tracking-wide text-ink-500">Zu zahlen</p>
        <p className="text-3xl font-bold">{formatPriceCents(totalCents)}</p>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2">
        <button
          type="button"
          onClick={() => setMethod('cash')}
          className={`btn ${method === 'cash' ? 'btn-primary' : 'btn-secondary'}`}
          aria-pressed={method === 'cash'}
        >
          Bargeld
        </button>
        <button
          type="button"
          onClick={() => setMethod('card')}
          className={`btn ${method === 'card' ? 'btn-primary' : 'btn-secondary'}`}
          aria-pressed={method === 'card'}
        >
          Karte
        </button>
      </div>

      {method === 'cash' && (
        <div className="mt-4 space-y-3">
          <div>
            <label className="label" htmlFor="tendered">Gegeben</label>
            <input
              id="tendered"
              className="input text-2xl font-bold text-center"
              inputMode="decimal"
              placeholder="0,00"
              value={tendered}
              onChange={(e) => setTendered(e.target.value)}
            />
          </div>
          <div className="grid grid-cols-4 gap-2">
            {[500, 1000, 2000, 5000].map((cents) => (
              <button
                key={cents}
                type="button"
                onClick={() => quickAdd(cents)}
                className="btn btn-secondary btn-sm"
              >
                +{(cents / 100).toFixed(2).replace('.', ',')} €
              </button>
            ))}
          </div>
          <div className="rounded-xl border border-[color:var(--border-strong)] p-3">
            <div className="flex justify-between text-sm">
              <span>Gegeben</span>
              <span className="font-semibold">
                {formatPriceCents(tenderedCents)}
              </span>
            </div>
            {enough ? (
              <div className="mt-1 flex justify-between text-lg">
                <span>Rückgeld</span>
                <span className="font-bold text-emerald-600">
                  {formatPriceCents(change)}
                </span>
              </div>
            ) : (
              <p className="mt-2 text-sm text-red-500">
                Es fehlen {formatPriceCents(totalCents - tenderedCents)}.
              </p>
            )}
          </div>
        </div>
      )}

      {method === 'card' && (
        <p className="mt-4 rounded-xl bg-[color:var(--bg-page)] p-4 text-sm text-ink-500">
          Kartenzahlung am Terminal. Betrag{' '}
          <span className="font-semibold">{formatPriceCents(totalCents)}</span>
          {' '}wird übertragen, sobald du unten bestätigst.
        </p>
      )}

      <button
        type="button"
        onClick={submit}
        disabled={!enough || busy}
        className="btn btn-primary btn-lg mt-4 w-full"
      >
        {busy ? 'Speichere …' : method === 'card' ? 'Bezahlung bestätigen' : 'Bezahlung abschließen'}
      </button>
    </BottomSheet>
  );
}

// -------------------------------------------------------------
// ReceiptSheet (Bildschirm-Bon)
// -------------------------------------------------------------

interface ReceiptSheetProps {
  receipt: Receipt;
  onClose: () => void;
}

function ReceiptSheet({ receipt, onClose }: ReceiptSheetProps) {
  const [voiding, setVoiding] = useState(false);

  const onVoid = async () => {
    if (!window.confirm('Diesen Bon wirklich stornieren?')) return;
    setVoiding(true);
    try {
      await voidReceipt(receipt.id);
      onClose();
      alert('Bon storniert — Bestand wurde wiederhergestellt.');
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Storno fehlgeschlagen.');
    } finally {
      setVoiding(false);
    }
  };

  const paymentLabel: Record<typeof receipt.payment_method, string> = {
    cash: 'Bargeld',
    card: 'Karte',
    mixed: 'Gemischt',
  };

  return (
    <BottomSheet
      open
      onClose={onClose}
      title={`Bon ${receipt.receipt_number}`}
      maxHeight="92vh"
    >
      <div className="rounded-xl border border-[color:var(--border-strong)] bg-[color:var(--bg-page)] p-3 text-sm">
        <div className="flex justify-between">
          <span>Datum</span>
          <span>{new Date(receipt.created_at).toLocaleString('de-DE')}</span>
        </div>
        <div className="flex justify-between">
          <span>Zahlung</span>
          <span>{paymentLabel[receipt.payment_method]}</span>
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
      </div>

      <ul className="mt-4 space-y-1 font-mono text-sm">
        {receipt.lines.map((l) => (
          <li key={l.id} className="flex justify-between gap-2">
            <span className="flex-1 truncate">
              {l.quantity}× {l.name_snapshot}
              {l.kind === 'deposit' && (
                <span className="ml-1 text-ink-400">(Pfand)</span>
              )}
            </span>
            <span className="shrink-0">{formatPriceCents(l.line_total_cents)}</span>
          </li>
        ))}
      </ul>

      <div className="mt-4 flex items-center justify-between border-t-2 border-dashed border-[color:var(--border-strong)] pt-3 text-lg font-bold">
        <span>Summe</span>
        <span>{formatPriceCents(receipt.total_cents)}</span>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2">
        <button type="button" onClick={onClose} className="btn btn-secondary">
          Schließen
        </button>
        <button
          type="button"
          onClick={onVoid}
          disabled={voiding || receipt.kind !== 'sale'}
          className="btn btn-danger"
          title={receipt.kind !== 'sale' ? 'Nur Verkauf-Bons koennen storniert werden' : ''}
        >
          {voiding ? 'Storniere …' : 'Stornieren'}
        </button>
      </div>
    </BottomSheet>
  );
}
