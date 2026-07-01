import { useEffect, useState } from 'react';
import {
  cacheCategories,
  cacheMovements,
  cacheProducts,
  readCachedCategories,
  readCachedMovements,
  readCachedProducts,
} from '@/db/dexie';
import {
  listCategories,
  listExpiring,
  listLowStock,
  listMovements,
  listProducts,
} from '@/api/client';
import type { Category, Product, StockMovement } from '@/types/api';
import { useAppStore } from '@/store';

interface DataState {
  products: Product[];
  categories: Category[];
  movements: StockMovement[];
  loading: boolean;
  fromCache: boolean;
  refresh: () => Promise<void>;
}

/**
 * Lade-Strategie:
 * 1) Cache first → instant render
 * 2) Background refresh, falls das Backend *eigentlich* erreichbar sein
 *    sollte (also nicht explizit "unreachable"). ``null`` heißt "noch
 *    nicht geprüft" → wir versuchen es einmal.
 */
function shouldTryNetwork(): boolean {
  const { backendReachable, isOnline } = useAppStore.getState();
  if (isOnline === false) return false;
  if (backendReachable === false) return false;
  return true;
}

export function useMarketData(): DataState {
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [movements, setMovements] = useState<StockMovement[]>([]);
  const [loading, setLoading] = useState(true);
  const [fromCache, setFromCache] = useState(false);

  const refresh = async () => {
    setLoading(true);
    // 1) Cache first (instant).
    const [cachedP, cachedC, cachedM] = await Promise.all([
      readCachedProducts(),
      readCachedCategories(),
      readCachedMovements(),
    ]);
    if (cachedP.length > 0) {
      setProducts(cachedP);
      setFromCache(true);
    }
    if (cachedC.length > 0) setCategories(cachedC);
    if (cachedM.length > 0) setMovements(cachedM);

    // 2) Background network refresh.
    if (shouldTryNetwork()) {
      try {
        const [prods, cats, movs] = await Promise.all([
          listProducts({ limit: 500 }),
          listCategories(),
          listMovements({ limit: 100 }),
        ]);
        await Promise.all([
          cacheProducts(prods.items),
          cacheCategories(cats),
          cacheMovements(movs.items),
        ]);
        setProducts(prods.items);
        setCategories(cats);
        setMovements(movs.items);
        setFromCache(false);
      } catch {
        // Network-Fehler → Cache bleibt sichtbar.
        setFromCache(true);
      }
    } else {
      setFromCache(true);
    }
    setLoading(false);
  };

  useEffect(() => {
    void refresh();
  }, []);

  return { products, categories, movements, loading, fromCache, refresh };
}

/** Ergänzende KPIs: low-stock + expiring. */
export function useStockKpis() {
  const [low, setLow] = useState(0);
  const [expiring, setExpiring] = useState(0);
  const refresh = async () => {
    if (!shouldTryNetwork()) return;
    try {
      const [l, e] = await Promise.all([listLowStock(), listExpiring(30)]);
      setLow(l.length);
      setExpiring(e.length);
    } catch {
      // ignore
    }
  };
  useEffect(() => {
    void refresh();
    const t = window.setInterval(refresh, 30000);
    return () => window.clearInterval(t);
  }, []);
  return { low, expiring, refresh };
}