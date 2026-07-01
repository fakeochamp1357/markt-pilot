import { useEffect, useRef, useState } from 'react';
import { Camera, CameraOff, KeyboardIcon, ShoppingCart, Check, Search } from 'lucide-react';
import { BrowserMultiFormatReader, type IScannerControls } from '@zxing/browser';
import { BottomSheet } from '@/components/BottomSheet';
import { ProductForm } from '@/components/ProductForm';
import { useMarketData } from '@/hooks/useData';
import { useAppStore } from '@/store';
import { useCartStore } from '@/store/cart';
import { getProductByBarcode } from '@/api/client';
import { cacheProducts, enqueueOutbox } from '@/db/dexie';
import { createProduct, listProducts } from '@/api/client';
import { refreshOutboxCountNow } from '@/hooks/useOutboxSync';
import { formatPriceCents } from '@/utils/format';
import type { Product } from '@/types/api';

export function ScannerPage() {
  const { categories, refresh } = useMarketData();
  const isOnline = useAppStore((s) => s.isOnline);
  const addToCart = useCartStore((s) => s.addProduct);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const controlsRef = useRef<IScannerControls | null>(null);
  const [active, setActive] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastHit, setLastHit] = useState<string | null>(null);
  const [manual, setManual] = useState(false);
  const [manualValue, setManualValue] = useState('');
  const [foundProduct, setFoundProduct] = useState<Product | null>(null);
  const [addedFlash, setAddedFlash] = useState(false);
  const [prefillBarcode, setPrefillBarcode] = useState<string | null>(null);
  const [showNew, setShowNew] = useState(false);

  const start = async () => {
    setError(null);
    try {
      const reader = new BrowserMultiFormatReader();
      if (!videoRef.current) return;
      const controls = await reader.decodeFromVideoDevice(undefined, videoRef.current, (result, _err) => {
        if (result) {
          const text = result.getText();
          setLastHit(text);
          void lookup(text);
        }
      });
      controlsRef.current = controls;
      setActive(true);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Kamera nicht verfügbar';
      setError(msg);
      setActive(false);
    }
  };

  const stop = () => {
    controlsRef.current?.stop();
    controlsRef.current = null;
    setActive(false);
  };

  useEffect(() => {
    return () => controlsRef.current?.stop();
  }, []);

  const lookup = async (code: string) => {
    try {
      const product = await getProductByBarcode(code);
      setFoundProduct(product);
      // Kamera weiterlaufen lassen — Cashier kann direkt weiter scannen.
    } catch {
      // Miss
      setPrefillBarcode(code);
      setShowNew(true);
    }
  };

  const onManualSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!manualValue.trim()) return;
    void lookup(manualValue.trim());
    setManualValue('');
    setManual(false);
  };

  const onAddToCart = (p: Product) => {
    addToCart(p, '1');
    setFoundProduct(null);
    setLastHit(p.barcode ?? null);
    setAddedFlash(true);
    window.setTimeout(() => setAddedFlash(false), 1500);
  };

  const onProductCreated = async (payload: Partial<Product>) => {
    if (!isOnline) {
      await enqueueOutbox({ kind: 'product.create', payload });
      await refreshOutboxCountNow();
    } else {
      const created = await createProduct(payload);
      const fresh = await listProducts({ limit: 500 });
      await cacheProducts(fresh.items);
      // Direkt in den Warenkorb, damit der Cashier nicht zur Kasse muss.
      addToCart(created, '1');
    }
    setShowNew(false);
    setPrefillBarcode(null);
    await refresh();
  };

  return (
    <div className="px-4 pt-3 space-y-3">
      <div className="relative aspect-[4/3] w-full overflow-hidden rounded-2xl bg-black">
        <video
          ref={videoRef}
          className="h-full w-full object-cover"
          autoPlay
          muted
          playsInline
        />
        {/* Viewfinder overlay */}
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <div className="relative h-2/5 w-3/4">
            <span className="absolute left-0 top-0 h-8 w-8 border-l-4 border-t-4 border-brand-500 rounded-tl-lg" />
            <span className="absolute right-0 top-0 h-8 w-8 border-r-4 border-t-4 border-brand-500 rounded-tr-lg" />
            <span className="absolute left-0 bottom-0 h-8 w-8 border-l-4 border-b-4 border-brand-500 rounded-bl-lg" />
            <span className="absolute right-0 bottom-0 h-8 w-8 border-r-4 border-b-4 border-brand-500 rounded-br-lg" />
            <div className="absolute inset-x-4 top-1/2 h-0.5 bg-red-500 animate-pulse" />
          </div>
        </div>
        {!active && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/70 text-white p-4 text-center">
            {error ? (
              <>
                <CameraOff size={48} className="mb-2 opacity-70" />
                <p className="font-semibold">Kamera nicht verfügbar</p>
                <p className="text-xs opacity-80 mt-1">{error}</p>
                <p className="text-xs opacity-80 mt-3">
                  Du kannst unten den Barcode manuell eingeben.
                </p>
              </>
            ) : (
              <>
                <Camera size={48} className="mb-2 opacity-70" />
                <p className="font-semibold">Bereit zum Scannen</p>
                <p className="text-xs opacity-80 mt-1">
                  Scannt direkt in den Warenkorb.
                </p>
              </>
            )}
          </div>
        )}
        {addedFlash && (
          <div
            className="pointer-events-none absolute inset-0 flex items-center justify-center bg-emerald-500/30 transition-opacity"
            aria-live="polite"
          >
            <Check size={64} className="text-white drop-shadow-md" />
          </div>
        )}
      </div>

      <div className="flex gap-2">
        {active ? (
          <button type="button" onClick={stop} className="btn-secondary flex-1">
            <CameraOff size={18} /> Kamera stoppen
          </button>
        ) : (
          <button type="button" onClick={start} className="btn-primary flex-1">
            <Camera size={18} /> Kamera starten
          </button>
        )}
        <button type="button" onClick={() => setManual((v) => !v)} className="btn-secondary">
          <KeyboardIcon size={18} />
        </button>
      </div>

      {manual && (
        <form onSubmit={onManualSubmit} className="card p-3 space-y-2">
          <label className="label" htmlFor="barcode-input">Barcode manuell eingeben</label>
          <input
            id="barcode-input"
            className="input"
            inputMode="numeric"
            placeholder="z.B. 4015001000008"
            value={manualValue}
            onChange={(e) => setManualValue(e.target.value)}
          />
          <button type="submit" className="btn btn-primary" disabled={!manualValue.trim()}>
            <Search size={16} />
            Suchen
          </button>
        </form>
      )}

      {lastHit && (
        <p className="text-xs text-ink-500">
          Letzter Scan: <span className="font-mono">{lastHit}</span>
        </p>
      )}

      <BottomSheet
        open={!!foundProduct}
        onClose={() => setFoundProduct(null)}
        title="Produkt gefunden"
      >
        {foundProduct && (
          <div className="space-y-3">
            <div className="rounded-xl bg-[color:var(--bg-page)] p-3">
              <p className="text-lg font-bold">{foundProduct.name}</p>
              <p className="text-sm text-[color:var(--text-secondary)]">
                {foundProduct.unit}
                {foundProduct.size_weight ? ` · ${foundProduct.size_weight}` : ''}
              </p>
              <p className="mt-2 text-2xl font-bold">{formatPriceCents(foundProduct.sell_price_cents)}</p>
              {foundProduct.deposit_cents > 0 && (
                <p className="mt-1 text-xs text-[color:var(--text-muted)]">
                  + {formatPriceCents(foundProduct.deposit_cents)} Pfand
                </p>
              )}
              <p className="mt-2 text-xs text-[color:var(--text-muted)]">
                Bestand: {foundProduct.stock_quantity}
              </p>
            </div>
            <button
              type="button"
              onClick={() => onAddToCart(foundProduct)}
            className="btn btn-primary"
          >
            <ShoppingCart size={16} />
            In den Warenkorb
          </button>
            <button
              type="button"
              onClick={() => setFoundProduct(null)}
              className="btn btn-ghost btn-sm w-full"
            >
              Überspringen
            </button>
          </div>
        )}
      </BottomSheet>

      <BottomSheet
        open={showNew}
        onClose={() => {
          setShowNew(false);
          setPrefillBarcode(null);
        }}
        title="Neues Produkt anlegen?"
        maxHeight="95vh"
      >
        <p className="text-sm text-[color:var(--text-secondary)] mb-3">
          Kein Produkt mit Barcode <span className="font-mono">{prefillBarcode}</span> gefunden.
          Lege es jetzt an:
        </p>
        <ProductForm
          defaultBarcode={prefillBarcode ?? undefined}
          categories={categories}
          onSubmit={onProductCreated}
          submitLabel="Anlegen &amp; in Warenkorb"
        />
      </BottomSheet>
    </div>
  );
}