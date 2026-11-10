import { useRef, useState } from 'react'
import { api, shortDocName, type DocumentInfo } from '../api'
import { ErrorNote, SectionTitle } from './ui'

export default function DataRoom({ clientId, documents, onChange }: {
  clientId: number
  documents: DocumentInfo[]
  onChange: () => void
}) {
  const input = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [warnings, setWarnings] = useState<string[]>([])
  const pages = documents.reduce((n, d) => n + d.page_count, 0)

  const upload = async (files: FileList | null) => {
    if (!files?.length) return
    setBusy(true)
    setError(null)
    try {
      const res = await api.uploadDocuments(clientId, Array.from(files))
      setWarnings(res.warnings)
      onChange()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
      if (input.current) input.current.value = ''
    }
  }

  return (
    <section aria-labelledby="dataroom">
      <SectionTitle id="dataroom">Data room</SectionTitle>
      <p className="-mt-2 mb-3 text-sm text-slate">
        {documents.length} {documents.length === 1 ? 'file' : 'files'}, {pages} pages
      </p>
      {documents.length > 0 && (
        <ul className="divide-y divide-rule overflow-hidden tp-chrome rounded-xl border border-rule bg-sheet shadow-sm">
          {documents.map((d) => (
            <li key={d.id}>
              <a href={api.fileUrl(d.id)} target="_blank" rel="noreferrer"
                className="flex items-baseline justify-between gap-3 px-4 py-2.5 text-sm hover:bg-paper">
                <span className="font-medium">{shortDocName(d.filename)}</span>
                <span className="shrink-0 text-slate">{d.page_count} p.</span>
              </a>
            </li>
          ))}
        </ul>
      )}
      <input ref={input} type="file" accept="application/pdf,.pdf" multiple hidden
        onChange={(e) => upload(e.target.files)} />
      <button type="button" disabled={busy} onClick={() => input.current?.click()}
        className="mt-3 w-full rounded-md border border-dashed border-slate/40 px-4 py-2.5 text-sm font-medium text-slate hover:border-brand hover:text-brand disabled:opacity-50">
        {busy ? 'Uploading and reading pages…' : 'Add PDF files'}
      </button>
      <div className="mt-3 space-y-2">
        {error && <ErrorNote message={error} />}
        {warnings.map((w) => <p key={w} className="text-sm text-heat">{w}</p>)}
      </div>
    </section>
  )
}
