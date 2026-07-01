/**
 * Theme-Hook: schaltet die ``dark``-Klasse auf <html> in Abhaengigkeit
 * der User-Praeferenz (``light | dark | system``) und reagiert auf
 * Aenderungen des System-Farbschemas, falls ``system`` gewaehlt ist.
 *
 * Persistierung ueber localStorage laeuft direkt im Store
 * (siehe ``useAppStore.setThemePref``).
 */
import { useEffect } from 'react';
import { resolveEffectiveTheme, useAppStore } from '@/store';

export function useTheme(): void {
  const themePref = useAppStore((s) => s.themePref);
  const setEffectiveTheme = useAppStore((s) => s.setEffectiveTheme);

  useEffect(() => {
    if (typeof document === 'undefined') return;
    const apply = (effective: 'light' | 'dark') => {
      const root = document.documentElement;
      if (effective === 'dark') {
        root.classList.add('dark');
      } else {
        root.classList.remove('dark');
      }
      // Update browser chrome color — wir verwenden Lila auf Schwarz
      // fuer den dunklen Modus, sonst Blau-Grau.
      const meta = document.querySelector('meta[name="theme-color"]');
      if (meta) {
        meta.setAttribute('content', effective === 'dark' ? '#0a0a12' : '#1f2937');
      }
    };

    const update = () => {
      const effective = resolveEffectiveTheme(themePref);
      setEffectiveTheme(effective);
      apply(effective);
    };

    update();

    // Bei 'system': auf OS-Aenderung reagieren
    if (themePref === 'system' && typeof window !== 'undefined' && window.matchMedia) {
      const mql = window.matchMedia('(prefers-color-scheme: dark)');
      const onChange = () => update();
      // Safari < 14 kennt addEventListener nicht, nutzt addListener.
      if (mql.addEventListener) {
        mql.addEventListener('change', onChange);
        return () => mql.removeEventListener('change', onChange);
      } else {
        // eslint-disable-next-line deprecation/deprecation
        mql.addListener(onChange);
        return () => {
          // eslint-disable-next-line deprecation/deprecation
          mql.removeListener(onChange);
        };
      }
    }
    return undefined;
  }, [themePref, setEffectiveTheme]);
}
