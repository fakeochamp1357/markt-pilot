/**
 * Domain-Typen — spiegeln die Backend-Schemas.
 */

export interface Category {
  id: number;
  name: string;
  color: string; // #RRGGBB
  sort_order: number;
  parent_id: number | null;
  created_at: string;
}

export interface Product {
  id: number;
  sku: string | null;
  barcode: string | null;
  name: string;
  category_id: number | null;
  unit: string;
  size_weight: string | null;
  cost_price: string; // Decimal als string
  sell_price: string;
  currency: string;
  stock_quantity: string;
  min_stock_level: string;
  expiry_date: string | null;
  supplier: string | null;
  notes: string | null;
  image_url: string | null;
  color_tag: string;
  is_active: boolean;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface ProductListResponse {
  items: Product[];
  total: number;
  limit: number;
  offset: number;
}

export type StockReason = 'purchase' | 'sale' | 'adjustment' | 'waste' | 'return';

export interface StockMovement {
  id: number;
  product_id: number;
  change: string;
  reason: StockReason;
  reference: string | null;
  created_by: string | null;
  created_at: string;
}

export interface StockMovementList {
  items: StockMovement[];
  total: number;
}

export interface LowStockProduct {
  id: number;
  name: string;
  sku: string | null;
  barcode: string | null;
  category_id: number | null;
  stock_quantity: string;
  min_stock_level: string;
  unit: string;
  color_tag: string;
  deficit: string;
}

export interface ExpiringProduct {
  id: number;
  name: string;
  sku: string | null;
  barcode: string | null;
  expiry_date: string;
  days_until_expiry: number;
  stock_quantity: string;
  color_tag: string;
}

export type FilterKey = 'all' | 'low' | 'expiring' | number; // number = category_id
export type SortKey =
  | 'name_asc'
  | 'name_desc'
  | 'price_asc'
  | 'price_desc'
  | 'newest'
  | 'expiring';

export const UNITS = ['Stück', 'kg', 'g', 'l', 'ml', 'Packung', 'Box', 'm'] as const;
export type Unit = (typeof UNITS)[number];