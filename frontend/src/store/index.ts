/**
 * Globaler Zustand-Store — Online-Status, Outbox-Counter, Backend-Health, Theme.
 */
import { create } from 'zustand';

export type ThemePref = 'light' | 'dark' | 'system';
/** Effektiv aktives Theme — ohne 'system'. Wird aus ThemePref + System abgeleitet. */
export type EffectiveTheme = 'light' | 'dark';

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
  /**
   * Theme-Praeferenz des Users. ``system`` = folgt ``prefers-color-scheme``.
   * Persistiert in localStorage.
   */
  themePref: ThemePref;
  /** Was tatsaechlich gerendert wird (auf ``system``-Aenderungen reagierend). */
  effectiveTheme: EffectiveTheme;
  setOnline: (v: boolean) => void;
  setOutboxCount: (n: number) => void;
  setBackendReachable: (v: boolean | null) => void;
  setThemePref: (t: ThemePref) => void;
  setEffectiveTheme: (t: EffectiveTheme) => void;
}

const STORAGE_KEY = 'markt-pilot:theme';

function readInitialThemePref(): ThemePref {
  if (typeof window === 'undefined') return 'system';
  try {
    const v = window.localStorage.getItem(STORAGE_KEY);
    if (v === 'light' || v === 'dark' || v === 'system') return v;
  } catch {
    /* localStorage kann in Private-Browsing kaputt sein — egal. */
  }
  return 'system';
}

function systemPrefersDark(): boolean {
  if (typeof window === 'undefined' || !window.matchMedia) return false;
  return window.matchMedia('(prefers-color-scheme: dark)').matches;
}

export const useAppStore = create<AppState>((set) => ({
  isOnline: typeof navigator !== 'undefined' ? navigator.onLine : true,
  outboxCount: 0,
  backendReachable: null,
  themePref: readInitialThemePref(),
  effectiveTheme: systemPrefersDark() ? 'dark' : 'light',
  setOnline: (v) => set({ isOnline: v }),
  setOutboxCount: (n) => set({ outboxCount: n }),
  setBackendReachable: (v) => set({ backendReachable: v }),
  setThemePref: (t) => {
    if (typeof window !== 'undefined') {
      try {
        window.localStorage.setItem(STORAGE_KEY, t);
      } catch {
        /* siehe oben */
      }
    }
    set({ themePref: t });
  },
  setEffectiveTheme: (t) => set({ effectiveTheme: t }),
}));

/** Wird vom useTheme-Hook benutzt, um aus Pref + System das effective zu berechnen. */
export function resolveEffectiveTheme(pref: ThemePref): EffectiveTheme {
  if (pref === 'dark') return 'dark';
  if (pref === 'light') return 'light';
  return systemPrefersDark() ? 'dark' : 'light';
}