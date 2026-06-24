/**
 * Offline-Sync: repliziert die Dexie-Outbox gegen das Backend.
 * - POST/PUT/DELETE landen zunächst in der Outbox.
 * - Sobald online, werden sie in FIFO-Reihenfolge ans Backend geschickt.
 * - Bei Erfolg wird der Eintrag entfernt und der Cache invalidiert.
 */
import { useEffect, useRef } from 'react';
import {
  cacheProducts,
  clearOutboxEntry,
  listOutbox,
  updateOutboxEntry,
  type OutboxEntry,
  type OutboxOp,
} from '@/db/dexie';
import {
  createCategory,
  createProduct,
  createStockMovement,
  deleteCategory,
  deleteProduct,
  listCategories,
  listProducts,
  updateCategory,
  updateProduct,
} from '@/api/client';
import { useAppStore } from '@/store';

let syncing = false;

async function runOp(op: OutboxOp): Promise<void> {
  switch (op.kind) {
    case 'product.create':
      // eslint-disable-next-line no-console
      console.debug('[outbox] product.create payload:', op.payload);
      await createProduct(op.payload);
      return;
    case 'product.update':
      await updateProduct(op.id, op.payload);
      return;
    case 'product.delete':
      await deleteProduct(op.id);
      return;
    case 'category.create':
      await createCategory(op.payload as Parameters<typeof createCategory>[0]);
      return;
    case 'category.update':
      await updateCategory(op.id, op.payload as Parameters<typeof updateCategory>[1]);
      return;
    case 'category.delete':
      await deleteCategory(op.id);
      return;
    case 'stock.movement':
      await createStockMovement({
        product_id: op.payload.product_id,
        change: op.payload.change,
        reason: op.payload.reason as Parameters<typeof createStockMovement>[0]['reason'],
        reference: op.payload.reference,
        created_by: op.payload.created_by,
      });
      return;
    default: {
      // exhaustiveness check
      const _exhaustive: never = op;
      void _exhaustive;
    }
  }
}

async function refreshCachesAfterSync(): Promise<void> {
  try {
    const [prods, cats] = await Promise.all([listProducts({ limit: 500 }), listCategories()]);
    await cacheProducts(prods.items);
    // categories cache – reuse helper
    const { cacheCategories } = await import('@/db/dexie');
    await cacheCategories(cats);
  } catch {
    // ignore – network may still be flaky
  }
}

export async function syncOutboxOnce(): Promise<{ processed: number; failed: number }> {
  if (syncing) return { processed: 0, failed: 0 };
  if (!navigator.onLine) return { processed: 0, failed: 0 };
  syncing = true;
  let processed = 0;
  let failed = 0;
  try {
    const queue = await listOutbox();
    for (const entry of queue) {
      if (entry.status === 'in_flight') continue;
      try {
        await updateOutboxEntry(entry.id!, { status: 'in_flight', attempts: entry.attempts + 1 });
        await runOp(entry.op);
        await clearOutboxEntry(entry.id!);
        processed += 1;
      } catch (err) {
        failed += 1;
        await updateOutboxEntry(entry.id!, {
          status: 'failed',
          last_error: err instanceof Error ? err.message : String(err),
        });
        // first failure: stop the loop to avoid hammering the server
        break;
      }
    }
    if (processed > 0) {
      await refreshCachesAfterSync();
    }
  } finally {
    syncing = false;
  }
  return { processed, failed };
}

/** Hook, der die Outbox regelmäßig und bei Online-Events synchronisiert. */
export function useOutboxSync(): void {
  const isOnline = useAppStore((s) => s.isOnline);
  const setOutboxCount = useAppStore((s) => s.setOutboxCount);
  const tickRef = useRef<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    const refreshCount = async () => {
      const queue = await listOutbox();
      if (!cancelled) setOutboxCount(queue.length);
    };
    void refreshCount();
    const tick = async () => {
      await refreshCount();
      if (navigator.onLine) {
        await syncOutboxOnce();
        await refreshCount();
      }
    };
    void tick();
    // Tighter interval (3s) so outbox counter and sync stay snappy.
    tickRef.current = window.setInterval(tick, 3000);
    const onOnline = () => void tick();
    const onOffline = () => void refreshCount();
    window.addEventListener('online', onOnline);
    window.addEventListener('offline', onOffline);
    return () => {
      cancelled = true;
      if (tickRef.current) window.clearInterval(tickRef.current);
      window.removeEventListener('online', onOnline);
      window.removeEventListener('offline', onOffline);
    };
  }, [setOutboxCount, isOnline]);
}

/** Manueller Trigger, damit die UI nach einer neuen Outbox-Operation den Counter aktualisiert. */
export async function refreshOutboxCountNow(): Promise<void> {
  const queue = await listOutbox();
  useAppStore.getState().setOutboxCount(queue.length);
}