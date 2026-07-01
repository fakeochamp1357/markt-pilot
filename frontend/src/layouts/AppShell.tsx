import { Outlet, useLocation } from 'react-router-dom';
import { Header } from './Header';
import { BottomTabs } from './BottomTabs';

const TITLES: Record<string, string> = {
  '/': 'MarktPilot',
  '/pos': 'Kasse',
  '/inventory': 'Warenbestand',
  '/categories': 'Kategorien',
  '/scanner': 'Scanner',
  '/more': 'Mehr',
};

export function AppShell() {
  const { pathname } = useLocation();
  // Match root for nested detail routes too.
  const rootKey = '/' + (pathname.split('/')[1] ?? '');
  const title = TITLES[rootKey] ?? 'MarktPilot';

  return (
    <div className="min-h-full flex flex-col">
      <Header title={title} />
      <main className="flex-1 pb-24">
        <Outlet />
      </main>
      <BottomTabs />
    </div>
  );
}