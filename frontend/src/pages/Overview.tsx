import { useDemo } from '../demo'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type Dashboard } from '../api'
import AgentChain from '../components/AgentChain'
import { Button, EmptyState, ErrorNote, PageHeader, SectionTitle } from '../components/ui'
import { useAsync } from '../useAsync'

function Kpi({ label, value, note, to, highlight = false }: {
  label: string; value: string; note: string; to: string; highlight?: boolean
}) {
  return (
    <Link to={to} className={`group relative block bg-sheet px-5 pb-5 pt-4 hover:bg-paper ${highlight ? 'before:absolute before:inset-x-0 before:top-0 before:h-[3px] before:bg-amber' : ''}`}>
      <dt className="tp-eyebrow flex items-center justify-between gap-2">
        {label}
        <span aria-hidden className="text-slate/60 transition-transform group-hover:translate-x-0.5 group-hover:text-petrol">→</span>
      </dt>
      <dd className={`mt-3 font-serif text-[40px] font-semibold leading-none tracking-[-0.02em] ${highlight ? 'text-amber' : 'text-ink'}`}>{value}</dd>
      <dd className="mt-2.5 border-t border-rule pt-2.5 text-xs text-slate">{note}</dd>
    </Link>
  )
}

function NextSteps({ todo }: { todo: Dashboard['todo'] }) {
  return (
    <section aria-labelledby="next">
      <SectionTitle id="next">Next steps</SectionTitle>
      {todo.length === 0 ? (
        <p className="border border-rule bg-sheet px-5 py-5 text-sm text-slate">
          All caught up. Add a client or import new tax updates to start the chain again.
        </p>
      ) : (
        <ol className="divide-y divide-rule border border-rule bg-sheet">
          {todo.map((t, i) => (
            <li key={t.key}>
              <Link to={t.to} className="group flex min-h-12 items-center gap-4 px-5 py-3 hover:bg-paper">
                <span className="w-6 shrink-0 font-mono text-xs font-medium text-petrol">
                  {String(i + 1).padStart(2, '0')}
                </span>
                <span className="flex-1 text-[15px] font-medium">{t.label}</span>
                <span aria-hidden className="text-slate transition-transform group-hover:translate-x-0.5 group-hover:text-petrol">→</span>
              </Link>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}

function WhoToCall({ clients }: { clients: Dashboard['top_clients'] }) {
  return (
    <section aria-labelledby="top">
      <SectionTitle id="top">Who to call first</SectionTitle>
      {clients.length === 0 ? (
        <p className="border border-rule bg-sheet px-5 py-5 text-sm text-slate">
          No open alerts. When a new tax update affects a former client, it appears here, ranked by relevance.
        </p>
      ) : (
        <ul className="divide-y divide-rule border border-rule bg-sheet">
          {clients.map((c) => (
            <li key={c.client_id}>
              <Link to={`/alerts#alert-${c.alert_id}`} className="flex items-start gap-4 px-5 py-3.5 hover:bg-paper">
                <span className="flex h-10 w-11 shrink-0 items-center justify-center border border-amber/35 bg-amber-soft font-serif text-xl font-semibold text-amber" aria-label={`Highest score ${c.score}`}>{c.score}</span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-baseline justify-between gap-3">
                    <span className="font-medium">{c.client}</span>
                    <span className="shrink-0 text-xs text-slate">{c.topics.length} {c.topics.length === 1 ? 'topic' : 'topics'}</span>
                  </span>
                  {c.topics.slice(0, 2).map((t) => (
                    <span key={t.title} className="mt-0.5 block truncate text-sm text-slate">{t.title}</span>
                  ))}
                  {c.topics.length > 2 && <span className="mt-0.5 block text-xs text-slate">and {c.topics.length - 2} more</span>}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

export default function Overview() {
  const demo = useDemo()
  const { data, error, reload } = useAsync(api.dashboard)
  const [loading, setLoading] = useState(false)
  const [demoError, setDemoError] = useState<string | null>(null)

  const loadDemo = async () => {
    setLoading(true)
    setDemoError(null)
    try {
      await api.loadDemo()
      reload()
    } catch (e) {
      setDemoError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  const c = data?.counts
  const empty = c && c.clients === 0 && c.updates === 0

  return (
    <>
      <PageHeader
        title="Overview"
        intro="Which former clients should you call this week, and why. TaxPulse matches new BMF letters and BFH rulings against the due diligence files of your past mandates."
      />
      {error && <ErrorNote message={error} />}

      {empty && (
        <EmptyState title="Your portfolio is empty">
          <p>Load four fictional German companies with their data rooms and six sample tax updates to try TaxPulse.</p>
          <div className="mt-5">
            <Button onClick={loadDemo} disabled={loading}>{loading ? 'Loading demo data…' : 'Load demo data'}</Button>
          </div>
          {demoError && <div className="mt-4 text-left"><ErrorNote message={demoError} /></div>}
        </EmptyState>
      )}

      {data && c && !empty && (
        <div className="space-y-12">
          <dl className="grid grid-cols-2 gap-px border border-rule bg-rule lg:grid-cols-4">
            <Kpi label="Clients profiled" value={`${c.clients_profiled} / ${c.clients}`} to="/clients"
              note={c.clients_missing_profile ? `${c.clients_missing_profile} waiting for the Profiler` : 'Every data room read'} />
            <Kpi label="Alerts to review" value={String(c.alerts_to_review)} to="/alerts" highlight={c.alerts_to_review > 0}
              note={`${c.alerts_accepted} accepted so far`} />
            <Kpi label="Emails to approve" value={String(c.drafts_to_review)} to="/outreach"
              note={`${c.drafts_ready} ready to send · ${c.emails_sent} sent`} />
            <Kpi label={demo ? "AI cost, as recorded" : "AI cost so far"} value={`$${c.cost_usd.toFixed(2)}`} to="/runs"
              note={`${c.updates} tax updates, ${c.updates_relevant} relevant`} />
          </dl>

          <div className="grid gap-10 lg:grid-cols-2">
            <NextSteps todo={data.todo} />
            <WhoToCall clients={data.top_clients} />
          </div>

          <AgentChain onFinished={reload} />
        </div>
      )}
    </>
  )
}
