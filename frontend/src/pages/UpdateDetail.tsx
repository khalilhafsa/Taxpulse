import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import { Button, EmptyState, ErrorNote, KindTag, PageHeader, SectionTitle, SourceTag, formatDate } from '../components/ui'
import { useAsync } from '../useAsync'

function List({ items, empty }: { items: string[]; empty: string }) {
  if (!items.length) return <p className="text-sm text-slate">{empty}</p>
  return (
    <ul className="space-y-2">
      {items.map((t) => (
        <li key={t} className="flex gap-3 text-[15px] leading-relaxed">
          <span className="mt-2.5 h-1.5 w-1.5 shrink-0 rounded-full bg-slate/50" />
          {t}
        </li>
      ))}
    </ul>
  )
}

export default function UpdateDetail() {
  const id = Number(useParams().id)
  const { data: u, error, reload } = useAsync(() => api.update(id), [id])
  const { data: health } = useAsync(api.health)
  const [actionError, setActionError] = useState<string | null>(null)

  const running = u?.analysis_status === 'running'
  useEffect(() => {
    if (!running) return
    const t = setInterval(reload, 2500)
    return () => clearInterval(t)
  }, [running, reload])

  const analyze = async () => {
    setActionError(null)
    try {
      await api.analyzeUpdate(id)
      reload()
    } catch (e) {
      setActionError((e as Error).message)
    }
  }

  if (error) return <ErrorNote message={error} />
  if (!u) return null
  const a = u.summary
  const noKey = health && !health.llm_configured

  return (
    <>
      <Link to="/updates" className="text-sm font-medium text-petrol hover:underline">Back to tax updates</Link>
      <div className="mt-4">
        <PageHeader
          title={a?.title_en ?? u.title}
          intro={
            <div className="flex flex-wrap items-center gap-2">
              <KindTag kind={a?.kind ?? u.kind} />
              <span>{formatDate(u.published_on)}</span>
              <SourceTag source={u.source} />
              {a && a.title_en !== u.title && <span lang="de" className="w-full">{u.title}</span>}
            </div>
          }
          action={
            <Button onClick={analyze} disabled={running || !!noKey}
              title={noKey ? 'Add your Anthropic API key to the .env file first' : undefined}>
              {running ? 'Analyst at work…' : a ? 'Analyse again' : 'Analyse'}
            </Button>
          }
        />
      </div>

      <div className="space-y-3">
        {actionError && <ErrorNote message={actionError} />}
        {u.analysis_status === 'failed' && u.analysis_error && <ErrorNote message={u.analysis_error} />}
      </div>

      {running && (
        <p className="mb-8 rounded-lg border border-petrol/25 bg-petrol-soft px-5 py-4 text-sm text-petrol" aria-live="polite">
          The Regulatory Analyst is reading this publication. This takes about ten seconds.
        </p>
      )}

      {a ? (
        <div className="space-y-10">
          {!a.relevant_for_companies && (
            <p className="rounded-md border border-rule bg-sheet px-4 py-3 text-sm text-slate">
              The Analyst found no impact on businesses. This publication will not be matched against your clients.
            </p>
          )}
          <p className="font-serif text-[19px] leading-relaxed">{a.summary}</p>

          <dl className="divide-y divide-rule rounded-lg border border-rule bg-sheet">
            {[
              ['Tax areas', a.tax_categories.join(', ')],
              ['Who is affected', a.who_is_affected],
              ['Applies from', a.effective_date],
            ].map(([label, value]) => (
              <div key={label} className="grid gap-1 px-5 py-3 sm:grid-cols-[150px_1fr] sm:gap-6">
                <dt className="text-sm text-slate">{label}</dt>
                <dd className="text-[15px] leading-relaxed">{value}</dd>
              </div>
            ))}
          </dl>

          <section aria-labelledby="criteria">
            <SectionTitle id="criteria">What makes a company affected</SectionTitle>
            <List items={a.trigger_criteria} empty="No specific criteria." />
          </section>

          <section aria-labelledby="exclusions">
            <SectionTitle id="exclusions">Not covered</SectionTitle>
            <List items={a.exclusions} empty="The publication names no exclusions." />
          </section>

          <section aria-labelledby="kw">
            <SectionTitle id="kw">Matching keywords</SectionTitle>
            <ul className="flex flex-wrap gap-1.5">
              {a.keywords.map((k) => <li key={k} className="rounded-full border border-rule bg-sheet px-3 py-1 text-sm">{k}</li>)}
            </ul>
          </section>
        </div>
      ) : !running && (
        <EmptyState title="Not analysed yet">
          Click Analyse to let the Regulatory Analyst extract the tax areas, the companies affected and the cases it excludes.
        </EmptyState>
      )}

      <details className="mt-10 rounded-lg border border-rule bg-sheet">
        <summary className="cursor-pointer px-5 py-3 text-sm font-medium">Original text</summary>
        <div className="border-t border-rule px-5 py-4">
          {u.url && (
            <a href={u.url} target="_blank" rel="noreferrer" className="mb-3 inline-block text-sm font-medium text-petrol hover:underline">
              Open the source page
            </a>
          )}
          <p className="whitespace-pre-wrap text-[13.5px] leading-relaxed">{u.raw_text}</p>
        </div>
      </details>
    </>
  )
}
