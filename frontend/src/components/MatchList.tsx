import { Link } from 'react-router-dom'
import { shortDocName, type Evidence, type Match } from '../api'

/** Relevance score; amber is reserved for scores that raise an alert. */
export function ScoreBadge({ score, threshold }: { score: number; threshold: number }) {
  const hot = score >= threshold
  return (
    <span
      className={`inline-flex min-w-[3.25rem] justify-center rounded-md px-2 py-1 font-serif text-lg font-semibold tabular-nums ${
        hot ? 'bg-amber-soft text-amber' : 'bg-paper text-slate'
      }`}
      title={hot ? `Alert: score of ${threshold} or more` : `Below the alert threshold of ${threshold}`}
    >
      {score}
    </span>
  )
}

const VERDICT = {
  affected: 'Affected',
  possibly_affected: 'Possibly affected',
  not_affected: 'Not affected',
}

function EvidenceRow({ e }: { e: Evidence }) {
  const c = e.citation
  return (
    <li className="grid gap-x-5 gap-y-1 py-3 md:grid-cols-2">
      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-slate">Update says</p>
        <p className="mt-0.5 text-sm leading-relaxed">{e.criterion}</p>
      </div>
      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-slate">
          Client file {e.supports === 'affected' ? 'shows' : 'rules it out'}
        </p>
        <p className="mt-0.5 text-sm leading-relaxed">{e.client_fact}</p>
        <p className="mt-1 text-[12.5px] leading-relaxed text-slate">
          “{c.quote}” <span className="whitespace-nowrap">({shortDocName(c.document)}, p.&nbsp;{c.page})</span>
          {!c.verified && (
            <span className="ml-1 text-danger" title="This quote was not found on that page. Check the source.">
              not verified
            </span>
          )}
        </p>
      </div>
    </li>
  )
}

function MatchCard({ m, threshold }: { m: Match; threshold: number }) {
  return (
    <li className={`rounded-lg border bg-sheet px-5 py-4 ${m.is_alert ? 'border-amber/40' : 'border-rule'}`}>
      <div className="flex flex-wrap items-start gap-4">
        <ScoreBadge score={m.score ?? 0} threshold={threshold} />
        <div className="min-w-0 flex-1">
          <p className="flex flex-wrap items-baseline gap-x-3">
            <Link to={`/clients/${m.client_id}`} className="font-semibold hover:underline">{m.client_name}</Link>
            {m.verdict && <span className={`text-sm ${m.is_alert ? 'text-amber' : 'text-slate'}`}>{VERDICT[m.verdict]}</span>}
          </p>
          <p className="mt-1 text-[14.5px] leading-relaxed">{m.reasoning}</p>
        </div>
      </div>
      {m.evidence.length > 0 && (
        <details className="mt-3" open={m.is_alert}>
          <summary className="cursor-pointer text-sm font-medium text-petrol">
            Evidence ({m.evidence.length})
          </summary>
          <ul className="mt-1 divide-y divide-rule">
            {m.evidence.map((e, i) => <EvidenceRow key={i} e={e} />)}
          </ul>
        </details>
      )}
      {m.missing_information && m.missing_information.length > 0 && (
        <div className="mt-3 text-sm">
          <p className="text-slate">To check with the client:</p>
          <ul className="mt-1 list-disc pl-5 leading-relaxed">
            {m.missing_information.map((x) => <li key={x}>{x}</li>)}
          </ul>
        </div>
      )}
    </li>
  )
}

export default function MatchList({ matches, threshold }: { matches: Match[]; threshold: number }) {
  const scored = matches.filter((m) => m.status === 'scored')
  const working = matches.filter((m) => m.status === 'running' || m.status === 'prefiltered')
  const failed = matches.filter((m) => m.status === 'failed')
  const filtered = matches.filter((m) => m.status === 'filtered_out')

  return (
    <div className="space-y-4">
      {working.length > 0 && (
        <p className="rounded-lg border border-petrol/25 bg-petrol-soft px-5 py-4 text-sm text-petrol" aria-live="polite">
          The Impact Matcher is checking {working.map((m) => m.client_name).join(', ')}. About twenty seconds per client.
        </p>
      )}
      {failed.map((m) => (
        <p key={m.id} className="rounded-md border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">
          {m.client_name}: {m.error}
        </p>
      ))}
      {scored.length > 0 && (
        <ol className="space-y-3">
          {scored.map((m) => <MatchCard key={m.id} m={m} threshold={threshold} />)}
        </ol>
      )}
      {filtered.length > 0 && (
        <div className="rounded-lg border border-rule bg-sheet px-5 py-4 text-sm">
          <p className="font-medium">Left out by the pre-filter, without calling Claude</p>
          <ul className="mt-2 space-y-1 text-slate">
            {filtered.map((m) => (
              <li key={m.id}><span className="text-ink">{m.client_name}</span>: {m.prefilter_reason}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
