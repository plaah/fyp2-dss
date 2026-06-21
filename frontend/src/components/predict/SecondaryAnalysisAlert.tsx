import { Info, AlertTriangle } from "lucide-react"
import type { SecondaryAnalysis } from "@/lib/api"

const MDC_CHAPTER_NAMES: Record<string, string> = {
  A: "Infeksi", B: "Neoplasma", C: "Neoplasma", D: "Darah",
  E: "Endokrin/DM", F: "Jiwa", G: "Saraf", H: "Mata/THT",
  I: "Kardiovaskular", J: "Pernapasan", K: "Pencernaan",
  L: "Muskuloskeletal", M: "Kulit", N: "Ginjal/Urologi",
  O: "Kebidanan", S: "Cedera", T: "Keracunan",
}

export function SecondaryAnalysisAlert({ analysis, currentSeverity }: {
  analysis: SecondaryAnalysis
  currentSeverity: string
}) {
  if (!analysis?.has_secondaries) return null

  const isWarning = analysis.severity_warning
  const baseClass = isWarning
    ? "border-amber-200 bg-amber-50"
    : "border-blue-200 bg-blue-50"
  const iconClass = isWarning ? "text-amber-600" : "text-blue-600"
  const titleClass = isWarning ? "text-amber-800" : "text-blue-800"
  const textClass = isWarning ? "text-amber-700" : "text-blue-700"
  const Icon = isWarning ? AlertTriangle : Info

  const chapterLabels = (analysis.chapter_list ?? [])
    .map(ch => `${ch} (${MDC_CHAPTER_NAMES[ch] ?? "lainnya"})`)
    .join(", ")

  return (
    <div className={`flex items-start gap-2.5 rounded-lg border px-4 py-3 ${baseClass}`}>
      <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${iconClass}`} />
      <div>
        <p className={`text-sm font-medium ${titleClass}`}>
          {analysis.count} diagnosis sekunder terdeteksi
        </p>
        <p className={`text-xs mt-0.5 ${textClass}`}>
          Chapter berbeda: {analysis.distinct_chapters} ({chapterLabels})
        </p>
        {analysis.has_comorbidity && (
          <p className={`text-xs mt-1 ${textClass}`}>
            Komorbiditas terdeteksi — prediksi CBG mempertimbangkan diagnosis utama saja.
          </p>
        )}
        {isWarning && analysis.escalator_chapters && analysis.escalator_chapters.length > 0 && (
          <p className="text-xs mt-1 font-medium text-amber-800">
            ⚠ Komorbiditas {analysis.escalator_chapters.map(ch => MDC_CHAPTER_NAMES[ch] ?? ch).join(", ")} —
            severity aktual mungkin lebih tinggi dari prediksi (saat ini: {currentSeverity}).
          </p>
        )}
      </div>
    </div>
  )
}
