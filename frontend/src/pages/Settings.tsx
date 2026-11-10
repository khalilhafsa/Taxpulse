import { useDemo } from '../demo'
import { useEffect, useState, type FormEvent } from 'react'
import { api, type Firm } from '../api'
import { Button, ErrorNote, PageHeader } from '../components/ui'
import WeeklyCheck from '../components/WeeklyCheck'
import { useAsync } from '../useAsync'

type TextKey = Exclude<keyof Firm, 'monthly_budget_usd' | 'spent_this_month_usd'>

const FIELDS: { key: TextKey; label: string; placeholder: string }[] = [
  { key: 'advisor_name', label: 'Your name', placeholder: 'Dr Lena Weber' },
  { key: 'advisor_title', label: 'Your title', placeholder: 'Partner, Tax Advisor (Steuerberaterin)' },
  { key: 'firm_name', label: 'Firm name', placeholder: 'Weber & Partner Steuerberatung' },
  { key: 'address', label: 'Address', placeholder: 'Street, postcode, city' },
  { key: 'phone', label: 'Phone', placeholder: '+49 30 …' },
  { key: 'email', label: 'Email', placeholder: 'name@firm.de' },
  { key: 'website', label: 'Website', placeholder: 'www.firm.de' },
]

export default function Settings() {
  const demo = useDemo()
  const { data, error } = useAsync(api.firm)
  const [firm, setFirm] = useState<Firm | null>(null)
  const [saved, setSaved] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  useEffect(() => { if (data) setFirm(data) }, [data])

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!firm) return
    setSaveError(null)
    try {
      setFirm(await api.saveFirm(firm))
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    } catch (err) {
      setSaveError((err as Error).message)
    }
  }

  const signature = firm
    ? [firm.advisor_name, firm.advisor_title, firm.firm_name, firm.address,
       [firm.phone, firm.email].filter(Boolean).join(' | '), firm.website].filter(Boolean).join('\n')
    : ''
  const field = 'mt-1.5 w-full rounded-md border border-rule bg-sheet px-3 shadow-sm py-2 text-[15px] focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/15'

  return (
    <>
      <PageHeader title="Settings" intro="Your firm details for email signatures, your AI budget and the weekly check." />
      {error && <ErrorNote message={error} />}
      {firm && (
        <div className="grid gap-10 lg:grid-cols-[1fr_320px]">
          <form onSubmit={submit} className="max-w-xl space-y-5">
            {FIELDS.map((f) => (
              <label key={f.key} className="block">
                <span className="text-sm font-medium">{f.label}</span>
                <input value={firm[f.key]} placeholder={f.placeholder} className={field}
                  onChange={(e) => setFirm({ ...firm, [f.key]: e.target.value })} />
              </label>
            ))}
            <fieldset className="border-t border-rule pt-6">
              <legend className="font-serif text-lg font-semibold">AI budget</legend>
              <label className="mt-2 block">
                <span className="text-sm font-medium">Monthly limit in US dollars</span>
                <span className="mt-0.5 block text-xs text-slate">
                  Agents stop before calling Claude once this month's spending reaches the limit. Leave 0 for no limit.
                </span>
                <input type="number" min={0} max={10000} step={0.5} value={firm.monthly_budget_usd}
                  onChange={(e) => setFirm({ ...firm, monthly_budget_usd: Math.max(0, Number(e.target.value) || 0) })}
                  className={`${field} max-w-40 tabular-nums`} />
              </label>
              {firm.spent_this_month_usd !== undefined && (
                <p className="mt-2 text-sm text-slate">Spent this month: ${firm.spent_this_month_usd.toFixed(2)}</p>
              )}
            </fieldset>
            {saveError && <ErrorNote message={saveError} />}
            <div className="flex items-center gap-3">
              <Button type="submit" disabled={demo} title={demo ? 'Switched off in the public demo' : undefined}>Save settings</Button>
              {saved && <span className="text-sm text-ok" role="status">Saved</span>}
            </div>
          </form>
          <aside>
            <p className="text-sm font-medium">Signature preview</p>
            <pre className="mt-2 whitespace-pre-wrap tp-chrome rounded-xl border border-rule bg-sheet shadow-sm px-4 py-4 font-sans text-sm leading-relaxed">
              {'Kind regards,\n\n' + (signature || '[Your name]\n[Firm name]')}
            </pre>
            <p className="mt-2 text-xs text-slate">New drafts use these details. Existing drafts keep their text.</p>
          </aside>
        </div>
      )}
      {demo
        ? <p className="mt-10 max-w-xl border-t border-rule pt-8 text-sm text-slate">The weekly check and the “Send to TaxPulse” button run on the advisor's own computer, so they are not part of the public demo.</p>
        : <div className="mt-10"><WeeklyCheck /></div>}
    </>
  )
}
