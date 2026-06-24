import { useEffect, useRef, useState } from 'react';
import { Camera, CameraOff, KeyboardIcon } from 'lucide-react';
import { BrowserMultiFormatReader, type IScannerControls } from '@zxing/browser';
import { BottomSheet } from '@/components/BottomSheet';
import { ProductForm } from '@/components/ProductForm';
import { useMarketData } from '@/hooks/useData';
import { useAppStore } from '@/store';
import { getProductByBarcode } from '@/api/client';
import { cacheProducts, enqueueOutbox } from '@/db/dexie';
import { createProduct, listProducts } from '@/api/client';
import { refreshOutboxCountNow } from '@/hooks/useOutboxSync';
import type { Product } from '@/types/api';

export function ScannerPage() {
  const { categories, refresh } = useMarketData();
  const isOnline = useAppStore((s) => s.isOnline);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const controlsRef = useRef<IScannerControls | null>(null);
  const [active, setActive] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastHit, setLastHit] = useState<string | null>(null);
  const [manual, setManual] = useState(false);
  const [manualValue, setManualValue] = useState('');
  const [foundProduct, setFoundProduct] = useState<Product | null>(null);
  const [prefillBarcode, setPrefillBarcode] = useState<string | null>(null);
  const [showNew, setShowNew] = useState(false);

  const start = async () => {
    setError(null);
    try {
      const reader = new BrowserMultiFormatReader();
      if (!videoRef.current) return;
      const controls = await reader.decodeFromVideoDevice(undefined, videoRef.current, (result, err) => {
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
      stop();
    } catch {
      // Miss
      stop();
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

  const onProductCreated = async (payload: Partial<Product>) => {
    if (!isOnline) {
      await enqueueOutbox({ kind: 'product.create', payload });
      await refreshOutboxCountNow();
    } else {
      await createProduct(payload);
    }
    const fresh = await listProducts({ limit: 500 });
    await cacheProducts(fresh.items);
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
                  Halte den Barcode in den Rahmen.
                </p>
              </>
            )}
          </div>
        )}
      </div>

      <div className="flex gap-2">
        {active ? (
          <button type="button" onClick={stop} className="btn-secondary flex-1">
            <CameraOff size={18} className="inline mr-1" /> Stop
          </button>
        ) : (
          <button type="button" onClick={start} className="btn-primary flex-1">
            <Camera size={18} className="inline mr-1" /> Kamera starten
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
          <button type="submit" className="btn-primary w-full" disabled={!manualValue.trim()}>
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
            <div className="rounded-xl bg-gray-50 p-3">
              <p className="text-lg font-bold">{foundProduct.name}</p>
              <p className="text-sm text-ink-600">{foundProduct.unit} · Menge {foundProduct.stock_quantity}</p>
              {foundProduct.barcode && (
                <p className="text-xs text-ink-500 mt-1 font-mono">{foundProduct.barcode}</p>
              )}
            </div>
            <button type="button" className="btn-primary w-full" onClick={() => setFoundProduct(null)}>
              Schließen
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
        <p className="text-sm text-ink-600 mb-3">
          Kein Produkt mit Barcode <span className="font-mono">{prefillBarcode}</span> gefunden.
          Lege es jetzt an:
        </p>
        <ProductForm
          defaultBarcode={prefillBarcode ?? undefined}
          categories={categories}
          onSubmit={onProductCreated}
          submitLabel="Anlegen"
        />
      </BottomSheet>
    </div>
  );
}