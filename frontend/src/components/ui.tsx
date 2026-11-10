import type { ReactNode } from 'react'

export function PageHeader({ title, intro, action }: { title: string; intro?: ReactNode; action?: ReactNode }) {
  return (
    <header className="mb-8 flex flex-wrap items-end justify-between gap-x-10 gap-y-5">
      <div className="max-w-2xl">
        <h1 className="tp-chrome-text pb-1 font-serif text-[36px] font-bold leading-[1.05] tracking-[-0.04em] md:text-[46px]">{title}</h1>
        {intro && <div className="mt-3 text-[15px] leading-relaxed text-slate">{intro}</div>}
      </div>
      {action}
    </header>
  )
}

/** The standard surface: a white card with a hairline border. */
export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`tp-chrome rounded-xl border border-rule bg-sheet shadow-sm ${className}`}>{children}</div>
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-slate/35 bg-sheet px-6 py-14 text-center">
      <p className="font-serif text-xl font-bold tracking-[-0.02em] text-ink">{title}</p>
      {children && <div className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-slate">{children}</div>}
    </div>
  )
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <div role="alert" className="rounded-md border border-danger/25 bg-danger/5 px-4 py-3 text-sm leading-relaxed text-danger">
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
    ? 'tp-btn-primary hover:brightness-125'
    : 'tp-btn-quiet hover:brightness-[1.02]'
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={`inline-flex min-h-10 items-center justify-center gap-2 rounded-md px-4 py-2 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-45 ${styles}`}
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
    <span className="inline-flex items-center gap-1.5 rounded-full bg-brand-soft px-2.5 py-0.5 text-xs font-semibold text-brand-deep">
      <span className="h-1.5 w-1.5 rounded-full bg-brand" aria-hidden />
      {KIND_LABEL[kind] ?? kind}
    </span>
  )
}

export function DemoTag() {
  return (
    <span className="inline-block rounded-full border border-dashed border-heat/50 px-2 py-0.5 text-[11px] font-semibold text-heat" title="Fictional demo data">
      Demo
    </span>
  )
}

export function SectionTitle({ children, id }: { children: ReactNode; id?: string }) {
  return (
    <h2 id={id} className="mb-4 flex items-baseline gap-3 font-serif text-[21px] font-bold tracking-[-0.025em]">
      {children}
    </h2>
  )
}

export const formatDate = (d: string | null) =>
  d ? new Date(d).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : 'Date unknown'

const SOURCE_LABEL: Record<string, string> = { bmf_feed: 'BMF feed', bfh_feed: 'BFH feed', manual: 'Added by hand' }

export function SourceTag({ source }: { source: string }) {
  if (source === 'demo') return <DemoTag />
  return <span className="text-xs text-slate">{SOURCE_LABEL[source] ?? source}</span>
}
