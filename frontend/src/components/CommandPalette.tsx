import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'

export type PaletteItem = { label: string; hint: string; to: string }

/** Ctrl+K / Cmd+K jump list: every page, every former client and every tax update. */
export default function CommandPalette({ open, onClose, pages }: { open: boolean; onClose: () => void; pages: PaletteItem[] }) {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const [extra, setExtra] = useState<PaletteItem[]>([])
  const input = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!open) return
    setQuery('')
    setActive(0)
    setTimeout(() => input.current?.focus(), 0)
    Promise.all([api.clients().catch(() => []), api.updates().catch(() => [])]).then(([clients, updates]) => {
      setExtra([
        ...clients.map((c) => ({ label: c.name, hint: 'Client', to: `/clients/${c.id}` })),
        ...updates.map((u) => ({ label: u.summary?.title_en ?? u.title, hint: 'Tax update', to: `/updates/${u.id}` })),
      ])
    })
  }, [open])

  const results = useMemo(() => {
    const all = [...pages, ...extra]
    const q = query.trim().toLowerCase()
    return (q ? all.filter((i) => i.label.toLowerCase().includes(q) || i.hint.toLowerCase().includes(q)) : all).slice(0, 9)
  }, [pages, extra, query])

  if (!open) return null

  const go = (item: PaletteItem | undefined) => {
    if (!item) return
    onClose()
    navigate(item.to)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-night/40 px-4 pt-[12vh] backdrop-blur-[2px]"
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div role="dialog" aria-modal="true" aria-label="Jump to" className="tp-pal w-full max-w-xl overflow-hidden rounded-xl border border-rule bg-sheet shadow-xl">
        <div className="flex items-center gap-3 border-b border-rule px-4">
          <svg viewBox="0 0 24 24" className="h-5 w-5 shrink-0 text-slate" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
            <circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" strokeLinecap="round" />
          </svg>
          <input ref={input} value={query} placeholder="Jump to a page, client or tax update…"
            aria-label="Search" role="combobox" aria-expanded="true" aria-controls="tp-palette-list"
            onChange={(e) => { setQuery(e.target.value); setActive(0) }}
            onKeyDown={(e) => {
              if (e.key === 'Escape') onClose()
              else if (e.key === 'ArrowDown') { e.preventDefault(); setActive((a) => Math.min(a + 1, results.length - 1)) }
              else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)) }
              else if (e.key === 'Enter') go(results[active])
            }}
            className="h-14 min-w-0 flex-1 bg-transparent text-[15px] outline-none placeholder:text-slate/70" />
          <kbd className="rounded-sm border border-rule px-1.5 py-0.5 font-mono text-[11px] text-slate">Esc</kbd>
        </div>
        <ul id="tp-palette-list" role="listbox" className="max-h-[50vh] overflow-y-auto p-2">
          {results.length === 0 && <li className="px-3 py-6 text-center text-sm text-slate">Nothing matches “{query}”.</li>}
          {results.map((r, i) => (
            <li key={r.to + r.label} role="option" aria-selected={i === active}>
              <button type="button" onMouseEnter={() => setActive(i)} onClick={() => go(r)}
                className={`flex w-full items-center gap-3 rounded-md px-3 py-2.5 text-left text-sm ${i === active ? 'bg-brand-soft text-brand-deep' : 'text-ink'}`}>
                <span className="min-w-0 flex-1 truncate font-medium">{r.label}</span>
                <span className="shrink-0 text-xs text-slate">{r.hint}</span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
