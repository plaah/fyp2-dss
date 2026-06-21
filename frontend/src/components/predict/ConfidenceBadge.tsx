import { CheckCircle2, AlertTriangle, AlertOctagon } from "lucide-react"

export function ConfidenceBadge({ confidence, label }: { confidence: number; label: string }) {
  const pct = Math.round(confidence * 100)
  if (pct >= 80) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-green-200 bg-green-50 px-2.5 py-0.5 text-xs font-medium text-green-700">
        <CheckCircle2 className="w-3 h-3" />
        {label} {pct}%
      </span>
    )
  }
  if (pct >= 60) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-700">
        <AlertTriangle className="w-3 h-3" />
        {label} {pct}%
      </span>
    )
  }
  return (
    <span className="inline-flex animate-pulse items-center gap-1 rounded-full border border-red-200 bg-red-50 px-2.5 py-0.5 text-xs font-medium text-red-700">
      <AlertOctagon className="w-3 h-3" />
      {label} {pct}% — Verifikasi
    </span>
  )
}
