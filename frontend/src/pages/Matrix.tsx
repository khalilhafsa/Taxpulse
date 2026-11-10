import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { api, type MatrixCell } from '../api'
import { EmptyState, ErrorNote, PageHeader } from '../components/ui'
import { useAsync } from '../useAsync'

// Heat is the relevance colour; its strength follows the Matcher's score.
const fill = (score: number) => `rgba(194, 65, 12, ${(0.08 + (score / 100) * 0.85).toFixed(2)})`

function cellInfo(cell: MatrixCell, threshold: number) {
  if (!cell) return { text: '·', title: 'Not matched yet', style: {}, cls: 'text-slate/50' }
  if (cell.stage === 'filtered_out')
    return { text: '–', title: 'Dropped by the pre-filter: no shared tax area (no AI used)', style: {}, cls: 'bg-paper text-slate' }
  if (cell.stage !== 'scored' || cell.score === null)
    return { text: '…', title: 'Waiting for the Impact Matcher', style: {}, cls: 'text-slate' }
  const status = cell.alert_status === 'accepted' ? ', accepted' : cell.alert_status === 'dismissed' ? ', dismissed' : ''
  return {
    text: String(cell.score),
    title: `Score ${cell.score} (${cell.verdict?.replace('_', ' ')})${cell.alert_id ? `, alert${status}` : ''}`,
    style: { backgroundColor: fill(cell.score) },
    cls: `${cell.score >= threshold ? 'text-white font-semibold' : 'text-ink'} ${cell.alert_status === 'dismissed' ? 'line-through opacity-60' : ''}`,
  }
}

function Legend({ threshold }: { threshold: number }) {
  const item = (swatch: ReactNode, label: string) => (
    <span className="flex items-center gap-2">{swatch}<span>{label}</span></span>
  )
  const box = 'inline-flex h-5 w-7 items-center justify-center rounded text-[11px]'
  return (
    <div className="mt-4 flex flex-wrap gap-x-6 gap-y-2 text-xs text-slate">
      {item(<span className={box} style={{ backgroundColor: fill(15) }}>15</span>, 'Not affected')}
      {item(<span className={box} style={{ backgroundColor: fill(45) }}>45</span>, 'Worth a look')}
      {item(<span className={`${box} font-semibold text-white`} style={{ backgroundColor: fill(88) }}>88</span>, `Alert (${threshold}+)`)}
      {item(<span className={`${box} bg-paper`}>–</span>, 'Dropped by the pre-filter, free')}
      {item(<span className={`${box} text-[13px]`}>✓</span>, 'Alert accepted')}
    </div>
  )
}

export default function Matrix() {
  const { data, error } = useAsync(api.matrix)

  const cells = data?.rows.flatMap((r) => r.cells) ?? []
  const filtered = cells.filter((c) => c?.stage === 'filtered_out').length
  const scored = cells.filter((c) => c?.stage === 'scored').length
  const alerts = cells.filter((c) => c?.alert_id).length

  return (
    <>
      <PageHeader
        title="Relevance matrix"
        intro="Every former client against every relevant tax update. The darker the cell, the more the update affects that client. Click a highlighted cell to open its alert."
      />
      {error && <ErrorNote message={error} />}
      {data && (data.rows.length === 0 || data.updates.length === 0) && (
        <EmptyState title="Nothing to compare yet">
          The matrix fills once at least one client has a profile and one tax update has been analysed as relevant.
          Use <Link to="/" className="font-medium text-brand hover:underline">Run the agents</Link> on the overview.
        </EmptyState>
      )}

      {data && data.rows.length > 0 && data.updates.length > 0 && (
        <>
          <p className="mb-4 text-sm text-slate">
            {data.rows.length} clients × {data.updates.length} updates = {cells.length} pairs.{' '}
            <span className="text-ink">{filtered}</span> dropped by the pre-filter for free,{' '}
            <span className="text-ink">{scored}</span> scored by the Impact Matcher,{' '}
            <span className="font-semibold text-heat">{alerts} {alerts === 1 ? 'alert' : 'alerts'}</span>.
          </p>
          <div className="overflow-x-auto tp-chrome rounded-xl border border-rule bg-sheet shadow-sm">
            <table className="w-full border-collapse text-sm">
              <caption className="sr-only">Matcher scores by client and tax update</caption>
              <thead>
                <tr className="border-b border-rule">
                  <th scope="col" className="sticky left-0 z-10 min-w-32 bg-sheet sm:min-w-44 px-4 py-3 text-left align-bottom font-medium text-slate">
                    Client
                  </th>
                  {data.updates.map((u) => (
                    <th key={u.id} scope="col" className="min-w-32 max-w-40 px-2 py-3 text-left align-bottom font-normal">
                      <Link to={`/updates/${u.id}`} className="group block" title={u.title}>
                        <span className="block text-[11px] font-semibold uppercase tracking-wide text-slate">
                          {u.categories[0] ?? u.kind}
                        </span>
                        <span className="mt-0.5 line-clamp-3 text-[13px] leading-snug text-ink group-hover:text-brand group-hover:underline">
                          {u.title}
                        </span>
                      </Link>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.rows.map((r) => (
                  <tr key={r.client.id} className="border-b border-rule last:border-b-0">
                    <th scope="row" className="sticky left-0 z-10 bg-sheet px-4 py-2 text-left text-[13px] font-medium sm:text-sm">
                      <Link to={`/clients/${r.client.id}`} className="hover:text-brand hover:underline">{r.client.name}</Link>
                    </th>
                    {r.cells.map((cell, i) => {
                      const info = cellInfo(cell, data.threshold)
                      const inner = (
                        <span style={info.style} title={info.title}
                          className={`relative flex h-11 items-center justify-center rounded-md tabular-nums ${info.cls}`}>
                          {info.text}
                          {cell?.alert_status === 'accepted' && (
                            <span className="absolute right-1 top-0.5 text-[11px] text-white" aria-label="accepted">✓</span>
                          )}
                        </span>
                      )
                      return (
                        <td key={data.updates[i].id} className="px-2 py-2">
                          {cell?.alert_id ? (
                            <Link to={`/alerts#alert-${cell.alert_id}`} className="block rounded-md hover:ring-2 hover:ring-brand/40"
                              aria-label={`${r.client.name}, ${data.updates[i].title}: ${info.title}`}>
                              {inner}
                            </Link>
                          ) : inner}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Legend threshold={data.threshold} />
        </>
      )}
    </>
  )
}
