import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Database,
  FileText,
  FileJson,
  Info,
  Trash2,
  RefreshCw,
  CheckCircle2,
  CloudOff,
  WifiOff,
  Settings,
  Receipt,
} from 'lucide-react';
import { listOutbox } from '@/db/dexie';
import { resetFailedOutboxEntries, syncOutboxOnce } from '@/hooks/useOutboxSync';
import { useAppStore } from '@/store';
import { useOnlineStatus } from '@/hooks/useOnlineStatus';
import { ThemeToggle } from '@/components/ThemeToggle';

function statusLabel(
  isOnline: boolean,
  backendReachable: boolean | null,
): { text: string; tone: 'good' | 'warn' | 'bad'; icon: React.ReactNode } {
  if (!isOnline) {
    return { text: 'Browser offline', tone: 'bad', icon: <WifiOff size={14} /> };
  }
  if (backendReachable === false) {
    return { text: 'Kein Backend (WLAN evtl. tot)', tone: 'bad', icon: <CloudOff size={14} /> };
  }
  if (backendReachable === null) {
    return { text: 'Prüfe Backend …', tone: 'warn', icon: <RefreshCw size={14} /> };
  }
  return { text: 'Online', tone: 'good', icon: <CheckCircle2 size={14} /> };
}

const TONE_CLASSES: Record<'good' | 'warn' | 'bad', string> = {
  good: 'text-emerald-600',
  warn: 'text-amber-600',
  bad: 'text-red-600',
};

export function MorePage() {
  const isOnline = useOnlineStatus();
  const backendReachable = useAppStore((s) => s.backendReachable);
  const outboxCount = useAppStore((s) => s.outboxCount);
  const [busy, setBusy] = useState(false);
  const [info, setInfo] = useState<string | null>(null);
  const status = statusLabel(isOnline, backendReachable);

  const handleSync = async () => {
    setBusy(true);
    setInfo(null);
    try {
      const queue = await listOutbox();
      const resetted = await resetFailedOutboxEntries();
      const res = await syncOutboxOnce();
      setInfo(
        `Verarbeitet: ${res.processed}, Fehler: ${res.failed}, ` +
          `vorher in Outbox: ${queue.length}, davon reaktiviert: ${resetted}.`,
      );
    } catch (e) {
      setInfo(e instanceof Error ? e.message : 'Sync fehlgeschlagen');
    } finally {
      setBusy(false);
    }
  };

  const handleClearCache = async () => {
    if (!window.confirm('Lokalen Cache wirklich leeren?')) return;
    const { db } = await import('@/db/dexie');
    await db.products.clear();
    await db.categories.clear();
    await db.movements.clear();
    setInfo('Cache geleert. Seite neu laden für frische Daten.');
  };

  return (
    <div className="px-4 pt-3 space-y-3">
      <Section icon={<Info />} title="Status">
        <Row label="Verbindung">
          <span className={`inline-flex items-center gap-1 ${TONE_CLASSES[status.tone]}`}>
            {status.icon} {status.text}
          </span>
        </Row>
        <Row label="Browser online">{isOnline ? 'ja' : 'nein'}</Row>
        <Row label="Backend erreichbar">
          {backendReachable === null ? 'noch nicht geprüft' : backendReachable ? 'ja' : 'nein'}
        </Row>
        <Row label="Offene Änderungen">{outboxCount}</Row>
      </Section>

      <Section icon={<RefreshCw />} title="Synchronisation">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handleSync}
            disabled={busy}
            className="btn btn-primary"
          >
            <RefreshCw size={16} className={busy ? 'animate-spin' : ''} />
            {busy ? 'Synchronisiere …' : 'Jetzt synchronisieren'}
          </button>
          <p className="flex-1 text-xs text-ink-500">
            Setzt fehlgeschlagene Einträge zurück und versucht erneut.
          </p>
        </div>
        {info && (
          <p className="mt-2 text-xs text-ink-600 border-l-2 border-brand-500 pl-2">
            {info}
          </p>
        )}
      </Section>

      <Section icon={<Receipt />} title="Kassenbuch">
        <Link
          to="/receipts"
          className="btn btn-secondary w-full"
        >
          <Receipt size={16} />
          Heutige Bons anzeigen
        </Link>
        <p className="mt-1 text-xs text-ink-500">
          Tagesübersicht, alle Bons, Storno-Funktion.
        </p>
      </Section>

      <Section icon={<Settings />} title="Einstellungen">
        <div>
          <p className="label !mb-2">Farbschema</p>
          <ThemeToggle />
          <p className="mt-2 text-xs text-ink-500">
            „System" folgt der OS-Einstellung. „Dunkel" ist schwarz mit
            futuristischem Lila.
          </p>
        </div>
      </Section>

      <Section icon={<Database />} title="Daten">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handleClearCache}
            className="btn btn-secondary btn-sm"
          >
            <Trash2 size={14} />
            Cache leeren
          </button>
          <p className="flex-1 text-xs text-ink-500">
            Entfernt nur Browser-Daten; Server bleibt unberührt.
          </p>
        </div>
      </Section>

      <Section icon={<FileText />} title="Export">
        <div className="grid grid-cols-2 gap-2">
          <a
            href="http://localhost:8000/api/products/export?format=csv"
            className="btn btn-secondary"
            download
            aria-label="Preisliste als CSV herunterladen"
          >
            <FileText size={16} />
            <span>CSV</span>
          </a>
          <a
            href="http://localhost:8000/api/products/export?format=json"
            className="btn btn-secondary"
            download
            aria-label="Preisliste als JSON herunterladen"
          >
            <FileJson size={16} />
            <span>JSON</span>
          </a>
          <a
            href="http://localhost:8000/api/products/export?format=xlsx"
            className="btn btn-secondary"
            download
            aria-label="Preisliste als XLSX herunterladen"
          >
            <Database size={16} />
            <span>XLSX</span>
          </a>
          <a
            href="http://localhost:8000/api/products/export?format=pdf"
            className="btn btn-secondary"
            download
            aria-label="Preisliste als PDF herunterladen"
          >
            <FileText size={16} />
            <span>PDF</span>
          </a>
        </div>
        <p className="mt-2 text-xs text-ink-500">
          Vollständiger Export deiner Preisliste. Datei wird heruntergeladen.
        </p>
      </Section>

      <Section icon={<Info />} title="Über">
        <p className="text-sm text-ink-600">
          MarktPilot v0.1.0 — Mobile-first Web-Frontend für Preislisten
          und Warenbestand. Offline-fähig dank Service Worker und
          IndexedDB-Cache.
        </p>
      </Section>
    </div>
  );
}

function Section({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="card p-3">
      <h3 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-ink-600 mb-2">
        <span className="text-ink-500">{icon}</span> {title}
      </h3>
      <div className="space-y-2">{children}</div>
    </section>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-ink-600">{label}</span>
      <span className="font-semibold">{children}</span>
    </div>
  );
}