import { useDemo } from '../demo'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, type FetchResult, type UpdateSummary } from '../api'
import { Button, EmptyState, ErrorNote, KindTag, PageHeader, SourceTag, formatDate } from '../components/ui'
import { useAsync } from '../useAsync'

function Status({ u }: { u: UpdateSummary }) {
  if (u.analysis_status === 'running')
    return <p className="mt-2 text-sm text-petrol">The Analyst is reading this publication…</p>
  if (u.analysis_status === 'failed')
    return <p className="mt-2 text-sm text-danger">Analysis failed: {u.analysis_error}</p>
  if (!u.summary) return <p className="mt-2 text-sm text-slate">Not analysed yet</p>
  if (!u.summary.relevant_for_companies)
    return <p className="mt-2 text-sm text-slate">No impact on businesses</p>
  return (
    <div className="mt-2 space-y-1.5">
      <p className="text-sm leading-relaxed text-ink">{u.summary.who_is_affected}</p>
      <ul className="flex flex-wrap gap-1.5">
        {u.summary.tax_categories.map((c) => (
          <li key={c} className="rounded-full border border-rule px-2.5 py-0.5 text-xs text-slate">{c}</li>
        ))}
      </ul>
    </div>
  )
}

export default function Updates() {
  const demo = useDemo()
  const navigate = useNavigate()
  const { data, error, loading, reload } = useAsync(api.updates)
  const { data: health } = useAsync(api.health)
  const [busy, setBusy] = useState<'fetch' | 'bfh' | 'analyze' | 'import' | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  const [fetchResult, setFetchResult] = useState<FetchResult | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [hideIrrelevant, setHideIrrelevant] = useState(false)

  const running = data?.some((u) => u.analysis_status === 'running')
  useEffect(() => {
    if (!running) return
    const t = setInterval(reload, 3000)
    return () => clearInterval(t)
  }, [running, reload])

  const act = async (kind: 'fetch' | 'bfh' | 'analyze') => {
    setBusy(kind)
    setActionError(null)
    try {
      if (kind === 'fetch') setFetchResult(await api.fetchBmf())
      if (kind === 'bfh') setFetchResult(await api.fetchBfh())
      else await api.analyzePending()
      reload()
    } catch (e) {
      setActionError((e as Error).message)
    } finally {
      setBusy(null)
    }
  }

  const importFile = async (file: File | undefined) => {
    if (!file) return
    setBusy('import')
    setActionError(null)
    try {
      setFetchResult(await api.importFeed(file))
      reload()
    } catch (e) {
      setActionError((e as Error).message)
    } finally {
      setBusy(null)
      if (fileInput.current) fileInput.current.value = ''
    }
  }

  const pending = data?.filter((u) => u.analysis_status === 'pending' || u.analysis_status === 'failed').length ?? 0
  const shown = data?.filter((u) => !hideIrrelevant || !u.summary || u.summary.relevant_for_companies) ?? []
  const noKey = health && !health.llm_configured

  return (
    <>
      <PageHeader
        title="Tax updates"
        intro={<>New BMF letters, laws and BFH rulings. The Regulatory Analyst reads each one and works out which companies it affects. BMF blocked? Use the <Link to="/settings#send-button" className="font-medium text-petrol hover:underline">Send to TaxPulse button</Link>.</>}
        action={
          <div className="flex flex-wrap gap-2">
            {!demo && <>
            <Button variant="quiet" onClick={() => navigate('/updates/new')}>Add update</Button>
            <input ref={fileInput} type="file" accept=".xml,.rss,application/xml,text/xml" hidden
              onChange={(e) => importFile(e.target.files?.[0])} />
            <Button variant="quiet" onClick={() => fileInput.current?.click()} disabled={busy !== null}
              title="Import the BMF RSS feed saved from your browser">
              {busy === 'import' ? 'Importing…' : 'Import feed file'}
            </Button>
            <Button variant="quiet" onClick={() => act('bfh')} disabled={busy !== null}>
              {busy === 'bfh' ? 'Fetching BFH news…' : 'Fetch BFH news'}
            </Button>
            <Button variant="quiet" onClick={() => act('fetch')} disabled={busy !== null}>
              {busy === 'fetch' ? 'Fetching BMF news…' : 'Fetch BMF news'}
            </Button>
            </>}
            <Button onClick={() => act('analyze')} disabled={busy !== null || pending === 0 || !!noKey || !!running}
              title={noKey ? 'Add your Anthropic API key to the .env file first' : undefined}>
              {running ? 'Analysing…' : `Analyse ${pending} new`}
            </Button>
          </div>
        }
      />

      <div className="mb-6 space-y-3">
        {(error || actionError) && <ErrorNote message={(error || actionError)!} />}
        {fetchResult && (
          <div className="rounded-md border border-petrol/25 bg-petrol-soft px-4 py-3 text-sm" role="status">
            <p className="text-petrol">
              {fetchResult.new === 0
                ? `No new publications. The feed lists ${fetchResult.found} items, all already in TaxPulse.`
                : `${fetchResult.new} new ${fetchResult.new === 1 ? 'publication' : 'publications'} added. Use Analyse to let the Regulatory Analyst read them.`}
            </p>
            {fetchResult.problems.length > 0 && (
              <details className="mt-2 text-slate">
                <summary className="cursor-pointer">{fetchResult.problems.length} {fetchResult.problems.length === 1 ? 'item' : 'items'} with notes</summary>
                <ul className="mt-1 list-disc pl-5">{fetchResult.problems.map((p) => <li key={p}>{p}</li>)}</ul>
              </details>
            )}
          </div>
        )}
      </div>

      {!loading && data?.length === 0 && (
        <EmptyState title="No updates yet">Fetch the latest BMF news, add a publication by hand, or load the demo data from the overview page.</EmptyState>
      )}

      {data && data.length > 0 && (
        <>
          <label className="mb-4 flex items-center gap-2 text-sm text-slate">
            <input type="checkbox" checked={hideIrrelevant} onChange={(e) => setHideIrrelevant(e.target.checked)}
              className="h-4 w-4 accent-petrol" />
            Hide publications with no impact on businesses
          </label>
          <ol className="space-y-3">
            {shown.map((u) => (
              <li key={u.id}>
                <Link to={`/updates/${u.id}`}
                  className={`block rounded-lg border border-rule bg-sheet px-5 py-4 hover:border-slate/40 ${u.summary && !u.summary.relevant_for_companies ? 'opacity-70' : ''}`}>
                  <div className="flex flex-wrap items-center gap-2 text-sm text-slate">
                    <KindTag kind={u.summary?.kind ?? u.kind} />
                    <time dateTime={u.published_on ?? undefined}>{formatDate(u.published_on)}</time>
                    <SourceTag source={u.source} />
                  </div>
                  <p className="mt-2 font-medium leading-snug">{u.summary?.title_en ?? u.title}</p>
                  {u.summary && u.summary.title_en !== u.title && (
                    <p className="mt-0.5 text-sm text-slate" lang="de">{u.title}</p>
                  )}
                  <Status u={u} />
                </Link>
              </li>
            ))}
          </ol>
        </>
      )}
    </>
  )
}
