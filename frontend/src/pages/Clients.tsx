import { useDemo } from '../demo'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { Button, DemoTag, EmptyState, ErrorNote, PageHeader } from '../components/ui'
import { useAsync } from '../useAsync'

export default function Clients() {
  const demo = useDemo()
  const { data, error, loading } = useAsync(api.clients)
  const navigate = useNavigate()

  return (
    <>
      <PageHeader
        title="Former clients"
        intro="Companies you advised on a due diligence mandate. Each one keeps its data room and a tax profile built from it."
        action={demo ? undefined : <Button onClick={() => navigate('/clients/new')}>Add client</Button>}
      />
      {error && <ErrorNote message={error} />}
      {!loading && data?.length === 0 && (
        <EmptyState title="No clients yet">Load the demo data from the overview page to get started.</EmptyState>
      )}
      {data && data.length > 0 && (
        <ul className="divide-y divide-rule overflow-hidden tp-chrome rounded-xl border border-rule bg-sheet shadow-sm">
          {data.map((c) => (
            <li key={c.id}>
              <Link to={`/clients/${c.id}`} className="flex flex-wrap items-center gap-x-6 gap-y-1 px-5 py-4 hover:bg-paper">
                <div className="w-full min-w-0 sm:w-auto sm:flex-1">
                  <p className="font-serif text-lg font-semibold">{c.name}</p>
                  <p className="text-sm text-slate">{c.mandate}</p>
                </div>
                <span className="text-sm text-slate">
                  {c.document_count} {c.document_count === 1 ? 'file' : 'files'}
                </span>
                <span className={`text-sm ${c.has_profile ? 'text-ok' : 'text-slate'}`}>
                  {c.has_profile ? 'Profile ready' : 'Profile not built yet'}
                </span>
                {c.is_demo && <DemoTag />}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  )
}
