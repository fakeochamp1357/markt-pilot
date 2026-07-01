import type { Product } from '@/types/api';

/** Formatiert einen Decimal-String in eine deutsche EUR-Anzeige. */
export function formatPrice(
  value: string | number | null | undefined,
  currency = '\u20AC'
): string {
  if (value === null || value === undefined || value === '') return '\u2014';
  const num = typeof value === 'string' ? parseFloat(value) : value;
  if (!isFinite(num)) return '\u2014';
  const fixed = num.toFixed(2);
  const [intPart, decPart] = fixed.split('.');
  const intWithSep = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  return `${intWithSep},${decPart} ${currency === '\u20AC' ? '\u20AC' : currency}`;
}

/** Formatiert Cent (int) in EUR-Anzeige. */
export function formatPriceCents(
  cents: number | null | undefined,
  currency = '\u20AC'
): string {
  if (cents === null || cents === undefined) return '\u2014';
  return formatPrice(cents / 100, currency);
}

/** Formatiert einen Decimal-String als kompakte Zahl (z.B. 12,5). */
export function formatQty(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '\u2014';
  const num = typeof value === 'string' ? parseFloat(value) : value;
  if (!isFinite(num)) return '\u2014';
  return num.toLocaleString('de-DE', { maximumFractionDigits: 3 });
}

/** Formatiert ein ISO-Datum (YYYY-MM-DD) zu deutscher Kurzform. */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleDateString('de-DE', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    });
  } catch {
    return iso;
  }
}

/** Berechnet Marge in % und absolut. */
export function computeMargin(
  cost: string | number,
  sell: string | number
): { pct: number; eur: number } {
  const c = typeof cost === 'string' ? parseFloat(cost) : cost;
  const s = typeof sell === 'string' ? parseFloat(sell) : sell;
  if (!isFinite(c) || !isFinite(s) || c <= 0) return { pct: 0, eur: s - c };
  return { pct: ((s - c) / c) * 100, eur: s - c };
}

/** Heuristik fuer Stock-Warnung. */
export function stockState(
  product: Pick<Product, 'stock_quantity' | 'min_stock_level'>
): 'low' | 'ok' {
  const stock = parseFloat(product.stock_quantity);
  const min = parseFloat(product.min_stock_level);
  if (!isFinite(stock) || !isFinite(min) || min <= 0) return 'ok';
  return stock < min ? 'low' : 'ok';
}
