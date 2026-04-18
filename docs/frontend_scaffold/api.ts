const BASE = '/api/v1'

export interface ShapItem {
  feature: string
  impact: number
  direction: 'positive' | 'negative'
}

export interface PredictionResult {
  predicted_mdc: string
  predicted_mdc_description: string
  predicted_severity: string
  predicted_severity_label: string
  predicted_cbg_code: string
  predicted_cbg_description: string
  predicted_base_tariff: number
  tariff_by_kelas: Record<string, number>
  mdc_confidence: number
  severity_confidence: number
  lookup_method: string
  mdc_source: string
  shap_explanation: ShapItem[]
  status: string
}

export interface FinancialResult {
  reimbursement_amount: number
  submitted_amount: number
  financial_gap: number
  gap_percentage: number
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  risk_explanation: string
  estimated_loss_idr: number
  reimbursement_probability: number
}

export interface RecommendationResult {
  primary_action: string
  priority: string
  recommendations: Array<{ rank: number; action: string; reason: string }>
  warnings: string[]
  summary: string
}

export interface FullAssessmentResponse {
  status: string
  prediction: PredictionResult
  financial: FinancialResult
  recommendation: RecommendationResult
}

export interface IcdResult {
  code: string
  description: string
  indonesian_term: string
  source: string
  confidence: string
}

export async function runFullAssessment(payload: {
  primary_icd10: string
  inacbg_icd10?: string
  icd9_procedure?: string
  care_type: string
  entry_type?: string
  kelas: string
  episodes?: number
  actual_tariff: number
}): Promise<FullAssessmentResponse> {
  const res = await fetch(`${BASE}/full-assessment`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`API error ${res.status}`)
  return res.json()
}

export async function searchIcd(
  q: string,
  type: 'diagnosis' | 'procedure',
  limit = 5
): Promise<IcdResult[]> {
  const res = await fetch(
    `${BASE}/icd-search?q=${encodeURIComponent(q)}&type=${type}&limit=${limit}`
  )
  if (!res.ok) return []
  const data = await res.json()
  return data.results ?? []
}

export async function getStats(): Promise<Record<string, unknown>> {
  const res = await fetch(`${BASE}/stats`)
  if (!res.ok) throw new Error('Stats fetch failed')
  return res.json()
}

export async function submitFeedback(payload: {
  submitted_cbg: string
  correct_cbg: string
  is_correct: boolean
  notes?: string
}): Promise<{ status: string; feedback_id: number }> {
  const res = await fetch(`${BASE}/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...payload, prediction_id: null }),
  })
  return res.json()
}
