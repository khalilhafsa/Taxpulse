import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, type UpdateKind } from '../api'
import { Button, ErrorNote, PageHeader } from '../components/ui'

const KINDS: [UpdateKind, string][] = [
  ['bmf_letter', 'BMF letter'],
  ['bfh_ruling', 'BFH ruling'],
  ['law', 'Law'],
  ['press_release', 'Press release'],
  ['other', 'Other tax news'],
]

export default function NewUpdate() {
  const navigate = useNavigate()
  const [title, setTitle] = useState('')
  const [kind, setKind] = useState<UpdateKind>('bfh_ruling')
  const [date, setDate] = useState('')
  const [url, setUrl] = useState('')
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const u = await api.addUpdate({ title, kind, published_on: date || null, url: url || null, text })
      navigate(`/updates/${u.id}`)
    } catch (err) {
      setError((err as Error).message)
      setBusy(false)
    }
  }

  const field = 'mt-1.5 w-full rounded-sm border border-ink/20 bg-sheet px-3 py-2 text-[15px] focus:border-petrol focus:outline-none focus:ring-2 focus:ring-petrol/15'

  return (
    <>
      <Link to="/updates" className="text-sm font-medium text-petrol hover:underline">Back to tax updates</Link>
      <div className="mt-4">
        <PageHeader title="Add a tax update"
          intro="Paste a ruling, BMF letter or newsletter item that is not in the BMF feed. German or English text both work." />
      </div>
      <form onSubmit={submit} className="max-w-2xl space-y-6">
        <label className="block">
          <span className="text-sm font-medium">Title</span>
          <input required minLength={3} value={title} onChange={(e) => setTitle(e.target.value)} className={field}
            placeholder="e.g. BFH, Urteil vom 12.06.2026 – IV R 3/25" />
        </label>
        <div className="grid gap-6 sm:grid-cols-2">
          <label className="block">
            <span className="text-sm font-medium">Type</span>
            <select value={kind} onChange={(e) => setKind(e.target.value as UpdateKind)} className={field}>
              {KINDS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </label>
          <label className="block">
            <span className="text-sm font-medium">Published on</span>
            <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className={field} />
          </label>
        </div>
        <label className="block">
          <span className="text-sm font-medium">Link to the source <span className="font-normal text-slate">(optional)</span></span>
          <input type="url" value={url} onChange={(e) => setUrl(e.target.value)} className={field} placeholder="https://" />
        </label>
        <label className="block">
          <span className="text-sm font-medium">Full text</span>
          <textarea required minLength={40} rows={12} value={text} onChange={(e) => setText(e.target.value)}
            className={`${field} font-[inherit] leading-relaxed`} />
        </label>
        {error && <ErrorNote message={error} />}
        <Button type="submit" disabled={busy || title.trim().length < 3 || text.trim().length < 40}>
          {busy ? 'Saving…' : 'Add update'}
        </Button>
      </form>
    </>
  )
}
