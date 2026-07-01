import { WifiOff, RefreshCw, CloudOff, CheckCircle2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useAppStore } from '@/store';
import { useOnlineStatus } from '@/hooks/useOnlineStatus';

interface HeaderProps {
  title: string;
  back?: boolean;
  right?: React.ReactNode;
}

export function Header({ title, right }: HeaderProps) {
  const isOnline = useOnlineStatus();
  const backendReachable = useAppStore((s) => s.backendReachable);
  const outboxCount = useAppStore((s) => s.outboxCount);

  // Drei unterscheidbare Zustaende:
  //  - browser offline          → "Offline"
  //  - browser online, backend weg → "Kein Backend"
  //  - alles gut                 → nichts anzeigen (oder dezent "Online")
  const showOffline = isOnline === false;
  const showBackendDown = isOnline === true && backendReachable === false;
  const showHealthy = isOnline === true && backendReachable === true;

  return (
    <header className="sticky top-0 z-20 bg-ink-800 text-white pt-safe pb-3 px-4 shadow-md">
      <div className="flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2 min-h-tap">
          <span className="text-xl font-bold tracking-tight">{title}</span>
        </Link>
        <div className="flex items-center gap-2">
          {showOffline && (
            <span className="badge-offline" aria-live="polite" title="Kein Netzwerk-Interface aktiv">
              <WifiOff size={14} /> Offline
            </span>
          )}
          {showBackendDown && (
            <span
              className="inline-flex items-center gap-1 rounded-full bg-red-500/20 px-2 py-0.5 text-xs font-semibold text-red-200"
              aria-live="polite"
              title="Browser online, aber Backend nicht erreichbar"
            >
              <CloudOff size={12} /> Kein Backend
            </span>
          )}
          {showHealthy && (
            <span
              className="inline-flex items-center gap-1 rounded-full bg-emerald-500/20 px-2 py-0.5 text-xs font-semibold text-emerald-200"
              title="Backend erreichbar"
            >
              <CheckCircle2 size={12} /> Online
            </span>
          )}
          {outboxCount > 0 && (
            <span
              className="inline-flex items-center gap-1 rounded-full bg-amber-500/20 px-2 py-0.5 text-xs font-semibold text-amber-200"
              title={`${outboxCount} ausstehende Änderungen`}
            >
              <RefreshCw size={12} /> {outboxCount}
            </span>
          )}
          {right}
        </div>
      </div>
    </header>
  );
}