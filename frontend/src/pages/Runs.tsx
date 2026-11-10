import { useEffect } from 'react'
import { api, formatDateTime, type AgentRun } from '../api'
import AgentChain from '../components/AgentChain'
import { EmptyState, ErrorNote, PageHeader } from '../components/ui'
import { useAsync } from '../useAsync'

const AGENT_LABEL: Record<string, string> = {
  profiler: 'Profiler',
  analyst: 'Regulatory Analyst',
  matcher: 'Impact Matcher',
  explainer: 'Impact Explainer',
  writer: 'Outreach Writer',
}

function Status({ run }: { run: AgentRun }) {
  if (run.status === 'running') return <span className="tp-busy text-ink">Running</span>
  if (run.status === 'failed') return <span className="text-danger" title={run.error}>Failed</span>
  return <span className="text-slate">Done</span>
}

export default function Runs() {
  const { data, error, reload } = useAsync(api.runs)
  const anyRunning = data?.runs.some((r) => r.status === 'running')

  useEffect(() => {
    if (!anyRunning) return
    const t = setInterval(reload, 3000)
    return () => clearInterval(t)
  }, [anyRunning, reload])

  return (
    <>
      <PageHeader
        title="Agent runs"
        intro="Every call to an agent, with how long it took, the tokens it used and what it cost."
      />
      <div className="mb-12"><AgentChain onFinished={reload} /></div>
      {error && <ErrorNote message={error} />}
      {data && data.runs.length === 0 && (
        <EmptyState title="No runs yet">Build a client profile or analyse a tax update to see the first run here.</EmptyState>
      )}
      {data && data.runs.length > 0 && (
        <>
          <p className="mb-4 text-sm text-slate">
            {data.totals.runs} {data.totals.runs === 1 ? 'run' : 'runs'}, {data.totals.tokens.toLocaleString('en-GB')} tokens, ${data.totals.cost_usd.toFixed(3)} in total
          </p>
          <div className="overflow-x-auto tp-chrome rounded-xl border border-rule bg-sheet shadow-sm">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead className="border-b border-rule text-slate">
                <tr>
                  {['Agent', 'Worked on', 'Status', 'Started', 'Duration', 'Tokens in / out', 'Cost'].map((h) => (
                    <th key={h} scope="col" className="px-4 py-3 font-medium">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-rule">
                {data.runs.map((r) => (
                  <tr key={r.id}>
                    <td className="px-4 py-3 font-medium">{AGENT_LABEL[r.agent] ?? r.agent}</td>
                    <td className="px-4 py-3">{r.subject_label}</td>
                    <td className="px-4 py-3"><Status run={r} /></td>
                    <td className="px-4 py-3 text-slate">{formatDateTime(r.started_at)}</td>
                    <td className="px-4 py-3 tabular-nums">{r.duration_ms ? `${(r.duration_ms / 1000).toFixed(1)} s` : ''}</td>
                    <td className="px-4 py-3 tabular-nums">
                      {r.tokens_in ? `${r.tokens_in.toLocaleString('en-GB')} / ${r.tokens_out.toLocaleString('en-GB')}` : ''}
                    </td>
                    <td className="px-4 py-3 tabular-nums">{r.status === 'done' ? `$${r.cost_usd.toFixed(3)}` : ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {data.runs.some((r) => r.status === 'failed') && (
            <p className="mt-3 text-sm text-slate">Hover a failed status to read the error.</p>
          )}
        </>
      )}
    </>
  )
}
