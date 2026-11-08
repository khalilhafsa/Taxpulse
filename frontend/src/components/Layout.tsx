import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { api } from '../api'
import { useAsync } from '../useAsync'
import { useEffect, useState } from 'react'
import { DemoContext } from '../demo'
import ErrorBoundary from './ErrorBoundary'
import Notifications from './Notifications'

const NAV = [
  { to: '/', label: 'Overview', end: true, group: 'This week' },
  { to: '/alerts', label: 'Alerts', group: 'This week' },
  { to: '/outreach', label: 'Outreach', group: 'This week' },
  { to: '/matrix', label: 'Matrix', group: 'This week' },
  { to: '/clients', label: 'Clients', group: 'Records' },
  { to: '/updates', label: 'Tax updates', group: 'Records' },
  { to: '/runs', label: 'Agent runs', group: 'System' },
  { to: '/quality', label: 'Quality', group: 'System' },
  { to: '/settings', label: 'Settings', group: 'System' },
]
const GROUPS = ['This week', 'Records', 'System']

function Logo() {
  return (
    <NavLink to="/" className="flex items-center gap-3" aria-label="TaxPulse, overview">
      <svg viewBox="0 0 32 32" className="h-9 w-9 shrink-0" aria-hidden>
        <rect width="32" height="32" rx="3" fill="#0B5560" />
        <path d="M5 17h6l3-7 4 13 3-6h6" fill="none" stroke="#fffefa" strokeWidth="2.4"
          strokeLinecap="square" strokeLinejoin="miter" />
      </svg>
      <span className="leading-none">
        <span className="block font-serif text-[22px] font-semibold tracking-tight">TaxPulse</span>
        <span className="tp-eyebrow mt-1 block whitespace-nowrap text-[10px]">Mandate monitor</span>
      </span>
    </NavLink>
  )
}

/** ISO calendar week, the way German offices count weeks. */
function isoWeek(d: Date) {
  const t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()))
  t.setUTCDate(t.getUTCDate() + 4 - (t.getUTCDay() || 7))
  const start = new Date(Date.UTC(t.getUTCFullYear(), 0, 1))
  return Math.ceil(((t.getTime() - start.getTime()) / 86400000 + 1) / 7)
}

function Masthead({ pathname }: { pathname: string }) {
  const now = new Date()
  const first = '/' + (pathname.split('/')[1] ?? '')
  const section = NAV.find((n) => n.to === first)
  return (
    <div className="border-b border-rule px-5 md:px-10">
      <div className="mx-auto flex h-11 max-w-6xl items-center justify-between gap-4">
        <p className="tp-eyebrow truncate">
          {section
            ? <>{section.group}<span aria-hidden className="mx-2 opacity-50">/</span><span className="text-ink">{section.label}</span></>
            : 'TaxPulse'}
        </p>
        <p className="tp-eyebrow hidden shrink-0 sm:block">
          Week {isoWeek(now)}<span aria-hidden className="mx-2 opacity-50">·</span>
          {now.toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
        </p>
      </div>
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
    <p className="flex items-center gap-2 text-xs text-slate" role="status">
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
    <div className="bg-ink px-5 py-2.5 text-sm text-paper md:px-10">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-x-6 gap-y-1.5">
        <p className="flex items-baseline gap-3">
          <span className="shrink-0 rounded-sm border border-paper/40 px-1.5 py-px font-mono text-[10px] font-medium uppercase tracking-[0.12em]">
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
              className="font-semibold underline decoration-paper/40 underline-offset-4 hover:decoration-paper disabled:opacity-50">
              {busy ? 'Starting over…' : 'Start the demo over'}
            </button>}
        {note && <p className="w-full text-[#f4b9b3]">{note}</p>}
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
    <div className="min-h-screen md:grid md:grid-cols-[248px_1fr]">
      <aside className="border-b border-rule bg-paper-deep px-5 py-4 md:sticky md:top-0 md:flex md:h-screen md:flex-col md:border-b-0 md:border-r md:px-5 md:py-7">
        <div className="flex items-center justify-between gap-3">
          <Logo />
          <Notifications />
        </div>
        <nav className="-mx-1 mt-4 flex gap-1 overflow-x-auto px-1 pb-1 [scrollbar-width:none] md:mx-0 md:mt-10 md:flex-col md:gap-6 md:overflow-visible md:px-0 md:pb-0" aria-label="Main">
          {GROUPS.map((g) => (
            <div key={g} className="shrink-0">
              <p className="tp-eyebrow mb-2 hidden px-3 text-[10px] md:block">{g}</p>
              <ul className="flex gap-1 md:block md:space-y-px">
                {NAV.filter((n) => n.group === g).map((n) => (
                  <li key={n.to}>
                    <NavLink
                      to={n.to}
                      end={n.end}
                      className={({ isActive }) =>
                        `relative flex min-h-9 items-center whitespace-nowrap rounded-sm px-3 text-[14px] font-medium ${
                          isActive
                            ? 'bg-sheet text-ink shadow-[inset_0_0_0_1px_var(--color-rule)] before:absolute before:inset-y-2 before:left-0 before:w-[3px] before:bg-petrol'
                            : 'text-slate hover:bg-sheet/70 hover:text-ink'
                        }`
                      }
                    >
                      {n.label}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>
        <div className="mt-auto hidden space-y-3 border-t border-rule pt-5 md:block">
          <Status />
          <p className="text-xs leading-relaxed text-slate">
            Demo companies are fictional. Not tax advice.
          </p>
        </div>
      </aside>
      <div className="min-w-0">
        {demo && <DemoBanner />}
        <Masthead pathname={pathname} />
        <main className="mx-auto w-full max-w-6xl px-5 py-8 md:px-10 md:py-10">
          <ErrorBoundary key={pathname}>
            <Outlet />
          </ErrorBoundary>
        </main>
      </div>
    </div>
    </DemoContext.Provider>
  )
}
