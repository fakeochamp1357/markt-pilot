import axios, { type AxiosInstance, type RawAxiosRequestHeaders } from 'axios';
import type {
  AnalyticsPeriod,
  AnalyticsSortBy,
  Category,
  DashboardSummary,
  DeadStockRow,
  ExpiringProduct,
  ExpiryAlert,
  LowStockProduct,
  MarginRow,
  NotificationItem,
  Product,
  ProductListResponse,
  Receipt,
  ReceiptCreatePayload,
  ReorderAlert,
  StockMovement,
  StockMovementList,
  StockReason,
  TopSeller,
} from '@/types/api';

const BASE_URL = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000/api';
/** Basis-URL ohne den ``/api``-Pfad — für Health-Checks etc. */
export const ROOT_URL: string = (() => {
  const base = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000/api';
  return base.replace(/\/api\/?$/, '');
})();

export const api: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' },
});

/** Axios-Instanz mit kurzem Timeout — für Health-Pings. */
export const healthApi: AxiosInstance = axios.create({
  baseURL: ROOT_URL,
  timeout: 2500,
  headers: { 'Content-Type': 'application/json' },
});

/** Header-Konstruktor: hängt X-Client-Op-Id an, wenn vorhanden. */
function idempotencyHeader(clientOpId: string | undefined): RawAxiosRequestHeaders {
  return clientOpId ? { 'X-Client-Op-Id': clientOpId } : {};
}

// ---------- Products ----------
export async function listProducts(params?: {
  q?: string;
  category?: number;
  active?: boolean;
  limit?: number;
  offset?: number;
}): Promise<ProductListResponse> {
  const { data } = await api.get<ProductListResponse>('/products', { params });
  return data;
}

export async function getProduct(id: number): Promise<Product> {
  const { data } = await api.get<Product>(`/products/${id}`);
  return data;
}

export async function getProductByBarcode(code: string): Promise<Product> {
  const { data } = await api.get<Product>(`/products/barcode/${encodeURIComponent(code)}`);
  return data;
}

export async function createProduct(
  payload: Partial<Product>,
  clientOpId?: string,
): Promise<Product> {
  const { data } = await api.post<Product>('/products', payload, {
    headers: idempotencyHeader(clientOpId),
  });
  return data;
}

export async function updateProduct(id: number, payload: Partial<Product>): Promise<Product> {
  const { data } = await api.put<Product>(`/products/${id}`, payload);
  return data;
}

export async function deleteProduct(id: number): Promise<Product> {
  const { data } = await api.delete<Product>(`/products/${id}`);
  return data;
}

// ---------- Categories ----------
export async function listCategories(): Promise<Category[]> {
  const { data } = await api.get<Category[]>('/categories');
  return data;
}

export async function createCategory(
  payload: {
    name: string;
    color: string;
    sort_order?: number;
    parent_id?: number | null;
  },
  clientOpId?: string,
): Promise<Category> {
  const { data } = await api.post<Category>('/categories', payload, {
    headers: idempotencyHeader(clientOpId),
  });
  return data;
}

export async function updateCategory(
  id: number,
  payload: Partial<{ name: string; color: string; sort_order: number; parent_id: number | null }>,
): Promise<Category> {
  const { data } = await api.put<Category>(`/categories/${id}`, payload);
  return data;
}

export async function deleteCategory(id: number): Promise<void> {
  await api.delete(`/categories/${id}`);
}

// ---------- Stock ----------
export async function createStockMovement(
  payload: {
    product_id: number;
    change: number;
    reason: StockReason;
    reference?: string;
    created_by?: string;
  },
  clientOpId?: string,
): Promise<StockMovement> {
  const { data } = await api.post<StockMovement>('/stock/movements', payload, {
    headers: idempotencyHeader(clientOpId),
  });
  return data;
}

export async function listMovements(params?: {
  product_id?: number;
  limit?: number;
  offset?: number;
}): Promise<StockMovementList> {
  const { data } = await api.get<StockMovementList>('/stock/movements', { params });
  return data;
}

export async function listLowStock(): Promise<LowStockProduct[]> {
  const { data } = await api.get<LowStockProduct[]>('/stock/low');
  return data;
}

export async function listExpiring(days = 30): Promise<ExpiringProduct[]> {
  const { data } = await api.get<ExpiringProduct[]>('/stock/expiring', { params: { days } });
  return data;
}

// ---------- Receipts (POS) ----------

/**
 * Erstellt einen Kassenbon. Idempotent via ``clientOpId`` — derselbe
 * Aufruf mit derselben UUID nach WLAN-Crash fuehrt nicht zu doppelten
 * Stock-Abbuchungen.
 */
export async function createReceipt(
  payload: ReceiptCreatePayload,
  clientOpId?: string,
): Promise<Receipt> {
  const { data } = await api.post<Receipt>('/receipts', payload, {
    headers: idempotencyHeader(clientOpId),
  });
  return data;
}

export async function listReceipts(params?: {
  cash_session?: string;
  limit?: number;
  offset?: number;
}): Promise<Receipt[]> {
  const { data } = await api.get<Receipt[]>('/receipts', { params });
  return data;
}

export async function getReceipt(id: number): Promise<Receipt> {
  const { data } = await api.get<Receipt>(`/receipts/${id}`);
  return data;
}

export async function getReceiptByNumber(number: string): Promise<Receipt> {
  const { data } = await api.get<Receipt>(`/receipts/by-number/${number}`);
  return data;
}

/** Storniert einen Bon — erzeugt einen Gegenbon und stellt Bestand wieder her. */
export async function voidReceipt(id: number): Promise<Receipt> {
  const { data } = await api.post<Receipt>(`/receipts/${id}/void`);
  return data;
}

// ---------- Analytics ----------
export async function getTopSellers(params?: {
  period?: AnalyticsPeriod;
  limit?: number;
  sort_by?: AnalyticsSortBy;
}): Promise<TopSeller[]> {
  const { data } = await api.get<TopSeller[]>('/analytics/top-sellers', { params });
  return data;
}

export async function getMargins(params?: {
  period?: AnalyticsPeriod;
  limit?: number;
  only_with_sales?: boolean;
}): Promise<MarginRow[]> {
  const { data } = await api.get<MarginRow[]>('/analytics/margins', { params });
  return data;
}

export async function getDeadStock(params?: {
  period?: AnalyticsPeriod;
  limit?: number;
  include_zero_stock?: boolean;
}): Promise<DeadStockRow[]> {
  const { data } = await api.get<DeadStockRow[]>('/analytics/dead-stock', { params });
  return data;
}

export async function getExpiryAlerts(params?: {
  warn_days?: number;
  include_expired?: boolean;
  limit?: number;
}): Promise<ExpiryAlert[]> {
  const { data } = await api.get<ExpiryAlert[]>('/analytics/expiry-alerts', { params });
  return data;
}

export async function getReorderAlerts(params?: {
  include_zero_min?: boolean;
  limit?: number;
}): Promise<ReorderAlert[]> {
  const { data } = await api.get<ReorderAlert[]>('/analytics/reorder-alerts', { params });
  return data;
}

export async function getDashboardSummary(params?: {
  period?: AnalyticsPeriod;
  warn_days?: number;
}): Promise<DashboardSummary> {
  const { data } = await api.get<DashboardSummary>('/analytics/dashboard/summary', {
    params,
  });
  return data;
}

export async function getNotifications(params?: {
  period?: AnalyticsPeriod;
  warn_days?: number;
  limit?: number;
}): Promise<NotificationItem[]> {
  const { data } = await api.get<NotificationItem[]>('/analytics/notifications', {
    params,
  });
  return data;
}