import { NavLink } from 'react-router-dom';
import { List, Boxes, Tag, ScanLine, MoreHorizontal, ShoppingCart } from 'lucide-react';
import clsx from 'clsx';

const TABS = [
  { to: '/', label: 'Preisliste', icon: List, end: true },
  { to: '/pos', label: 'Kasse', icon: ShoppingCart },
  { to: '/inventory', label: 'Warenbestand', icon: Boxes },
  { to: '/categories', label: 'Kategorien', icon: Tag },
  { to: '/scanner', label: 'Scanner', icon: ScanLine },
  { to: '/more', label: 'Mehr', icon: MoreHorizontal },
];

export function BottomTabs() {
  return (
    <nav
      className="fixed bottom-0 inset-x-0 z-30 border-t border-[color:var(--border-strong)] bg-[color:var(--bg-card)] pb-safe shadow-[0_-2px_8px_rgba(0,0,0,0.04)]"
      aria-label="Hauptnavigation"
    >
      <ul className="grid grid-cols-6">
        {TABS.map(({ to, label, icon: Icon, end }) => (
          <li key={to}>
            <NavLink
              to={to}
              end={end}
              className={({ isActive }) =>
                clsx(
                  'flex flex-col items-center justify-center gap-0.5 min-h-tap py-2 text-[10px] font-medium transition-colors',
                  isActive ? 'text-[color:var(--accent)]' : 'text-ink-500 hover:text-ink-900'
                )
              }
            >
              <Icon size={20} strokeWidth={2} aria-hidden />
              <span className="truncate">{label}</span>
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
