import { useState } from 'react';
import { Save } from 'lucide-react';
import { BottomSheet } from './BottomSheet';
import type { Product, StockReason } from '@/types/api';
import { formatQty } from '@/utils/format';

const REASONS: { key: StockReason; label: string }[] = [
  { key: 'purchase', label: 'Wareneingang' },
  { key: 'sale', label: 'Verkauf' },
  { key: 'adjustment', label: 'Korrektur' },
  { key: 'waste', label: 'Verlust / Müll' },
  { key: 'return', label: 'Retoure' },
];

interface StockAdjustSheetProps {
  open: boolean;
  product: Product | null;
  onClose: () => void;
  onSubmit: (payload: { product_id: number; change: number; reason: StockReason; reference?: string }) => Promise<void>;
}

export function StockAdjustSheet({ open, product, onClose, onSubmit }: StockAdjustSheetProps) {
  const [delta, setDelta] = useState('');
  const [reason, setReason] = useState<StockReason>('purchase');
  const [reference, setReference] = useState('');
  const [submitting, setSubmitting] = useState(false);

  if (!product) return null;
  const parsed = parseFloat(delta.replace(',', '.'));
  const valid = isFinite(parsed) && parsed !== 0;

  const submit = async () => {
    if (!valid) return;
    setSubmitting(true);
    try {
      await onSubmit({
        product_id: product.id,
        change: parsed,
        reason,
        reference: reference.trim() || undefined,
      });
      setDelta('');
      setReference('');
      onClose();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <BottomSheet open={open} onClose={onClose} title="Bestand anpassen">
      <p className="text-sm text-ink-600 mb-3">
        <span className="font-semibold">{product.name}</span> · aktuell {formatQty(product.stock_quantity)} {product.unit}
      </p>
      <div className="space-y-3">
        <div>
          <label className="label" htmlFor="adj-delta">Änderung</label>
          <input
            id="adj-delta"
            className="input"
            inputMode="decimal"
            placeholder="z.B. +10 oder -2,5"
            value={delta}
            onChange={(e) => setDelta(e.target.value)}
          />
          <p className="mt-1 text-xs text-ink-500">Positiv = Zugang, negativ = Abgang.</p>
        </div>
        <div>
          <label className="label" htmlFor="adj-reason">Grund</label>
          <select
            id="adj-reason"
            className="input"
            value={reason}
            onChange={(e) => setReason(e.target.value as StockReason)}
          >
            {REASONS.map((r) => (
              <option key={r.key} value={r.key}>{r.label}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="adj-ref">Referenz / Notiz</label>
          <input
            id="adj-ref"
            className="input"
            placeholder="z.B. Lieferschein 4711"
            value={reference}
            onChange={(e) => setReference(e.target.value)}
          />
        </div>
        <button
          type="button"
          disabled={!valid || submitting}
          onClick={submit}
          className="btn btn-primary disabled:opacity-50"
        >
          <Save size={16} />
          {submitting ? 'Speichern …' : 'Buchen'}
        </button>
      </div>
    </BottomSheet>
  );
}