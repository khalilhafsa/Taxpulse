import { EmptyState, PageHeader } from '../components/ui'

const PAGES = {
  alerts: {
    title: 'Alerts',
    intro: 'Former clients affected by a new tax update, ranked by relevance.',
    empty: 'No alerts yet',
    body: 'Alerts appear here after the first portfolio scan.',
  },
}

export default function Placeholder({ page }: { page: keyof typeof PAGES }) {
  const p = PAGES[page]
  return (
    <>
      <PageHeader title={p.title} intro={p.intro} />
      <EmptyState title={p.empty}>{p.body}</EmptyState>
    </>
  )
}
