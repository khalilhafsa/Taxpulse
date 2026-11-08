import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { api } from '../api'
import { useAsync } from '../useAsync'
import { useEffect, useState } from 'react'
import { DemoContext } from '../demo'
import ErrorBoundary from './ErrorBoundary'
import Notifications from './Notifications'

const NAV = [
  { to: '/', label: 'Briefing', end: true },
  { to: '/alerts', label: 'Alerts' },
  { to: '/outreach', label: 'Outreach' },
  { to: '/matrix', label: 'Matrix' },
  { to: '/clients', label: 'Clients' },
  { to: '/updates', label: 'Tax updates' },
  { to: '/runs', label: 'Agent runs' },
  { to: '/quality', label: 'Quality' },
  { to: '/settings', label: 'Settings' },
]

/** ISO calendar week, the way German offices count weeks. */
export function isoWeek(d: Date) {
  const t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()))
  t.setUTCDate(t.getUTCDate() + 4 - (t.getUTCDay() || 7))
  const start = new Date(Date.UTC(t.getUTCFullYear(), 0, 1))
  return Math.ceil(((t.getTime() - start.getTime()) / 86400000 + 1) / 7)
}

function Logo() {
  return (
    <NavLink to="/" className="flex shrink-0 items-center gap-3" aria-label="TaxPulse, briefing">
      <svg viewBox="0 0 32 32" className="h-8 w-8" aria-hidden>
        <rect width="32" height="32" fill="#6cc7b5" />
        <path d="M4 17h7l3-8 4 15 3-7h7" fill="none" stroke="#0c2427" strokeWidth="2.6" strokeLinecap="square" />
      </svg>
      <span className="font-serif text-[23px] font-semibold tracking-[-0.02em] text-white">TaxPulse</span>
    </NavLink>
  )
}

function Status() {
  const { data, error } = useAsync(api.health)
  const state = error ? ['bg-[#ff8a80]', 'Backend offline']
    : !data ? ['bg-white/40', 'Connecting']
    : data.key_problem ? ['bg-[#ff8a80]', 'API key needs fixing']
    : data.llm_configured ? ['bg-[#7fd6c2]', 'Agents ready']
    : ['bg-signal', 'No API key set']
  return (
    <p className="hidden items-center gap-2 text-xs text-white/70 xl:flex" role="status">
      <span className={`h-2 w-2 rounded-full ${state[0]}`} aria-hidden />
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
    <div className="tp-hatch border-b border-ink/15 px-5 py-2 text-[13px] text-ink md:px-8">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-x-6 gap-y-1.5">
        <p className="flex items-baseline gap-3">
          <span className="shrink-0 bg-ink px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-[0.14em] text-paper">
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
              className="font-semibold underline decoration-ink/30 underline-offset-4 hover:decoration-ink disabled:opacity-50">
              {busy ? 'Starting over…' : 'Start the demo over'}
            </button>}
        {note && <p className="w-full text-danger">{note}</p>}
      </div>
    </div>
  )
}

export default function Layout() {
  const { pathname } = useLocation()
  const { data: health } = useAsync(api.health)
  const demo = !!health?.demo_mode
  const now = new Date()
  return (
    <DemoContext.Provider value={demo}>
    <div className="flex min-h-screen flex-col">
      {demo && <DemoBanner />}
      <header className="sticky top-0 z-40 bg-night text-white">
        <div className="mx-auto flex h-16 w-full max-w-7xl items-center gap-8 px-5 md:px-8">
          <Logo />
          <nav className="hidden h-full flex-1 items-stretch lg:flex" aria-label="Main">
            {NAV.map((n) => (
              <NavLink key={n.to} to={n.to} end={n.end}
                className={({ isActive }) =>
                  `relative flex items-center px-3 text-[14px] font-medium ${
                    isActive
                      ? 'text-white after:absolute after:inset-x-3 after:bottom-0 after:h-[3px] after:bg-signal'
                      : 'text-white/65 hover:text-white'
                  }`}>
                {n.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-4 lg:ml-0">
            <Status />
            <Notifications />
          </div>
        </div>
        <nav className="flex gap-1 overflow-x-auto border-t border-white/10 px-3 [scrollbar-width:none] lg:hidden" aria-label="Main mobile">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end}
              className={({ isActive }) =>
                `relative flex min-h-11 shrink-0 items-center whitespace-nowrap px-3 text-[14px] font-medium ${
                  isActive ? 'text-white after:absolute after:inset-x-3 after:bottom-0 after:h-[3px] after:bg-signal' : 'text-white/65'
                }`}>
              {n.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <div className="border-b border-ink/15">
        <div className="mx-auto flex h-10 max-w-7xl items-center justify-between gap-4 px-5 md:px-8">
          <p className="tp-eyebrow truncate">Mandate monitor for former clients</p>
          <p className="tp-eyebrow hidden shrink-0 sm:block">
            Week {isoWeek(now)}<span aria-hidden className="mx-2 opacity-50">/</span>
            {now.toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
          </p>
        </div>
      </div>
      <main className="mx-auto w-full max-w-7xl flex-1 px-5 py-9 md:px-8 md:py-12">
        <ErrorBoundary key={pathname}>
          <Outlet />
        </ErrorBoundary>
      </main>
      <footer className="border-t border-ink/15">
        <div className="mx-auto flex max-w-7xl flex-wrap justify-between gap-2 px-5 py-6 text-xs text-slate md:px-8">
          <p>TaxPulse · regulatory radar for German tax advisors</p>
          <p>Demo companies are fictional. Not tax advice.</p>
        </div>
      </footer>
    </div>
    </DemoContext.Provider>
  )
}
