import { useDemo } from '../demo'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, formatDateTime, type EmailDraft, type OutreachEntry } from '../api'
import { Button, EmptyState, ErrorNote, PageHeader } from '../components/ui'
import { useAsync } from '../useAsync'

const STATUS: Record<EmailDraft['status'], { label: string; className: string }> = {
  draft: { label: 'Draft, needs your review', className: 'border-heat/40 bg-heat-soft text-heat' },
  approved: { label: 'Approved, ready to send', className: 'border-brand/30 bg-brand-soft text-brand' },
  sent: { label: 'Marked as sent', className: 'border-rule bg-paper text-slate' },
}

const MAX_WORDS = 250 // same limit and same counting as the partner review (writer.email_core)

function countWords(body: string): number {
  let text = body.split('\n\nKind regards,\n\n')[0].trim()
  const nl = text.indexOf('\n')
  if (nl > 0 && text.slice(0, nl).trim().toLowerCase().startsWith('dear')) text = text.slice(nl + 1)
  return text.trim().split(/\s+/).filter(Boolean).length
}

function DraftEditor({ d, to, onChange, canRevise = false }: {
  d: EmailDraft; to: string; onChange: () => void; canRevise?: boolean
}) {
  const [remarks, setRemarks] = useState('')
  const [subject, setSubject] = useState(d.subject)
  const [body, setBody] = useState(d.body)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  useEffect(() => {
    setSubject(d.subject)
    setBody(d.body)
  }, [d.subject, d.body])

  const dirty = subject !== d.subject || body !== d.body
  const locked = d.status === 'sent'
  const words = countWords(body)
  const placeholders = /\[Your name\]|\[Firm name\]/.test(body)
  const notes = d.review_notes ? d.review_notes.split('\n').filter(Boolean) : []

  const act = async (fn: () => Promise<unknown>) => {
    setError(null)
    try {
      await fn()
      onChange()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(`Subject: ${subject}\n\n${body}`)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      setError('Copying is blocked by the browser. Select the text and copy it by hand.')
    }
  }

  const field = 'w-full rounded-md border border-rule bg-sheet px-3 shadow-sm py-2 text-[15px] focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/15 disabled:bg-paper'

  return (
    <div className="tp-chrome rounded-xl border border-rule bg-sheet shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-rule bg-paper px-5 py-2.5 text-sm">
        <span className={`rounded-full border px-2.5 py-0.5 text-xs font-semibold ${STATUS[d.status].className}`}>
          {STATUS[d.status].label}
        </span>
        <span className="text-xs text-slate">
          Written {formatDateTime(d.created_at)}{d.edited_by_user && ', edited by you'}
        </span>
      </div>
      <div className="px-5 pb-5 pt-4">
      <p className="grid grid-cols-[4.5rem_1fr] items-baseline border-b border-rule pb-2.5 text-sm">
        <span className="tp-eyebrow">To</span><span>{to}</span>
      </p>
      {d.remarks && (
        <p className="mt-3 rounded-md border border-brand/20 bg-paper px-3 py-2 text-sm text-slate">
          Rewritten from your remarks: <span className="text-ink">“{d.remarks}”</span>
        </p>
      )}
      <label className="mt-3 grid items-center gap-1 sm:grid-cols-[4.5rem_1fr]">
        <span className="tp-eyebrow">Subject</span>
        <input value={subject} onChange={(e) => setSubject(e.target.value)} disabled={locked} className={`${field} font-medium`} />
      </label>
      <label className="mt-4 block">
        <span className="tp-eyebrow">Email</span>
        <textarea value={body} onChange={(e) => setBody(e.target.value)} disabled={locked} rows={14}
          className={`${field} mt-1.5 px-4 py-3 text-[15.5px] leading-[1.7]`} />
      </label>
      <p className={`mt-1 text-xs ${words > MAX_WORDS ? 'text-danger' : 'text-slate'}`}>
        {words} words without greeting and signature{words > MAX_WORDS && ` (partner review limit: ${MAX_WORDS})`}{placeholders && ' · add your firm details in Settings, or replace [Your name] and [Firm name]'}
      </p>

      {notes.length > 0 ? (
        <div className="mt-3 rounded-md border border-heat/20 bg-heat-soft px-4 py-3 text-sm">
          <p className="font-medium">Partner review: {notes.length} {notes.length === 1 ? 'point' : 'points'} to check before approving</p>
          <ul className="mt-1.5 list-disc space-y-1 pl-5 text-ink/80">{notes.map((n) => <li key={n}>{n}</li>)}</ul>
        </div>
      ) : (
        <p className="mt-1 text-xs text-brand">
          Partner review passed: advisor's voice, cautious wording, caveat included{d.revised && ' (first draft revised once)'}.
        </p>
      )}

      {error && <div className="mt-3"><ErrorNote message={error} /></div>}

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {!locked && dirty && <Button onClick={() => act(() => api.editDraft(d.id, subject, body))}>Save changes</Button>}
        {d.status === 'draft' && !dirty && (
          <Button onClick={() => act(() => api.setDraftStatus(d.id, 'approved'))} disabled={placeholders}
            title={placeholders ? 'Replace [Your name] and [Firm name] first' : undefined}>
            Approve
          </Button>
        )}
        {d.status === 'approved' && (
          <>
            <a href={`mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`}
              className="tp-btn-primary inline-flex min-h-10 items-center rounded-md px-4 py-2 text-sm font-semibold">
              Open in my email app
            </a>
            <Button variant="quiet" onClick={() => act(() => api.setDraftStatus(d.id, 'sent'))}>Mark as sent</Button>
          </>
        )}
        <Button variant="quiet" onClick={copy}>{copied ? 'Copied' : 'Copy'}</Button>
        {!locked && (
          <Button variant="quiet" onClick={() => window.confirm('Delete this draft?') && act(() => api.deleteDraft(d.id))}>
            Delete draft
          </Button>
        )}
      </div>

      {canRevise && !locked && (
        <div className="mt-6 rounded-lg border border-brand/20 bg-brand-soft/50 px-4 py-4">
          <label className="block">
            <span className="text-sm font-semibold">Your remarks for the Outreach Writer</span>
            <span className="mt-0.5 block text-xs text-slate">
              Write what to change, like you would to a colleague. A new version is written; this one is kept below.
            </span>
            <textarea value={remarks} onChange={(e) => setRemarks(e.target.value)} rows={3} maxLength={2000}
              placeholder="e.g. Make it shorter. Mention that we already met at the 2024 closing. Propose a call on Thursday or Friday."
              className={`${field} mt-2 font-[inherit]`} />
          </label>
          <div className="mt-2">
            <Button disabled={remarks.trim().length < 3 || dirty}
              title={dirty ? 'Save or undo your text changes first' : undefined}
              onClick={() => act(async () => { await api.reviseDraft(d.id, remarks); setRemarks('') })}>
              Rewrite with my remarks
            </Button>
          </div>
        </div>
      )}
      </div>
    </div>
  )
}

function ClientBlock({ e, onChange }: { e: OutreachEntry; onChange: () => void }) {
  const demo = useDemo()
  const [error, setError] = useState<string | null>(null)
  const latest = e.drafts[0]
  const to = e.client.contact_name
    ? `${e.client.contact_name}${e.client.contact_title ? `, ${e.client.contact_title}` : ''} · ${e.client.name}`
    : `${e.client.name} (no contact set: add one on the client page)`
  const withMemo = e.alerts.filter((a) => a.has_memo).length
  const waiting = e.alerts.length - withMemo

  const write = async () => {
    setError(null)
    try {
      await api.draftEmail(e.client.id)
      onChange()
    } catch (err) {
      setError((err as Error).message)
    }
  }

  return (
    <section className="tp-chrome rounded-2xl border border-rule bg-sheet p-5 shadow-sm md:p-7" aria-labelledby={`c${e.client.id}`}>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id={`c${e.client.id}`} className="tp-chrome-text inline-block pb-0.5 font-serif text-[32px] font-bold leading-tight tracking-[-0.03em]">
            <Link to={`/clients/${e.client.id}`} className="hover:text-brand hover:underline">{e.client.name}</Link>
          </h2>
          <p className="text-sm text-slate">{e.client.mandate}</p>
        </div>
        <Button onClick={write} disabled={e.writer_running || waiting > 0}
          title={waiting > 0 ? 'Every accepted alert needs its memo first, so the email covers all of them' : undefined}>
          {e.writer_running ? 'Writing the email…' : latest ? 'Write a new version' : 'Draft email'}
        </Button>
      </div>

      <ul className="mt-4 divide-y divide-rule border-y border-rule text-sm">
        {e.alerts.map((a) => (
          <li key={a.id} className="flex items-baseline gap-3 py-2">
            <span className="w-9 shrink-0 font-mono text-[13px] font-medium text-heat">{a.score}</span>
            <span>
              <span className="font-medium">{a.title}</span>
              {a.headline ? <span className="text-slate"> · {a.headline}</span>
                : <span className="text-slate"> · memo not written yet</span>}
            </span>
          </li>
        ))}
      </ul>
      {waiting > 0 && (
        <p className="mt-2 text-sm text-slate" aria-live="polite">
          Waiting for {waiting} {waiting === 1 ? 'memo' : 'memos'} so the email covers every accepted alert. If a memo failed, write it again on the Alerts page.
        </p>
      )}
      {latest && e.alerts_not_in_draft > 0 && (
        <p className="mt-2 text-sm text-heat">
          {e.alerts_not_in_draft} accepted {e.alerts_not_in_draft === 1 ? 'topic is' : 'topics are'} not in the latest draft. Write a new version to include {e.alerts_not_in_draft === 1 ? 'it' : 'them'}.
        </p>
      )}

      {error && <div className="mt-3"><ErrorNote message={error} /></div>}
      {e.writer_error && !e.writer_running && <div className="mt-3"><ErrorNote message={e.writer_error} /></div>}
      {e.writer_running && (
        <p className="mt-4 rounded-md border border-brand/20 bg-brand-soft px-4 py-3 text-sm text-brand" aria-live="polite">
          The Outreach Writer is writing a new version. It is checked by the partner review before it appears here…
        </p>
      )}

      {latest && !e.writer_running && <div className="mt-5"><DraftEditor d={latest} to={to} onChange={onChange} canRevise={!demo} /></div>}
      {e.drafts.length > 1 && (
        <details className="mt-3 text-sm">
          <summary className="cursor-pointer text-slate">{e.drafts.length - 1} earlier {e.drafts.length === 2 ? 'version' : 'versions'}</summary>
          <div className="mt-3 space-y-3">{e.drafts.slice(1).map((d) => <DraftEditor key={d.id} d={d} to={to} onChange={onChange} />)}</div>
        </details>
      )}
    </section>
  )
}

export default function Outreach() {
  const { data, error, reload } = useAsync(api.outreach)
  const running = data?.some((e) => e.writer_running || e.alerts.some((a) => !a.has_memo))
  useEffect(() => {
    if (!running) return
    const t = setInterval(reload, 3000)
    return () => clearInterval(t)
  }, [running, reload])

  return (
    <>
      <PageHeader
        title="Outreach"
        intro="One email per former client, combining every alert you accepted. TaxPulse never sends anything: review, approve and send it from your own email app."
      />
      {error && <ErrorNote message={error} />}
      {data && data.length === 0 && (
        <EmptyState title="No accepted alerts yet">
          Accept an alert on the <Link to="/alerts" className="font-medium text-brand hover:underline">Alerts</Link> page. Its impact memo is written automatically, then you can draft the email here.
        </EmptyState>
      )}
      <div className="space-y-10">
        {data?.map((e) => <ClientBlock key={e.client.id} e={e} onChange={reload} />)}
      </div>
    </>
  )
}
