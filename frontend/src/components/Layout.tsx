import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { api } from '../api'
import { useAsync } from '../useAsync'
import { useEffect, useState, type ReactNode } from 'react'
import { DemoContext } from '../demo'
import CommandPalette from './CommandPalette'
import ErrorBoundary from './ErrorBoundary'
import Notifications from './Notifications'

const I = (d: ReactNode) => (
  <svg viewBox="0 0 24 24" className="h-[18px] w-[18px] shrink-0" fill="none" stroke="currentColor" strokeWidth="1.7"
    strokeLinecap="round" strokeLinejoin="round" aria-hidden>{d}</svg>
)

const ICONS: Record<string, ReactNode> = {
  briefing: I(<><circle cx="12" cy="12" r="8.5" /><circle cx="12" cy="12" r="4.5" /><path d="M12 12 18 6" /></>),
  alerts: I(<><path d="M6 9a6 6 0 1 1 12 0c0 4.5 1.5 6.5 2 7H4c.5-.5 2-2.5 2-7Z" /><path d="M10 20a2 2 0 0 0 4 0" /></>),
  outreach: I(<><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m3.5 6.5 8.5 6 8.5-6" /></>),
  matrix: I(<><rect x="3.5" y="3.5" width="7" height="7" rx="1" /><rect x="13.5" y="3.5" width="7" height="7" rx="1" /><rect x="3.5" y="13.5" width="7" height="7" rx="1" /><rect x="13.5" y="13.5" width="7" height="7" rx="1" /></>),
  clients: I(<><path d="M4 20V8l8-4 8 4v12" /><path d="M9 20v-6h6v6" /><path d="M3 20h18" /></>),
  updates: I(<><path d="M7 3.5h7l4 4V20a.5.5 0 0 1-.5.5h-10A.5.5 0 0 1 7 20Z" /><path d="M14 3.5V8h4" /><path d="M10 13h5M10 16.5h5" /></>),
  runs: I(<><path d="M4 18 9 12l4 3 7-9" /><path d="M15 6h5v5" /></>),
  quality: I(<><path d="M12 3 4.5 6v5.5c0 4.5 3.2 8 7.5 9.5 4.3-1.5 7.5-5 7.5-9.5V6Z" /><path d="m8.8 12 2.2 2.2 4.4-4.4" /></>),
  settings: I(<><circle cx="12" cy="12" r="3" /><path d="M19 12a7 7 0 0 0-.1-1.2l2-1.6-2-3.4-2.4 1a7 7 0 0 0-2-1.2L14 3h-4l-.5 2.6a7 7 0 0 0-2 1.2l-2.4-1-2 3.4 2 1.6a7 7 0 0 0 0 2.4l-2 1.6 2 3.4 2.4-1a7 7 0 0 0 2 1.2L10 21h4l.5-2.6a7 7 0 0 0 2-1.2l2.4 1 2-3.4-2-1.6c.1-.4.1-.8.1-1.2Z" /></>),
}

const NAV = [
  { to: '/', label: 'Briefing', icon: 'briefing', end: true, group: 'Work' },
  { to: '/alerts', label: 'Alerts', icon: 'alerts', group: 'Work' },
  { to: '/outreach', label: 'Outreach', icon: 'outreach', group: 'Work' },
  { to: '/matrix', label: 'Matrix', icon: 'matrix', group: 'Work' },
  { to: '/clients', label: 'Clients', icon: 'clients', group: 'Records' },
  { to: '/updates', label: 'Tax updates', icon: 'updates', group: 'Records' },
  { to: '/runs', label: 'Agent runs', icon: 'runs', group: 'System' },
  { to: '/quality', label: 'Quality', icon: 'quality', group: 'System' },
  { to: '/settings', label: 'Settings', icon: 'settings', group: 'System' },
]
const GROUPS = ['Work', 'Records', 'System']
const PAGES = NAV.map((n) => ({ label: n.label, hint: 'Page', to: n.to }))

/** ISO calendar week, the way German offices count weeks. */
export function isoWeek(d: Date) {
  const t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()))
  t.setUTCDate(t.getUTCDate() + 4 - (t.getUTCDay() || 7))
  const start = new Date(Date.UTC(t.getUTCFullYear(), 0, 1))
  return Math.ceil(((t.getTime() - start.getTime()) / 86400000 + 1) / 7)
}

function Logo() {
  return (
    <NavLink to="/" className="flex shrink-0 items-center gap-2.5" aria-label="TaxPulse, briefing">
      <svg viewBox="0 0 32 32" className="h-8 w-8" aria-hidden>
        <rect width="32" height="32" rx="6" fill="var(--primary)" />
        <path d="M5.5 17h5l2.5-6 4 11 2.5-5h7" fill="none" stroke="var(--primary-foreground)" strokeWidth="2.3" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <span className="font-serif text-[19px] font-bold tracking-[-0.01em] text-sidebar-foreground">TaxPulse</span>
    </NavLink>
  )
}

function Status() {
  const { data, error } = useAsync(api.health)
  const state = error ? ['bg-[#ff8a80]', 'Backend offline']
    : !data ? ['bg-slate/40', 'Connecting']
    : data.key_problem ? ['bg-[#ff8a80]', 'API key needs fixing']
    : data.llm_configured ? ['bg-[#5ee0a8]', 'Agents ready']
    : ['bg-relevance', 'No API key set']
  return (
    <p className="flex items-center gap-2 text-xs text-slate" role="status">
      <span className="relative flex h-2 w-2" aria-hidden>
        <span className={`absolute inset-0 rounded-full ${state[0]} opacity-60 motion-safe:animate-ping`} />
        <span className={`relative h-2 w-2 rounded-full ${state[0]}`} />
      </span>
      {state[1]}
    </p>
  )
}

function DemoBanner() {
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState<string | null>(null)
  const [restored, setRestored] = useState(() => new URLSearchParams(window.location.search).has('restored'))
  useEffect(() => {
    if (!restored) return
    window.history.replaceState(null, '', window.location.pathname)
    const t = setTimeout(() => setRestored(false), 6000)
    return () => clearTimeout(t)
  }, [restored])
  const reset = async () => {
    setBusy(true)
    setNote(null)
    try {
      await api.resetDemo()
      window.location.assign('/?restored=1')
    } catch (e) {
      setNote((e as Error).message)
      setBusy(false)
    }
  }
  return (
    <div className="tp-hatch border-b border-heat/20 px-5 py-2 text-[13px] text-ink md:px-8">
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-1.5">
        <p className="flex items-baseline gap-3">
          <span className="shrink-0 rounded-sm bg-heat px-1.5 py-0.5 text-[10.5px] font-bold uppercase tracking-[0.1em] text-white dark:text-night">
            Demo
          </span>
          <span>
            <strong className="font-semibold">Public demo.</strong> The companies are fictional, and the agents replay results
            they produced with Claude, so nothing here calls the AI.
          </span>
        </p>
        {restored
          ? <span className="font-semibold" role="status">Done: the demo is back at its starting point.</span>
          : <button type="button" onClick={reset} disabled={busy}
              className="font-semibold text-accent-foreground underline decoration-current/40 underline-offset-4 hover:decoration-current disabled:opacity-50">
              {busy ? 'Starting over…' : 'Start the demo over'}
            </button>}
        {note && <p className="w-full text-danger">{note}</p>}
      </div>
    </div>
  )
}

/** Light / dark switch. The choice is remembered in this browser (see the script in index.html). */
function ThemeToggle() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains('dark'))
  const flip = () => {
    const next = !dark
    document.documentElement.classList.toggle('dark', next)
    try { localStorage.setItem('taxpulse.theme', next ? 'dark' : 'light') } catch { /* private window */ }
    setDark(next)
  }
  return (
    <button type="button" onClick={flip} aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'} aria-pressed={dark}
      className="flex h-10 w-10 items-center justify-center rounded-md text-slate hover:bg-card hover:text-ink">
      {dark ? (
        <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden>
          <circle cx="12" cy="12" r="4" /><path d="M12 2.5v2M12 19.5v2M4.6 4.6l1.4 1.4M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4 6 18M18 6l1.4-1.4" />
        </svg>
      ) : (
        <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
          <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z" />
        </svg>
      )}
    </button>
  )
}

function SearchButton({ onOpen, dark = false }: { onOpen: () => void; dark?: boolean }) {
  const mac = typeof navigator !== 'undefined' && /Mac/i.test(navigator.platform)
  return (
    <button type="button" onClick={onOpen}
      className={`flex h-10 w-full items-center gap-2.5 rounded-md px-3 text-sm ${
        dark ? 'bg-card text-slate ring-1 ring-sidebar-border hover:text-ink'
          : 'border border-rule bg-sheet text-slate shadow-sm hover:border-slate/40 hover:text-ink'}`}>
      <svg viewBox="0 0 24 24" className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" strokeWidth="1.9" aria-hidden>
        <circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" strokeLinecap="round" />
      </svg>
      <span className="flex-1 text-left">Jump to…</span>
      <kbd className={`rounded-sm px-1.5 py-px font-mono text-[10.5px] ${dark ? 'border border-sidebar-border text-slate' : 'border border-rule text-slate'}`}>
        {mac ? '⌘' : 'Ctrl'} K
      </kbd>
    </button>
  )
}

export default function Layout() {
  const { pathname } = useLocation()
  const { data: health } = useAsync(api.health)
  const demo = !!health?.demo_mode
  const [palette, setPalette] = useState(false)
  const now = new Date()
  const first = '/' + (pathname.split('/')[1] ?? '')
  const section = NAV.find((n) => n.to === first)

  // Click ripple on every themed button: a small circle spreads from the click point.
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const onDown = (e: PointerEvent) => {
      const btn = (e.target as Element | null)?.closest?.('.tp-btn-primary, .tp-btn-quiet') as HTMLElement | null
      if (!btn || (btn as HTMLButtonElement).disabled) return
      const r = btn.getBoundingClientRect()
      const dot = document.createElement('span')
      dot.className = 'tp-ripple'
      dot.style.left = `${e.clientX - r.left}px`
      dot.style.top = `${e.clientY - r.top}px`
      btn.appendChild(dot)
      dot.addEventListener('animationend', () => dot.remove())
    }
    window.addEventListener('pointerdown', onDown)
    return () => window.removeEventListener('pointerdown', onDown)
  }, [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); setPalette((p) => !p) }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  return (
    <DemoContext.Provider value={demo}>
    <div className="min-h-screen lg:grid lg:grid-cols-[256px_minmax(0,1fr)]">
      <aside className="tp-rail lg:sticky lg:top-0 lg:flex lg:h-screen lg:flex-col">
        <div className="flex items-center justify-between gap-3 px-5 py-4 lg:px-5 lg:pb-5 lg:pt-6">
          <Logo />
          <div className="flex items-center gap-1 lg:hidden">
            <button type="button" onClick={() => setPalette(true)} aria-label="Jump to"
              className="flex h-10 w-10 items-center justify-center rounded-md text-slate hover:bg-card hover:text-ink">
              <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.9" aria-hidden>
                <circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" strokeLinecap="round" />
              </svg>
            </button>
          </div>
        </div>
        <div className="hidden px-4 lg:block"><SearchButton dark onOpen={() => setPalette(true)} /></div>
        <nav className="flex gap-1 overflow-x-auto px-3 pb-3 [scrollbar-width:none] lg:mt-7 lg:flex-col lg:gap-6 lg:overflow-visible lg:px-3 lg:pb-0" aria-label="Main">
          {GROUPS.map((g) => (
            <div key={g} className="flex shrink-0 gap-1 lg:block">
              <p className="mb-2 hidden px-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate/80 lg:block">{g}</p>
              {NAV.filter((n) => n.group === g).map((n) => (
                <NavLink key={n.to} to={n.to} end={n.end}
                  className={({ isActive }) =>
                    `flex min-h-10 items-center gap-3 whitespace-nowrap rounded-md px-3 text-[14px] font-medium ${
                      isActive ? 'tp-rail-active' : 'text-sidebar-foreground/80 hover:bg-brand-soft hover:text-brand-deep'
                    }`}>
                  {ICONS[n.icon]}
                  {n.label}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <div className="mt-auto hidden space-y-3 border-t border-sidebar-border px-5 py-5 lg:block">
          <Status />
          <p className="text-xs leading-relaxed text-slate">Demo companies are fictional. Not tax advice.</p>
        </div>
      </aside>

      <div className="flex min-h-screen min-w-0 flex-col">
        {demo && <DemoBanner />}
        <div className="sticky top-0 z-30 border-b border-rule bg-paper/85 backdrop-blur-md">
          <div className="flex h-14 items-center justify-between gap-4 px-5 md:px-8">
            <p className="flex min-w-0 items-center gap-2 text-sm">
              <span className="text-slate">TaxPulse</span>
              <span aria-hidden className="text-slate/50">/</span>
              <span className="truncate font-semibold">{section?.label ?? 'TaxPulse'}</span>
            </p>
            <div className="flex items-center gap-3">
              <span className="hidden rounded-full border border-rule bg-card px-3 py-1 text-xs font-medium text-slate sm:inline">
                Week {isoWeek(now)} · {now.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}
              </span>
              <ThemeToggle />
              <Notifications />
            </div>
          </div>
        </div>
        <main className="mx-auto w-full max-w-[1240px] flex-1 px-5 py-8 md:px-8 md:py-10">
          <ErrorBoundary key={pathname}>
            <div className="tp-page"><Outlet /></div>
          </ErrorBoundary>
        </main>
      </div>
      <CommandPalette open={palette} onClose={() => setPalette(false)} pages={PAGES} />
    </div>
    </DemoContext.Provider>
  )
}
