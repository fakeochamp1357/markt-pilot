import { WifiOff, RefreshCw } from 'lucide-react';
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
  const outboxCount = useAppStore((s) => s.outboxCount);

  return (
    <header className="sticky top-0 z-20 bg-ink-800 text-white pt-safe pb-3 px-4 shadow-md">
      <div className="flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2 min-h-tap">
          <span className="text-xl font-bold tracking-tight">{title}</span>
        </Link>
        <div className="flex items-center gap-2">
          {!isOnline && (
            <span className="badge-offline" aria-live="polite">
              <WifiOff size={14} /> Offline
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