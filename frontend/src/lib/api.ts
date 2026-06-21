const BASE = '/api/v1'

export interface ShapItem {
  feature: string
  impact: number
  direction: 'positive' | 'negative'
}

export interface AlternativeCbg {
  cbg_code: string
  base_tariff: number
  severity: string
  severity_label: string
  basis: string
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
  combination_rarity: number
  alternative_cbgs: AlternativeCbg[]
  secondary_diagnoses: string[]
  procedures: string[]
  secondary_analysis: SecondaryAnalysis
  procedure_analysis: ProcedureAnalysis
  status: string
}

export interface SecondaryAnalysis {
  has_secondaries: boolean
  count?: number
  distinct_chapters?: number
  chapter_list?: string[]
  has_comorbidity?: boolean
  has_escalator?: boolean
  escalator_chapters?: string[]
  severity_warning?: boolean
}

export interface ProcedureAnalysis {
  has_procedures: boolean
  count: number
  codes?: string[]
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
  coding_tips: string[]
  estimated_resolution_days: number
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

export interface RecentPrediction {
  id: number
  created_at: string
  idrg_primary_icd10: string
  idrg_icd9_procedure: string
  ml_prediction: string
  risk_level: string
  financial_gap: number
  reimbursement_probability: number
  primary_action: string
  top_shap_feature: string
  actual_tariff: number
  base_tariff: number
  care_type: string
  kelas: string
  source: string
}

export interface PredictionHistoryPoint {
  date: string
  count: number
  valid: number
}

export interface RecentFeedbackItem {
  icd_codes: string
  cbg_prediction: string
  confirmed: boolean
  created_at: string
}

export interface TrustScoreBreakdown {
  mdc_confidence: number
  confirmation_rate: number
  grouping_valid: number
}

export interface PendingReviewItem {
  id: number
  icd_codes: string
  cbg_prediction: string
  mdc_confidence: number | null
  risk_level: string
  created_at: string
}

export interface StatsResponse {
  status: string
  total_predictions: number
  today_predictions: number
  avg_reimbursement_probability: number
  total_financial_gap_idr: number
  grouping_valid_pct: number
  grouping_valid_count: number
  coding_incomplete_count: number
  coding_incomplete_pct: number
  grouping_invalid_count: number
  grouping_invalid_pct: number
  risk_distribution: Record<string, number>
  prediction_history: PredictionHistoryPoint[]
  recent_predictions: RecentPrediction[]
  // Impact stats
  feedback_total: number
  feedback_confirmed: number
  feedback_confirmation_rate: number
  avg_mdc_confidence: number | null
  recent_feedback: RecentFeedbackItem[]
  trust_score: number | null
  trust_score_breakdown: TrustScoreBreakdown | null
  pending_review: PendingReviewItem[]
}

export async function runFullAssessment(payload: {
  primary_icd10: string
  inacbg_icd10?: string
  icd9_procedure?: string
  icd9_procedures?: string[]
  secondary_icd10?: string[]
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
  const res = await fetch(`${BASE}/icd-search?q=${encodeURIComponent(q)}&type=${type}&limit=${limit}`)
  if (!res.ok) return []
  const data = await res.json()
  return (data.results ?? []) as IcdResult[]
}

export async function getStats(): Promise<StatsResponse> {
  const res = await fetch(`${BASE}/stats`)
  if (!res.ok) throw new Error('Stats fetch failed')
  return res.json()
}

export async function submitFeedback(payload: {
  prediction_id?: number | null
  submitted_cbg: string
  correct_cbg?: string
  is_correct: boolean
  notes?: string
}): Promise<{ status: string; feedback_id: number }> {
  const res = await fetch(`${BASE}/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`Feedback API error ${res.status}`)
  return res.json()
}
