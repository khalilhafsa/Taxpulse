import type { ReactNode } from 'react'

export function PageHeader({ title, intro, action }: { title: string; intro?: ReactNode; action?: ReactNode }) {
  return (
    <header className="mb-8 flex flex-wrap items-end justify-between gap-4 border-b border-rule pb-6">
      <div className="max-w-2xl">
        <h1 className="font-serif text-3xl font-semibold tracking-tight text-ink">{title}</h1>
        {intro && <div className="mt-2 text-[15px] leading-relaxed text-slate">{intro}</div>}
      </div>
      {action}
    </header>
  )
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-rule bg-sheet px-6 py-12 text-center">
      <p className="font-serif text-lg font-semibold text-ink">{title}</p>
      {children && <div className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-slate">{children}</div>}
    </div>
  )
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <div role="alert" className="rounded-md border border-danger/30 bg-danger/5 px-4 py-3 text-sm leading-relaxed text-danger">
      {message}
    </div>
  )
}

export function Button({ children, onClick, disabled, variant = 'primary', type = 'button', title }: {
  children: ReactNode
  onClick?: () => void
  disabled?: boolean
  variant?: 'primary' | 'quiet'
  type?: 'button' | 'submit'
  title?: string
}) {
  const styles = variant === 'primary'
    ? 'bg-petrol text-white hover:bg-petrol/90'
    : 'border border-rule bg-sheet text-ink hover:border-slate/40'
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={`rounded-md px-4 py-2 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${styles}`}
    >
      {children}
    </button>
  )
}

const KIND_LABEL: Record<string, string> = {
  bmf_letter: 'BMF letter', bfh_ruling: 'BFH ruling', law: 'Law', press_release: 'Press release', other: 'Tax news',
}

export function KindTag({ kind }: { kind: string }) {
  return (
    <span className="inline-block rounded bg-petrol-soft px-2 py-0.5 text-xs font-semibold text-petrol">
      {KIND_LABEL[kind] ?? kind}
    </span>
  )
}

export function DemoTag() {
  return (
    <span className="inline-block rounded border border-rule px-2 py-0.5 text-xs text-slate" title="Fictional demo data">
      Demo
    </span>
  )
}

export function SectionTitle({ children, id }: { children: ReactNode; id?: string }) {
  return <h2 id={id} className="mb-3 font-serif text-xl font-semibold">{children}</h2>
}

export const formatDate = (d: string | null) =>
  d ? new Date(d).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : 'Date unknown'

const SOURCE_LABEL: Record<string, string> = { bmf_feed: 'BMF feed', bfh_feed: 'BFH feed', manual: 'Added by hand' }

export function SourceTag({ source }: { source: string }) {
  if (source === 'demo') return <DemoTag />
  return <span className="text-xs text-slate">{SOURCE_LABEL[source] ?? source}</span>
}
