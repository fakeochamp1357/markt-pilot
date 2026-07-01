/**
 * Offline-Sync: repliziert die Dexie-Outbox gegen das Backend.
 * - POST/PUT/DELETE landen zunächst in der Outbox.
 * - Sobald das Backend erreichbar ist, werden sie in FIFO-Reihenfolge
 *   ans Backend geschickt.
 * - Bei Erfolg wird der Eintrag entfernt und der Cache invalidiert.
 * - 4xx-Antworten (z.B. "Barcode vergeben") sind terminal: weitere
 *   Versuche helfen nicht, der Eintrag bleibt sichtbar als 'failed'.
 * - 5xx / Netzwerkfehler sind transient: nach MAX_ATTEMPTS Versuchen
 *   wird der Eintrag dauerhaft 'failed' und muss manuell angestoßen
 *   werden (Button "Jetzt synchronisieren" resettet die Versuche).
 */
import { useEffect, useRef } from 'react';
import axios from 'axios';
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
import { useBackendHealth, pingBackendNow } from '@/hooks/useBackendHealth';

let syncing = false;

/** Max Retries pro Outbox-Eintrag bei transienten Fehlern. */
const MAX_ATTEMPTS = 8;

function isClientError(err: unknown): boolean {
  return axios.isAxiosError(err) && err.response !== undefined &&
    err.response.status >= 400 && err.response.status < 500;
}

async function runOp(op: OutboxOp, clientOpId?: string): Promise<void> {
  switch (op.kind) {
    case 'product.create':
      // eslint-disable-next-line no-console
      console.debug('[outbox] product.create', { clientOpId, payload: op.payload });
      await createProduct(op.payload, clientOpId);
      return;
    case 'product.update':
      await updateProduct(op.id, op.payload);
      return;
    case 'product.delete':
      await deleteProduct(op.id);
      return;
    case 'category.create':
      await createCategory(
        op.payload as Parameters<typeof createCategory>[0],
        clientOpId,
      );
      return;
    case 'category.update':
      await updateCategory(op.id, op.payload as Parameters<typeof updateCategory>[1]);
      return;
    case 'category.delete':
      await deleteCategory(op.id);
      return;
    case 'stock.movement':
      await createStockMovement(
        {
          product_id: op.payload.product_id,
          change: op.payload.change,
          reason: op.payload.reason as Parameters<typeof createStockMovement>[0]['reason'],
          reference: op.payload.reference,
          created_by: op.payload.created_by,
        },
        clientOpId,
      );
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
    const { cacheCategories } = await import('@/db/dexie');
    await cacheCategories(cats);
  } catch {
    // ignore – network may still be flaky
  }
}

export async function syncOutboxOnce(): Promise<{ processed: number; failed: number }> {
  if (syncing) return { processed: 0, failed: 0 };

  // Health-Gate: wenn wir wissen, dass das Backend down ist, gar nicht erst
  // versuchen (schneller Return, kein Log-Spam).
  const { backendReachable, isOnline } = useAppStore.getState();
  if (isOnline === false) return { processed: 0, failed: 0 };
  if (backendReachable === false) {
    // Versuch eines letzten Pings — falls Backend zwischenzeitlich
    // wieder da ist, wollen wir das mitkriegen.
    const ok = await pingBackendNow();
    if (!ok) return { processed: 0, failed: 0 };
  }

  syncing = true;
  let processed = 0;
  let failed = 0;
  try {
    const queue = await listOutbox();
    for (const entry of queue) {
      // Permanent-failed-Einträge (4xx oder MAX_ATTEMPTS erreicht) werden
      // uebersprungen — der User muss manuell via "Jetzt synchronisieren"
      // zuruecksetzen.
      if (entry.status === 'failed') continue;
      if (entry.status === 'in_flight') continue;
      try {
        await updateOutboxEntry(entry.id!, { status: 'in_flight', attempts: entry.attempts + 1 });
        await runOp(entry.op, entry.client_op_id);
        await clearOutboxEntry(entry.id!);
        processed += 1;
      } catch (err) {
        failed += 1;
        const msg = err instanceof Error ? err.message : String(err);
        if (isClientError(err)) {
          // 4xx: terminal — Eingabe falsch (z.B. barcode vergeben). Nicht
          // weiter versuchen, in failed parken, aber Loop NICHT abbrechen
          // (nachfolgende Ops sind u.U. unabhaengig).
          await updateOutboxEntry(entry.id!, {
            status: 'failed',
            last_error: `Abgelehnt: ${msg}`,
          });
        } else if (entry.attempts + 1 >= MAX_ATTEMPTS) {
          // Transient, aber max retries erreicht
          await updateOutboxEntry(entry.id!, {
            status: 'failed',
            last_error: `Max Retries (${MAX_ATTEMPTS}) erreicht: ${msg}`,
          });
          break;
        } else {
          // Transient: zurueck auf pending, beim naechsten Tick erneut.
          await updateOutboxEntry(entry.id!, {
            status: 'pending',
            last_error: msg,
          });
          break;
        }
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

/**
 * Setzt alle permanent-failed-Eintraege zurueck auf pending.
 * Wird vom "Jetzt synchronisieren"-Button in der Mehr-Seite aufgerufen,
 * damit der User explizit "ich will alles nochmal versuchen" sagen kann.
 */
export async function resetFailedOutboxEntries(): Promise<number> {
  const queue = await listOutbox();
  const failed = queue.filter((e) => e.status === 'failed');
  for (const entry of failed) {
    await updateOutboxEntry(entry.id!, {
      status: 'pending',
      attempts: 0,
      last_error: undefined,
    });
  }
  return failed.length;
}

/** Hook, der die Outbox regelmäßig und bei Online-Events synchronisiert. */
export function useOutboxSync(): void {
  // Health-Hook hier mit-mounten, damit App-weit der State befuellt wird.
  useBackendHealth();

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
      await syncOutboxOnce();
      await refreshCount();
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
      if (tickRef.current !== null) window.clearInterval(tickRef.current);
      window.removeEventListener('online', onOnline);
      window.removeEventListener('offline', onOffline);
    };
  }, [setOutboxCount]);
}

/** Manueller Trigger, damit die UI nach einer neuen Outbox-Operation den Counter aktualisiert. */
export async function refreshOutboxCountNow(): Promise<void> {
  const queue = await listOutbox();
  useAppStore.getState().setOutboxCount(queue.length);
}
