import { Component, type ReactNode } from 'react'

/** Shows what went wrong instead of a blank page, with a way back. */
export default class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  componentDidCatch(error: Error) {
    console.error('[TaxPulse] page crashed:', error)
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <div role="alert" className="rounded-lg border border-danger/30 bg-sheet px-6 py-6">
        <p className="font-serif text-lg font-semibold">This page could not be displayed</p>
        <p className="mt-2 text-sm text-slate">
          Reload the page. If it happens again, send this message to whoever maintains TaxPulse:
        </p>
        <pre className="mt-3 overflow-x-auto whitespace-pre-wrap rounded-md bg-paper px-3 py-2 text-xs text-danger">
          {this.state.error.message}
        </pre>
        <div className="mt-4 flex gap-3">
          <button type="button" onClick={() => window.location.reload()}
            className="tp-btn-primary rounded-md px-4 py-2 text-sm font-semibold">
            Reload the page
          </button>
          <a href="/" className="rounded-md border border-rule px-4 py-2 text-sm font-semibold hover:border-slate/40">Go to the overview</a>
        </div>
      </div>
    )
  }
}
