import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, formatDateTime, type Pipeline, type Stage } from '../api'
import { Bubble, Team, useHandoff } from './AgentTeam'
import { useDemo } from '../demo'
import { Button, ErrorNote } from './ui'

const VERB: Record<string, string> = {
  profiler: 'is reading the data room of',
  analyst: 'is analysing',
  matcher: 'is scoring',
  explainer: 'is writing the memo for',
  writer: 'is drafting the email for',
}

const modelName = (m: string) =>
  m.includes('haiku') ? 'Haiku' : m.includes('sonnet') ? 'Sonnet' : m.includes('opus') ? 'Opus' : m
const secs = (ms: number) => (ms >= 10_000 ? `${Math.round(ms / 1000)} s` : `${(ms / 1000).toFixed(1)} s`)
const clock = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
const utc = (iso: string) => new Date(iso.endsWith('Z') || iso.includes('+') ? iso : `${iso}Z`)


const BUBBLE: Record<string, string> = {
  profiler: 'Reading', analyst: 'Analysing', matcher: 'Scoring', explainer: 'Writing the memo:', writer: 'Drafting:',
}
const shorten = (s: string) => (s.length > 46 ? `${s.slice(0, 44).trimEnd()}…` : s)

function useReducedMotion() {
  const [reduce, setReduce] = useState(() => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false)
  useEffect(() => {
    const m = window.matchMedia?.('(prefers-reduced-motion: reduce)')
    if (!m) return
    const on = () => setReduce(m.matches)
    m.addEventListener('change', on)
    return () => m.removeEventListener('change', on)
  }, [])
  return reduce
}

/** Counts up to a new value instead of jumping. */
function Count({ value }: { value: number }) {
  const [shown, setShown] = useState(value)
  const from = useRef(value)
  useEffect(() => {
    const start = performance.now()
    const a = from.current
    let raf = 0
    const step = (t: number) => {
      const k = Math.min(1, (t - start) / 700)
      setShown(Math.round(a + (value - a) * (1 - (1 - k) ** 3)))
      if (k < 1) raf = requestAnimationFrame(step)
      else from.current = value
    }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
  }, [value])
  return <>{shown}</>
}

function StageLabel({ s, at }: { s: Stage; at: boolean }) {
  return (
    <div className="px-1.5 text-center" title={s.role}>
      <p className={`text-[13px] font-semibold leading-tight ${at ? 'text-brand' : ''}`}>{s.name}</p>
      <p className="mt-1 text-xs text-slate tabular-nums">
        <span className="font-semibold text-ink"><Count value={s.done} /></span> of {s.total} {s.unit}
      </p>
      <p className="mt-0.5 text-[11px] leading-snug text-slate">
        {!s.llm ? 'No AI, free' : s.runs ? `${modelName(s.model)}, $${s.cost_usd.toFixed(2)}${s.avg_duration_ms ? `, ~${secs(s.avg_duration_ms)} each` : ''}` : 'Not run yet'}
      </p>
      {s.failed > 0 && <Link to="/runs" className="mt-0.5 block text-[11px] font-medium text-danger hover:underline">{s.failed} failed</Link>}
    </div>
  )
}

function Activity({ log }: { log: Pipeline['log'] }) {
  // Lines that appear after the first load glow for a moment.
  const firstSeen = useRef<Map<number, number> | null>(null)
  if (firstSeen.current === null) firstSeen.current = new Map(log.map((r) => [r.id, 0]))
  for (const r of log) if (!firstSeen.current.has(r.id)) firstSeen.current.set(r.id, Date.now())
  const fresh = (id: number) => Date.now() - (firstSeen.current?.get(id) ?? 0) < 1200
  if (!log.length) return null
  return (
    <div className="mt-5">
      <h3 className="text-sm font-semibold">Latest activity</h3>
      <ol className="mt-2 divide-y divide-rule text-[13px]" aria-live="polite">
        {log.map((r) => (
          <li key={r.id} className={`grid grid-cols-[4.5rem_1fr_auto] gap-x-3 py-1.5 sm:grid-cols-[4.5rem_10rem_1fr_auto] ${
            fresh(r.id) ? 'tp-row-new' : ''}`}>
            <span className="text-slate tabular-nums">
              {utc(r.started_at).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </span>
            <span className="hidden font-medium sm:block">{AGENT[r.agent] ?? r.agent}</span>
            <span className="truncate text-slate"><span className="font-medium text-ink sm:hidden">{AGENT[r.agent] ?? r.agent}: </span>{r.label}</span>
            <span className={`text-right tabular-nums ${r.status === 'failed' ? 'text-danger' : r.status === 'running' ? 'text-brand' : 'text-slate'}`}>
              {r.status === 'running' ? 'working…' : r.status === 'failed' ? 'failed' : `${secs(r.duration_ms)}, $${r.cost_usd.toFixed(3)}`}
            </span>
          </li>
        ))}
      </ol>
    </div>
  )
}

const AGENT: Record<string, string> = {
  profiler: 'Profiler', analyst: 'Regulatory Analyst', matcher: 'Impact Matcher',
  explainer: 'Impact Explainer', writer: 'Outreach Writer',
}

/** The six stages of TaxPulse, live: progress, model, cost and what each agent is working on right now. */
export default function AgentChain({ onFinished }: { onFinished?: () => void }) {
  const [p, setP] = useState<Pipeline | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [starting, setStarting] = useState(false)
  const [flashing, setFlashing] = useState<Set<string>>(new Set())
  const [now, setNow] = useState(Date.now())
  const wasBusy = useRef(false)
  const prevBusy = useRef<Set<string>>(new Set())
  const reduce = useReducedMotion()

  const load = () => api.pipeline().then(setP).catch((e: Error) => setError(e.message))
  useEffect(() => { load() }, [])

  const busyKeys = new Set(p?.stages.filter((s) => s.running > 0).map((s) => s.key) ?? [])
  if (busyKeys.has('matcher')) busyKeys.add('prefilter')
  const busy = !!p && (p.chain.running || busyKeys.size > 0)
  const busySig = [...busyKeys].sort().join(',')

  // Poll fast while agents work, slowly otherwise (work can also start from other pages).
  useEffect(() => {
    if (wasBusy.current && !busy) onFinished?.()
    wasBusy.current = busy
    const t = setInterval(load, busy ? 1500 : 15000)
    return () => clearInterval(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [busy])

  // A stage that just finished flashes once.
  useEffect(() => {
    const ended = [...prevBusy.current].filter((k) => !busyKeys.has(k))
    prevBusy.current = new Set(busyKeys)
    if (!ended.length) return
    setFlashing(new Set(ended))
    const t = setTimeout(() => setFlashing(new Set()), 1600)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [busySig])

  useEffect(() => {
    if (!busy) return
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [busy])

  const demo = useDemo()
  const watch = async () => {
    setError(null)
    setStarting(true)
    try {
      await api.watchDemo()
      window.location.reload() // every panel starts from the empty demo while the team works
    } catch (e) {
      setError((e as Error).message)
      setStarting(false)
    }
  }

  const start = async () => {
    setError(null)
    setStarting(true)
    try {
      await api.runChain()
      await load()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setStarting(false)
    }
  }

  const handoff = useHandoff(busyKeys, p?.stages ?? [])

  if (!p) return error ? <ErrorNote message={error} /> : null
  const total = p.stages.reduce((sum, s) => sum + s.cost_usd, 0)
  const working = p.stages.find((s) => s.running > 0 && s.llm)
  const elapsed = p.chain.running && p.chain.started_at ? Math.max(0, Math.round((now - utc(p.chain.started_at).getTime()) / 1000)) : null
  const pending = [
    p.pending.profiles && `${p.pending.profiles} ${p.pending.profiles === 1 ? 'profile' : 'profiles'} to build`,
    p.pending.analyses && `${p.pending.analyses} ${p.pending.analyses === 1 ? 'update' : 'updates'} to analyse`,
    p.pending.scans && `${p.pending.scans} ${p.pending.scans === 1 ? 'update' : 'updates'} to match`,
  ].filter(Boolean).join(', ')

  return (
    <section aria-labelledby="chain">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div className="max-w-2xl">
          <h2 id="chain" className="tp-chrome-text inline-block pb-0.5 font-serif text-[21px] font-bold tracking-[-0.025em]">Agent chain</h2>
          <p className="mt-1 text-sm text-slate" aria-live="polite">
            {working ? (
              <>
                <span className="font-semibold text-brand">{working.name}</span> {VERB[working.key]}{' '}
                <span className="text-ink">{working.current || 'the next item'}</span>
                {elapsed !== null && <span className="tabular-nums">, {clock(elapsed)} since you started the run</span>}
              </>
            ) : busy ? 'Handing over to the next agent…'
              : `Five AI agents and one rule-based filter, each handing its work to the next. ${demo ? `Recorded cost with Claude: $${total.toFixed(2)}.` : `$${total.toFixed(2)} spent so far.`}`}
          </p>
        </div>
        <div className="flex flex-col items-start gap-1 sm:items-end">
          <Button onClick={demo && p.pending.total === 0 ? watch : start} disabled={busy || starting || (!demo && p.pending.total === 0)}>
            {busy ? 'Agents at work…' : demo && p.pending.total === 0 ? 'Watch the agents work' : p.pending.total === 0 ? 'Up to date' : 'Run the agents'}
          </Button>
          <p className="text-xs text-slate">
            {busy ? 'Watch the team pass the work along.' : demo && p.pending.total === 0 ? 'Starts the demo over and replays the whole chain, about a minute.' : p.pending.total === 0 ? 'Nothing new. Add a client or import tax updates.' : pending}
          </p>
        </div>
      </div>
      {error && <div className="mb-4"><ErrorNote message={error} /></div>}
      {p.chain.error && !busy && <div className="mb-4"><ErrorNote message={`The last run stopped: ${p.chain.error}`} /></div>}

      <div className="overflow-hidden tp-chrome rounded-xl border border-rule bg-sheet shadow-sm">
        <div className="overflow-x-auto">
          <div className="relative min-w-[720px] bg-[linear-gradient(to_bottom,#23262c,#1a1d21)] lg:min-w-0">
            {working && (
              <Bubble index={p.stages.indexOf(working)}
                text={`${BUBBLE[working.key]} ${working.current ? shorten(working.current) : ''}`} />
            )}
            <Team p={p} busyKeys={busyKeys} finished={flashing} handoff={handoff} reduce={reduce} />
          </div>
        </div>
        <div className="hidden grid-cols-6 border-t border-rule/70 pb-4 pt-3 lg:grid">
          {p.stages.map((s) => <StageLabel key={s.key} s={s} at={busyKeys.has(s.key)} />)}
        </div>
        <ol className="divide-y divide-rule border-t border-rule lg:hidden">
          {p.stages.map((s, i) => (
            <li key={s.key} className="flex items-baseline gap-3 px-4 py-2.5 text-sm">
              <span className={`w-4 shrink-0 font-semibold ${busyKeys.has(s.key) ? 'text-brand' : 'text-slate'}`}>{i + 1}</span>
              <span className={`flex-1 font-medium ${busyKeys.has(s.key) ? 'text-brand' : ''}`}>{s.name}</span>
              <span className="text-xs text-slate tabular-nums"><Count value={s.done} /> of {s.total}</span>
            </li>
          ))}
        </ol>
      </div>
      <p className="mt-2 flex flex-wrap justify-between gap-2 text-xs text-slate">
        <span>Stages 1 to 4 run on their own. Stages 5 and 6 start only after you accept an alert.</span>
        {p.waiting_for_review > 0 && (
          <Link to="/alerts" className="font-semibold text-heat hover:underline">
            {p.waiting_for_review} {p.waiting_for_review === 1 ? 'alert is' : 'alerts are'} waiting at the gate for your review
          </Link>
        )}
      </p>

      <Activity log={p.log ?? []} />
      <p className="sr-only">Last update {p.chain.finished_at ? formatDateTime(p.chain.finished_at) : 'never'}.</p>
    </section>
  )
}
