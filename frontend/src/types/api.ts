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
  /** Pfand pro Stueck (Cent), 0 wenn keins. */
  deposit_cents: number;
  /** > 1 = wird in Packungen eingekauft (z.B. Vimto 24er-Tray). */
  pieces_per_pack: number;
  /** Einheit der Packung, z.B. "Tray" oder "Karton" (optional). */
  pack_unit: string | null;
  /** Barcode der Packung (optional, kann != barcode sein). */
  pack_barcode: string | null;
  /** VK in Cent — fuer mathefreie Cart-Berechnungen auf Pi. */
  sell_price_cents: number;
  /** EK in Cent (fuer Margenanzeige). */
  cost_price_cents: number;
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

// ----------------------------------------------------------------
// Receipt / POS
// ----------------------------------------------------------------

export type ReceiptKind = 'sale' | 'storno' | 'return';
export type ReceiptLineKind = 'sale' | 'deposit' | 'return' | 'storno';
export type PaymentMethod = 'cash' | 'card' | 'mixed';

export interface ReceiptLine {
  id: number;
  position: number;
  kind: ReceiptLineKind;
  product_id: number | null;
  name_snapshot: string;
  unit_snapshot: string;
  quantity: string;
  unit_price_cents: number;
  line_total_cents: number;
  comment: string | null;
}

export interface Receipt {
  id: number;
  receipt_number: string;
  kind: ReceiptKind;
  original_receipt_id: number | null;
  cash_session: string;
  payment_method: PaymentMethod;
  tendered_cents: number;
  change_cents: number;
  total_cents: number;
  cashier_name: string | null;
  notes: string | null;
  print_requested: boolean;
  created_at: string;
  lines: ReceiptLine[];
}

export interface ReceiptCreatePayload {
  kind?: ReceiptKind;
  original_receipt_id?: number | null;
  cash_session: string;
  payment_method: PaymentMethod;
  tendered_cents?: number;
  change_cents?: number;
  total_cents: number;
  cashier_name?: string | null;
  notes?: string | null;
  print_requested?: boolean;
  lines: {
    kind: ReceiptLineKind;
    product_id: number | null;
    name_snapshot: string;
    unit_snapshot: string;
    quantity: string;
    unit_price_cents: number;
    line_total_cents: number;
    comment?: string | null;
  }[];
}

// ---------------------------------------------------------------------------
// Analytics
// ---------------------------------------------------------------------------

export type AnalyticsPeriod = 'week' | 'month' | 'quarter' | 'year' | 'all';
export type AnalyticsSeverity = 'info' | 'warn' | 'danger';
export type AnalyticsSortBy = 'qty' | 'revenue' | 'margin';

export interface TopSeller {
  product_id: number;
  name: string;
  qty_sold: string;
  revenue: string; // EUR
  margin: string; // EUR
  margin_pct: string;
}

export interface MarginRow {
  product_id: number;
  name: string;
  qty_sold: string;
  revenue: string;
  cost: string;
  margin: string;
  margin_pct: string;
}

export interface DeadStockRow {
  product_id: number;
  name: string;
  sku: string | null;
  last_sale_at: string | null;
  days_since_last_sale: number | null;
  stock_quantity: string;
  stock_value: string;
}

export interface ExpiryAlert {
  product_id: number;
  name: string;
  expiry_date: string;
  days_until_expiry: number;
  stock_quantity: string;
  severity: AnalyticsSeverity;
}

export interface ReorderAlert {
  product_id: number;
  name: string;
  sku: string | null;
  stock_quantity: string;
  min_stock_level: string;
  deficit: string;
  suggested_order_qty: string;
}

export interface DashboardSummary {
  total_active_products: number;
  total_inventory_value: string;
  total_sales_period: string;
  total_margin_period: string;
  units_sold_period: string;
  expiry_soon_count: number;
  expired_count: number;
  reorder_count: number;
  dead_stock_count: number;
  period: AnalyticsPeriod;
}

export interface NotificationItem {
  type: 'expiry_soon' | 'expired' | 'reorder' | 'dead_stock';
  severity: AnalyticsSeverity;
  product_id: number;
  product_name: string;
  message: string;
  created_at: string;
}