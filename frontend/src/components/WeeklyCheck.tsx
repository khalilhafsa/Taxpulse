import { useEffect, useState } from 'react'
import { api, formatDateTime, type AutomationSettings } from '../api'
import SendButtonSetup from './SendButton'
import { Button, ErrorNote } from './ui'

const hourLabel = (h: number) => `${String(h).padStart(2, '0')}:00`
const STATUS: Record<string, string> = { done: 'went well', action: 'is waiting for your BMF click', problems: 'needs your attention', failed: 'failed' }

/** Settings for the weekly check, with a button to run it now. */
export default function WeeklyCheck() {
  const [a, setA] = useState<AutomationSettings | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const [perm, setPerm] = useState<string>(() => ('Notification' in window ? Notification.permission : 'unsupported'))

  const load = () => api.automation().then(setA).catch((e: Error) => setError(e.message))
  useEffect(() => { load() }, [])
  useEffect(() => {
    if (!a?.running) return
    const t = setInterval(load, 3000)
    return () => clearInterval(t)
  }, [a?.running])

  if (!a) return error ? <ErrorNote message={error} /> : null

  const save = async (next: Partial<AutomationSettings>) => {
    setError(null)
    const merged = { ...a, ...next }
    setA(merged)
    try {
      setA(await api.saveAutomation({ enabled: merged.enabled, weekday: merged.weekday, hour: merged.hour, fetch_bmf: merged.fetch_bmf, fetch_bfh: merged.fetch_bfh }))
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const runNow = async () => {
    setError(null)
    try {
      await api.runWeeklyCheck()
      load()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const allow = async () => {
    if (!('Notification' in window)) return
    setPerm(await Notification.requestPermission())
  }

  const select = 'mt-1.5 rounded-md border border-rule bg-sheet px-3 shadow-sm py-2 text-[15px] focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/15 disabled:opacity-50'

  return (
    <>
    <section aria-labelledby="weekly" className="max-w-xl border-t border-rule pt-8">
      <h2 id="weekly" className="font-serif text-lg font-semibold">Weekly check</h2>
      <p className="mt-1 text-sm leading-relaxed text-slate">
        Once a week, TaxPulse fetches new publications, runs the agents and tells you under the bell what is new.
        It never contacts a client. TaxPulse must be running at that time; if your computer was off, the check runs as
        soon as you start TaxPulse again.
      </p>

      <label className="mt-5 flex items-center gap-3">
        <input type="checkbox" checked={a.enabled} onChange={(e) => save({ enabled: e.target.checked })}
          className="h-5 w-5 accent-[var(--color-brand)]" />
        <span className="text-[15px] font-medium">Run the weekly check</span>
        {saved && <span className="text-sm text-brand" role="status">Saved</span>}
      </label>

      <div className="mt-4 flex flex-wrap gap-4">
        <label className="block">
          <span className="text-sm font-medium">Day</span>
          <select value={a.weekday} disabled={!a.enabled} onChange={(e) => save({ weekday: Number(e.target.value) })} className={`${select} block`}>
            {a.days.map((d, i) => <option key={d} value={i}>{d}</option>)}
          </select>
        </label>
        <label className="block">
          <span className="text-sm font-medium">Time</span>
          <select value={a.hour} disabled={!a.enabled} onChange={(e) => save({ hour: Number(e.target.value) })} className={`${select} block`}>
            {Array.from({ length: 24 }, (_, h) => <option key={h} value={h}>{hourLabel(h)}</option>)}
          </select>
        </label>
      </div>
      <fieldset className="mt-4 space-y-3">
        <legend className="text-sm font-medium">Sources</legend>
        <label className="flex items-start gap-3">
          <input type="checkbox" checked={a.fetch_bfh} disabled={!a.enabled} onChange={(e) => save({ fetch_bfh: e.target.checked })}
            className="mt-0.5 h-4 w-4 accent-[var(--color-brand)]" />
          <span className="text-sm">
            Federal Fiscal Court (BFH): new decisions and press releases
            <span className="block text-xs text-slate">Fully automatic.</span>
          </span>
        </label>
        <label className="flex items-start gap-3">
          <input type="checkbox" checked={a.fetch_bmf} disabled={!a.enabled} onChange={(e) => save({ fetch_bmf: e.target.checked })}
            className="mt-0.5 h-4 w-4 accent-[var(--color-brand)]" />
          <span className="text-sm">
            Federal Ministry of Finance (BMF): letters, laws and tax news
            <span className="block text-xs text-slate">The BMF website usually asks for a security check. You then get a notification and send the feed with one click (see below).</span>
          </span>
        </label>
      </fieldset>

      <div className="mt-5 space-y-1 text-sm text-slate">
        {a.enabled && a.next_run_at && (
          <p>Next check: <span className="text-ink">{a.days[a.weekday]} {new Date(a.next_run_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })} at {hourLabel(a.hour)}</span></p>
        )}
        {a.last_run_at && a.last_status && (
          <p>
            Last check {formatDateTime(a.last_run_at)} {STATUS[a.last_status] ?? ''}
            {a.last_trigger === 'catch_up' && ' (caught up after the computer was off)'}: {a.last_summary}.
          </p>
        )}
      </div>

      {error && <div className="mt-4"><ErrorNote message={error} /></div>}
      <div className="mt-5 flex flex-wrap items-center gap-3">
        <Button variant="quiet" onClick={runNow} disabled={a.running}>
          {a.running ? 'Checking now…' : 'Run the check now'}
        </Button>
        {perm === 'default' && <Button variant="quiet" onClick={allow}>Show desktop notifications</Button>}
        {perm === 'granted' && <span className="text-sm text-slate">Desktop notifications are on.</span>}
        {perm === 'denied' && <span className="text-sm text-slate">Desktop notifications are blocked in this browser's site settings.</span>}
      </div>
    </section>
    <div id="send-button" className="mt-10 scroll-mt-6"><SendButtonSetup feedUrl={a.bmf_feed_url} /></div>
    </>
  )
}
