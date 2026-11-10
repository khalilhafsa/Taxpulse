import { useDemo } from '../demo'
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type AlertItem, type Evaluation, type ImpactMemo } from '../api'
import { Button, EmptyState, ErrorNote, KindTag, PageHeader } from '../components/ui'
import { useAsync } from '../useAsync'

const TABS: { key: AlertItem['status']; label: string }[] = [
  { key: 'new', label: 'To review' },
  { key: 'accepted', label: 'Accepted' },
  { key: 'dismissed', label: 'Dismissed' },
]

function Score({ value }: { value: number }) {
  return (
    <div className="tp-metal-dark flex shrink-0 items-center gap-4 px-5 py-4 text-white sm:w-[120px] sm:flex-col sm:items-start sm:gap-0 sm:py-6" aria-label={`Relevance ${value} out of 100`}>
      <p className="tp-eyebrow text-[10px] text-white/60">Relevance</p>
      <p className="font-serif text-[52px] font-semibold leading-none tracking-[-0.015em] text-relevance sm:mt-2">{value}</p>
      <div className="h-1 flex-1 bg-white/10 sm:mt-4 sm:w-full sm:flex-none">
        <div className="h-full bg-relevance" style={{ width: `${value}%` }} />
      </div>
    </div>
  )
}

function MemoView({ m }: { m: ImpactMemo }) {
  const kind = { risk: 'Risk', opportunity: 'Opportunity', both: 'Risk and opportunity' }[m.risk_or_opportunity]
  const kindColor = m.risk_or_opportunity === 'opportunity' ? 'text-brand' : 'text-danger'
  return (
    <div className="mt-6 rounded-xl border border-brand/15 bg-brand-soft/40 px-5 py-5">
      <p className="tp-eyebrow">Impact memo</p>
      <p className="mt-2 font-serif text-[19px] font-semibold leading-snug">{m.headline}</p>
      <p className="mt-1 text-sm">
        <span className={`font-medium ${kindColor}`}>{kind}</span>
        <span className="text-slate"> · urgency {m.urgency} · deadline: {m.deadline}</span>
      </p>
      <p className="mt-3 text-[15px] leading-relaxed">{m.impact}</p>
      <div className="mt-3 grid gap-4 sm:grid-cols-2">
        <div>
          <p className="tp-eyebrow">Next steps for the client</p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm marker:text-brand">{m.recommended_actions.map((x) => <li key={x}>{x}</li>)}</ul>
        </div>
        {m.questions_for_client.length > 0 && (
          <div>
            <p className="tp-eyebrow">Ask the client first</p>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm marker:text-brand">{m.questions_for_client.map((x) => <li key={x}>{x}</li>)}</ul>
          </div>
        )}
      </div>
      <p className="mt-4 border-t border-rule pt-3 text-sm"><span className="font-semibold">Engagement to propose: </span>{m.proposed_mandate}</p>
    </div>
  )
}

function AlertCard({ a, onChange, focused = false }: { a: AlertItem; onChange: () => void; focused?: boolean }) {
  const [dismissing, setDismissing] = useState(false)
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)

  const decide = async (status: AlertItem['status'], why = '') => {
    setError(null)
    try {
      await api.setAlertStatus(a.id, status, why)
      onChange()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const supporting = a.evidence.filter((e) => e.supports_impact)
  const against = a.evidence.filter((e) => !e.supports_impact)

  return (
    <li id={`alert-${a.id}`} className={`tp-chrome scroll-mt-28 overflow-hidden rounded-xl border bg-sheet shadow-sm transition-shadow ${focused ? 'border-brand ring-4 ring-brand/15' : 'border-ink/15'}`}>
      <div className="flex flex-col sm:flex-row">
        <Score value={a.score} />
        <div className="min-w-0 flex-1 px-5 py-5 md:px-8 md:py-6">
          <p className="font-serif text-[26px] font-semibold leading-snug tracking-[-0.01em]">
            <Link to={`/clients/${a.client.id}`} className="hover:text-brand hover:underline">{a.client.name}</Link>
          </p>
          <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-slate">
            <KindTag kind={a.update.kind} />
            <Link to={`/updates/${a.update.id}`} className="font-medium text-ink hover:underline">{a.update.title}</Link>
          </p>
          <p className="mt-3 text-[15px] leading-relaxed">{a.reasoning}</p>

          {a.evidence.length > 0 && (
            <div className="mt-5">
              <div className="grid gap-6 border-b border-rule pb-1.5 sm:grid-cols-[1fr_1fr]">
                <p className="tp-eyebrow">Evidence from the client file</p>
                <p className="tp-eyebrow hidden sm:block">Criterion of the update</p>
              </div>
              <ul className="divide-y divide-rule">
                {[...supporting, ...against].map((e, i) => (
                  <li key={i} className="grid gap-1 py-2.5 text-sm sm:grid-cols-[1fr_1fr] sm:gap-6">
                    <p className="flex gap-2">
                      <span aria-hidden className={e.verified ? 'text-brand' : 'text-danger'}>{e.verified ? '✓' : '?'}</span>
                      <span>
                        {e.client_fact}
                        {!e.verified && <span className="block text-xs text-danger">Not found word for word in the profile</span>}
                      </span>
                    </p>
                    <p className="text-slate">
                      <span className={`mr-1.5 inline-block rounded-full px-2 py-px text-[11px] font-semibold ${e.supports_impact ? 'bg-brand-soft text-brand-deep' : 'bg-danger/10 text-danger'}`}>
                        {e.supports_impact ? 'Meets' : 'Against'}
                      </span>
                      {e.criterion}
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {a.missing_information.length > 0 && (
            <p className="mt-3 text-sm text-slate">
              <span className="font-medium text-ink">To confirm with the client: </span>
              {a.missing_information.join('; ')}
            </p>
          )}

          {a.status === 'accepted' && a.memo_status === 'running' && (
            <p className="mt-5 rounded-md border border-brand/20 bg-brand-soft px-4 py-3 text-sm text-brand" aria-live="polite">
              The Impact Explainer is writing the memo for this client…
            </p>
          )}
          {a.status === 'accepted' && a.memo && a.memo_status !== 'running' && <MemoView m={a.memo} />}
          {a.status === 'accepted' && a.memo_status === 'failed' && (
            <div className="mt-3"><ErrorNote message={a.memo_error || 'The memo could not be written.'} /></div>
          )}

          {a.status === 'dismissed' && a.dismiss_reason && (
            <p className="mt-3 text-sm text-slate">Dismissed: {a.dismiss_reason}</p>
          )}

          <div className="mt-6 flex flex-wrap items-center gap-2 border-t border-rule pt-4">
            {a.status !== 'accepted' && <Button onClick={() => decide('accepted')}>Accept</Button>}
            {a.status === 'new' && !dismissing && (
              <Button variant="quiet" onClick={() => setDismissing(true)}>Dismiss</Button>
            )}
            {a.status === 'accepted' && a.memo_status !== 'running' && (
              <Button variant="quiet" onClick={() => api.writeMemo(a.id).then(onChange, (e: Error) => setError(e.message))}>
                {a.memo ? 'Rewrite memo' : 'Write memo'}
              </Button>
            )}
            {a.status === 'accepted' && a.memo && (
              <Link to="/outreach" className="px-2 text-sm font-medium text-brand hover:underline">Draft the email</Link>
            )}
            {a.status !== 'new' && <Button variant="quiet" onClick={() => decide('new')}>Move back to review</Button>}
          </div>
          {dismissing && (
            <form className="mt-3 flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); decide('dismissed', reason) }}>
              <input autoFocus value={reason} onChange={(e) => setReason(e.target.value)}
                placeholder="Why is this not relevant? e.g. client already advised"
                aria-label="Reason for dismissing"
                className="min-h-10 min-w-0 flex-1 rounded-md border border-rule bg-sheet px-3 shadow-sm py-2 text-sm focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/15" />
              <Button type="submit" variant="quiet" disabled={!reason.trim()}>Dismiss alert</Button>
              <Button variant="quiet" onClick={() => setDismissing(false)}>Cancel</Button>
            </form>
          )}
          {error && <div className="mt-3"><ErrorNote message={error} /></div>}
        </div>
      </div>
    </li>
  )
}

function EvaluationBox({ e }: { e: Evaluation }) {
  if (!e.evaluated_pairs) return null
  const perfect = e.affected_found === e.affected_total && e.false_alerts === 0
  return (
    <section aria-labelledby="eval" className="tp-chrome mb-8 rounded-xl border border-rule bg-sheet px-5 py-4 shadow-sm">
      <h2 id="eval" className="tp-eyebrow text-ink">Accuracy on the labelled demo cases</h2>
      <p className="mt-1 text-sm text-slate">
        Each demo client and demo update pair has a known right answer. Threshold: relevance {e.threshold}.
        {e.alerts_on_other_updates > 0 && (
          <> This score covers the {e.alerts_on_demo_updates} alerts on demo updates. The
          other {e.alerts_on_other_updates} come from real BMF publications, which have no answer key: review them yourself.</>
        )}
      </p>
      <dl className="mt-3 flex flex-wrap gap-x-10 gap-y-2">
        <div>
          <dt className="text-xs text-slate">Affected clients found</dt>
          <dd className={`font-serif text-2xl font-semibold ${e.affected_found === e.affected_total ? 'text-brand' : 'text-danger'}`}>
            {e.affected_found} of {e.affected_total}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-slate">False alerts</dt>
          <dd className={`font-serif text-2xl font-semibold ${e.false_alerts === 0 ? 'text-brand' : 'text-danger'}`}>
            {e.false_alerts} of {e.not_affected_total}
          </dd>
        </div>
      </dl>
      {!perfect && (
        <ul className="mt-3 space-y-1 text-sm">
          {e.missed.map((m) => <li key={m.client + m.update} className="text-danger">Missed: {m.client} × {m.update} (score {m.score}). {m.why_expected}</li>)}
          {e.false_alert_details.map((f) => <li key={f.client + f.update} className="text-danger">False alert: {f.client} × {f.update} (score {f.score})</li>)}
        </ul>
      )}
      {e.not_evaluated > 0 && (
        <p className="mt-2 text-sm text-slate">{e.not_evaluated} labelled pairs are not scanned yet.</p>
      )}
    </section>
  )
}

export default function Alerts() {
  const demo = useDemo()
  const [tab, setTab] = useState<AlertItem['status']>('new')
  const { data: alerts, error, reload: reloadAlerts } = useAsync(api.alerts)
  const { data: status, reload: reloadStatus } = useAsync(api.scanStatus)
  const { data: evaluation, reload: reloadEval } = useAsync(api.evaluation)
  const { data: health } = useAsync(api.health)
  const [actionError, setActionError] = useState<string | null>(null)

  const reload = useCallback(() => {
    reloadAlerts()
    reloadStatus()
    reloadEval()
  }, [reloadAlerts, reloadStatus, reloadEval])

  const busy = !!status && (status.scan_running > 0 || status.profiles_running > 0)
  const polling = busy || !!alerts?.some((a) => a.memo_status === 'running')
  useEffect(() => {
    if (!polling) return
    const t = setInterval(reload, 3000)
    return () => clearInterval(t)
  }, [polling, reload])

  const run = async (fn: () => Promise<unknown>) => {
    setActionError(null)
    try {
      await fn()
      reload()
    } catch (e) {
      setActionError((e as Error).message)
    }
  }

  const noKey = health && !health.llm_configured
  const shown = alerts?.filter((a) => a.status === tab) ?? []

  // Deep link from the dashboard or the matrix: /alerts#alert-12 opens the right tab and scrolls to it.
  const [jumped, setJumped] = useState(false)
  const [focusId, setFocusId] = useState<number | null>(null)
  useEffect(() => {
    const id = Number(window.location.hash.replace('#alert-', ''))
    const target = alerts?.find((a) => a.id === id)
    if (!target || jumped) return
    setJumped(true)
    setFocusId(id)
    setTab(target.status)
    setTimeout(() => document.getElementById(`alert-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50)
  }, [alerts, jumped])
  const count = (s: AlertItem['status']) => alerts?.filter((a) => a.status === s).length ?? 0

  return (
    <>
      <PageHeader
        title="Alerts"
        intro="Former clients affected by a new tax update, ranked by relevance. Each alert shows the facts from the client file that triggered it."
        action={
          <div className="flex flex-wrap gap-2">
            <Button variant="quiet" onClick={() => run(() => api.scan(true))} disabled={busy || !!noKey}>Rescan everything</Button>
            <Button onClick={() => run(() => api.scan())} disabled={busy || !!noKey || !status?.updates_unscanned}
              title={noKey ? 'Add your Anthropic API key to the .env file first' : undefined}>
              {status?.scan_running ? 'Scanning…' : !status?.updates_unscanned ? 'Everything scanned' : `Scan ${status.updates_unscanned} new ${status.updates_unscanned === 1 ? 'update' : 'updates'}`}
            </Button>
          </div>
        }
      />

      <div className="mb-6 space-y-3">
        {(error || actionError) && <ErrorNote message={(error || actionError)!} />}
        {status && status.clients_without_profile > 0 && (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-heat/20 bg-heat-soft px-4 py-3 text-sm">
            <span>
              {status.clients_without_profile} {status.clients_without_profile === 1 ? 'client has' : 'clients have'} no profile yet
              and will not be checked.{!demo && ' About $0.11 each.'}
            </span>
            <Button variant="quiet" disabled={busy || !!noKey} onClick={() => run(api.buildMissingProfiles)}>
              {status.profiles_running ? 'Building profiles…' : 'Build missing profiles'}
            </Button>
          </div>
        )}
        {status && status.updates_not_analysed > 0 && (
          <p className="text-sm text-slate">
            {status.updates_not_analysed} tax {status.updates_not_analysed === 1 ? 'update is' : 'updates are'} not analysed yet.{' '}
            <Link to="/updates" className="font-medium text-brand hover:underline">Analyse them first</Link>.
          </p>
        )}
        {status?.scan_running ? (
          <p className="rounded-md border border-brand/20 bg-brand-soft px-5 py-4 text-sm text-brand" aria-live="polite">
            The Impact Matcher is checking {status.scan_running} {status.scan_running === 1 ? 'update' : 'updates'} against every client profile.
          </p>
        ) : null}
      </div>

      {evaluation && <EvaluationBox e={evaluation} />}

      <div role="tablist" className="mb-5 inline-flex max-w-full gap-1 overflow-x-auto rounded-lg bg-paper-deep p-1 shadow-[inset_0_1px_2px_rgb(15_17_21/0.12)] [scrollbar-width:none]">
        {TABS.map((t) => (
          <button key={t.key} role="tab" aria-selected={tab === t.key} onClick={() => setTab(t.key)}
            className={`inline-flex min-h-9 items-center gap-2 whitespace-nowrap rounded-md px-3.5 text-sm font-semibold ${tab === t.key ? 'tp-btn-quiet text-ink' : 'text-slate hover:text-ink'}`}>
            {t.label}
            <span className={`rounded-full px-2 py-px text-[11.5px] ${tab === t.key ? 'bg-primary text-primary-foreground' : 'bg-sheet/70 text-slate'}`}>{count(t.key)}</span>
          </button>
        ))}
      </div>

      {alerts && shown.length === 0 && (
        <EmptyState title={tab === 'new' ? 'Nothing to review' : `No ${tab} alerts`}>
          {tab === 'new' && (demo
            ? <>The agents are still at work, or everything has been reviewed. Watch them on the <Link to="/" className="font-medium text-brand hover:underline">Overview</Link>.</>
            : 'Scan your portfolio after adding clients or analysing new tax updates.')}
        </EmptyState>
      )}
      <ol className="space-y-4">
        {shown.map((a) => <AlertCard key={a.id} a={a} onChange={reload} focused={a.id === focusId} />)}
      </ol>
    </>
  )
}
