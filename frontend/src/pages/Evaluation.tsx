import { Link } from 'react-router-dom'
import { api, type EvaluationRow } from '../api'
import { EmptyState, ErrorNote, PageHeader } from '../components/ui'
import { useAsync } from '../useAsync'

const EXPECTED = { affected: 'Must be flagged', not_affected: 'Must not be flagged', either: 'Either is fine' }

const OUTCOME: Record<EvaluationRow['outcome'], [string, string]> = {
  correct: ['Correct', 'text-petrol'],
  borderline: ['Borderline', 'text-slate'],
  missed: ['Missed', 'text-danger font-semibold'],
  false_alert: ['False alert', 'text-danger font-semibold'],
  pending: ['Not scored yet', 'text-slate'],
}

function Result({ r }: { r: EvaluationRow }) {
  if (r.stage === 'filtered_out') return <span className="text-slate">Pre-filter</span>
  if (r.score === null) return <span className="text-slate">–</span>
  return <span className={`tabular-nums ${r.alert ? 'font-semibold text-amber' : ''}`}>{r.score}</span>
}

export default function Evaluation() {
  const { data: ev, error } = useAsync(api.evaluation)

  return (
    <>
      <PageHeader
        title="Evaluation"
        intro={<>The Impact Matcher's alerts on the demo portfolio, compared with answers labelled by hand. Target: no affected client missed, and at most one false alert per ten pairs.</>}
      />
      {error && <ErrorNote message={error} />}
      {ev && (
        <>
          <div className={`mb-6 rounded-lg border px-5 py-4 ${!ev.complete ? 'border-rule bg-sheet' : ev.passed ? 'border-petrol/30 bg-petrol-soft' : 'border-danger/30 bg-danger/5'}`}>
            <p className={`font-serif text-xl font-semibold ${!ev.complete ? '' : ev.passed ? 'text-petrol' : 'text-danger'}`}>
              {!ev.complete ? `${ev.pending} of ${ev.pairs} pairs not scored yet`
                : ev.passed ? 'The Matcher passes the evaluation' : 'The Matcher does not pass yet'}
            </p>
            <p className="mt-1 text-sm text-slate">
              {!ev.complete
                ? 'Build the profiles of the four demo clients, analyse the six demo updates, then run Scan portfolio on the Alerts page.'
                : `Alert threshold: score of ${ev.threshold} or more.`}
            </p>
          </div>

          <dl className="mb-8 grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-rule bg-rule sm:grid-cols-4">
            {[
              ['Affected clients found', ev.recall === null ? '–' : `${Math.round(ev.recall * 100)} %`],
              ['Missed', ev.missed],
              ['False alerts', ev.false_alert],
              ['Correct', `${ev.correct} / ${ev.judged}`],
            ].map(([label, value]) => (
              <div key={label} className="bg-sheet px-5 py-4">
                <dt className="text-sm text-slate">{label}</dt>
                <dd className="mt-1 font-serif text-2xl font-semibold">{value}</dd>
              </div>
            ))}
          </dl>

          {ev.rows.length === 0 ? <EmptyState title="No labelled pairs" /> : (
            <div className="overflow-x-auto rounded-lg border border-rule bg-sheet">
              <table className="w-full min-w-[760px] text-left text-sm">
                <thead className="border-b border-rule text-slate">
                  <tr>
                    {['Update', 'Client', 'Expected', 'Score', 'Result'].map((h) => (
                      <th key={h} scope="col" className="px-4 py-3 font-medium">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-rule">
                  {ev.rows.map((r) => (
                    <tr key={`${r.update}-${r.client}`}>
                      <td className="max-w-[260px] px-4 py-3">
                        {r.update_id ? <Link to={`/updates/${r.update_id}`} className="hover:underline">{r.update}</Link> : r.update}
                      </td>
                      <td className="px-4 py-3">{r.client}</td>
                      <td className="px-4 py-3" title={r.why}>
                        {EXPECTED[r.expected]}
                        <span className="block text-xs text-slate">{r.why}</span>
                      </td>
                      <td className="px-4 py-3"><Result r={r} /></td>
                      <td className={`px-4 py-3 ${OUTCOME[r.outcome][1]}`}>{OUTCOME[r.outcome][0]}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </>
  )
}
