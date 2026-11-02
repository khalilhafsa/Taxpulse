// Typed helpers for the TaxPulse API. Vite proxies /api to the backend.

export type Health = { status: string; llm_configured: boolean; key_problem: string | null; demo_mode?: boolean; models: { reasoning: string; fast: string } }
export type Stats = { clients: number; documents: number; updates: number; alerts_open: number; drafts_open: number }

export type ClientSummary = {
  id: number
  slug: string
  name: string
  mandate: string
  contact_name: string
  contact_title: string
  salutation: string
  is_demo: boolean
  document_count: number
  has_profile: boolean
}

export type DocumentInfo = { id: number; filename: string; page_count: number; uploaded_at: string }

export type Citation = { document: string; page: number; quote: string; verified: boolean }
export type Fact = { label: string; value: string; citations: Citation[] }
export type TaxArea = {
  category: string
  title: string
  assessment: 'risk' | 'opportunity' | 'neutral'
  severity: 'high' | 'medium' | 'low'
  summary: string
  facts: Fact[]
}
export type ProfileData = {
  company_name: string
  summary: string
  key_facts: Fact[]
  tax_areas: TaxArea[]
  open_points: Fact[]
  keywords: string[]
  verification: { verified: number; total: number }
  source_pages: number
}
export type Profile = { id: number; version: number; data: ProfileData; created_at: string; run_id: number | null }

export type AgentRun = {
  id: number
  agent: string
  status: 'running' | 'done' | 'failed'
  model: string
  subject: string
  subject_label: string
  tokens_in: number
  tokens_out: number
  cost_usd: number
  duration_ms: number
  error: string
  started_at: string
  finished_at: string | null
}

export type ClientDetail = ClientSummary & {
  documents: DocumentInfo[]
  profile: Profile | null
  profile_run: AgentRun | null
  active_run_id: number | null
}

export type PageText = { document_id: number; filename: string; page_number: number; page_count: number; text: string }

export type UpdateKind = 'bmf_letter' | 'bfh_ruling' | 'law' | 'press_release' | 'other'

export type UpdateAnalysis = {
  title_en: string
  kind: UpdateKind
  relevant_for_companies: boolean
  tax_categories: string[]
  summary: string
  who_is_affected: string
  trigger_criteria: string[]
  exclusions: string[]
  effective_date: string
  keywords: string[]
}

export type UpdateSummary = {
  id: number
  external_id: string
  kind: UpdateKind
  title: string
  published_on: string | null
  source: 'demo' | 'bmf_feed' | 'manual'
  url: string | null
  summary: UpdateAnalysis | null
  analysis_status: 'pending' | 'running' | 'done' | 'failed'
  analysis_error: string | null
}

export type UpdateDetail = UpdateSummary & { raw_text: string }

export type FetchResult = { found: number; new: number; already_known: number; problems: string[] }

export type Evidence = { client_fact: string; criterion: string; supports_impact: boolean; verified: boolean }

export type AlertItem = {
  id: number
  status: 'new' | 'accepted' | 'dismissed'
  dismiss_reason: string
  created_at: string
  score: number
  verdict: 'affected' | 'not_affected' | 'uncertain'
  reasoning: string
  evidence: Evidence[]
  missing_information: string[]
  client: { id: number; name: string; is_demo: boolean }
  update: { id: number; title: string; original_title: string; kind: UpdateKind; published_on: string | null; tax_categories: string[]; source: string }
  memo: ImpactMemo | null
  memo_status: 'none' | 'running' | 'done' | 'failed'
  memo_error: string
}

export type ImpactMemo = {
  headline: string
  impact: string
  risk_or_opportunity: 'risk' | 'opportunity' | 'both'
  urgency: 'high' | 'medium' | 'low'
  deadline: string
  recommended_actions: string[]
  proposed_mandate: string
  questions_for_client: string[]
}

export type EmailDraft = {
  id: number
  client_id: number
  alert_ids: number[]
  subject: string
  body: string
  status: 'draft' | 'approved' | 'sent'
  edited_by_user: boolean
  revised: boolean
  review_notes: string
  remarks: string
  created_at: string
  updated_at: string
}

export type OutreachEntry = {
  client: { id: number; name: string; mandate: string; contact_name: string; contact_title: string; salutation: string }
  alerts: { id: number; score: number; title: string; has_memo: boolean; headline: string | null; urgency: string | null }[]
  drafts: EmailDraft[]
  writer_running: boolean
  writer_error: string
  alerts_not_in_draft: number
}

export type ScanStatus = {
  updates_ready: number
  updates_unscanned: number
  updates_not_analysed: number
  clients_total: number
  clients_without_profile: number
  scan_running: number
  profiles_running: number
}

export type Evaluation = {
  alerts_on_demo_updates: number
  alerts_on_other_updates: number
  labelled_pairs: number
  evaluated_pairs: number
  not_evaluated: number
  affected_total: number
  affected_found: number
  not_affected_total: number
  false_alerts: number
  missed: { client: string; update: string; score: number; why_expected: string }[]
  false_alert_details: { client: string; update: string; score: number }[]
  threshold: number
}

export type Firm = {
  firm_name: string
  advisor_name: string
  advisor_title: string
  phone: string
  email: string
  address: string
  website: string
  monthly_budget_usd: number
  spent_this_month_usd?: number
}

export type StabilityRun = { index: number; cost_usd: number; affected_found: number; affected_total: number; false_alerts: number; not_affected_total: number }
export type Stability = {
  id: number; status: 'running' | 'done' | 'failed'; error: string; runs_planned: number; runs_done: number; cost_usd: number
  started_at: string; finished_at: string | null; per_run: StabilityRun[]
  scored_pairs: number; consistent_pairs: number; consistency: number | null
  clear_pairs: number; clear_consistency: number | null
  mean_score_spread: number | null; max_score_spread: number | null
  affected_found_min: number | null; affected_found_mean: number | null; false_alerts_max: number | null
  affected_total: number | null; not_affected_total: number | null; perfect_runs: number
  unstable_pairs: { client: string; update: string; scores: number[]; flagged: boolean[]; expected: string }[]
}
export type Quality = {
  matcher_accuracy: Evaluation
  stability: Stability | null
  citations: { verified: number; total: number; profiles: number }
  emails: { drafts: number; passed_first_time: number; fixed_by_revision: number; still_flagged: number }
  reliability: { runs: number; failed: number; retried: number; interrupted: number }
  per_agent: { agent: string; model: string; runs: number; failed: number; cost_usd: number; avg_cost_usd: number; avg_duration_ms: number; tokens: number; success_rate: number }[]
  budget: { monthly_usd: number; spent_this_month_usd: number }
}

export type AutomationSettings = {
  enabled: boolean; weekday: number; hour: number; fetch_bmf: boolean; fetch_bfh: boolean; bmf_feed_url: string
  last_run_at: string | null; last_trigger: string; last_status: '' | 'done' | 'action' | 'problems' | 'failed'; last_summary: string
  running: boolean; days: string[]; next_run_at: string | null
}
export type AppNotification = { id: number; kind: 'weekly' | 'action' | 'problem' | 'info'; title: string; body: string; link: string; read: boolean; created_at: string }

export type Contact = { contact_name: string; contact_title: string; salutation: string }

export class ApiError extends Error {}

export type DashboardCounts = {
  clients: number; clients_profiled: number; clients_missing_profile: number
  updates: number; updates_not_analysed: number; updates_relevant: number; updates_unscanned: number
  alerts_to_review: number; alerts_accepted: number; clients_to_draft: number
  drafts_to_review: number; drafts_ready: number; emails_sent: number; cost_usd: number
}
export type Dashboard = {
  counts: DashboardCounts
  todo: { key: string; count: number; to: string; label: string }[]
  top_clients: { client: string; client_id: number; score: number; alert_id: number; topics: { title: string; score: number; kind: string }[] }[]
  recent_runs: { id: number; agent: string; status: AgentRun['status']; cost_usd: number; duration_ms: number; started_at: string; label: string }[]
}
export type MatrixCell = { stage: string; score: number | null; verdict: string | null; alert_id: number | null; alert_status: AlertItem['status'] | null } | null
export type Matrix = {
  updates: { id: number; title: string; kind: string; categories: string[]; external_id: string; scanned: boolean }[]
  rows: { client: { id: number; name: string; is_demo: boolean }; cells: MatrixCell[] }[]
  threshold: number
}
export type Stage = {
  key: string; name: string; role: string; llm: boolean
  done: number; total: number; unit: string
  runs: number; cost_usd: number; avg_duration_ms: number; running: number; failed: number; model: string; current: string
}
export type Pipeline = {
  stages: Stage[]
  chain: { running: boolean; step: string; pipeline_id: string; error: string; started_at: string | null; finished_at: string | null }
  pairs: { total: number; filtered_out: number }
  pending: { profiles: number; analyses: number; scans: number; total: number }
  waiting_for_review: number
  log: { id: number; agent: string; status: AgentRun['status']; label: string; duration_ms: number; cost_usd: number; started_at: string; finished_at: string | null }[]
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`/api${path}`, init)
  } catch {
    throw new ApiError('The backend is not reachable. Check that the TaxPulse API window is running.')
  }
  if (!res.ok) {
    let detail: string | null = null
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') detail = body.detail
    } catch {
      /* not JSON: the dev proxy answered because the backend is down */
    }
    if (!detail && (res.status === 502 || res.status === 504))
      detail = 'The backend is not running. Start it with start.bat.'
    throw new ApiError(detail ?? `${res.status} ${res.statusText}`)
  }
  return res.json() as Promise<T>
}

const json = (body: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

export const api = {
  health: () => request<Health>('/health'),
  stats: () => request<Stats>('/stats'),
  dashboard: () => request<Dashboard>('/dashboard'),
  matrix: () => request<Matrix>('/matrix'),
  pipeline: () => request<Pipeline>('/pipeline'),
  runChain: () => request<{ pipeline_id: string }>('/pipeline/run', { method: 'POST' }),
  clients: () => request<ClientSummary[]>('/clients'),
  client: (id: number) => request<ClientDetail>(`/clients/${id}`),
  createClient: (name: string, mandate: string, contact?: Contact) =>
    request<ClientSummary>('/clients', json({ name, mandate, ...contact })),
  saveContact: (id: number, contact: Contact) =>
    request<ClientSummary>(`/clients/${id}/contact`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(contact) }),
  firm: () => request<Firm>('/settings/firm'),
  quality: () => request<Quality>('/quality'),
  resetDemo: () => request<{ reset: boolean }>('/demo/reset', { method: 'POST' }),
  automation: () => request<AutomationSettings>('/automation'),
  saveAutomation: (a: { enabled: boolean; weekday: number; hour: number; fetch_bmf: boolean; fetch_bfh: boolean }) =>
    request<AutomationSettings>('/automation', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(a) }),
  runWeeklyCheck: () => request<{ started: boolean }>('/automation/run', { method: 'POST' }),
  notifications: () => request<{ items: AppNotification[]; unread: number }>('/notifications'),
  readNotification: (id: number) => request<AppNotification>(`/notifications/${id}/read`, { method: 'POST' }),
  readAllNotifications: () => request<{ ok: boolean }>('/notifications/read-all', { method: 'POST' }),
  startStability: (runs: number) => request<{ batch_id: number }>('/quality/stability', json({ runs })),
  saveFirm: (firm: Firm) =>
    request<Firm>('/settings/firm', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(firm) }),
  uploadDocuments: (id: number, files: File[]) => {
    const form = new FormData()
    files.forEach((f) => form.append('files', f))
    return request<{ added: DocumentInfo[]; warnings: string[] }>(`/clients/${id}/documents`, { method: 'POST', body: form })
  },
  buildProfile: (id: number) => request<{ run_id: number }>(`/clients/${id}/profile`, { method: 'POST' }),
  page: (documentId: number, page: number) => request<PageText>(`/documents/${documentId}/pages/${page}`),
  fileUrl: (documentId: number, page?: number) => `/api/documents/${documentId}/file${page ? `#page=${page}` : ''}`,
  run: (id: number) => request<AgentRun>(`/runs/${id}`),
  runs: () => request<{ runs: AgentRun[]; totals: { runs: number; cost_usd: number; tokens: number } }>('/runs'),
  updates: () => request<UpdateSummary[]>('/updates'),
  update: (id: number) => request<UpdateDetail>(`/updates/${id}`),
  fetchBmf: () => request<FetchResult>('/updates/fetch', { method: 'POST' }),
  fetchBfh: () => request<FetchResult>('/updates/fetch-bfh', { method: 'POST' }),
  importFeed: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<FetchResult>('/updates/import-feed', { method: 'POST', body: form })
  },
  addUpdate: (body: { title: string; kind: UpdateKind; published_on: string | null; url: string | null; text: string }) =>
    request<UpdateSummary>('/updates', json(body)),
  analyzeUpdate: (id: number) => request<{ queued: number }>(`/updates/${id}/analyze`, { method: 'POST' }),
  analyzePending: () => request<{ queued: number }>('/updates/analyze-pending', { method: 'POST' }),
  scanStatus: () => request<ScanStatus>('/scan/status'),
  scan: (rescanAll = false) => request<{ queued: number }>('/scan', json({ rescan_all: rescanAll })),
  buildMissingProfiles: () => request<{ queued: number }>('/clients/build-missing-profiles', { method: 'POST' }),
  alerts: (status?: string) => request<AlertItem[]>(`/alerts${status ? `?status=${status}` : ''}`),
  setAlertStatus: (id: number, status: AlertItem['status'], reason = '') =>
    request<AlertItem>(`/alerts/${id}/status`, json({ status, reason })),
  evaluation: () => request<Evaluation>('/evaluation'),
  writeMemo: (id: number) => request<AlertItem>(`/alerts/${id}/memo`, { method: 'POST' }),
  outreach: () => request<OutreachEntry[]>('/outreach'),
  draftEmail: (clientId: number) => request<{ run_id: number; alerts: number }>(`/clients/${clientId}/draft-email`, { method: 'POST' }),
  editDraft: (id: number, subject: string, body: string) =>
    request<EmailDraft>(`/drafts/${id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ subject, body }) }),
  setDraftStatus: (id: number, status: EmailDraft['status']) => request<EmailDraft>(`/drafts/${id}/status`, json({ status })),
  reviseDraft: (id: number, remarks: string) => request<{ run_id: number }>(`/drafts/${id}/revise`, json({ remarks })),
  deleteDraft: (id: number) => request<{ deleted: number }>(`/drafts/${id}`, { method: 'DELETE' }),
  loadDemo: () => request<{ added: Record<string, number> }>('/demo/seed', { method: 'POST' }),
}

export const shortDocName = (filename: string) =>
  filename.replace(/^\d+_/, '').replace(/\.pdf$/i, '').replace(/_/g, ' ')

export const formatDateTime = (iso: string) =>
  new Date(iso.endsWith('Z') || iso.includes('+') ? iso : `${iso}Z`).toLocaleString('en-GB', {
    day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
  })
