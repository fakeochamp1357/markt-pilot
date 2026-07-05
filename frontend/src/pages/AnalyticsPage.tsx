import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  Bell,
  Boxes,
  CalendarClock,
  CircleAlert,
  CircleX,
  Euro,
  PackageX,
  RefreshCw,
  TrendingUp,
  Wallet,
} from 'lucide-react';
import {
  getDashboardSummary,
  getDeadStock,
  getExpiryAlerts,
  getMargins,
  getNotifications,
  getReorderAlerts,
  getTopSellers,
} from '@/api/client';
import { useAppStore } from '@/store';
import { formatDate, formatPrice, formatQty } from '@/utils/format';
import type {
  AnalyticsPeriod,
  AnalyticsSeverity,
  DashboardSummary,
  DeadStockRow,
  ExpiryAlert,
  MarginRow,
  NotificationItem,
  ReorderAlert,
  TopSeller,
} from '@/types/api';

const PERIODS: { value: AnalyticsPeriod; label: string }[] = [
  { value: 'week', label: '7 Tage' },
  { value: 'month', label: '30 Tage' },
  { value: 'quarter', label: '90 Tage' },
  { value: 'year', label: '1 Jahr' },
  { value: 'all', label: 'Alles' },
];

const SEVERITY_STYLE: Record<AnalyticsSeverity, { bg: string; text: string; dot: string }> = {
  danger: { bg: 'bg-red-50', text: 'text-red-700', dot: 'bg-red-500' },
  warn: { bg: 'bg-amber-50', text: 'text-amber-800', dot: 'bg-amber-500' },
  info: { bg: 'bg-sky-50', text: 'text-sky-800', dot: 'bg-sky-500' },
};

export function AnalyticsPage() {
  const isOnline = useAppStore((s) => s.isOnline);
  const [period, setPeriod] = useState<AnalyticsPeriod>('month');
  const [warnDays, setWarnDays] = useState(7);

  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [topSellers, setTopSellers] = useState<TopSeller[]>([]);
  const [margins, setMargins] = useState<MarginRow[]>([]);
  const [deadStock, setDeadStock] = useState<DeadStockRow[]>([]);
  const [expiries, setExpiries] = useState<ExpiryAlert[]>([]);
  const [reorders, setReorders] = useState<ReorderAlert[]>([]);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, ts, m, d, e, r, n] = await Promise.all([
        getDashboardSummary({ period, warn_days: warnDays }),
        getTopSellers({ period, limit: 10, sort_by: 'qty' }),
        getMargins({ period, limit: 10 }),
        getDeadStock({ period, limit: 30 }),
        getExpiryAlerts({ warn_days: warnDays, limit: 50 }),
        getReorderAlerts({ limit: 50 }),
        getNotifications({ period, warn_days: warnDays, limit: 30 }),
      ]);
      setSummary(s);
      setTopSellers(ts);
      setMargins(m);
      setDeadStock(d);
      setExpiries(e);
      setReorders(r);
      setNotifications(n);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [period, warnDays]);

  useEffect(() => {
    void load();
  }, [load]);

  const counts = useMemo(() => {
    const expired = notifications.filter((n) => n.type === 'expired').length;
    const soon = notifications.filter((n) => n.type === 'expiry_soon').length;
    const reorder = notifications.filter((n) => n.type === 'reorder').length;
    return { expired, soon, reorder, total: notifications.length };
  }, [notifications]);

  return (
    <div className="px-4 pt-3 pb-4 space-y-4">
      <div className="flex items-center gap-2 overflow-x-auto -mx-4 px-4">
        <span className="text-xs uppercase tracking-wide text-ink-500 mr-1">Zeitraum:</span>
        {PERIODS.map((p) => (
          <button
            key={p.value}
            type="button"
            onClick={() => setPeriod(p.value)}
            className={`whitespace-nowrap rounded-full px-3 py-1 text-xs font-semibold border transition-colors ${
              period === p.value
                ? 'bg-brand-600 text-white border-brand-600'
                : 'bg-white text-ink-700 border-gray-200 hover:bg-gray-50'
            }`}
          >
            {p.label}
          </button>
        ))}
        <button
          type="button"
          onClick={() => void load()}
          disabled={loading}
          className="ml-auto inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-semibold bg-gray-100 text-ink-700 hover:bg-gray-200 disabled:opacity-50"
        >
          <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
          Aktualisieren
        </button>
      </div>

      {error && (
        <div className="card border-red-200 bg-red-50 p-3 text-sm text-red-700 flex items-center gap-2">
          <CircleAlert size={16} /> {error}
        </div>
      )}

      {!isOnline && (
        <div className="card border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
          Offline — die Analyse basiert auf dem letzten Stand, den dein Gerät
          vom Server kennt.
        </div>
      )}

      <DashboardSection summary={summary} counts={counts} />

      <Section
        title="Top-Seller"
        icon={<TrendingUp size={18} />}
        subtitle={`Verkauft im Zeitraum ${periodLabel(period)}`}
        empty={topSellers.length === 0}
        emptyText="Noch keine Verkäufe in diesem Zeitraum."
      >
        <TopSellersList rows={topSellers} />
      </Section>

      <Section
        title="Marge pro Produkt"
        icon={<Wallet size={18} />}
        subtitle="Sortiert nach absoluter Marge (€)"
        empty={margins.length === 0}
        emptyText="Noch keine Verkäufe für eine Margin-Analyse."
      >
        <MarginsList rows={margins} />
      </Section>

      <Section
        title="Nachbestellen"
        icon={<Boxes size={18} />}
        subtitle={`${reorders.length} Produkt(e) unter Mindestbestand`}
        empty={reorders.length === 0}
        emptyText="Alles ausreichend auf Lager."
      >
        <ReorderList rows={reorders} />
      </Section>

      <Section
        title="MHD-Warnungen"
        icon={<CalendarClock size={18} />}
        subtitle={`Schwelle: ${warnDays} Tage`}
        right={
          <div className="flex items-center gap-1">
            {[3, 7, 14, 30].map((d) => (
              <button
                key={d}
                type="button"
                onClick={() => setWarnDays(d)}
                className={`rounded-full px-2 py-0.5 text-xs font-semibold border ${
                  warnDays === d
                    ? 'bg-brand-600 text-white border-brand-600'
                    : 'bg-white text-ink-700 border-gray-200 hover:bg-gray-50'
                }`}
              >
                {d} T
              </button>
            ))}
          </div>
        }
        empty={expiries.length === 0}
        emptyText="Nichts läuft bald ab."
      >
        <ExpiryList rows={expiries} />
      </Section>

      <Section
        title="Ladenhüter"
        icon={<PackageX size={18} />}
        subtitle={`Keine Verkäufe in ${periodLabel(period)}`}
        empty={deadStock.length === 0}
        emptyText="Alles wurde im Zeitraum mindestens einmal verkauft."
      >
        <DeadStockList rows={deadStock} />
      </Section>

      <Section
        title="Alle Benachrichtigungen"
        icon={<Bell size={18} />}
        subtitle={`${notifications.length} aktiv`}
        empty={notifications.length === 0}
        emptyText="Keine offenen Meldungen."
      >
        <NotificationsList items={notifications} />
      </Section>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sections
// ---------------------------------------------------------------------------

function Section({
  title,
  subtitle,
  icon,
  empty,
  emptyText,
  right,
  children,
}: {
  title: string;
  subtitle?: string;
  icon: React.ReactNode;
  empty: boolean;
  emptyText: string;
  right?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-2">
      <header className="flex items-center gap-2">
        <span className="text-ink-700">{icon}</span>
        <div className="flex-1 min-w-0">
          <h2 className="text-base font-bold leading-tight">{title}</h2>
          {subtitle && <p className="text-xs text-ink-500">{subtitle}</p>}
        </div>
        {right}
      </header>
      {empty ? (
        <p className="card p-4 text-center text-sm text-ink-500">{emptyText}</p>
      ) : (
        children
      )}
    </section>
  );
}

function DashboardSection({
  summary,
  counts,
}: {
  summary: DashboardSummary | null;
  counts: { expired: number; soon: number; reorder: number; total: number };
}) {
  return (
    <section className="grid grid-cols-2 gap-2">
      <Kpi
        icon={<Boxes size={18} />}
        label="Aktive Produkte"
        value={summary ? String(summary.total_active_products) : '—'}
      />
      <Kpi
        icon={<Euro size={18} />}
        label="Lagerwert"
        value={summary ? formatPrice(summary.total_inventory_value) : '—'}
      />
      <Kpi
        icon={<TrendingUp size={18} />}
        label="Umsatz (Zeitraum)"
        value={summary ? formatPrice(summary.total_sales_period) : '—'}
      />
      <Kpi
        icon={<Wallet size={18} />}
        label="Marge (Zeitraum)"
        value={summary ? formatPrice(summary.total_margin_period) : '—'}
        tone="good"
      />
      <Kpi
        icon={<CircleX size={18} />}
        label="MHD abgelaufen"
        value={String(counts.expired)}
        tone={counts.expired > 0 ? 'danger' : undefined}
      />
      <Kpi
        icon={<CalendarClock size={18} />}
        label="MHD bald"
        value={String(counts.soon)}
        tone={counts.soon > 0 ? 'warn' : undefined}
      />
      <Kpi
        icon={<AlertTriangle size={18} />}
        label="Nachbestellen"
        value={String(counts.reorder)}
        tone={counts.reorder > 0 ? 'warn' : undefined}
      />
      <Kpi
        icon={<Bell size={18} />}
        label="Notifications"
        value={String(counts.total)}
      />
    </section>
  );
}

function Kpi({
  icon,
  label,
  value,
  tone,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  tone?: 'good' | 'warn' | 'danger';
}) {
  const cls =
    tone === 'danger'
      ? 'border-red-200 bg-red-50'
      : tone === 'warn'
        ? 'border-amber-200 bg-amber-50'
        : tone === 'good'
          ? 'border-emerald-200 bg-emerald-50'
          : '';
  const valueCls =
    tone === 'danger'
      ? 'text-red-700'
      : tone === 'warn'
        ? 'text-amber-800'
        : tone === 'good'
          ? 'text-emerald-700'
          : 'text-ink-900';
  return (
    <div className={`card p-3 ${cls}`}>
      <div className="flex items-center gap-2 text-ink-600">
        {icon}
        <span className="text-xs font-medium uppercase tracking-wide">{label}</span>
      </div>
      <p className={`mt-1 text-2xl font-bold ${valueCls}`}>{value}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Listen
// ---------------------------------------------------------------------------

function TopSellersList({ rows }: { rows: TopSeller[] }) {
  return (
    <ul className="space-y-1">
      {rows.map((r, idx) => (
        <li key={r.product_id} className="card flex items-center gap-3 p-3">
          <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-brand-100 text-xs font-bold text-brand-700">
            {idx + 1}
          </span>
          <div className="min-w-0 flex-1">
            <p className="font-semibold truncate">{r.name}</p>
            <p className="text-xs text-ink-500">
              {formatQty(r.qty_sold)} verkauft · Marge {formatPrice(r.margin)}
            </p>
          </div>
          <div className="text-right">
            <p className="font-bold">{formatPrice(r.revenue)}</p>
            <p className="text-xs text-emerald-700">{formatQty(r.margin_pct)} %</p>
          </div>
        </li>
      ))}
    </ul>
  );
}

function MarginsList({ rows }: { rows: MarginRow[] }) {
  return (
    <ul className="space-y-1">
      {rows.map((r) => {
        const pct = parseFloat(r.margin_pct);
        const pctCls =
          !isFinite(pct) || pct < 0
            ? 'text-red-700'
            : pct < 20
              ? 'text-amber-700'
              : 'text-emerald-700';
        return (
          <li key={r.product_id} className="card p-3">
            <div className="flex items-center gap-3">
              <div className="min-w-0 flex-1">
                <p className="font-semibold truncate">{r.name}</p>
                <p className="text-xs text-ink-500">
                  Verkauf: {formatPrice(r.revenue)} · Kosten: {formatPrice(r.cost)} ·{' '}
                  {formatQty(r.qty_sold)}×
                </p>
              </div>
              <div className="text-right">
                <p className="font-bold">{formatPrice(r.margin)}</p>
                <p className={`text-xs ${pctCls}`}>
                  {isFinite(pct) ? `${pct.toFixed(1)} %` : '—'}
                </p>
              </div>
            </div>
            <MarginBar pct={pct} />
          </li>
        );
      })}
    </ul>
  );
}

function MarginBar({ pct }: { pct: number }) {
  // 0–100 % Mapping; bei negativer Marge roter Bereich.
  const clamped = Math.max(-50, Math.min(100, pct));
  const widthPct = Math.min(100, Math.abs(clamped));
  const left = clamped < 0 ? 50 - widthPct / 2 : 50;
  const color =
    clamped < 0
      ? 'bg-red-500'
      : clamped < 20
        ? 'bg-amber-500'
        : 'bg-emerald-500';
  return (
    <div className="relative mt-2 h-1.5 rounded-full bg-gray-100">
      <span className="absolute left-1/2 top-0 h-full w-px bg-gray-300" aria-hidden />
      <span
        className={`absolute top-0 h-full rounded-full ${color}`}
        style={{ left: `${left}%`, width: `${widthPct / 2}%` }}
      />
    </div>
  );
}

function ReorderList({ rows }: { rows: ReorderAlert[] }) {
  return (
    <ul className="space-y-1">
      {rows.map((r) => (
        <li key={r.product_id} className="card flex items-center gap-3 p-3">
          <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-amber-100 text-amber-700">
            <Boxes size={16} />
          </span>
          <div className="min-w-0 flex-1">
            <p className="font-semibold truncate">{r.name}</p>
            <p className="text-xs text-ink-500">
              Aktuell {formatQty(r.stock_quantity)} · Mindest{' '}
              {formatQty(r.min_stock_level)} · Defizit {formatQty(r.deficit)}
            </p>
          </div>
          <div className="text-right">
            <p className="text-xs text-ink-500 uppercase tracking-wide">Bestellvorschlag</p>
            <p className="text-lg font-bold text-amber-700">
              {formatQty(r.suggested_order_qty)}
            </p>
          </div>
        </li>
      ))}
    </ul>
  );
}

function ExpiryList({ rows }: { rows: ExpiryAlert[] }) {
  return (
    <ul className="space-y-1">
      {rows.map((r) => {
        const sty = SEVERITY_STYLE[r.severity];
        const tag =
          r.days_until_expiry < 0
            ? `vor ${-r.days_until_expiry} Tag(en)`
            : r.days_until_expiry === 0
              ? 'heute'
              : `in ${r.days_until_expiry} Tag(en)`;
        return (
          <li
            key={r.product_id}
            className={`card flex items-center gap-3 p-3 ${sty.bg}`}
          >
            <span className={`inline-flex h-2.5 w-2.5 rounded-full ${sty.dot}`} />
            <div className="min-w-0 flex-1">
              <p className={`font-semibold truncate ${sty.text}`}>{r.name}</p>
              <p className={`text-xs ${sty.text}`}>
                MHD {formatDate(r.expiry_date)} · abgelaufen {tag} · Bestand{' '}
                {formatQty(r.stock_quantity)}
              </p>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function DeadStockList({ rows }: { rows: DeadStockRow[] }) {
  return (
    <ul className="space-y-1">
      {rows.map((r) => (
        <li key={r.product_id} className="card flex items-center gap-3 p-3">
          <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-sky-100 text-sky-700">
            <PackageX size={16} />
          </span>
          <div className="min-w-0 flex-1">
            <p className="font-semibold truncate">{r.name}</p>
            <p className="text-xs text-ink-500">
              {r.last_sale_at
                ? `Letzter Verkauf vor ${r.days_since_last_sale ?? '?'} Tag(en)`
                : 'Noch nie verkauft'}{' '}
              · {formatQty(r.stock_quantity)} auf Lager ({formatPrice(r.stock_value)})
            </p>
          </div>
        </li>
      ))}
    </ul>
  );
}

function NotificationsList({ items }: { items: NotificationItem[] }) {
  return (
    <ul className="space-y-1">
      {items.map((n, i) => {
        const sty = SEVERITY_STYLE[n.severity];
        const tag = notificationTag(n.type);
        return (
          <li
            key={`${n.type}-${n.product_id}-${i}`}
            className={`card flex items-start gap-3 p-3 ${sty.bg}`}
          >
            <span className={`mt-1 inline-flex h-2 w-2 rounded-full ${sty.dot}`} />
            <div className="min-w-0 flex-1">
              <p className={`text-xs font-semibold uppercase tracking-wide ${sty.text}`}>
                {tag}
              </p>
              <p className={`font-semibold truncate ${sty.text}`}>{n.product_name}</p>
              <p className={`text-xs ${sty.text}`}>{n.message}</p>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function notificationTag(t: NotificationItem['type']): string {
  switch (t) {
    case 'expired':
      return 'MHD abgelaufen';
    case 'expiry_soon':
      return 'MHD bald';
    case 'reorder':
      return 'Nachbestellen';
    case 'dead_stock':
      return 'Ladenhüter';
  }
}

function periodLabel(p: AnalyticsPeriod): string {
  switch (p) {
    case 'week':
      return '7 Tagen';
    case 'month':
      return '30 Tagen';
    case 'quarter':
      return '90 Tagen';
    case 'year':
      return '1 Jahr';
    case 'all':
      return 'gesamter Zeitraum';
  }
}