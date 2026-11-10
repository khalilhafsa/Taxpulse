import { useEffect, useRef, useState } from 'react'
import { api, shortDocName, type Citation, type DocumentInfo, type PageText } from '../api'

/** Escape regex special characters so the quote can be searched literally. */
const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

/** Highlight the quote in the page text, tolerant of line breaks and spacing. */
function highlight(text: string, quote: string) {
  const words = quote.trim().split(/\s+/).map(escape)
  if (!words.length) return [text]
  const match = new RegExp(words.join('\\s+'), 'i').exec(text)
  if (!match) return [text]
  return [
    text.slice(0, match.index),
    <mark key="q" className="rounded-sm bg-heat-soft px-0.5 text-ink ring-1 ring-heat/40">{match[0]}</mark>,
    text.slice(match.index + match[0].length),
  ]
}

export default function SourcePanel({ citation, documents, onClose }: {
  citation: Citation
  documents: DocumentInfo[]
  onClose: () => void
}) {
  const doc = documents.find((d) => d.filename === citation.document)
  const [pageNumber, setPageNumber] = useState(citation.page)
  const [page, setPage] = useState<PageText | null>(null)
  const [error, setError] = useState<string | null>(null)
  const closeRef = useRef<HTMLButtonElement>(null)

  useEffect(() => setPageNumber(citation.page), [citation])
  useEffect(() => {
    closeRef.current?.focus()
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  useEffect(() => {
    setPage(null)
    setError(null)
    if (!doc) return setError(`The document “${citation.document}” is not in this data room.`)
    if (pageNumber < 1 || pageNumber > doc.page_count)
      return setError(`${shortDocName(doc.filename)} has ${doc.page_count} pages; page ${pageNumber} does not exist.`)
    api.page(doc.id, pageNumber).then(setPage).catch((e: Error) => setError(e.message))
  }, [doc, pageNumber, citation.document])

  const onCitedPage = pageNumber === citation.page

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-ink/20" onClick={onClose}>
      <aside
        role="dialog"
        aria-label="Source of this fact"
        onClick={(e) => e.stopPropagation()}
        className="flex h-full w-full max-w-xl flex-col border-l border-rule bg-sheet shadow-xl"
      >
        <header className="flex items-start justify-between gap-4 border-b border-rule px-6 py-5">
          <div>
            <p className="font-serif text-lg font-semibold">{shortDocName(citation.document)}</p>
            <p className="mt-0.5 text-sm text-slate">
              {doc && pageNumber > doc.page_count
                ? `Cited page ${pageNumber} (the document has ${doc.page_count})`
                : `Page ${pageNumber}${doc ? ` of ${doc.page_count}` : ''}`}
            </p>
          </div>
          <button ref={closeRef} onClick={onClose} className="rounded-md px-2 py-1 text-sm font-medium text-slate hover:bg-paper hover:text-ink">
            Close
          </button>
        </header>

        <div className={`border-b px-6 py-3 text-sm ${citation.verified ? 'border-brand/20 bg-brand-soft text-brand' : 'border-danger/20 bg-danger/5 text-danger'}`}>
          {citation.verified
            ? 'Quote found on this page. The highlighted passage is the evidence the agent used.'
            : 'TaxPulse could not find this quote on the cited page. Check the source before relying on this fact.'}
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5">
          {!onCitedPage && <p className="mb-3 text-xs text-slate">You are viewing a neighbouring page. The citation points to page {citation.page}.</p>}
          {error && <p className="text-sm text-danger">{error}</p>}
          {!error && !page && <p className="text-sm text-slate">Loading page…</p>}
          {page && (
            <p className="whitespace-pre-wrap text-[13.5px] leading-relaxed text-ink">
              {onCitedPage ? highlight(page.text, citation.quote) : page.text}
            </p>
          )}
          {!citation.verified && (
            <div className="mt-6 border-t border-rule pt-4 text-sm">
              <p className="text-slate">Quote given by the agent</p>
              <p className="mt-1 italic">“{citation.quote}”</p>
            </div>
          )}
        </div>

        {doc && (
          <footer className="flex items-center justify-between gap-3 border-t border-rule px-6 py-4 text-sm">
            <div className="flex gap-2">
              <button disabled={pageNumber <= 1} onClick={() => setPageNumber((n) => Math.min(n - 1, doc.page_count))}
                className="rounded-md border border-rule px-3 py-1.5 font-medium disabled:opacity-40">Previous page</button>
              <button disabled={pageNumber >= doc.page_count} onClick={() => setPageNumber((n) => n + 1)}
                className="rounded-md border border-rule px-3 py-1.5 font-medium disabled:opacity-40">Next page</button>
            </div>
            <a href={api.fileUrl(doc.id, pageNumber)} target="_blank" rel="noreferrer" className="font-medium text-brand hover:underline">
              Open PDF
            </a>
          </footer>
        )}
      </aside>
    </div>
  )
}
