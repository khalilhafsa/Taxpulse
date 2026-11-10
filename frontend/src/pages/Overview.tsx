import { useDemo } from '../demo'
import { useState, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, type Dashboard } from '../api'
import AgentChain from '../components/AgentChain'
import { isoWeek } from '../components/Layout'
import { Button, Card, EmptyState, ErrorNote, PageHeader, SectionTitle } from '../components/ui'
import { useAsync } from '../useAsync'

type Top = Dashboard['top_clients']

const greeting = () => {
  const h = new Date().getHours()
  return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening'
}

/**
 * Relevance radar: every former client with an open alert is a blip. The more relevant the
 * update, the closer to the centre, so the clients to call first sit in the bullseye.
 */
function Radar({ clients, active, onActive }: { clients: Top; active: number | null; onActive: (i: number | null) => void }) {
  const navigate = useNavigate()
  const S = 320, c = S / 2, R = 146
  const dist = (score: number) => R * (1 - Math.min(100, Math.max(0, score)) / 100) * 1.6 + 14
  const blips = clients.map((cl, i) => {
    const angle = (-90 + (360 / Math.max(clients.length, 1)) * i + 28) * (Math.PI / 180)
    const d = Math.min(dist(cl.score), R - 6)
    return { ...cl, x: c + Math.cos(angle) * d, y: c + Math.sin(angle) * d }
  })
  return (
    <svg viewBox={`0 0 ${S} ${S}`} className="mx-auto block w-full max-w-[340px]" role="img"
      aria-label={`Relevance radar with ${clients.length} former ${clients.length === 1 ? 'client' : 'clients'}`}>
      <defs>
        <radialGradient id="tp-core" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#fbbf24" stopOpacity=".32" />
          <stop offset="100%" stopColor="#fbbf24" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="tp-beam" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#ffffff" stopOpacity="0" />
          <stop offset="100%" stopColor="#ffffff" stopOpacity=".22" />
        </linearGradient>
      </defs>
      {[1, 0.72, 0.44].map((k, i) => (
        <circle key={k} cx={c} cy={c} r={R * k} fill="none" stroke="#fff" strokeOpacity={0.09 + i * 0.03} strokeDasharray={i === 0 ? '0' : '2 4'} />
      ))}
      <circle cx={c} cy={c} r={R * 0.3} fill="url(#tp-core)" />
      <path d={`M${c} ${c - R}V${c + R}M${c - R} ${c}H${c + R}`} stroke="#fff" strokeOpacity=".07" />
      <g className="tp-sweep">
        <path d={`M${c} ${c} L${c + R} ${c} A${R} ${R} 0 0 0 ${c + R * Math.cos(-0.9)} ${c + R * Math.sin(-0.9)} Z`} fill="url(#tp-beam)" />
        <line x1={c} y1={c} x2={c + R} y2={c} stroke="#ffffff" strokeOpacity=".6" />
      </g>
      <text x={c + 6} y={c - R * 0.72 + 14} fill="#fff" fillOpacity=".35" fontSize="10" fontFamily="IBM Plex Mono, monospace">60</text>
      <text x={c + 6} y={c - R * 0.44 + 14} fill="#fff" fillOpacity=".35" fontSize="10" fontFamily="IBM Plex Mono, monospace">80</text>
      {blips.map((b, i) => (
        <g key={b.client_id} onMouseEnter={() => onActive(i)} onMouseLeave={() => onActive(null)}>
          <circle cx={b.x} cy={b.y} r="0" fill="none" stroke="#fbbf24" className="tp-blip-ring" style={{ animationDelay: `${i * 0.5}s` }} />
          <g role="link" tabIndex={0} aria-label={`${b.client}, score ${b.score}`} className="cursor-pointer outline-none"
            onFocus={() => onActive(i)} onBlur={() => onActive(null)}
            onClick={() => navigate(`/alerts#alert-${b.alert_id}`)}
            onKeyDown={(e) => { if (e.key === 'Enter') navigate(`/alerts#alert-${b.alert_id}`) }}>
            <circle cx={b.x} cy={b.y} r={active === i ? 9 : 7} fill="#fbbf24" stroke="#1c1917" strokeWidth="2.5" />
            <text x={b.x} y={b.y - 14} textAnchor="middle" fill="#fff" fillOpacity={active === null || active === i ? 0.95 : 0.4}
              fontSize="11.5" fontWeight="600" fontFamily="Instrument Sans, sans-serif">
              {b.client.replace(/ (GmbH|AG|SE|KG|MVZ).*$/, '')}
            </text>
          </g>
        </g>
      ))}
      <circle cx={c} cy={c} r="3" fill="#fff" />
    </svg>
  )
}

function Lead({ clients, toReview }: { clients: Top; toReview: number }) {
  const [active, setActive] = useState<number | null>(null)
  const top = clients[0]
  const focus = active !== null ? clients[active] : top
  return (
    <section aria-labelledby="lead" className="tp-chrome-dark relative overflow-hidden rounded-2xl text-white">
      <div className="grid gap-8 p-6 md:p-9 lg:grid-cols-[minmax(0,1fr)_360px] lg:items-center">
        <div>
          <p className="inline-flex items-center gap-2 rounded-full bg-white/[0.07] px-3 py-1 text-xs font-medium text-white/75 ring-1 ring-white/10">
            <span className="h-1.5 w-1.5 rounded-full bg-relevance" aria-hidden />
            Week {isoWeek(new Date())} radar
          </p>
          {focus ? (
            <>
              <p className="mt-6 text-sm text-white/55">{active !== null ? 'On the radar' : 'Call first'}</p>
              <h2 id="lead" className="tp-chrome-text-light mt-1 pb-1 font-serif text-[34px] font-bold leading-[1.05] tracking-[-0.015em] md:text-[48px]">
                {focus.client}
              </h2>
              <div className="mt-5 flex items-end gap-4">
                <p className="font-serif text-[64px] font-bold leading-[0.8] tracking-[-0.015em] text-relevance">{focus.score}</p>
                <p className="pb-1 text-sm leading-snug text-white/60">relevance<br />out of 100</p>
              </div>
              <ul className="mt-6 space-y-2 text-[14.5px] leading-snug text-white/80">
                {focus.topics.slice(0, 3).map((t) => (
                  <li key={t.title} className="flex gap-3">
                    <span className="mt-0.5 w-8 shrink-0 rounded-sm bg-white/[0.08] text-center font-mono text-[12px] leading-5 text-relevance">{t.score}</span>
                    <span>{t.title}</span>
                  </li>
                ))}
              </ul>
              <div className="mt-7 flex flex-wrap items-center gap-3">
                <Link to={`/alerts#alert-${focus.alert_id}`}
                  className="tp-btn-primary inline-flex min-h-11 items-center gap-2 rounded-md px-5 text-sm font-semibold">
                  Open the alert <span aria-hidden>→</span>
                </Link>
                <Link to="/alerts" className="inline-flex min-h-11 items-center rounded-md px-4 text-sm font-semibold text-white/80 ring-1 ring-white/15 hover:bg-white/[0.07] hover:text-white">
                  All {toReview} to review
                </Link>
              </div>
            </>
          ) : (
            <>
              <h2 id="lead" className="tp-chrome-text-light mt-6 pb-1 font-serif text-[34px] font-bold leading-[1.05] tracking-[-0.015em] md:text-[44px]">
                The radar is quiet this week.
              </h2>
              <p className="mt-4 max-w-md text-[15px] leading-relaxed text-white/65">
                When a new BMF letter or BFH ruling affects one of your former clients, it shows up here. The closer to the centre, the more urgent the call.
              </p>
            </>
          )}
        </div>
        <div>
          <Radar clients={clients} active={active} onActive={setActive} />
          <p className="mt-3 text-center text-xs text-white/45">Closer to the centre = more relevant. Hover a client to preview it.</p>
        </div>
      </div>
    </section>
  )
}

const KPI_ICON: Record<string, ReactNode> = {
  clients: <path d="M4 20V8l8-4 8 4v12M9 20v-6h6v6M3 20h18" />,
  alerts: <><path d="M6 9a6 6 0 1 1 12 0c0 4.5 1.5 6.5 2 7H4c.5-.5 2-2.5 2-7Z" /><path d="M10 20a2 2 0 0 0 4 0" /></>,
  emails: <><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m3.5 6.5 8.5 6 8.5-6" /></>,
  cost: <><circle cx="12" cy="12" r="8.5" /><path d="M14.5 9.2c-.5-.8-1.5-1.2-2.5-1.2-1.4 0-2.5.8-2.5 2s1.1 1.6 2.5 2 2.5.8 2.5 2-1.1 2-2.5 2c-1 0-2-.4-2.5-1.2M12 6.5V8M12 16v1.5" /></>,
}

function Kpi({ label, value, note, to, icon, highlight = false }: {
  label: string; value: string; note: string; to: string; icon: string; highlight?: boolean
}) {
  return (
    <Link to={to} className="tp-chrome group rounded-xl border border-rule bg-sheet p-5 shadow-sm">
      <dt className="flex items-center justify-between gap-2 text-[13px] font-medium text-slate">
        {label}
        <span className={`flex h-8 w-8 items-center justify-center rounded-md ${highlight ? 'bg-heat-soft text-heat' : 'tp-btn-quiet text-slate'}`} aria-hidden>
          <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{KPI_ICON[icon]}</svg>
        </span>
      </dt>
      <dd className={`mt-3 pb-0.5 font-serif text-[40px] font-bold leading-none tracking-[-0.015em] ${highlight ? 'text-heat' : 'tp-chrome-text'}`}>{value}</dd>
      <dd className="mt-2.5 flex items-center justify-between text-[13px] text-slate">
        {note}
        <span aria-hidden className="opacity-0 transition-opacity group-hover:opacity-100">→</span>
      </dd>
    </Link>
  )
}

function NextSteps({ todo }: { todo: Dashboard['todo'] }) {
  return (
    <Card className="p-5 md:p-6">
      <SectionTitle id="next">Your next steps</SectionTitle>
      {todo.length === 0 ? (
        <p className="text-sm text-slate">All caught up. Add a client or import new tax updates to start the chain again.</p>
      ) : (
        <ol className="space-y-2" aria-labelledby="next">
          {todo.map((t, i) => (
            <li key={t.key}>
              <Link to={t.to} className="group flex min-h-12 items-center gap-3.5 rounded-lg border border-rule px-3.5 py-2.5 hover:border-brand/40 hover:bg-brand-soft/50">
                <span className="tp-btn-primary flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold">{i + 1}</span>
                <span className="flex-1 text-[14.5px] font-medium">{t.label}</span>
                <span aria-hidden className="text-slate transition-transform group-hover:translate-x-0.5 group-hover:text-brand">→</span>
              </Link>
            </li>
          ))}
        </ol>
      )}
    </Card>
  )
}

function Ranking({ clients }: { clients: Top }) {
  return (
    <Card className="p-5 md:p-6">
      <SectionTitle id="top">Who to call, ranked</SectionTitle>
      {clients.length === 0 ? (
        <p className="text-sm text-slate">No open alerts. When a new tax update affects a former client, it appears here, ranked by relevance.</p>
      ) : (
        <ol className="-mx-2" aria-labelledby="top">
          {clients.map((c, i) => (
            <li key={c.client_id}>
              <Link to={`/alerts#alert-${c.alert_id}`} className="group grid grid-cols-[2.25rem_minmax(0,1fr)_5.5rem] items-center gap-3 rounded-lg px-2 py-3 hover:bg-paper">
                <span className="tp-btn-quiet flex h-9 w-9 items-center justify-center rounded-full font-serif text-sm font-bold text-slate">{i + 1}</span>
                <span className="min-w-0">
                  <span className="block truncate font-semibold group-hover:text-brand">{c.client}</span>
                  <span className="mt-0.5 block truncate text-[13px] text-slate">
                    {c.topics[0]?.title}{c.topics.length > 1 && ` · +${c.topics.length - 1} more`}
                  </span>
                </span>
                <span aria-label={`Highest score ${c.score}`}>
                  <span className="flex items-baseline justify-end gap-1 font-serif text-[22px] font-bold tracking-[-0.015em] text-heat">{c.score}</span>
                  <span className="mt-1 block h-1.5 overflow-hidden rounded-full bg-heat-soft" aria-hidden>
                    <span className="block h-full rounded-full bg-heat" style={{ width: `${c.score}%` }} />
                  </span>
                </span>
              </Link>
            </li>
          ))}
        </ol>
      )}
    </Card>
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
        title={`${greeting()}.`}
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
        <div className="tp-stagger space-y-8">
          <Lead clients={data.top_clients} toReview={c.alerts_to_review} />

          <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Kpi icon="clients" label="Clients profiled" value={`${c.clients_profiled}/${c.clients}`} to="/clients"
              note={c.clients_missing_profile ? `${c.clients_missing_profile} waiting for the Profiler` : 'Every data room read'} />
            <Kpi icon="alerts" label="Alerts to review" value={String(c.alerts_to_review)} to="/alerts" highlight={c.alerts_to_review > 0}
              note={`${c.alerts_accepted} accepted so far`} />
            <Kpi icon="emails" label="Emails to approve" value={String(c.drafts_to_review)} to="/outreach"
              note={`${c.drafts_ready} ready · ${c.emails_sent} sent`} />
            <Kpi icon="cost" label={demo ? 'AI cost, as recorded' : 'AI cost so far'} value={`$${c.cost_usd.toFixed(2)}`} to="/runs"
              note={`${c.updates} updates, ${c.updates_relevant} relevant`} />
          </dl>

          <div className="grid gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
            <NextSteps todo={data.todo} />
            <Ranking clients={data.top_clients} />
          </div>

          <Card className="p-5 md:p-7"><AgentChain onFinished={reload} /></Card>
        </div>
      )}
    </>
  )
}
