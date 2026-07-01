/**
 * Theme-Toggle: 3-Wege-Schalter (Hell / System / Dunkel) mit Icons.
 * Kompakt, passt in die Einstellungs-Sektion der Mehr-Seite.
 */
import { Monitor, Moon, Sun } from 'lucide-react';
import clsx from 'clsx';
import type { ThemePref } from '@/store';
import { useAppStore } from '@/store';

const OPTIONS: { key: ThemePref; label: string; icon: React.ReactNode }[] = [
  { key: 'light', label: 'Hell', icon: <Sun size={16} /> },
  { key: 'system', label: 'System', icon: <Monitor size={16} /> },
  { key: 'dark', label: 'Dunkel', icon: <Moon size={16} /> },
];

export function ThemeToggle() {
  const themePref = useAppStore((s) => s.themePref);
  const setThemePref = useAppStore((s) => s.setThemePref);

  return (
    <div
      className="grid grid-cols-3 gap-2"
      role="radiogroup"
      aria-label="Farbschema wählen"
    >
      {OPTIONS.map((o) => {
        const active = themePref === o.key;
        return (
          <button
            key={o.key}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => setThemePref(o.key)}
            className={clsx(
              'flex flex-col items-center justify-center gap-1 rounded-xl border px-3 py-3 text-sm font-medium transition-colors',
              active
                ? 'border-transparent text-white'
                : 'border-[color:var(--border-strong)] text-[color:var(--text-primary)] hover:bg-[color:var(--bg-hover)]',
            )}
            style={
              active
                ? {
                    backgroundColor: 'var(--accent-strong)',
                    boxShadow: 'var(--shadow-accent)',
                  }
                : undefined
            }
          >
            {o.icon}
            <span>{o.label}</span>
          </button>
        );
      })}
    </div>
  );
}
