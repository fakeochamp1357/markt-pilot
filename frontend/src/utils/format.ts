import type { Product } from '@/types/api';

/** Formatiert einen Decimal-String in eine deutsche EUR-Anzeige. */
export function formatPrice(value: string | number | null | undefined, currency = '€'): string {
  if (value === null || value === undefined || value === '') return '—';
  const num = typeof value === 'string' ? parseFloat(value) : value;
  if (!isFinite(num)) return '—';
  // Tausender-Punkt + Komma als Dezimaltrennzeichen
  const fixed = num.toFixed(2);
  const [intPart, decPart] = fixed.split('.');
  const intWithSep = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  return `${intWithSep},${decPart} ${currency}`.replace('€', '€');
}

/** Formatiert einen Decimal-String als kompakte Zahl (z.B. 12,5). */
export function formatQty(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—';
  const num = typeof value === 'string' ? parseFloat(value) : value;
  if (!isFinite(num)) return '—';
  return num.toLocaleString('de-DE', { maximumFractionDigits: 3 });
}

/** Formatiert ein ISO-Datum (YYYY-MM-DD) zu deutscher Kurzform. */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' });
  } catch {
    return iso;
  }
}

/** Berechnet Marge in % und absolut. */
export function computeMargin(cost: string | number, sell: string | number): { pct: number; eur: number } {
  const c = typeof cost === 'string' ? parseFloat(cost) : cost;
  const s = typeof sell === 'string' ? parseFloat(sell) : sell;
  if (!isFinite(c) || !isFinite(s) || c <= 0) return { pct: 0, eur: s - c };
  return { pct: ((s - c) / c) * 100, eur: s - c };
}

/** Heuristik für Stock-Warnung. */
export function stockState(product: Pick<Product, 'stock_quantity' | 'min_stock_level'>): 'low' | 'ok' {
  const stock = parseFloat(product.stock_quantity);
  const min = parseFloat(product.min_stock_level);
  if (!isFinite(stock) || !isFinite(min) || min <= 0) return 'ok';
  return stock < min ? 'low' : 'ok';
}

/** Erzeugt eine UUID-v4-ähnliche ID (für Outbox-Local-IDs). */
export function uid(): string {
  return 'x'.repeat(8).replace(/x/g, () => Math.floor(Math.random() * 16).toString(16));
}