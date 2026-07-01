/**
 * Backend-Health-Check: pingt /healthz alle paar Sekunden.
 *
 * Warum nicht nur ``navigator.onLine``?
 *   Browser meldet "online" sobald irgendein Netzwerk-Interface aktiv ist
 *   — z.B. ein WLAN das connected ist, aber kein Internet liefert. Für die
 *   Kasse ist das eine Falle: "Browser sagt online, aber Backend kommt
 *   nicht durch". Daher der echte Health-Ping.
 *
 * Zustände:
 *   - ``true``  → Backend hat 200 zurückgegeben
 *   - ``false`` → Backend nicht erreichbar (Timeout, 5xx, Netzwerkfehler)
 *   - ``null``  → noch kein Ping gemacht (App gerade gestartet)
 */
import { useEffect, useRef } from 'react';
import { healthApi } from '@/api/client';
import { useAppStore } from '@/store';

const PING_INTERVAL_MS = 5_000;

async function pingBackend(): Promise<boolean> {
  try {
    const resp = await healthApi.get('/healthz');
    return resp.status === 200;
  } catch {
    return false;
  }
}

export function useBackendHealth(): void {
  const setBackendReachable = useAppStore((s) => s.setBackendReachable);
  const isOnline = useAppStore((s) => s.isOnline);
  const tickRef = useRef<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    const ping = async () => {
      if (!navigator.onLine) {
        // Browser sagt offline — kein Sinn zu pingen.
        if (!cancelled) setBackendReachable(false);
        return;
      }
      const ok = await pingBackend();
      if (!cancelled) setBackendReachable(ok);
    };
    void ping();
    tickRef.current = window.setInterval(ping, PING_INTERVAL_MS);
    const onOnline = () => void ping();
    const onOffline = () => setBackendReachable(false);
    window.addEventListener('online', onOnline);
    window.addEventListener('offline', onOffline);
    return () => {
      cancelled = true;
      if (tickRef.current !== null) window.clearInterval(tickRef.current);
      window.removeEventListener('online', onOnline);
      window.removeEventListener('offline', onOffline);
    };
    // isOnline als Re-Ping-Trigger, falls das Browser-Event verpasst wurde
  }, [setBackendReachable, isOnline]);
}

/** Manueller Trigger, z.B. nach einem User-Klick auf "Jetzt synchronisieren". */
export async function pingBackendNow(): Promise<boolean> {
  const ok = await pingBackend();
  useAppStore.getState().setBackendReachable(ok);
  return ok;
}
