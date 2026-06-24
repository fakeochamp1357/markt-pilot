import { useEffect, useMemo, useRef, useState } from 'react';
import { Plus, Search, SlidersHorizontal, ArrowUpDown, RefreshCcw, X } from 'lucide-react';
import { BottomSheet } from '@/components/BottomSheet';
import { ProductCard } from '@/components/ProductCard';
import { ProductForm } from '@/components/ProductForm';
import { StockAdjustSheet } from '@/components/StockAdjustSheet';
import { useMarketData } from '@/hooks/useData';
import { useAppStore } from '@/store';
import { syncOutboxOnce, refreshOutboxCountNow } from '@/hooks/useOutboxSync';
import {
  cacheProducts,
  enqueueOutbox,
} from '@/db/dexie';
import { createProduct, deleteProduct, listProducts, updateProduct } from '@/api/client';
import type { FilterKey, Product, SortKey } from '@/types/api';
import { formatDate, formatPrice } from '@/utils/format';

function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = window.setTimeout(() => setV(value), ms);
    return () => window.clearTimeout(t);
  }, [value, ms]);
  return v;
}

const SORTS: { key: SortKey; label: string }[] = [
  { key: 'name_asc', label: 'Name A → Z' },
  { key: 'name_desc', label: 'Name Z → A' },
  { key: 'price_asc', label: 'Preis aufsteigend' },
  { key: 'price_desc', label: 'Preis absteigend' },
  { key: 'newest', label: 'Neueste zuerst' },
  { key: 'expiring', label: 'Bald ablaufend' },
];

export function PreislistePage() {
  const { products, categories, fromCache, refresh } = useMarketData();
  const isOnline = useAppStore((s) => s.isOnline);
  const outboxCount = useAppStore((s) => s.outboxCount);

  const [search, setSearch] = useState('');
  const debouncedSearch = useDebounced(search, 250);
  const [filter, setFilter] = useState<FilterKey>('all');
  const [sort, setSort] = useState<SortKey>('name_asc');
  const [showSort, setShowSort] = useState(false);

  const [selected, setSelected] = useState<Product | null>(null);
  const [actionSheet, setActionSheet] = useState<Product | null>(null);
  const [editSheet, setEditSheet] = useState<Product | null | 'new'>(null);
  const [stockSheet, setStockSheet] = useState<Product | null>(null);

  const [refreshing, setRefreshing] = useState(false);

  const pullStart = useRef<{ y: number } | null>(null);
  const [pullDistance, setPullDistance] = useState(0);

  const onPullStart = (e: React.TouchEvent) => {
    if (window.scrollY > 0) return;
    pullStart.current = { y: e.touches[0].clientY };
  };
  const onPullMove = (e: React.TouchEvent) => {
    if (!pullStart.current) return;
    const dy = e.touches[0].clientY - pullStart.current.y;
    if (dy > 0 && dy < 200) setPullDistance(dy);
  };
  const onPullEnd = async () => {
    if (pullDistance > 80) {
      await onRefresh();
    }
    setPullDistance(0);
    pullStart.current = null;
  };

  const onRefresh = async () => {
    setRefreshing(true);
    if (isOnline) await syncOutboxOnce();
    await refresh();
    setRefreshing(false);
  };

  const filtered = useMemo<Product[]>(() => {
    const q = debouncedSearch.trim().toLowerCase();
    const today = new Date();
    const horizon = new Date();
    horizon.setDate(today.getDate() + 30);
    let list = products.filter((p) => p.is_active);
    if (q) {
      list = list.filter((p) => {
        const blob = `${p.name} ${p.barcode ?? ''} ${p.sku ?? ''}`.toLowerCase();
        return blob.includes(q);
      });
    }
    if (filter === 'low') {
      list = list.filter((p) => parseFloat(p.stock_quantity) < parseFloat(p.min_stock_level) && parseFloat(p.min_stock_level) > 0);
    } else if (filter === 'expiring') {
      list = list.filter((p) => {
        if (!p.expiry_date) return false;
        const d = new Date(p.expiry_date);
        return d <= horizon && d >= new Date('1900-01-01');
      });
    } else if (typeof filter === 'number') {
      list = list.filter((p) => p.category_id === filter);
    }
    list = [...list];
    switch (sort) {
      case 'name_asc':
        list.sort((a, b) => a.name.localeCompare(b.name, 'de'));
        break;
      case 'name_desc':
        list.sort((a, b) => b.name.localeCompare(a.name, 'de'));
        break;
      case 'price_asc':
        list.sort((a, b) => parseFloat(a.sell_price) - parseFloat(b.sell_price));
        break;
      case 'price_desc':
        list.sort((a, b) => parseFloat(b.sell_price) - parseFloat(a.sell_price));
        break;
      case 'newest':
        list.sort((a, b) => (a.created_at < b.created_at ? 1 : -1));
        break;
      case 'expiring':
        list.sort((a, b) => {
          if (!a.expiry_date && !b.expiry_date) return 0;
          if (!a.expiry_date) return 1;
          if (!b.expiry_date) return -1;
          return a.expiry_date.localeCompare(b.expiry_date);
        });
        break;
    }
    return list;
  }, [products, debouncedSearch, filter, sort]);

  const submitProduct = async (payload: Partial<Product>) => {
    if (editSheet === 'new') {
      if (!isOnline) {
        // Offline → in Outbox; erzeuge eine Platzhalter-ID für UI.
        await enqueueOutbox({ kind: 'product.create', payload });
        await refreshOutboxCountNow();
        // Optimistic: ins Cache schreiben (mit fake-id), wird später überschrieben.
        const fakeId = -Date.now();
        await cacheProducts([{ ...(payload as Product), id: fakeId, created_at: new Date().toISOString(), updated_at: new Date().toISOString(), version: 1 }]);
      } else {
        const created = await createProduct(payload);
        await cacheProducts([created]);
      }
    } else if (editSheet && typeof editSheet === 'object') {
      if (!isOnline) {
        await enqueueOutbox({ kind: 'product.update', id: editSheet.id, payload });
        await refreshOutboxCountNow();
        await cacheProducts([{ ...editSheet, ...payload } as Product]);
      } else {
        const updated = await updateProduct(editSheet.id, payload);
        await cacheProducts([updated]);
      }
    }
    setEditSheet(null);
    await refresh();
  };

  const onDelete = async () => {
    if (!actionSheet) return;
    if (!window.confirm(`Produkt "${actionSheet.name}" wirklich deaktivieren?`)) return;
    if (!isOnline) {
      await enqueueOutbox({ kind: 'product.delete', id: actionSheet.id });
      await refreshOutboxCountNow();
      await cacheProducts([{ ...actionSheet, is_active: false }]);
    } else {
      await deleteProduct(actionSheet.id);
    }
    setActionSheet(null);
    await refresh();
  };

  const onStock = async (payload: { product_id: number; change: number; reason: 'purchase' | 'sale' | 'adjustment' | 'waste' | 'return'; reference?: string }) => {
    if (!isOnline) {
      await enqueueOutbox({ kind: 'stock.movement', payload });
      await refreshOutboxCountNow();
    } else {
      const { createStockMovement } = await import('@/api/client');
      await createStockMovement(payload);
      // Produkt-Bestand lokal aktualisieren
      const fresh = await listProducts({ limit: 500 });
      await cacheProducts(fresh.items);
    }
    setStockSheet(null);
    await refresh();
  };

  return (
    <div
      className="px-4 pt-3"
      onTouchStart={onPullStart}
      onTouchMove={onPullMove}
      onTouchEnd={onPullEnd}
    >
      <div className="relative">
        <Search size={18} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-500" />
        <input
          className="input pl-9 pr-9"
          placeholder="Produkt suchen..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Produkt suchen"
        />
        {search && (
          <button
            type="button"
            onClick={() => setSearch('')}
            className="absolute right-2 top-1/2 -translate-y-1/2 tap rounded-full text-ink-500 hover:bg-gray-100"
            aria-label="Suche löschen"
          >
            <X size={18} />
          </button>
        )}
      </div>

      <div className="mt-3 flex items-center gap-2">
        <button
          type="button"
          onClick={() => setShowSort(true)}
          className="chip"
          aria-label="Sortieren"
        >
          <SlidersHorizontal size={14} /> Filter
        </button>
        <button
          type="button"
          onClick={() => setShowSort(true)}
          className="chip"
          aria-label="Sortieren"
        >
          <ArrowUpDown size={14} /> Sortieren
        </button>
        <div className="ml-auto text-xs text-ink-500">
          {refreshing && <span className="inline-flex items-center gap-1"><RefreshCcw size={12} className="animate-spin" /> aktualisiere …</span>}
          {!refreshing && fromCache && <span>aus Cache</span>}
        </div>
      </div>

      <div className="mt-3 flex gap-2 overflow-x-auto pb-1 -mx-1 px-1">
        <button
          type="button"
          className={`chip ${filter === 'all' ? 'chip-active' : ''}`}
          onClick={() => setFilter('all')}
        >
          Alle
        </button>
        <button
          type="button"
          className={`chip ${filter === 'low' ? 'chip-active' : ''}`}
          onClick={() => setFilter('low')}
        >
          Niedriger Bestand
        </button>
        <button
          type="button"
          className={`chip ${filter === 'expiring' ? 'chip-active' : ''}`}
          onClick={() => setFilter('expiring')}
        >
          Läuft bald ab
        </button>
        {categories.map((c) => (
          <button
            key={c.id}
            type="button"
            className={`chip ${filter === c.id ? 'chip-active' : ''}`}
            onClick={() => setFilter(c.id)}
            style={filter === c.id ? { backgroundColor: c.color, borderColor: c.color } : {}}
          >
            <span aria-hidden className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: c.color }} />
            {c.name}
          </button>
        ))}
      </div>

      <div
        className="text-center text-xs text-brand-700 select-none transition-opacity"
        style={{ opacity: pullDistance / 80, height: pullDistance > 0 ? 24 : 0 }}
      >
        {pullDistance > 80 ? 'Loslassen zum Aktualisieren' : 'Ziehen zum Aktualisieren'}
      </div>

      <ul className="mt-2 space-y-2">
        {filtered.length === 0 && (
          <li className="card p-6 text-center text-ink-500">
            Keine Produkte gefunden.
          </li>
        )}
        {filtered.map((p) => (
          <li key={p.id}>
            <ProductCard
              product={p}
              categories={categories}
              onClick={() => setActionSheet(p)}
            />
          </li>
        ))}
      </ul>

      <button
        type="button"
        onClick={() => setEditSheet('new')}
        className="fixed bottom-24 right-4 z-30 inline-flex items-center justify-center h-14 w-14 rounded-full bg-brand-600 text-white shadow-xl hover:bg-brand-700 active:bg-brand-700"
        aria-label="Neues Produkt anlegen"
      >
        <Plus size={28} />
      </button>

      {/* Bottom-Sheet: Product Actions */}
      <BottomSheet
        open={!!actionSheet}
        onClose={() => setActionSheet(null)}
        title={actionSheet?.name}
      >
        {actionSheet && (
          <div className="space-y-3">
            <div className="rounded-xl bg-gray-50 p-3">
              <div className="flex items-center justify-between">
                <span className="text-ink-600">Verkaufspreis</span>
                <span className="price-big">{formatPrice(actionSheet.sell_price)}</span>
              </div>
              <div className="mt-1 flex items-center justify-between text-sm">
                <span className="text-ink-600">Bestand</span>
                <span className="font-semibold">
                  {actionSheet.stock_quantity} {actionSheet.unit}
                </span>
              </div>
              {actionSheet.expiry_date && (
                <div className="mt-1 flex items-center justify-between text-sm">
                  <span className="text-ink-600">MHD</span>
                  <span>{formatDate(actionSheet.expiry_date)}</span>
                </div>
              )}
              {actionSheet.barcode && (
                <div className="mt-1 flex items-center justify-between text-sm">
                  <span className="text-ink-600">Barcode</span>
                  <span className="font-mono">{actionSheet.barcode}</span>
                </div>
              )}
            </div>
            <div className="grid grid-cols-3 gap-2">
              <button
                type="button"
                className="btn-secondary"
                onClick={() => {
                  setEditSheet(actionSheet);
                  setActionSheet(null);
                }}
              >
                Bearbeiten
              </button>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => {
                  setStockSheet(actionSheet);
                  setActionSheet(null);
                }}
              >
                Bestand
              </button>
              <button
                type="button"
                className="btn-danger"
                onClick={onDelete}
              >
                Löschen
              </button>
            </div>
            {outboxCount > 0 && (
              <p className="text-xs text-amber-700">
                Hinweis: {outboxCount} Änderung(en) werden synchronisiert, sobald du online bist.
              </p>
            )}
          </div>
        )}
      </BottomSheet>

      {/* Bottom-Sheet: Edit / New Product */}
      <BottomSheet
        open={editSheet !== null}
        onClose={() => setEditSheet(null)}
        title={editSheet === 'new' ? 'Neues Produkt' : 'Produkt bearbeiten'}
        maxHeight="95vh"
      >
        <ProductForm
          initial={editSheet && editSheet !== 'new' ? editSheet : undefined}
          categories={categories}
          onSubmit={submitProduct}
          submitLabel={editSheet === 'new' ? 'Anlegen' : 'Speichern'}
        />
      </BottomSheet>

      {/* Bottom-Sheet: Stock Adjustment */}
      <StockAdjustSheet
        open={!!stockSheet}
        product={stockSheet}
        onClose={() => setStockSheet(null)}
        onSubmit={onStock}
      />

      {/* Sort Sheet */}
      <BottomSheet open={showSort} onClose={() => setShowSort(false)} title="Sortieren">
        <ul className="space-y-1">
          {SORTS.map((s) => (
            <li key={s.key}>
              <button
                type="button"
                className={`w-full text-left px-3 py-3 rounded-xl ${sort === s.key ? 'bg-brand-50 text-brand-800 font-semibold' : 'hover:bg-gray-50'}`}
                onClick={() => {
                  setSort(s.key);
                  setShowSort(false);
                }}
              >
                {s.label}
              </button>
            </li>
          ))}
        </ul>
      </BottomSheet>
    </div>
  );
}