import axios, { type AxiosInstance } from 'axios';
import type {
  Category,
  ExpiringProduct,
  LowStockProduct,
  Product,
  ProductListResponse,
  StockMovement,
  StockMovementList,
  StockReason,
} from '@/types/api';

const BASE_URL = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000/api';

export const api: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' },
});

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

export async function createProduct(payload: Partial<Product>): Promise<Product> {
  const { data } = await api.post<Product>('/products', payload);
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

export async function createCategory(payload: {
  name: string;
  color: string;
  sort_order?: number;
  parent_id?: number | null;
}): Promise<Category> {
  const { data } = await api.post<Category>('/categories', payload);
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
export async function createStockMovement(payload: {
  product_id: number;
  change: number;
  reason: StockReason;
  reference?: string;
  created_by?: string;
}): Promise<StockMovement> {
  const { data } = await api.post<StockMovement>('/stock/movements', payload);
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