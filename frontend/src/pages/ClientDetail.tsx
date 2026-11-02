import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, formatDateTime, type AgentRun, type Citation } from '../api'
import ContactCard from '../components/ContactCard'
import DataRoom from '../components/DataRoom'
import ProfileView from '../components/ProfileView'
import SourcePanel from '../components/SourcePanel'
import { Button, DemoTag, EmptyState, ErrorNote, PageHeader } from '../components/ui'
import { useAsync } from '../useAsync'

/** Poll a running agent until it finishes. */
function useRun(runId: number | null, onFinish: (run: AgentRun) => void) {
  const [run, setRun] = useState<AgentRun | null>(null)
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    if (!runId) return
    let stop = false
    const started = Date.now()
    const tick = setInterval(() => setElapsed(Math.round((Date.now() - started) / 1000)), 1000)
    const poll = async () => {
      while (!stop) {
        try {
          const r = await api.run(runId)
          setRun(r)
          if (r.status !== 'running') {
            onFinish(r)
            break
          }
        } catch {
          /* backend restarting: keep polling */
        }
        await new Promise((res) => setTimeout(res, 2000))
      }
    }
    poll()
    return () => {
      stop = true
      clearInterval(tick)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId])

  return { run, elapsed }
}

export default function ClientDetail() {
  const id = Number(useParams().id)
  const { data: c, error, reload } = useAsync(() => api.client(id), [id])
  const { data: health } = useAsync(api.health)
  const [runId, setRunId] = useState<number | null>(null)
  const [runError, setRunError] = useState<string | null>(null)
  const [citation, setCitation] = useState<Citation | null>(null)

  // Resume watching a run that was already going when the page opened.
  useEffect(() => {
    if (c?.active_run_id) setRunId(c.active_run_id)
  }, [c?.active_run_id])

  const onFinish = useCallback((r: AgentRun) => {
    setRunId(null)
    if (r.status === 'failed') setRunError(r.error || 'The Profiler stopped without an error message.')
    reload()
  }, [reload])
  const { elapsed } = useRun(runId, onFinish)

  const start = async () => {
    setRunError(null)
    try {
      setRunId((await api.buildProfile(id)).run_id)
    } catch (e) {
      setRunError((e as Error).message)
    }
  }

  if (error) return <ErrorNote message={error} />
  if (!c) return null

  const pages = c.documents.reduce((n, d) => n + d.page_count, 0)
  const noKey = health && !health.llm_configured
  const v = c.profile?.data.verification
  const running = runId !== null

  const action = (
    <div className="flex items-center gap-3 sm:flex-col sm:items-end sm:gap-2">
      <Button onClick={start} disabled={running || !c.documents.length || !!noKey}
        title={noKey ? 'Add your Anthropic API key to the .env file first' : undefined}>
        {running ? 'Profiler at work…' : c.profile ? 'Rebuild profile' : 'Build profile'}
      </Button>
      {c.is_demo && <DemoTag />}
    </div>
  )

  return (
    <>
      <Link to="/clients" className="text-sm font-medium text-petrol hover:underline">Back to clients</Link>
      <div className="mt-4">
        <PageHeader title={c.name} intro={c.mandate} action={action} />
      </div>

      {noKey && (
        <div className="mb-6 rounded-md border border-amber/30 bg-amber-soft px-4 py-3 text-sm leading-relaxed">
          The agents need an Anthropic API key. Paste it after <code className="font-semibold">ANTHROPIC_API_KEY=</code> in
          the <code className="font-semibold">.env</code> file of the project, then restart TaxPulse.
        </div>
      )}
      {health?.key_problem && <div className="mb-6"><ErrorNote message={health.key_problem} /></div>}
      {runError && <div className="mb-6"><ErrorNote message={runError} /></div>}

      <div className="grid gap-10 lg:grid-cols-[1fr_260px]">
        <div className="min-w-0">
          {running && (
            <div className="mb-8 rounded-lg border border-petrol/25 bg-petrol-soft px-5 py-4" aria-live="polite">
              <p className="flex items-center gap-2.5 font-medium text-petrol">
                <span className="relative flex h-2.5 w-2.5">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-petrol opacity-60 motion-reduce:animate-none" />
                  <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-petrol" />
                </span>
                The Profiler is reading {pages} pages
              </p>
              <p className="mt-1 text-sm text-slate">
                It extracts every tax-relevant fact and quotes the page it comes from. This usually takes one to two minutes. {elapsed} s
              </p>
            </div>
          )}

          {c.profile ? (
            <>
              <p className="mb-6 text-sm text-slate">
                Profile version {c.profile.version}, built {formatDateTime(c.profile.created_at)}
                {c.profile_run && <> in {Math.round(c.profile_run.duration_ms / 1000)} s for ${c.profile_run.cost_usd.toFixed(3)}</>}.{' '}
                {v && (
                  <span className={v.verified === v.total ? 'text-petrol' : 'text-ink'}>
                    {v.verified} of {v.total} citations verified against the source pages.
                  </span>
                )}
              </p>
              <ProfileView profile={c.profile} onCite={setCitation} />
            </>
          ) : !running && (
            <EmptyState title="No profile yet">
              Build the profile to let the Profiler read the data room. Every fact it extracts links to the page it comes from.
            </EmptyState>
          )}
        </div>

        <aside className="lg:sticky lg:top-8 lg:self-start">
          <ContactCard clientId={c.id} onChange={reload}
            contact={{ contact_name: c.contact_name, contact_title: c.contact_title, salutation: c.salutation }} />
          <DataRoom clientId={c.id} documents={c.documents} onChange={reload} />
        </aside>
      </div>

      {citation && <SourcePanel citation={citation} documents={c.documents} onClose={() => setCitation(null)} />}
    </>
  )
}
