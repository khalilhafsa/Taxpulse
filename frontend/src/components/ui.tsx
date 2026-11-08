import type { ReactNode } from 'react'

export function PageHeader({ title, intro, action }: { title: string; intro?: ReactNode; action?: ReactNode }) {
  return (
    <header className="mb-10 grid gap-x-12 gap-y-5 border-b-2 border-ink pb-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,26rem)] lg:items-end">
      <h1 className="font-serif text-[44px] font-semibold leading-[0.98] tracking-[-0.03em] text-ink md:text-[64px]">{title}</h1>
      {(intro || action) && (
        <div className="lg:border-l lg:border-ink/15 lg:pl-8">
          {intro && <div className="text-[15px] leading-relaxed text-slate">{intro}</div>}
          {action && <div className={intro ? 'mt-5' : ''}>{action}</div>}
        </div>
      )}
    </header>
  )
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="border border-dashed border-ink/25 bg-sheet px-6 py-14 text-center">
      <p className="font-serif text-xl font-semibold text-ink">{title}</p>
      {children && <div className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-slate">{children}</div>}
    </div>
  )
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <div role="alert" className="border-l-[3px] border-danger bg-danger/5 px-4 py-3 text-sm leading-relaxed text-danger">
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
    ? 'border border-petrol bg-petrol text-white hover:border-petrol-deep hover:bg-petrol-deep'
    : 'border border-ink/20 bg-sheet text-ink hover:border-ink/45 hover:bg-paper'
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={`inline-flex min-h-10 items-center justify-center gap-2 rounded-sm px-4 py-2 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${styles}`}
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
    <span className="inline-block rounded-sm border border-petrol/30 bg-petrol-soft px-1.5 py-px font-mono text-[10.5px] font-medium uppercase tracking-[0.08em] text-petrol">
      {KIND_LABEL[kind] ?? kind}
    </span>
  )
}

export function DemoTag() {
  return (
    <span className="inline-block rounded-sm border border-dashed border-slate/50 px-1.5 py-px font-mono text-[10.5px] uppercase tracking-[0.08em] text-slate" title="Fictional demo data">
      Demo
    </span>
  )
}

export function SectionTitle({ children, id }: { children: ReactNode; id?: string }) {
  return (
    <h2 id={id} className="mb-4 flex items-baseline gap-3 border-t-2 border-ink pt-3 font-serif text-[26px] font-semibold tracking-[-0.015em]">
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
