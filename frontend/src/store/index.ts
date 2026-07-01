/**
 * Globaler Zustand-Store — Online-Status, Outbox-Counter, Backend-Health.
 */
import { create } from 'zustand';

interface AppState {
  /** Browser-level "Netzwerk-Interface ist aktiv" — unzuverlässig. */
  isOnline: boolean;
  /** Outbox-Queue-Länge, angezeigt im Header als Badge. */
  outboxCount: number;
  /**
   * Echter Health-Check gegen ``/healthz``. ``null`` heißt "noch nicht
   * geprüft" — z.B. direkt nach App-Start, bevor der erste Ping zurückkam.
   * ``true`` = Backend antwortet, ``false`` = Backend nicht erreichbar
   * (Browser-Online oder nicht).
   */
  backendReachable: boolean | null;
  setOnline: (v: boolean) => void;
  setOutboxCount: (n: number) => void;
  setBackendReachable: (v: boolean | null) => void;
}

export const useAppStore = create<AppState>((set) => ({
  isOnline: typeof navigator !== 'undefined' ? navigator.onLine : true,
  outboxCount: 0,
  backendReachable: null,
  setOnline: (v) => set({ isOnline: v }),
  setOutboxCount: (n) => set({ outboxCount: n }),
  setBackendReachable: (v) => set({ backendReachable: v }),
}));