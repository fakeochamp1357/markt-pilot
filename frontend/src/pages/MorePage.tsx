import { useState } from 'react';
import { Database, FileDown, Info, Trash2, RefreshCw } from 'lucide-react';
import { listOutbox } from '@/db/dexie';
import { syncOutboxOnce } from '@/hooks/useOutboxSync';
import { useAppStore } from '@/store';
import { useOnlineStatus } from '@/hooks/useOnlineStatus';

export function MorePage() {
  const isOnline = useOnlineStatus();
  const outboxCount = useAppStore((s) => s.outboxCount);
  const [busy, setBusy] = useState(false);
  const [info, setInfo] = useState<string | null>(null);

  const handleSync = async () => {
    setBusy(true);
    setInfo(null);
    try {
      const queue = await listOutbox();
      const res = await syncOutboxOnce();
      setInfo(`Verarbeitet: ${res.processed}, Fehler: ${res.failed}, vorher in Outbox: ${queue.length}`);
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
        <Row label="Verbindung">{isOnline ? 'online' : 'offline'}</Row>
        <Row label="Offene Änderungen">{outboxCount}</Row>
      </Section>

      <Section icon={<RefreshCw />} title="Synchronisation">
        <button
          type="button"
          onClick={handleSync}
          disabled={busy}
          className="btn-primary w-full"
        >
          {busy ? 'Synchronisiere …' : 'Jetzt synchronisieren'}
        </button>
        {info && <p className="mt-2 text-xs text-ink-600">{info}</p>}
      </Section>

      <Section icon={<Database />} title="Daten">
        <button
          type="button"
          onClick={handleClearCache}
          className="btn-secondary w-full"
        >
          <Trash2 size={18} className="inline mr-1" /> Lokalen Cache leeren
        </button>
        <p className="mt-2 text-xs text-ink-500">
          Hinweis: Beim Leeren werden nur die Browser-Daten entfernt.
          Server-Daten bleiben unverändert.
        </p>
      </Section>

      <Section icon={<FileDown />} title="Export">
        <a
          href="http://localhost:8000/api/products/export?format=csv"
          className="btn-secondary w-full"
          download
        >
          CSV-Export herunterladen
        </a>
        <a
          href="http://localhost:8000/api/products/export?format=json"
          className="btn-secondary w-full"
          download
        >
          JSON-Export herunterladen
        </a>
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