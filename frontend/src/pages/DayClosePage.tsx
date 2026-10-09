/**
 * Tagesabschluss (Z-Bericht).
 *
 *  - Z-Bericht des gewaehlten Tages: Umsatz, Zahlungsarten, MwSt-Saetze
 *  - Kassenzaehlung mit Zaehlprotokoll (Scheine/Muenzen) und Differenz
 *  - "Tag abschliessen" sperrt die Schicht — danach keine Bons mehr
 *  - Abgeschlossene Tage zeigen den eingefrorenen Bericht (druckbar)
 */
import { useEffect, useMemo, useState } from 'react';
import { CalendarDays, Lock, LockOpen, Printer, Wallet } from 'lucide-react';
import { apiErrorMessage, closeDay, getZReport, listDayCloses } from '@/api/client';
import { formatDate, formatPriceCents } from '@/utils/format';
import type { DayCloseSummary, PaymentMethod, ZReport } from '@/types/api';

/** Gleiche Schicht-Kennung wie POSPage (UTC-Datum). */
function todaySession(): string {
  return new Date().toISOString().slice(0, 10);
}

const PAYMENT_LABEL: Record<PaymentMethod, string> = {
  cash: 'Bar',
  card: 'Karte',
  mixed: 'Gemischt',
};

const NOTES = [50000, 20000, 10000, 5000, 2000, 1000, 500];
const COINS = [200, 100, 50, 20, 10, 5, 2, 1];

const FLOAT_KEY = 'marktpilot.dayclose.openingFloat';

/** "100,50" -> 10050; leer/ungueltig -> null */
function parseEuroToCents(s: string): number | null {
  const t = s.trim().replace(/\./g, '').replace(',', '.');
  if (t === '') return 0;
  if (!/^\d+(\.\d{0,2})?$/.test(t)) return null;
  return Math.round(parseFloat(t) * 100);
}

function denomLabel(cents: number): string {
  return cents >= 100 ? `${cents / 100} €` : `${cents} ct`;
}

function readFloat(): string {
  try {
    return localStorage.getItem(FLOAT_KEY) ?? '';
  } catch {
    return '';
  }
}

function writeFloat(v: string): void {
  try {
    localStorage.setItem(FLOAT_KEY, v);
  } catch {
    /* Private-Browsing — egal. */
  }
}

export function DayClosePage() {
  const [session, setSession] = useState(todaySession());
  const [report, setReport] = useState<ZReport | null>(null);
  const [closes, setCloses] = useState<DayCloseSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [floatStr, setFloatStr] = useState(readFloat());
  const [counts, setCounts] = useState<Record<number, string>>({});
  const [cashierName, setCashierName] = useState('');
  const [notes, setNotes] = useState('');
  const [busy, setBusy] = useState(false);

  const load = async (s: string) => {
    setLoading(true);
    setError(null);
    try {
      const [rep, list] = await Promise.all([getZReport(s), listDayCloses(14)]);
      setReport(rep);
      setCloses(list);
    } catch (e) {
      setError(apiErrorMessage(e, 'Z-Bericht konnte nicht geladen werden.'));
      setReport(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load(session);
    setCounts({});
  }, [session]);

  const openingFloat = parseEuroToCents(floatStr);
  const counted = useMemo(
    () =>
      [...NOTES, ...COINS].reduce(
        (sum, d) => sum + d * (parseInt(counts[d] ?? '', 10) || 0),
        0,
      ),
    [counts],
  );
  const expected = report ? (openingFloat ?? 0) + report.cash_sales_cents : 0;
  const difference = counted - expected;
  const hasMixed = report?.by_payment.some((p) => p.payment_method === 'mixed') ?? false;

  const onClose = async () => {
    if (!report || openingFloat === null) return;
    const ok = window.confirm(
      `Tag ${formatDate(session)} wirklich abschließen?\n\n` +
        `Gezählt: ${formatPriceCents(counted)}\n` +
        `Differenz: ${formatPriceCents(difference)}\n\n` +
        'Danach können für diesen Tag keine Bons mehr gebucht werden.',
    );
    if (!ok) return;
    setBusy(true);
    try {
      const denominations: Record<string, number> = {};
      for (const d of [...NOTES, ...COINS]) {
        const n = parseInt(counts[d] ?? '', 10) || 0;
        if (n > 0) denominations[String(d)] = n;
      }
      const closed = await closeDay(session, {
        opening_float_cents: openingFloat,
        counted_cash_cents: counted,
        cashier_name: cashierName.trim() || null,
        notes: notes.trim() || null,
        denominations,
      });
      writeFloat(floatStr);
      setReport(closed);
      setCloses(await listDayCloses(14));
    } catch (e) {
      window.alert(apiErrorMessage(e, 'Tagesabschluss fehlgeschlagen.'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="px-4 pt-3 pb-8 space-y-3">
      <section className="card p-3 print:hidden">
        <label className="label" htmlFor="dc-date">
          <CalendarDays size={14} className="mr-1 inline" />
          Tag
        </label>
        <input
          id="dc-date"
          type="date"
          className="input"
          value={session}
          max={todaySession()}
          onChange={(e) => e.target.value && setSession(e.target.value)}
        />
      </section>

      {loading && (
        <p className="py-8 text-center text-sm text-[color:var(--text-muted)]">Lade Z-Bericht …</p>
      )}
      {error && (
        <p className="rounded-xl border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-200">
          {error}
        </p>
      )}

      {!loading && report && (
        <>
          <StatusBanner report={report} />

          <Section title="Umsatz">
            <Row label="Verkaufs-Bons">{report.sale_count}</Row>
            <Row label="Stornos">
              {report.storno_count}
              {report.storno_total_cents > 0 && (
                <span className="ml-1 font-normal text-[color:var(--text-muted)]">
                  ({formatPriceCents(report.storno_total_cents)})
                </span>
              )}
            </Row>
            {report.return_count > 0 && <Row label="Retouren">{report.return_count}</Row>}
            {report.first_receipt_number && (
              <Row label="Bon-Nummern">
                <span className="font-mono text-xs">
                  {report.first_receipt_number} – {report.last_receipt_number}
                </span>
              </Row>
            )}
            <div className="mt-1 flex items-center justify-between border-t border-[color:var(--border-strong)] pt-2 text-base font-bold">
              <span>Umsatz brutto</span>
              <span>{formatPriceCents(report.total_cents)}</span>
            </div>
          </Section>

          <Section title="Zahlungsarten">
            {report.by_payment.length === 0 && <Empty />}
            {report.by_payment.map((p) => (
              <Row key={p.payment_method} label={`${PAYMENT_LABEL[p.payment_method]} (${p.receipt_count})`}>
                {formatPriceCents(p.total_cents)}
              </Row>
            ))}
          </Section>

          <Section title="Mehrwertsteuer">
            {report.by_vat.length === 0 ? (
              <Empty />
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-[10px] uppercase tracking-wide text-[color:var(--text-muted)]">
                    <th className="pb-1 font-semibold">Satz</th>
                    <th className="pb-1 text-right font-semibold">Netto</th>
                    <th className="pb-1 text-right font-semibold">MwSt</th>
                    <th className="pb-1 text-right font-semibold">Brutto</th>
                  </tr>
                </thead>
                <tbody>
                  {report.by_vat.map((v) => (
                    <tr key={v.vat_rate}>
                      <td>{v.vat_rate} %</td>
                      <td className="text-right">{formatPriceCents(v.net_cents)}</td>
                      <td className="text-right">{formatPriceCents(v.vat_cents)}</td>
                      <td className="text-right">{formatPriceCents(v.gross_cents)}</td>
                    </tr>
                  ))}
                  <tr className="border-t border-[color:var(--border-strong)] font-semibold">
                    <td className="pt-1">Summe</td>
                    <td className="pt-1 text-right">
                      {formatPriceCents(report.by_vat.reduce((s, v) => s + v.net_cents, 0))}
                    </td>
                    <td className="pt-1 text-right">
                      {formatPriceCents(report.by_vat.reduce((s, v) => s + v.vat_cents, 0))}
                    </td>
                    <td className="pt-1 text-right">
                      {formatPriceCents(report.by_vat.reduce((s, v) => s + v.gross_cents, 0))}
                    </td>
                  </tr>
                </tbody>
              </table>
            )}
          </Section>

          {report.closed ? (
            <ClosedCash report={report} />
          ) : (
            <Section title="Kassenzählung" icon={<Wallet size={14} />}>
              <div>
                <label className="label" htmlFor="dc-float">Wechselgeld zu Tagesbeginn (€)</label>
                <input
                  id="dc-float"
                  className="input"
                  inputMode="decimal"
                  placeholder="0,00"
                  value={floatStr}
                  onChange={(e) => setFloatStr(e.target.value)}
                />
                {openingFloat === null && (
                  <p className="mt-1 text-xs text-red-600">Bitte Betrag wie 150,00 eingeben.</p>
                )}
              </div>

              <DenomGrid title="Scheine" values={NOTES} counts={counts} setCounts={setCounts} />
              <DenomGrid title="Münzen" values={COINS} counts={counts} setCounts={setCounts} />

              <div className="rounded-xl bg-[color:var(--bg-page)] p-3 text-sm">
                <Row label="Wechselgeld">{formatPriceCents(openingFloat ?? 0)}</Row>
                <Row label="+ Bareinnahmen">{formatPriceCents(report.cash_sales_cents)}</Row>
                <Row label="= Soll in der Kasse">{formatPriceCents(expected)}</Row>
                <Row label="Gezählt (Ist)">{formatPriceCents(counted)}</Row>
                <DiffRow cents={difference} />
              </div>
              {hasMixed && (
                <p className="text-xs text-amber-600">
                  Gemischte Zahlungen (Bar + Karte) sind nicht im Soll enthalten, weil die
                  Aufteilung nicht gespeichert wird.
                </p>
              )}

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="label" htmlFor="dc-name">Gezählt von</label>
                  <input
                    id="dc-name"
                    className="input"
                    placeholder="Name"
                    maxLength={80}
                    value={cashierName}
                    onChange={(e) => setCashierName(e.target.value)}
                  />
                </div>
                <div>
                  <label className="label" htmlFor="dc-notes">Notiz</label>
                  <input
                    id="dc-notes"
                    className="input"
                    placeholder="optional"
                    maxLength={500}
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                  />
                </div>
              </div>

              <button
                type="button"
                onClick={onClose}
                disabled={busy || openingFloat === null}
                className="btn btn-primary"
              >
                <Lock size={16} />
                {busy ? 'Schließe ab …' : 'Tag abschließen'}
              </button>
              <p className="text-xs text-[color:var(--text-muted)]">
                Danach sind für diesen Tag keine Bons mehr möglich. Stornos alter Bons
                werden auf den aktuellen Tag gebucht.
              </p>
            </Section>
          )}
        </>
      )}

      {closes.length > 0 && (
        <Section title="Letzte Abschlüsse" className="print:hidden">
          <ul className="space-y-1">
            {closes.map((c) => (
              <li key={c.z_number}>
                <button
                  type="button"
                  onClick={() => setSession(c.cash_session)}
                  className="flex w-full items-center justify-between gap-2 rounded-lg px-1 py-1 text-left text-sm active:bg-[color:var(--bg-hover)]"
                >
                  <span>
                    <span className="font-mono text-xs text-[color:var(--text-muted)]">Z{c.z_number}</span>{' '}
                    {formatDate(c.cash_session)}
                  </span>
                  <span className="flex items-center gap-2">
                    <span className="font-semibold">{formatPriceCents(c.total_cents)}</span>
                    <DiffBadge cents={c.difference_cents} />
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </Section>
      )}
    </div>
  );
}

function StatusBanner({ report }: { report: ZReport }) {
  if (!report.closed) {
    return (
      <div className="card flex items-center gap-2 border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-600">
        <LockOpen size={18} className="shrink-0" />
        <span className="flex-1">
          <strong>{formatDate(report.cash_session)} ist offen.</strong> Zahlen sind vorläufig.
        </span>
      </div>
    );
  }
  return (
    <div className="card flex items-center gap-2 border-emerald-500/40 bg-emerald-500/10 p-3 text-sm text-emerald-700">
      <Lock size={18} className="shrink-0" />
      <span className="flex-1">
        <strong>Z-Bericht Nr. {report.z_number}</strong> · {formatDate(report.cash_session)}
        <br />
        <span className="text-xs">
          Abgeschlossen {report.closed_at && new Date(report.closed_at).toLocaleString('de-DE')}
          {report.cashier_name && ` von ${report.cashier_name}`}
        </span>
      </span>
      <button type="button" onClick={() => window.print()} className="btn btn-ghost btn-sm print:hidden">
        <Printer size={14} />
        Drucken
      </button>
    </div>
  );
}

function ClosedCash({ report }: { report: ZReport }) {
  const denoms = report.denominations
    ? Object.entries(report.denominations)
        .map(([k, n]) => [parseInt(k, 10), n] as const)
        .sort((a, b) => b[0] - a[0])
    : [];
  return (
    <Section title="Kassenbestand" icon={<Wallet size={14} />}>
      <Row label="Wechselgeld">{formatPriceCents(report.opening_float_cents)}</Row>
      <Row label="+ Bareinnahmen">{formatPriceCents(report.cash_sales_cents)}</Row>
      <Row label="= Soll">{formatPriceCents(report.expected_cash_cents)}</Row>
      <Row label="Gezählt (Ist)">{formatPriceCents(report.counted_cash_cents)}</Row>
      <DiffRow cents={report.difference_cents ?? 0} />
      {denoms.length > 0 && (
        <div className="mt-2 grid grid-cols-2 gap-x-4 text-xs text-[color:var(--text-secondary)]">
          {denoms.map(([d, n]) => (
            <div key={d} className="flex justify-between">
              <span>
                {n} × {denomLabel(d)}
              </span>
              <span>{formatPriceCents(d * n)}</span>
            </div>
          ))}
        </div>
      )}
      {report.notes && <p className="text-xs text-[color:var(--text-muted)]">Notiz: {report.notes}</p>}
    </Section>
  );
}

function DenomGrid({
  title,
  values,
  counts,
  setCounts,
}: {
  title: string;
  values: number[];
  counts: Record<number, string>;
  setCounts: React.Dispatch<React.SetStateAction<Record<number, string>>>;
}) {
  return (
    <div>
      <p className="label">{title}</p>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {values.map((d) => (
          <label key={d} className="flex items-center gap-2 text-sm">
            <span className="w-12 shrink-0 text-right font-semibold">{denomLabel(d)}</span>
            <span className="text-[color:var(--text-muted)]">×</span>
            <input
              className="input !py-1"
              inputMode="numeric"
              placeholder="0"
              aria-label={`Anzahl ${denomLabel(d)}`}
              value={counts[d] ?? ''}
              onChange={(e) =>
                setCounts((c) => ({ ...c, [d]: e.target.value.replace(/\D/g, '') }))
              }
            />
          </label>
        ))}
      </div>
    </div>
  );
}

function diffTone(cents: number): string {
  if (cents === 0) return 'text-emerald-600';
  return cents < 0 ? 'text-red-600' : 'text-amber-600';
}

function DiffRow({ cents }: { cents: number }) {
  const label = cents === 0 ? 'Differenz (stimmt)' : cents < 0 ? 'Differenz (Fehlbetrag)' : 'Differenz (Überschuss)';
  return (
    <div className={`flex items-center justify-between border-t border-[color:var(--border-strong)] pt-1 font-bold ${diffTone(cents)}`}>
      <span>{label}</span>
      <span>
        {cents > 0 ? '+' : ''}
        {formatPriceCents(cents)}
      </span>
    </div>
  );
}

function DiffBadge({ cents }: { cents: number }) {
  if (cents === 0) return <span className="text-xs text-emerald-600">±0</span>;
  return (
    <span className={`text-xs ${diffTone(cents)}`}>
      {cents > 0 ? '+' : ''}
      {formatPriceCents(cents)}
    </span>
  );
}

function Section({
  title,
  icon,
  className = '',
  children,
}: {
  title: string;
  icon?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <section className={`card p-3 ${className}`}>
      <h3 className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-[color:var(--text-secondary)]">
        {icon}
        {title}
      </h3>
      <div className="space-y-2">{children}</div>
    </section>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-[color:var(--text-secondary)]">{label}</span>
      <span className="font-semibold">{children}</span>
    </div>
  );
}

function Empty() {
  return <p className="text-sm text-[color:var(--text-muted)]">Keine Buchungen.</p>;
}
