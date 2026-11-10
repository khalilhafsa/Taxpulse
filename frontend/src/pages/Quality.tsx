import { useDemo } from '../demo'
import { useEffect, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { api, type Stability } from '../api'
import { Button, ErrorNote, PageHeader, SectionTitle } from '../components/ui'
import { useAsync } from '../useAsync'

const AGENT: Record<string, string> = {
  profiler: 'Profiler', analyst: 'Regulatory Analyst', matcher: 'Impact Matcher',
  explainer: 'Impact Explainer', writer: 'Outreach Writer',
}
const CLIENT: Record<string, string> = {
  mueller_praezisionstechnik: 'Müller Präzisionstechnik', nordlicht_immobilien: 'Nordlicht Immobilien',
  brightloop_software: 'Brightloop Software', kaiser_dental: 'Kaiser Dental',
}
const pct = (a: number, b: number) => (b ? `${Math.round((a / b) * 100)}%` : 'n/a')
const secs = (ms: number) => (ms >= 10_000 ? `${Math.round(ms / 1000)} s` : `${(ms / 1000).toFixed(1)} s`)
const RUNS = 5
const DEMO_UPDATES = 6

/** One row per run: a dot per affected client (filled = found), then any false alerts in heat. */
function RunStrip({ s }: { s: Stability }) {
  return (
    <ol className="space-y-2">
      {s.per_run.map((r) => (
        <li key={r.index} className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
          <span className="w-12 text-slate">Run {r.index}</span>
          <span className="flex gap-1.5" aria-label={`${r.affected_found} of ${r.affected_total} affected clients found`}>
            {Array.from({ length: r.affected_total }, (_, i) => (
              <span key={i} className={`h-3.5 w-3.5 rounded-full border-2 border-ok ${i < r.affected_found ? "bg-ok" : "bg-transparent"}`} />
            ))}
          </span>
          <span className="flex gap-1.5" aria-label={`${r.false_alerts} false alerts`}>
            {Array.from({ length: r.false_alerts }, (_, i) => <span key={i} className="h-3.5 w-3.5 rotate-45 rounded-sm bg-heat" />)}
          </span>
          <span className="text-slate tabular-nums">
            {r.affected_found} of {r.affected_total} found{r.false_alerts ? `, ${r.false_alerts} false ${r.false_alerts === 1 ? 'alert' : 'alerts'}` : ', no false alert'}
          </span>
        </li>
      ))}
      {s.status === 'running' && (
        <li className="flex items-center gap-4 text-sm text-slate" aria-live="polite">
          <span className="w-12">Run {s.runs_done + 1}</span>
          <span className="flex gap-1.5">
            {Array.from({ length: s.affected_total ?? 7 }, (_, i) => (
              <span key={i} className="h-3.5 w-3.5 animate-pulse rounded-full border-2 border-slate/40 motion-reduce:animate-none"
                style={{ animationDelay: `${i * 120}ms` }} />
            ))}
          </span>
          <span>The Matcher is scoring…</span>
        </li>
      )}
    </ol>
  )
}

function verdict(s: Stability) {
  if (!s.per_run.length) return null
  const n = s.per_run.length
  const all = s.affected_total ?? 0
  const found = s.affected_found_min === all
    ? `found all ${all} affected clients in every run`
    : `found between ${s.affected_found_min} and ${all} of the ${all} affected clients (${s.affected_found_mean} on average)`
  const fa = s.false_alerts_max === 0 ? 'and never raised a false alert' : `and raised at most ${s.false_alerts_max} false ${s.false_alerts_max === 1 ? 'alert' : 'alerts'} in a run`
  return `In ${n} ${n === 1 ? 'run' : 'runs'}, the Impact Matcher ${found}, ${fa}.`
}

function StabilitySection({ s, estimate, onStart, starting, error }: {
  s: Stability | null; estimate: number | null; onStart: () => void; starting: boolean; error: string | null
}) {
  const demo = useDemo()
  const running = s?.status === 'running'
  return (
    <section aria-labelledby="stability" className="tp-chrome rounded-xl border border-rule bg-sheet shadow-sm px-6 py-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="max-w-xl">
          <SectionTitle id="stability">Stability test</SectionTitle>
          <p className="text-sm leading-relaxed text-slate">
            An AI does not answer exactly the same way twice. This test asks the real Impact Matcher to score the
            24 hand-labelled demo pairs {RUNS} times and checks that it keeps finding the same clients. Nothing is
            written to your alerts.
          </p>
        </div>
        <div className="flex flex-col items-start gap-1 sm:items-end">
          <Button onClick={onStart} disabled={running || starting || demo} title={demo ? 'The public demo shows the recorded test' : undefined}>
            {running ? `Run ${Math.min(s!.runs_done + 1, s!.runs_planned)} of ${s!.runs_planned}…` : `Run the test ${RUNS} times`}
          </Button>
          {demo ? <span className="text-xs text-slate">Recorded with the real Claude agents</span>
            : !running && estimate !== null && <span className="text-xs text-slate">About ${estimate.toFixed(2)} in Claude credits</span>}
        </div>
      </div>
      {error && <div className="mt-4"><ErrorNote message={error} /></div>}
      {s?.status === 'failed' && <div className="mt-4"><ErrorNote message={`The last test stopped: ${s.error}`} /></div>}

      {s && (s.per_run.length > 0 || running) && (
        <div className="mt-6 grid gap-8 lg:grid-cols-[1fr_16rem]">
          <div>
            <RunStrip s={s} />
            <p className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-slate">
              <span className="flex items-center gap-1.5"><span className="h-3 w-3 rounded-full bg-ok" />affected client found</span>
              <span className="flex items-center gap-1.5"><span className="h-3 w-3 rounded-full border-2 border-ok" />missed</span>
              <span className="flex items-center gap-1.5"><span className="h-3 w-3 rotate-45 rounded-sm bg-heat" />false alert</span>
            </p>
          </div>
          {s.consistency !== null && (
            <div className="border-t border-rule pt-5 lg:border-l lg:border-t-0 lg:pl-8 lg:pt-0">
              {s.clear_consistency !== null ? (
                <>
                  <p className="font-serif text-5xl font-semibold tabular-nums text-ok">{Math.round(s.clear_consistency * 100)}%</p>
                  <p className="mt-1 text-sm text-slate">
                    of the {s.clear_pairs} clear-cut pairs got the same alert decision in every run.
                  </p>
                  {s.scored_pairs > s.clear_pairs && (
                    <p className="mt-3 text-sm text-slate">
                      The {s.scored_pairs - s.clear_pairs} borderline {s.scored_pairs - s.clear_pairs === 1 ? 'pair is' : 'pairs are'} not counted: either answer is acceptable there.
                    </p>
                  )}
                </>
              ) : (
                <>
                  <p className="font-serif text-5xl font-semibold tabular-nums text-ok">{Math.round(s.consistency * 100)}%</p>
                  <p className="mt-1 text-sm text-slate">
                    of the {s.scored_pairs} pairs the Matcher scored got the same alert decision in every run.
                  </p>
                </>
              )}
              {s.mean_score_spread !== null && (
                <p className="mt-3 text-sm text-slate">Scores moved by {s.mean_score_spread} points on average between runs.</p>
              )}
            </div>
          )}
        </div>
      )}

      {s && s.status !== 'running' && s.per_run.length > 0 && (
        <>
          <p className="mt-6 text-[15px] leading-relaxed">{verdict(s)} The test cost ${s.cost_usd.toFixed(2)}.</p>
          {s.unstable_pairs.length > 0 && (
            <div className="mt-4">
              <p className="text-sm font-medium">Pairs that changed decision between runs</p>
              <ul className="mt-2 divide-y divide-rule text-sm">
                {s.unstable_pairs.map((u) => (
                  <li key={`${u.client}${u.update}`} className="flex flex-wrap justify-between gap-2 py-2">
                    <span>{CLIENT[u.client] ?? u.client} and {u.update} <span className="text-slate">({u.expected === 'either' ? 'labelled borderline: either answer is acceptable' : `expected: ${u.expected.replace('_', ' ')}`})</span></span>
                    <span className="tabular-nums text-slate">scores {u.scores.join(', ')}</span>
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-xs text-slate">
                {s.unstable_pairs.every((u) => u.expected === 'either')
                  ? 'Only pairs labelled as borderline changed. On every clear-cut pair, the decision was identical in all runs.'
                  : 'Scores near the alert threshold can tip either way. The advisor still reviews every alert.'}
              </p>
            </div>
          )}
        </>
      )}
    </section>
  )
}

function Figure({ value, label, children }: { value: string; label: string; children?: ReactNode }) {
  return (
    <div className="rounded-xl border border-rule bg-sheet p-5 shadow-sm">
      <p className="font-serif text-3xl font-semibold tabular-nums">{value}</p>
      <p className="mt-1 text-sm font-medium">{label}</p>
      {children && <p className="mt-1 text-xs leading-relaxed text-slate">{children}</p>}
    </div>
  )
}

export default function Quality() {
  const { data: q, error, reload } = useAsync(api.quality)
  const [starting, setStarting] = useState(false)
  const [startError, setStartError] = useState<string | null>(null)
  const running = q?.stability?.status === 'running'

  useEffect(() => {
    if (!running) return
    const t = setInterval(reload, 2500)
    return () => clearInterval(t)
  }, [running, reload])

  const start = async () => {
    setStartError(null)
    setStarting(true)
    try {
      await api.startStability(RUNS)
      reload()
    } catch (e) {
      setStartError((e as Error).message)
    } finally {
      setStarting(false)
    }
  }

  const matcher = q?.per_agent.find((a) => a.agent === 'matcher')
  const estimate = matcher ? matcher.avg_cost_usd * DEMO_UPDATES * RUNS : null

  return (
    <>
      <PageHeader title="Quality"
        intro="How far you can trust the agents: measured against hand-labelled demo answers and on every real run." />
      {error && <ErrorNote message={error} />}
      {q && (
        <div className="space-y-12">
          <StabilitySection s={q.stability} estimate={estimate} onStart={start} starting={starting} error={startError} />

          <section aria-labelledby="figures">
            <SectionTitle id="figures">In everyday use</SectionTitle>
            <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
              <Figure value={`${q.matcher_accuracy.affected_found} / ${q.matcher_accuracy.affected_total}`} label="Affected clients found">
                In the latest scan of the demo data, with {q.matcher_accuracy.false_alerts} false {q.matcher_accuracy.false_alerts === 1 ? 'alert' : 'alerts'} out of {q.matcher_accuracy.not_affected_total} unaffected pairs.
              </Figure>
              <Figure value={pct(q.citations.verified, q.citations.total)} label="Profile citations verified">
                {q.citations.verified} of {q.citations.total} quotes found word for word on the cited page, across {q.citations.profiles} profiles.
              </Figure>
              <Figure value={q.emails.drafts ? pct(q.emails.passed_first_time + q.emails.fixed_by_revision, q.emails.drafts) : 'n/a'} label="Emails passing the partner review">
                {q.emails.passed_first_time} passed first time, {q.emails.fixed_by_revision} after one revision, {q.emails.still_flagged} still flagged for you.
              </Figure>
              <Figure value={pct(q.reliability.runs - q.reliability.failed, q.reliability.runs)} label="Agent runs completed">
                {q.reliability.failed} of {q.reliability.runs} failed. {q.reliability.retried} recovered by an automatic retry
                {q.reliability.interrupted ? `, ${q.reliability.interrupted} cut off by a restart` : ''}.
              </Figure>
            </div>
          </section>

          <section aria-labelledby="agents">
            <SectionTitle id="agents">Cost and speed per agent</SectionTitle>
            <div className="overflow-x-auto tp-chrome rounded-xl border border-rule bg-sheet shadow-sm">
              <table className="w-full text-sm">
                <thead className="border-b border-rule text-left text-slate">
                  <tr>
                    <th scope="col" className="px-4 py-2.5 font-medium">Agent</th>
                    <th scope="col" className="px-4 py-2.5 font-medium">Model</th>
                    <th scope="col" className="px-4 py-2.5 text-right font-medium">Runs</th>
                    <th scope="col" className="px-4 py-2.5 text-right font-medium">Succeeded</th>
                    <th scope="col" className="px-4 py-2.5 text-right font-medium">Average time</th>
                    <th scope="col" className="px-4 py-2.5 text-right font-medium">Average cost</th>
                    <th scope="col" className="px-4 py-2.5 text-right font-medium">Total cost</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-rule tabular-nums">
                  {q.per_agent.map((a) => (
                    <tr key={a.agent}>
                      <th scope="row" className="px-4 py-2.5 text-left font-medium">{AGENT[a.agent] ?? a.agent}</th>
                      <td className="whitespace-nowrap px-4 py-2.5 text-slate">{a.model}</td>
                      <td className="px-4 py-2.5 text-right">{a.runs}</td>
                      <td className="px-4 py-2.5 text-right">{Math.round(a.success_rate * 100)}%</td>
                      <td className="px-4 py-2.5 text-right">{a.avg_duration_ms ? secs(a.avg_duration_ms) : 'n/a'}</td>
                      <td className="px-4 py-2.5 text-right">${a.avg_cost_usd.toFixed(3)}</td>
                      <td className="px-4 py-2.5 text-right">${a.cost_usd.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-3 text-sm text-slate">
              {q.budget.monthly_usd > 0
                ? `Spent $${q.budget.spent_this_month_usd.toFixed(2)} of your $${q.budget.monthly_usd.toFixed(2)} monthly budget. `
                : `Spent $${q.budget.spent_this_month_usd.toFixed(2)} this month, no budget limit set. `}
              <Link to="/settings" className="font-medium text-brand hover:underline">
                {q.budget.monthly_usd > 0 ? 'Change the budget' : 'Set a monthly budget'}
              </Link>
            </p>
          </section>
        </div>
      )}
    </>
  )
}
