import { Pencil, Package } from 'lucide-react';
import type { Category, Product } from '@/types/api';
import { formatDate, formatPrice, formatQty, stockState } from '@/utils/format';

interface ProductCardProps {
  product: Product;
  categories: Category[];
  onClick: () => void;
}

export function ProductCard({ product, categories, onClick }: ProductCardProps) {
  const cat = categories.find((c) => c.id === product.category_id);
  const stripe = cat?.color ?? product.color_tag ?? '#3B82F6';
  const state = stockState(product);
  return (
    <button
      type="button"
      onClick={onClick}
      className="card relative flex w-full overflow-hidden text-left active:bg-gray-50 transition-colors"
      aria-label={`Produkt ${product.name} öffnen`}
    >
      <span
        aria-hidden
        className="block w-1.5 shrink-0"
        style={{ backgroundColor: stripe }}
      />
      <div className="flex-1 p-3 min-w-0">
        <div className="flex items-start gap-2">
          <div className="min-w-0 flex-1">
            <p className="font-bold text-ink-900 truncate">{product.name}</p>
            <p className="text-sm text-ink-600">
              {product.unit}
              {product.size_weight ? `: ${product.size_weight}` : ''}
            </p>
            <p className="text-sm text-ink-600">
              Menge:{' '}
              <span className={state === 'low' ? 'font-semibold text-red-600' : 'font-medium'}>
                {formatQty(product.stock_quantity)}
              </span>
              {product.expiry_date && (
                <span className="text-ink-500"> · {formatDate(product.expiry_date)}</span>
              )}
            </p>
          </div>
          <div className="shrink-0 text-right">
            <p className="price-big">{formatPrice(product.sell_price)}</p>
            {state === 'low' && (
              <p className="mt-1 inline-flex items-center gap-1 text-xs font-semibold text-red-600">
                <Package size={12} /> Niedrig
              </p>
            )}
          </div>
        </div>
      </div>
      <span className="absolute right-2 top-2 text-ink-400">
        <Pencil size={14} />
      </span>
    </button>
  );
}