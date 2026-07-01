/**
 * Dexie-Schema: lokale Caches + Outbox für Offline-Mutationen.
 */
import Dexie, { type Table } from 'dexie';
import type { Category, Product, StockMovement } from '@/types/api';
import { newUuid } from '@/utils/uuid';

export interface CachedProduct {
  id: number;
  payload: Product;
  cached_at: number;
}

export interface CachedCategory {
  id: number;
  payload: Category;
  cached_at: number;
}

export interface CachedMovement {
  id: string; // composite
  payload: StockMovement;
  cached_at: number;
}

export type OutboxOp =
  | { kind: 'product.create'; payload: Partial<Product> }
  | { kind: 'product.update'; id: number; payload: Partial<Product> }
  | { kind: 'product.delete'; id: number }
  | { kind: 'category.create'; payload: Partial<Category> }
  | { kind: 'category.update'; id: number; payload: Partial<Category> }
  | { kind: 'category.delete'; id: number }
  | {
      kind: 'stock.movement';
      payload: {
        product_id: number;
        change: number;
        reason: string;
        reference?: string;
        created_by?: string;
      };
    };

export interface OutboxEntry {
  id?: number;
  op: OutboxOp;
  /**
   * Client-seitige Idempotenz-UUID (nur für create-artige Ops gesetzt).
   * Wird beim POST als ``X-Client-Op-Id``-Header mitgeschickt. Das Backend
   * cached die erste Antwort unter dieser ID; ein Retry nach WLAN-Crash
   * erzeugt damit **kein** Duplikat.
   */
  client_op_id?: string;
  created_at: number;
  attempts: number;
  last_error?: string;
  status: 'pending' | 'in_flight' | 'failed';
}

class MarktPilotDB extends Dexie {
  products!: Table<CachedProduct, number>;
  categories!: Table<CachedCategory, number>;
  movements!: Table<CachedMovement, string>;
  outbox!: Table<OutboxEntry, number>;
  kv!: Table<{ key: string; value: unknown }, string>;

  constructor() {
    super('markt-pilot');
    this.version(1).stores({
      products: 'id, category_id, is_active, cached_at',
      categories: 'id, sort_order, cached_at',
      movements: 'id, product_id, cached_at',
      outbox: '++id, status, created_at',
      kv: 'key',
    });
  }
}

export const db = new MarktPilotDB();

export async function cacheProducts(products: Product[]): Promise<void> {
  const now = Date.now();
  await db.products.bulkPut(products.map((p) => ({ id: p.id, payload: p, cached_at: now })));
}

export async function cacheCategories(categories: Category[]): Promise<void> {
  const now = Date.now();
  await db.categories.bulkPut(
    categories.map((c) => ({ id: c.id, payload: c, cached_at: now })),
  );
}

export async function cacheMovements(movs: StockMovement[]): Promise<void> {
  const now = Date.now();
  await db.movements.bulkPut(
    movs.map((m) => ({ id: `${m.id}`, payload: m, cached_at: now })),
  );
}

export async function readCachedProducts(): Promise<Product[]> {
  return (await db.products.toArray())
    .map((row) => row.payload)
    .sort((a, b) => a.name.localeCompare(b.name, 'de'));
}

export async function readCachedCategories(): Promise<Category[]> {
  return (await db.categories.toArray())
    .map((row) => row.payload)
    .sort((a, b) => a.sort_order - b.sort_order || a.name.localeCompare(b.name, 'de'));
}

export async function readCachedMovements(): Promise<StockMovement[]> {
  return (await db.movements.toArray())
    .map((row) => row.payload)
    .sort((a, b) => (a.created_at < b.created_at ? 1 : -1));
}

/** Op-Kinds, die einen serverseitigen POST erzeugen und damit eine
 * Idempotenz-UUID benötigen. PUTs und DELETEs sind per HTTP-Semantik
 * idempotent und brauchen keine. */
const CREATE_KINDS: ReadonlySet<OutboxOp['kind']> = new Set<OutboxOp['kind']>([
  'product.create',
  'category.create',
  'stock.movement',
]);

export interface EnqueueResult {
  id: number;
  /** Die für diesen Eintrag generierte Idempotenz-UUID (nur bei Create-Ops). */
  clientOpId: string | null;
}

export async function enqueueOutbox(op: OutboxOp): Promise<EnqueueResult> {
  const clientOpId = CREATE_KINDS.has(op.kind) ? newUuid() : undefined;
  const id = await db.outbox.add({
    op,
    client_op_id: clientOpId,
    created_at: Date.now(),
    attempts: 0,
    status: 'pending',
  });
  return { id: Number(id), clientOpId: clientOpId ?? null };
}

export async function listOutbox(): Promise<OutboxEntry[]> {
  return db.outbox.orderBy('created_at').toArray();
}

export async function clearOutboxEntry(id: number): Promise<void> {
  await db.outbox.delete(id);
}

export async function updateOutboxEntry(
  id: number,
  patch: Partial<OutboxEntry>,
): Promise<void> {
  await db.outbox.update(id, patch);
}