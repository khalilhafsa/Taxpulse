import { useDemo } from '../demo'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type Dashboard } from '../api'
import AgentChain from '../components/AgentChain'
import { isoWeek } from '../components/Layout'
import { Button, EmptyState, ErrorNote, PageHeader, SectionTitle } from '../components/ui'
import { useAsync } from '../useAsync'

/** The lead of the week: the former client to call first, set like the front page of a briefing. */
function Lead({ clients, toReview }: { clients: Dashboard['top_clients']; toReview: number }) {
  const [top, ...rest] = clients
  return (
    <section aria-labelledby="lead" className="relative overflow-hidden bg-night text-white">
      <div aria-hidden className="pointer-events-none absolute -right-10 -top-24 select-none font-serif text-[300px] font-semibold leading-none text-white/[0.04]">§</div>
      <div className="relative grid gap-10 px-6 py-9 md:px-10 md:py-12 lg:grid-cols-[minmax(0,1fr)_19rem] lg:gap-14">
        <div>
          <p className="tp-eyebrow text-signal">Briefing · week {isoWeek(new Date())}</p>
          {top ? (
            <>
              <h1 id="lead" className="mt-4 max-w-3xl font-serif text-[40px] font-semibold leading-[1.02] tracking-[-0.03em] md:text-[60px]">
                Call {top.client} first.
              </h1>
              <ul className="mt-6 max-w-2xl space-y-2 text-[15px] leading-relaxed text-white/80">
                {top.topics.slice(0, 3).map((t) => (
                  <li key={t.title} className="flex gap-3">
                    <span className="w-7 shrink-0 font-mono text-[13px] text-relevance">{t.score}</span>
                    <span>{t.title}</span>
                  </li>
                ))}
              </ul>
              <div className="mt-8 flex flex-wrap items-center gap-3">
                <Link to={`/alerts#alert-${top.alert_id}`}
                  className="inline-flex min-h-11 items-center gap-2 bg-signal px-5 text-sm font-semibold text-night hover:bg-white">
                  Open the alert <span aria-hidden>→</span>
                </Link>
                <Link to="/alerts" className="inline-flex min-h-11 items-center px-3 text-sm font-semibold text-white/80 underline decoration-white/30 underline-offset-4 hover:text-white hover:decoration-white">
                  {toReview} {toReview === 1 ? 'alert' : 'alerts'} to review
                </Link>
              </div>
            </>
          ) : (
            <>
              <h1 id="lead" className="mt-4 max-w-3xl font-serif text-[40px] font-semibold leading-[1.02] tracking-[-0.03em] md:text-[60px]">
                No former client needs a call this week.
              </h1>
              <p className="mt-5 max-w-xl text-[15px] leading-relaxed text-white/75">
                When a new BMF letter or BFH ruling affects one of your past mandates, it leads this briefing, ranked by relevance.
              </p>
            </>
          )}
        </div>

        {top && (
          <div className="border-t border-white/15 pt-8 lg:border-l lg:border-t-0 lg:pl-10 lg:pt-0">
            <p className="tp-eyebrow text-white/60">Relevance score</p>
            <p className="mt-2 font-serif text-[112px] font-semibold leading-[0.85] tracking-[-0.04em] text-relevance" aria-label={`Highest score ${top.score} out of 100`}>
              {top.score}
            </p>
            <div className="mt-4 h-1 bg-white/10" aria-hidden>
              <div className="h-full bg-relevance" style={{ width: `${top.score}%` }} />
            </div>
            {rest.length > 0 && (
              <>
                <p className="tp-eyebrow mt-8 text-white/60">Then call</p>
                <ol className="mt-2 divide-y divide-white/10 border-y border-white/10">
                  {rest.slice(0, 3).map((c) => (
                    <li key={c.client_id}>
                      <Link to={`/alerts#alert-${c.alert_id}`} className="flex items-baseline gap-3 py-2.5 text-sm text-white/85 hover:text-white">
                        <span className="w-7 shrink-0 font-mono text-[13px] text-relevance">{c.score}</span>
                        <span className="min-w-0 flex-1 truncate">{c.client}</span>
                        <span aria-hidden className="text-white/40">→</span>
                      </Link>
                    </li>
                  ))}
                </ol>
              </>
            )}
          </div>
        )}
      </div>
    </section>
  )
}

function Kpi({ label, value, note, to, highlight = false }: {
  label: string; value: string; note: string; to: string; highlight?: boolean
}) {
  return (
    <Link to={to} className="group block px-0 py-6 sm:px-6 sm:first:pl-0 lg:py-7">
      <dt className="tp-eyebrow flex items-center gap-2">
        {highlight && <span className="h-2 w-2 bg-amber" aria-hidden />}
        {label}
      </dt>
      <dd className={`mt-3 font-serif text-[52px] font-semibold leading-none tracking-[-0.035em] ${highlight ? 'text-amber' : 'text-ink'} group-hover:underline group-hover:decoration-2 group-hover:underline-offset-8`}>
        {value}
      </dd>
      <dd className="mt-3 text-[13px] text-slate">{note}</dd>
    </Link>
  )
}

function NextSteps({ todo }: { todo: Dashboard['todo'] }) {
  return (
    <section aria-labelledby="next">
      <SectionTitle id="next">Your next steps</SectionTitle>
      {todo.length === 0 ? (
        <p className="py-3 text-sm text-slate">
          All caught up. Add a client or import new tax updates to start the chain again.
        </p>
      ) : (
        <ol className="divide-y divide-rule border-b border-rule">
          {todo.map((t, i) => (
            <li key={t.key}>
              <Link to={t.to} className="group flex min-h-14 items-center gap-4 py-3 hover:bg-sheet">
                <span className="font-serif text-[28px] font-semibold leading-none text-petrol">{i + 1}</span>
                <span className="flex-1 text-[15px] font-medium">{t.label}</span>
                <span aria-hidden className="pr-2 text-slate transition-transform group-hover:translate-x-1 group-hover:text-petrol">→</span>
              </Link>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}

function Ranking({ clients }: { clients: Dashboard['top_clients'] }) {
  return (
    <section aria-labelledby="top">
      <SectionTitle id="top">Who to call, ranked</SectionTitle>
      {clients.length === 0 ? (
        <p className="py-3 text-sm text-slate">
          No open alerts. When a new tax update affects a former client, it appears here, ranked by relevance.
        </p>
      ) : (
        <ol className="divide-y divide-rule border-b border-rule">
          {clients.map((c, i) => (
            <li key={c.client_id}>
              <Link to={`/alerts#alert-${c.alert_id}`} className="group grid grid-cols-[2rem_minmax(0,1fr)_4.5rem] items-start gap-4 py-4 hover:bg-sheet sm:grid-cols-[2.5rem_minmax(0,1fr)_7rem]">
                <span className="pt-1 font-mono text-xs text-slate">{String(i + 1).padStart(2, '0')}</span>
                <span className="min-w-0">
                  <span className="block font-serif text-[20px] font-semibold leading-snug group-hover:text-petrol">{c.client}</span>
                  {c.topics.slice(0, 2).map((t) => (
                    <span key={t.title} className="mt-0.5 block truncate text-sm text-slate">{t.title}</span>
                  ))}
                  {c.topics.length > 2 && <span className="mt-0.5 block text-xs text-slate">and {c.topics.length - 2} more</span>}
                </span>
                <span className="text-right" aria-label={`Highest score ${c.score}`}>
                  <span className="block font-serif text-[30px] font-semibold leading-none text-amber">{c.score}</span>
                  <span className="mt-2 block h-[3px] bg-amber-soft" aria-hidden>
                    <span className="block h-full bg-amber" style={{ width: `${c.score}%` }} />
                  </span>
                </span>
              </Link>
            </li>
          ))}
        </ol>
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
      {error && <ErrorNote message={error} />}

      {(empty || (!data && !error)) && (
        <PageHeader
          title="Briefing"
          intro="Which former clients should you call this week, and why. TaxPulse matches new BMF letters and BFH rulings against the due diligence files of your past mandates."
        />
      )}

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
        <div className="space-y-14">
          <div>
            <Lead clients={data.top_clients} toReview={c.alerts_to_review} />
            <dl className="grid grid-cols-2 border-b-2 border-ink sm:divide-x sm:divide-ink/15 lg:grid-cols-4">
              <Kpi label="Clients profiled" value={`${c.clients_profiled}/${c.clients}`} to="/clients"
                note={c.clients_missing_profile ? `${c.clients_missing_profile} waiting for the Profiler` : 'Every data room read'} />
              <Kpi label="Alerts to review" value={String(c.alerts_to_review)} to="/alerts" highlight={c.alerts_to_review > 0}
                note={`${c.alerts_accepted} accepted so far`} />
              <Kpi label="Emails to approve" value={String(c.drafts_to_review)} to="/outreach"
                note={`${c.drafts_ready} ready to send · ${c.emails_sent} sent`} />
              <Kpi label={demo ? 'AI cost, as recorded' : 'AI cost so far'} value={`$${c.cost_usd.toFixed(2)}`} to="/runs"
                note={`${c.updates} tax updates, ${c.updates_relevant} relevant`} />
            </dl>
          </div>

          <div className="grid gap-12 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
            <NextSteps todo={data.todo} />
            <Ranking clients={data.top_clients} />
          </div>

          <AgentChain onFinished={reload} />
        </div>
      )}
    </>
  )
}
