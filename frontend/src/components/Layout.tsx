import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { api } from '../api'
import { useAsync } from '../useAsync'
import { useState } from 'react'
import { DemoContext } from '../demo'
import ErrorBoundary from './ErrorBoundary'
import Notifications from './Notifications'

const NAV = [
  { to: '/', label: 'Overview', end: true },
  { to: '/clients', label: 'Clients' },
  { to: '/updates', label: 'Tax updates' },
  { to: '/matrix', label: 'Matrix' },
  { to: '/alerts', label: 'Alerts' },
  { to: '/outreach', label: 'Outreach' },
  { to: '/runs', label: 'Agent runs' },
  { to: '/quality', label: 'Quality' },
  { to: '/settings', label: 'Settings' },
]

function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <svg viewBox="0 0 32 32" className="h-8 w-8" aria-hidden>
        <rect width="32" height="32" rx="7" fill="#0F5C63" />
        <path d="M5 17h6l3-7 4 13 3-6h6" fill="none" stroke="#fff" strokeWidth="2.6"
          strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <span className="font-serif text-xl font-semibold tracking-tight">TaxPulse</span>
    </div>
  )
}

function Status() {
  const { data, error } = useAsync(api.health)
  const state = error ? ['bg-danger', 'Backend offline']
    : !data ? ['bg-rule', 'Connecting']
    : data.key_problem ? ['bg-danger', 'API key needs fixing']
    : data.llm_configured ? ['bg-petrol', 'Agents ready']
    : ['bg-amber', 'No API key set']
  return (
    <p className="flex items-center gap-2 text-xs text-slate">
      <span className={`h-2 w-2 rounded-full ${state[0]}`} />
      {state[1]}
    </p>
  )
}

function DemoBanner() {
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState<string | null>(null)
  const reset = async () => {
    setBusy(true)
    setNote(null)
    try {
      await api.resetDemo()
      window.location.assign('/')
    } catch (e) {
      setNote((e as Error).message)
      setBusy(false)
    }
  }
  return (
    <div className="border-b border-petrol/20 bg-petrol-soft px-5 py-2.5 text-sm text-petrol md:px-10">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-x-6 gap-y-1">
        <p>
          <strong className="font-semibold">Public demo.</strong> The companies are fictional, and the agents replay results
          they produced with Claude, so nothing here calls the AI.
        </p>
        <button type="button" onClick={reset} disabled={busy} className="font-semibold underline-offset-2 hover:underline disabled:opacity-50">
          {busy ? 'Starting over…' : 'Start the demo over'}
        </button>
        {note && <p className="w-full text-danger">{note}</p>}
      </div>
    </div>
  )
}

export default function Layout() {
  const { pathname } = useLocation()
  const { data: health } = useAsync(api.health)
  const demo = !!health?.demo_mode
  return (
    <DemoContext.Provider value={demo}>
    <div className="min-h-screen md:grid md:grid-cols-[232px_1fr]">
      <aside className="border-b border-rule bg-sheet px-5 py-5 md:sticky md:top-0 md:flex md:h-screen md:flex-col md:border-b-0 md:border-r">
        <div className="flex items-center justify-between gap-3">
          <Logo />
          <Notifications />
        </div>
        <nav className="mt-6 flex gap-1 overflow-x-auto md:mt-10 md:flex-col" aria-label="Main">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) =>
                `whitespace-nowrap rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  isActive ? 'bg-petrol-soft text-petrol' : 'text-slate hover:bg-paper hover:text-ink'
                }`
              }
            >
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto hidden space-y-3 pt-6 md:block">
          <Status />
          <p className="text-xs leading-relaxed text-slate">
            Demo companies are fictional. Not tax advice.
          </p>
        </div>
      </aside>
      <div className="min-w-0">
      {demo && <DemoBanner />}
      <main className="mx-auto w-full max-w-5xl px-5 py-8 md:px-10 md:py-12">
        <ErrorBoundary key={pathname}>
          <Outlet />
        </ErrorBoundary>
      </main>
      </div>
    </div>
    </DemoContext.Provider>
  )
}
