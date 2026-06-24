/**
 * Globaler Zustand-Store — Online-Status, Outbox-Counter, Selection.
 */
import { create } from 'zustand';

interface AppState {
  isOnline: boolean;
  outboxCount: number;
  setOnline: (v: boolean) => void;
  setOutboxCount: (n: number) => void;
}

export const useAppStore = create<AppState>((set) => ({
  isOnline: typeof navigator !== 'undefined' ? navigator.onLine : true,
  outboxCount: 0,
  setOnline: (v) => set({ isOnline: v }),
  setOutboxCount: (n) => set({ outboxCount: n }),
}));