/**
 * Cart-Store fuer die Kasse (POS).
 *
 * Persistenz: localStorage, damit ein versehentliches Schliessen
 * des Tabs oder ein Pi-Reboot die angefangene Bestellung nicht
 * verliert.
 *
 * Was NICHT hier lebt: abgeschlossene Bons. Die gehen raus zum
 * Backend (via ``useCartStore().commit()`` -> API) und werden
 * dort gespeichert + in Dexie repliziert (siehe receipts-Tabelle).
 *
 * Aufbau:
 *   Eine Cart = eine "Transaktion" = eine Liste von Lines + Total.
 *   Lines duerfen mehrfach vorkommen (z.B. 2x Red Bull + 1x Cola).
 *   Beim Hinzufuegen wird geprueft, ob das Produkt schon in der
 *   Liste ist — dann wird nur die Menge erhoeht.
 */
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import type { Product } from '@/types/api';
import { newUuid } from '@/utils/uuid';

export interface CartLine {
  /** Eindeutige Line-ID innerhalb des Carts */
  id: string;
  /** Produkt-ID oder null fuer deposit-only / manuelle Zeilen */
  productId: number | null;
  /** Snapshot — bleibt sichtbar auch wenn Produkt spaeter umbenannt wird */
  nameSnapshot: string;
  unitSnapshot: string;
  /** Decimal als string (fuer kg/g/ml-Mengen) */
  quantity: string;
  /** Einzelpreis in Cent (int) */
  unitPriceCents: number;
  /** Pfand-Cents pro Stueck (0 wenn keins) */
  depositCents: number;
  /** 'sale' | 'deposit' — im Cart nur diese zwei; rest macht das Backend */
  kind: 'sale' | 'deposit';
  /** Hex-Farbe des Produkts (f\u00fcr UI) */
  colorTag: string;
}

interface CartState {
  lines: CartLine[];
  /** Client-Op-UUID pro Checkout — wird fuer Idempotenz beim POST gebraucht */
  checkoutClientOpId: string | null;
  addProduct: (product: Product, qty?: string) => void;
  addDepositOnly: (product: Product, qty?: string) => void;
  setQuantity: (lineId: string, qty: string) => void;
  removeLine: (lineId: string) => void;
  clear: () => void;
  totalCents: () => number;
  totalDepositCents: () => number;
  grandTotalCents: () => number;
  newCheckoutOpId: () => string;
}

export const useCartStore = create<CartState>()(
  persist(
    (set, get) => ({
      lines: [],
      checkoutClientOpId: null,

      addProduct: (product, qty = '1') => {
        // Fallback: wenn sell_price_cents fehlt (alter Cache), aus
        // sell_price ableiten. Spart eine Cache-Migration.
        const unitPriceCents =
          product.sell_price_cents ??
          Math.round(parseFloat(product.sell_price) * 100);
        const existing = get().lines.find(
          (l) => l.productId === product.id && l.kind === 'sale'
        );
        if (existing) {
          // Menge erhoehen
          const newQty = (
            parseFloat(existing.quantity.replace(',', '.')) +
            parseFloat(qty.replace(',', '.'))
          ).toString().replace('.', ',');
          set({
            lines: get().lines.map((l) =>
              l.id === existing.id ? { ...l, quantity: newQty } : l
            ),
          });
        } else {
          const saleLine: CartLine = {
            id: newUuid(),
            productId: product.id,
            nameSnapshot: product.name,
            unitSnapshot: product.unit,
            quantity: qty,
            unitPriceCents,
            depositCents: product.deposit_cents,
            kind: 'sale',
            colorTag: product.color_tag,
          };
          const lines: CartLine[] = [saleLine];
          // Pfand auto-hinzufuegen, falls Produkt Pfand hat
          if (product.deposit_cents > 0) {
            lines.push({
              id: newUuid(),
              productId: product.id,
              nameSnapshot: 'Pfand',
              unitSnapshot: product.unit,
              quantity: qty,
              unitPriceCents: product.deposit_cents,
              depositCents: product.deposit_cents,
              kind: 'deposit',
              colorTag: '#94a3b8',
            });
          }
          set({ lines: [...get().lines, ...lines] });
        }
      },

      addDepositOnly: (product, qty = '1') => {
        if (product.deposit_cents <= 0) return;
        set({
          lines: [
            ...get().lines,
            {
              id: newUuid(),
              productId: product.id,
              nameSnapshot: 'Pfand',
              unitSnapshot: product.unit,
              quantity: qty,
              unitPriceCents: product.deposit_cents,
              depositCents: product.deposit_cents,
              kind: 'deposit',
              colorTag: '#94a3b8',
            },
          ],
        });
      },

      setQuantity: (lineId, qty) => {
        set({
          lines: get().lines.map((l) =>
            l.id === lineId ? { ...l, quantity: qty } : l
          ),
        });
      },

      removeLine: (lineId) => {
        set({ lines: get().lines.filter((l) => l.id !== lineId) });
      },

      clear: () => set({ lines: [], checkoutClientOpId: null }),

      totalCents: () => {
        return get()
          .lines.filter((l) => l.kind === 'sale')
          .reduce((sum, l) => {
            const q = parseFloat(l.quantity.replace(',', '.')) || 0;
            return sum + Math.round(q * l.unitPriceCents);
          }, 0);
      },

      totalDepositCents: () => {
        return get()
          .lines.filter((l) => l.kind === 'deposit')
          .reduce((sum, l) => {
            const q = parseFloat(l.quantity.replace(',', '.')) || 0;
            return sum + Math.round(q * l.unitPriceCents);
          }, 0);
      },

      grandTotalCents: () => get().totalCents() + get().totalDepositCents(),

      newCheckoutOpId: () => {
        const id = newUuid();
        set({ checkoutClientOpId: id });
        return id;
      },
    }),
    {
      name: 'markt-pilot:cart',
      storage: createJSONStorage(() => localStorage),
      // checkoutClientOpId nicht persistieren — frische UUID pro Session
      partialize: (state) => ({ lines: state.lines }) as CartState,
    }
  )
);
