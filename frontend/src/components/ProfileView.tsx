import { shortDocName, type Citation, type Fact, type Profile, type TaxArea } from '../api'
import { SectionTitle } from './ui'

type OnCite = (c: Citation) => void

function CitationChip({ citation, onCite }: { citation: Citation; onCite: OnCite }) {
  const base = 'inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[11.5px] font-medium transition-colors'
  const style = citation.verified
    ? 'border-rule bg-paper text-slate hover:border-petrol/30 hover:bg-petrol-soft hover:text-petrol'
    : 'border-dashed border-danger/50 bg-danger/5 text-danger hover:bg-danger/10'
  return (
    <button
      type="button"
      onClick={() => onCite(citation)}
      className={`${base} ${style}`}
      title={citation.verified ? `“${citation.quote}”` : 'Quote not found on this page. Check the source.'}
    >
      {shortDocName(citation.document)}, p.&nbsp;{citation.page}
      {!citation.verified && <span aria-label="not verified">?</span>}
    </button>
  )
}

function Citations({ items, onCite }: { items: Citation[]; onCite: OnCite }) {
  return (
    <span className="ml-1.5 inline-flex flex-wrap gap-1 align-middle">
      {items.map((c, i) => <CitationChip key={i} citation={c} onCite={onCite} />)}
    </span>
  )
}

function FactLine({ fact, onCite }: { fact: Fact; onCite: OnCite }) {
  return (
    <p className="text-[14.5px] leading-relaxed">
      {fact.value}
      <Citations items={fact.citations} onCite={onCite} />
    </p>
  )
}

const ASSESSMENT = {
  risk: { label: 'Risk', className: 'text-danger' },
  opportunity: { label: 'Opportunity', className: 'text-petrol' },
  neutral: { label: 'Neutral', className: 'text-slate' },
}
const SEVERITY_ORDER = { high: 0, medium: 1, low: 2 }

function TaxAreaItem({ area, onCite }: { area: TaxArea; onCite: OnCite }) {
  const a = ASSESSMENT[area.assessment]
  return (
    <li className="grid gap-x-6 gap-y-2 py-5 md:grid-cols-[160px_1fr]">
      <div className="text-sm">
        <p className="font-medium text-ink">{area.category}</p>
        <p className={`mt-0.5 ${a.className}`}>
          {a.label}{area.assessment !== 'neutral' && <span className="text-slate">, {area.severity}</span>}
        </p>
      </div>
      <div>
        <p className="font-semibold leading-snug">{area.title}</p>
        <p className="mt-1 text-sm leading-relaxed text-slate">{area.summary}</p>
        <ul className="mt-3 space-y-2">
          {area.facts.map((f, i) => (
            <li key={i}>
              <span className="text-sm text-slate">{f.label}: </span>
              <FactLine fact={f} onCite={onCite} />
            </li>
          ))}
        </ul>
      </div>
    </li>
  )
}

export default function ProfileView({ profile, onCite }: { profile: Profile; onCite: OnCite }) {
  const d = profile.data
  const areas = [...d.tax_areas].sort((x, y) =>
    (x.assessment === 'neutral' ? 1 : 0) - (y.assessment === 'neutral' ? 1 : 0) ||
    SEVERITY_ORDER[x.severity] - SEVERITY_ORDER[y.severity])

  return (
    <div className="space-y-10">
      <p className="font-serif text-[19px] leading-relaxed text-ink">{d.summary}</p>

      <section aria-labelledby="facts">
        <SectionTitle id="facts">Key facts</SectionTitle>
        <dl className="divide-y divide-rule rounded-lg border border-rule bg-sheet">
          {d.key_facts.map((f, i) => (
            <div key={i} className="grid gap-1 px-5 py-3 sm:grid-cols-[150px_1fr] sm:gap-6">
              <dt className="text-sm text-slate">{f.label}</dt>
              <dd><FactLine fact={f} onCite={onCite} /></dd>
            </div>
          ))}
        </dl>
      </section>

      <section aria-labelledby="areas">
        <SectionTitle id="areas">Tax exposure</SectionTitle>
        <ul className="divide-y divide-rule rounded-lg border border-rule bg-sheet px-5">
          {areas.map((a, i) => <TaxAreaItem key={i} area={a} onCite={onCite} />)}
        </ul>
      </section>

      <section aria-labelledby="open">
        <SectionTitle id="open">Open points from the due diligence</SectionTitle>
        <ul className="space-y-2">
          {d.open_points.map((f, i) => (
            <li key={i} className="flex gap-3">
              <span className="mt-2.5 h-1.5 w-1.5 shrink-0 rounded-full bg-slate/50" />
              <FactLine fact={f} onCite={onCite} />
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="keywords">
        <SectionTitle id="keywords">Matching keywords</SectionTitle>
        <p className="mb-3 text-sm text-slate">Used later to pre-select the clients a new tax update might concern.</p>
        <ul className="flex flex-wrap gap-1.5">
          {d.keywords.map((k) => (
            <li key={k} className="rounded-full border border-rule bg-sheet px-3 py-1 text-sm">{k}</li>
          ))}
        </ul>
      </section>
    </div>
  )
}
