import { useEffect, useMemo, useState } from 'react';
import { Plus, TrendingDown, CalendarClock, Boxes, Euro } from 'lucide-react';
import { BottomSheet } from '@/components/BottomSheet';
import { useMarketData, useStockKpis } from '@/hooks/useData';
import { useAppStore } from '@/store';
import { syncOutboxOnce } from '@/hooks/useOutboxSync';
import { cacheProducts, cacheMovements, enqueueOutbox } from '@/db/dexie';
import { createStockMovement, listProducts } from '@/api/client';
import { refreshOutboxCountNow } from '@/hooks/useOutboxSync';
import { formatDate, formatPrice, formatQty } from '@/utils/format';
import type { Product, StockReason } from '@/types/api';

export function InventoryPage() {
  const { products, movements, refresh } = useMarketData();
  const { low, expiring } = useStockKpis();
  const isOnline = useAppStore((s) => s.isOnline);

  const [tab, setTab] = useState<'overview' | 'movements'>('overview');
  const [sheet, setSheet] = useState<null | 'in' | { product: Product }>(null);
  const [submitting, setSubmitting] = useState(false);
  const [qty, setQty] = useState('');
  const [reference, setReference] = useState('');
  const [productId, setProductId] = useState<number | ''>('');
  const [reason, setReason] = useState<StockReason>('purchase');

  const totalProducts = products.filter((p) => p.is_active).length;
  const totalValue = useMemo(
    () =>
      products
        .filter((p) => p.is_active)
        .reduce((acc, p) => acc + parseFloat(p.sell_price) * parseFloat(p.stock_quantity), 0),
    [products],
  );

  const onSubmitMovement = async () => {
    const change = parseFloat(qty.replace(',', '.'));
    if (!isFinite(change) || change === 0) return;
    let pid: number | null = null;
    if (sheet === 'in') {
      if (productId === '') return;
      pid = Number(productId);
    } else if (sheet && typeof sheet === 'object') {
      pid = sheet.product.id;
    }
    if (pid === null) return;
    const sign = sheet === 'in' ? Math.abs(change) : change;
    setSubmitting(true);
    try {
      const payload = { product_id: pid, change: sign, reason, reference: reference.trim() || undefined };
      if (!isOnline) {
        await enqueueOutbox({ kind: 'stock.movement', payload });
        await refreshOutboxCountNow();
      } else {
        await createStockMovement(payload);
        const fresh = await listProducts({ limit: 500 });
        await cacheProducts(fresh.items);
      }
      setQty('');
      setReference('');
      setProductId('');
      setSheet(null);
      await syncOutboxOnce().catch(() => undefined);
      await refresh();
    } finally {
      setSubmitting(false);
    }
  };

  useEffect(() => {
    if (sheet && typeof sheet === 'object') {
      setProductId(sheet.product.id);
      setReason('purchase');
    } else if (sheet === 'in') {
      setProductId('');
    }
  }, [sheet]);

  // refresh movements cache after successful movement
  useEffect(() => {
    if (movements.length > 0) cacheMovements(movements).catch(() => undefined);
  }, [movements]);

  return (
    <div className="px-4 pt-3 space-y-3">
      <div className="grid grid-cols-2 gap-2">
        <Kpi icon={<Boxes size={18} />} label="Produkte" value={String(totalProducts)} />
        <Kpi
          icon={<Euro size={18} />}
          label="Lagerwert"
          value={formatPrice(totalValue.toFixed(2))}
        />
        <Kpi
          icon={<TrendingDown size={18} />}
          label="Niedriger Bestand"
          value={String(low)}
          tone="warn"
        />
        <Kpi
          icon={<CalendarClock size={18} />}
          label="Läuft bald ab"
          value={String(expiring)}
          tone="warn"
        />
      </div>

      <div className="flex gap-2 border-b border-gray-200">
        <button
          type="button"
          className={`px-3 py-2 text-sm font-semibold ${tab === 'overview' ? 'text-brand-700 border-b-2 border-brand-600' : 'text-ink-500'}`}
          onClick={() => setTab('overview')}
        >
          Übersicht
        </button>
        <button
          type="button"
          className={`px-3 py-2 text-sm font-semibold ${tab === 'movements' ? 'text-brand-700 border-b-2 border-brand-600' : 'text-ink-500'}`}
          onClick={() => setTab('movements')}
        >
          Aktuelle Bewegungen
        </button>
      </div>

      {tab === 'overview' && (
        <div className="space-y-2">
          {products
            .filter((p) => p.is_active)
            .sort((a, b) => parseFloat(a.stock_quantity) - parseFloat(b.stock_quantity))
            .slice(0, 8)
            .map((p) => {
              const stock = parseFloat(p.stock_quantity);
              const min = parseFloat(p.min_stock_level);
              const lowState = min > 0 && stock < min;
              return (
                <button
                  key={p.id}
                  type="button"
                  className="card flex w-full items-center gap-3 p-3 text-left active:bg-gray-50"
                  onClick={() => setSheet({ product: p })}
                >
                  <span className="block h-10 w-1.5 rounded-full" style={{ backgroundColor: p.color_tag }} />
                  <div className="min-w-0 flex-1">
                    <p className="font-semibold truncate">{p.name}</p>
                    <p className="text-xs text-ink-500">
                      {p.unit} · Mindest {formatQty(p.min_stock_level)}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className={`text-lg font-bold ${lowState ? 'text-red-600' : 'text-ink-900'}`}>
                      {formatQty(p.stock_quantity)}
                    </p>
                    {lowState && <p className="text-xs text-red-600 font-semibold">niedrig</p>}
                  </div>
                </button>
              );
            })}
        </div>
      )}

      {tab === 'movements' && (
        <ul className="space-y-2">
          {movements.length === 0 && (
            <li className="card p-6 text-center text-ink-500">Keine Bewegungen bisher.</li>
          )}
          {movements.map((m) => {
            const prod = products.find((p) => p.id === m.product_id);
            const sign = parseFloat(m.change) >= 0 ? '+' : '';
            return (
              <li key={m.id} className="card flex items-center gap-3 p-3">
                <span
                  className={`inline-flex h-8 w-8 items-center justify-center rounded-full text-sm font-bold ${
                    parseFloat(m.change) >= 0 ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'
                  }`}
                >
                  {sign}
                  {parseFloat(m.change).toFixed(2).replace(/\.00$/, '')}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="font-medium truncate">{prod?.name ?? `Produkt #${m.product_id}`}</p>
                  <p className="text-xs text-ink-500">
                    {labelReason(m.reason)} · {formatDate(m.created_at)}
                  </p>
                </div>
                {m.reference && <span className="text-xs text-ink-500 truncate max-w-[40%]">{m.reference}</span>}
              </li>
            );
          })}
        </ul>
      )}

      <button
        type="button"
        onClick={() => setSheet('in')}
        className="btn-primary w-full"
      >
        <Plus size={18} className="inline mr-1" /> Wareneingang erfassen
      </button>

      <BottomSheet
        open={sheet !== null}
        onClose={() => setSheet(null)}
        title={sheet === 'in' ? 'Wareneingang' : 'Bestand anpassen'}
      >
        <div className="space-y-3">
          {sheet === 'in' && (
            <div>
              <label className="label" htmlFor="prod">Produkt</label>
              <select
                id="prod"
                className="input"
                value={productId}
                onChange={(e) => setProductId(e.target.value ? Number(e.target.value) : '')}
              >
                <option value="">— Produkt wählen —</option>
                {products.filter((p) => p.is_active).map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </div>
          )}
          {sheet && typeof sheet === 'object' && (
            <p className="rounded-xl bg-gray-50 p-3 text-sm">
              <span className="font-semibold">{sheet.product.name}</span> · aktuell{' '}
              {formatQty(sheet.product.stock_quantity)} {sheet.product.unit}
            </p>
          )}
          <div>
            <label className="label" htmlFor="qty">Menge (positiv = Zugang, negativ = Abgang)</label>
            <input
              id="qty"
              className="input"
              inputMode="decimal"
              placeholder="z.B. 10"
              value={qty}
              onChange={(e) => setQty(e.target.value)}
            />
          </div>
          <div>
            <label className="label" htmlFor="reason">Grund</label>
            <select id="reason" className="input" value={reason} onChange={(e) => setReason(e.target.value as StockReason)}>
              <option value="purchase">Wareneingang</option>
              <option value="sale">Verkauf</option>
              <option value="adjustment">Korrektur</option>
              <option value="waste">Verlust / Müll</option>
              <option value="return">Retoure</option>
            </select>
          </div>
          <div>
            <label className="label" htmlFor="ref">Referenz / Notiz</label>
            <input
              id="ref"
              className="input"
              placeholder="optional"
              value={reference}
              onChange={(e) => setReference(e.target.value)}
            />
          </div>
          <button
            type="button"
            disabled={submitting}
            onClick={onSubmitMovement}
            className="btn-primary w-full"
          >
            {submitting ? 'Speichern …' : 'Buchen'}
          </button>
        </div>
      </BottomSheet>
    </div>
  );
}

function Kpi({
  icon,
  label,
  value,
  tone,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  tone?: 'warn';
}) {
  return (
    <div
      className={`card p-3 ${tone === 'warn' ? 'border-amber-200 bg-amber-50' : ''}`}
    >
      <div className="flex items-center gap-2 text-ink-600">
        {icon}
        <span className="text-xs font-medium uppercase tracking-wide">{label}</span>
      </div>
      <p className={`mt-1 text-2xl font-bold ${tone === 'warn' ? 'text-amber-800' : 'text-ink-900'}`}>{value}</p>
    </div>
  );
}

function labelReason(r: string): string {
  switch (r) {
    case 'purchase': return 'Wareneingang';
    case 'sale': return 'Verkauf';
    case 'adjustment': return 'Korrektur';
    case 'waste': return 'Verlust';
    case 'return': return 'Retoure';
    default: return r;
  }
}