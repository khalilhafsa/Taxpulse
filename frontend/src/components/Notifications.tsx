import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, formatDateTime, type AppNotification } from '../api'

const SEEN_KEY = 'taxpulse.lastNotified'

function readSeen(): number {
  try { return Number(localStorage.getItem(SEEN_KEY) || 0) } catch { return 0 }
}
function writeSeen(id: number) {
  try { localStorage.setItem(SEEN_KEY, String(id)) } catch { /* private window: no memory, no problem */ }
}

/** Bell with unread count; the panel lists the weekly check results and problems. New ones also
 *  appear as desktop notifications when the advisor allowed them in Settings. */
export default function Notifications() {
  const [items, setItems] = useState<AppNotification[]>([])
  const [unread, setUnread] = useState(0)
  const [open, setOpen] = useState(false)
  const box = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()

  const go = (link: string) => {
    if (!link) return
    if (/^https?:/.test(link)) window.open(link, '_blank', 'noopener')
    else navigate(link)
  }

  const load = async () => {
    try {
      const n = await api.notifications()
      setItems(n.items)
      setUnread(n.unread)
      const newest = n.items[0]?.id ?? 0
      const seen = readSeen()
      if (seen === 0) {
        writeSeen(newest) // first visit: do not pop up old messages
      } else if (newest > seen) {
        writeSeen(newest)
        if ('Notification' in window && Notification.permission === 'granted') {
          n.items.filter((x) => x.id > seen && !x.read).slice(0, 3).forEach((x) => {
            const note = new Notification(x.title, { body: x.body.split('\n')[0], tag: `taxpulse-${x.id}` })
            note.onclick = () => { window.focus(); go(x.link) }
          })
        }
      }
    } catch { /* backend offline: the status dot already says so */ }
  }

  useEffect(() => {
    load()
    const t = setInterval(load, 30000)
    return () => clearInterval(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false) }
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', esc)
    return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', esc) }
  }, [open])

  const openItem = async (n: AppNotification) => {
    setOpen(false)
    if (!n.read) await api.readNotification(n.id).catch(() => undefined)
    load()
    go(n.link)
  }

  return (
    <div ref={box} className="relative">
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open} aria-haspopup="dialog"
        aria-label={unread ? `Notifications, ${unread} unread` : 'Notifications'}
        className="relative flex h-10 w-10 items-center justify-center rounded-md text-slate hover:bg-sheet hover:text-ink">
        <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
          <path d="M6 9a6 6 0 1 1 12 0c0 4.5 1.5 6.5 2 7H4c.5-.5 2-2.5 2-7Z" /><path d="M10 20a2 2 0 0 0 4 0" />
        </svg>
        {unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-heat px-1 text-[10px] font-bold text-white dark:text-night ring-2 ring-paper">
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </button>
      {open && (
        <div role="dialog" aria-label="Notifications"
          className="absolute right-0 z-30 mt-2 w-[min(22rem,calc(100vw-2.5rem))] overflow-hidden rounded-xl border border-rule bg-sheet shadow-sm text-ink shadow-lg">
          <div className="flex items-center justify-between border-b border-rule px-4 py-2.5">
            <p className="text-sm font-semibold">Notifications</p>
            {unread > 0 && (
              <button type="button" className="text-xs font-medium text-brand hover:underline"
                onClick={async () => { await api.readAllNotifications().catch(() => undefined); load() }}>
                Mark all as read
              </button>
            )}
          </div>
          {items.length === 0 ? (
            <p className="px-4 py-6 text-sm text-slate">Nothing yet. The weekly check reports here.</p>
          ) : (
            <ul className="max-h-96 divide-y divide-rule overflow-y-auto">
              {items.map((n) => (
                <li key={n.id}>
                  <button type="button" onClick={() => openItem(n)} className={`block w-full px-4 py-3 text-left hover:bg-paper ${n.read ? '' : 'bg-brand-soft/40'}`}>
                    <span className="flex items-start gap-2">
                      <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${n.read ? 'bg-transparent' : n.kind === 'problem' ? 'bg-danger' : n.kind === 'action' ? 'bg-brand' : 'bg-heat'}`} />
                      <span className="min-w-0">
                        <span className="block text-sm font-medium">{n.title}</span>
                        {n.body && (
                          <span className={`mt-0.5 whitespace-pre-line text-xs leading-relaxed text-slate ${n.kind === 'problem' || n.kind === 'action' ? 'block' : 'line-clamp-3'}`}>
                            {n.body}
                          </span>
                        )}
                        <span className="mt-1 block text-[11px] text-slate">{formatDateTime(n.created_at)}</span>
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
