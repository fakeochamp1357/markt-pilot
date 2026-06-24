import { NavLink } from 'react-router-dom';
import { List, Boxes, Tag, ScanLine, MoreHorizontal } from 'lucide-react';
import clsx from 'clsx';

const TABS = [
  { to: '/', label: 'Preisliste', icon: List, end: true },
  { to: '/inventory', label: 'Warenbestand', icon: Boxes },
  { to: '/categories', label: 'Kategorien', icon: Tag },
  { to: '/scanner', label: 'Scanner', icon: ScanLine },
  { to: '/more', label: 'Mehr', icon: MoreHorizontal },
];

export function BottomTabs() {
  return (
    <nav
      className="fixed bottom-0 inset-x-0 z-30 bg-white border-t border-gray-200 pb-safe shadow-[0_-2px_8px_rgba(0,0,0,0.04)]"
      aria-label="Hauptnavigation"
    >
      <ul className="grid grid-cols-5">
        {TABS.map(({ to, label, icon: Icon, end }) => (
          <li key={to}>
            <NavLink
              to={to}
              end={end}
              className={({ isActive }) =>
                clsx(
                  'flex flex-col items-center justify-center gap-0.5 min-h-tap py-2 text-xs font-medium transition-colors',
                  isActive ? 'text-brand-600' : 'text-ink-500 hover:text-ink-800',
                )
              }
            >
              <Icon size={22} strokeWidth={2} aria-hidden />
              <span>{label}</span>
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}