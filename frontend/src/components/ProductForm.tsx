import { useEffect, useState } from 'react';
import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { ScanLine, Calculator } from 'lucide-react';
import type { Category, Product } from '@/types/api';
import { UNITS } from '@/types/api';
import { computeMargin, formatPrice } from '@/utils/format';

const Schema = z.object({
  name: z.string().min(1, 'Name ist erforderlich').max(200, 'Maximal 200 Zeichen'),
  category_id: z.union([z.number().int(), z.null(), z.undefined()]).optional().transform((v) => (v === undefined ? null : v)),
  barcode: z.string().max(32).nullable().optional().or(z.literal('')),
  sku: z.string().max(64).nullable().optional().or(z.literal('')),
  size_weight: z.string().max(40).nullable().optional().or(z.literal('')),
  unit: z.string().min(1, 'Einheit wählen'),
  cost_price: z
    .string()
    .refine((v) => v === '' || /^\d+([.,]\d{1,2})?$/.test(v), {
      message: 'Ungültiger Betrag (z.B. 1,99)',
    })
    .optional()
    .or(z.literal('')),
  sell_price: z
    .string()
    .refine((v) => v === '' || /^\d+([.,]\d{1,2})?$/.test(v), {
      message: 'Ungültiger Betrag (z.B. 1,99)',
    })
    .optional()
    .or(z.literal('')),
  stock_quantity: z
    .string()
    .refine((v) => v === '' || /^\d+([.,]\d{0,3})?$/.test(v), {
      message: 'Nur Zahlen, max. 3 Nachkommastellen',
    })
    .optional()
    .or(z.literal('')),
  min_stock_level: z
    .string()
    .refine((v) => v === '' || /^\d+([.,]\d{0,3})?$/.test(v), {
      message: 'Nur Zahlen',
    })
    .optional()
    .or(z.literal('')),
  expiry_date: z.string().nullable().optional(),
  supplier: z.string().max(200).nullable().optional().or(z.literal('')),
  notes: z.string().max(1000).nullable().optional().or(z.literal('')),
});

export type ProductFormValues = z.infer<typeof Schema>;

function parseDecimal(s: string | undefined | null): number {
  if (!s) return 0;
  return parseFloat(s.replace(',', '.'));
}

function decimalToInput(n: number): string {
  return Number.isFinite(n) ? n.toFixed(2).replace('.', ',') : '';
}

interface ProductFormProps {
  initial?: Partial<Product>;
  categories: Category[];
  defaultBarcode?: string;
  onSubmit: (payload: Partial<Product>) => Promise<void> | void;
  onScan?: () => void;
  submitLabel?: string;
}

export function ProductForm({
  initial,
  categories,
  defaultBarcode,
  onSubmit,
  onScan,
  submitLabel = 'Speichern',
}: ProductFormProps) {
  const {
    register,
    control,
    handleSubmit,
    watch,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<ProductFormValues>({
    resolver: zodResolver(Schema),
    defaultValues: {
      name: initial?.name ?? '',
      category_id: initial?.category_id ?? null,
      barcode: initial?.barcode ?? defaultBarcode ?? '',
      sku: initial?.sku ?? '',
      size_weight: initial?.size_weight ?? '',
      unit: initial?.unit ?? 'Stück',
      cost_price: initial?.cost_price ? decimalToInput(parseFloat(initial.cost_price)) : '',
      sell_price: initial?.sell_price ? decimalToInput(parseFloat(initial.sell_price)) : '',
      stock_quantity: initial?.stock_quantity
        ? String(initial.stock_quantity).replace('.', ',')
        : '',
      min_stock_level: initial?.min_stock_level
        ? String(initial.min_stock_level).replace('.', ',')
        : '',
      expiry_date: initial?.expiry_date ?? '',
      supplier: initial?.supplier ?? '',
      notes: initial?.notes ?? '',
    },
  });

  const costStr = watch('cost_price');
  const sellStr = watch('sell_price');
  const costNum = parseDecimal(costStr);
  const sellNum = parseDecimal(sellStr);
  const margin = computeMargin(costNum, sellNum);

  // Wenn defaultBarcode sich ändert (z.B. Scanner-Hit), setze das Feld.
  const [lastApplied, setLastApplied] = useState(defaultBarcode);
  useEffect(() => {
    if (defaultBarcode && defaultBarcode !== lastApplied) {
      setValue('barcode', defaultBarcode, { shouldDirty: true });
      setLastApplied(defaultBarcode);
    }
  }, [defaultBarcode, lastApplied, setValue]);

  const submit = async (vals: ProductFormValues) => {
    // eslint-disable-next-line no-console
    // eslint-disable-next-line no-console
    console.log('[ProductForm] submit vals:', JSON.stringify(vals));
    const payload: Partial<Product> = {
      name: vals.name.trim(),
      category_id: vals.category_id == null ? null : vals.category_id,
      barcode: vals.barcode?.trim() ? vals.barcode.trim() : null,
      sku: vals.sku?.trim() ? vals.sku.trim() : null,
      size_weight: vals.size_weight?.trim() ? vals.size_weight.trim() : null,
      unit: vals.unit,
      cost_price: parseDecimal(vals.cost_price).toFixed(2),
      sell_price: parseDecimal(vals.sell_price).toFixed(2),
      stock_quantity: parseDecimal(vals.stock_quantity).toFixed(3),
      min_stock_level: parseDecimal(vals.min_stock_level).toFixed(3),
      expiry_date: vals.expiry_date ? vals.expiry_date : null,
      supplier: vals.supplier?.trim() ? vals.supplier.trim() : null,
      notes: vals.notes?.trim() ? vals.notes.trim() : null,
      is_active: initial?.is_active ?? true,
      color_tag: initial?.color_tag ?? '#3B82F6',
      currency: initial?.currency ?? 'EUR',
    };
    // eslint-disable-next-line no-console
    // eslint-disable-next-line no-console
    console.log('[ProductForm] payload:', JSON.stringify(payload));
    await onSubmit(payload);
  };

  return (
    <form onSubmit={handleSubmit(submit)} className="space-y-3">
      <div>
        <label className="label" htmlFor="f-name">Name *</label>
        <input id="f-name" className="input" placeholder="z.B. Bananen Fairtrade" {...register('name')} />
        {errors.name && <p className="mt-1 text-xs text-red-600">{errors.name.message}</p>}
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label" htmlFor="f-cat">Kategorie</label>
          <Controller
            control={control}
            name="category_id"
            render={({ field }) => (
              <select
                id="f-cat"
                className="input"
                value={field.value === null || field.value === undefined ? 'null' : String(field.value)}
                onChange={(e) => {
                  const v = e.target.value;
                  field.onChange(v === 'null' ? null : Number(v));
                }}
                onBlur={field.onBlur}
              >
                <option value="null">— Keine —</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            )}
          />
        </div>
        <div>
          <label className="label" htmlFor="f-unit">Einheit</label>
          <select id="f-unit" className="input" {...register('unit')}>
            {UNITS.map((u) => (
              <option key={u} value={u}>
                {u}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div>
        <label className="label" htmlFor="f-barcode">Barcode</label>
        <div className="flex gap-2">
          <input
            id="f-barcode"
            className="input flex-1"
            inputMode="numeric"
            placeholder="z.B. 4015001000008"
            {...register('barcode')}
          />
          {onScan && (
            <button
              type="button"
              onClick={onScan}
              className="btn-secondary shrink-0 px-3"
              aria-label="Barcode scannen"
            >
              <ScanLine size={18} />
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label" htmlFor="f-sku">SKU</label>
          <input id="f-sku" className="input" placeholder="optional" {...register('sku')} />
        </div>
        <div>
          <label className="label" htmlFor="f-size">Größe / Gewicht</label>
          <input id="f-size" className="input" placeholder="z.B. 1kg" {...register('size_weight')} />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label" htmlFor="f-cost">EK (€)</label>
          <input
            id="f-cost"
            className="input"
            inputMode="decimal"
            placeholder="0,00"
            {...register('cost_price')}
          />
          {errors.cost_price && (
            <p className="mt-1 text-xs text-red-600">{errors.cost_price.message}</p>
          )}
        </div>
        <div>
          <label className="label" htmlFor="f-sell">VK (€)</label>
          <input
            id="f-sell"
            className="input"
            inputMode="decimal"
            placeholder="0,00"
            {...register('sell_price')}
          />
          {errors.sell_price && (
            <p className="mt-1 text-xs text-red-600">{errors.sell_price.message}</p>
          )}
        </div>
      </div>

      {costNum > 0 && sellNum > 0 && (
        <div className="flex items-center gap-2 rounded-xl bg-brand-50 border border-brand-100 px-3 py-2 text-sm">
          <Calculator size={16} className="text-brand-700" />
          <span className="font-medium text-brand-900">
            Marge: {margin.pct.toFixed(1)} % ({formatPrice(margin.eur)})
          </span>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label" htmlFor="f-stock">Anfangsbestand</label>
          <input
            id="f-stock"
            className="input"
            inputMode="decimal"
            placeholder="0"
            {...register('stock_quantity')}
          />
        </div>
        <div>
          <label className="label" htmlFor="f-min">Min-Bestand</label>
          <input
            id="f-min"
            className="input"
            inputMode="decimal"
            placeholder="0"
            {...register('min_stock_level')}
          />
        </div>
      </div>

      <div>
        <label className="label" htmlFor="f-mhd">MHD</label>
        <input id="f-mhd" type="date" className="input" {...register('expiry_date')} />
      </div>

      <div>
        <label className="label" htmlFor="f-supplier">Lieferant</label>
        <input id="f-supplier" className="input" placeholder="optional" {...register('supplier')} />
      </div>

      <div>
        <label className="label" htmlFor="f-notes">Notizen</label>
        <textarea id="f-notes" className="input min-h-[80px]" placeholder="optional" {...register('notes')} />
      </div>

      <div className="sticky bottom-0 -mx-4 px-4 pt-2 pb-1 bg-white">
        <button type="submit" disabled={isSubmitting} className="btn-primary w-full">
          {isSubmitting ? 'Speichern …' : submitLabel}
        </button>
      </div>
    </form>
  );
}