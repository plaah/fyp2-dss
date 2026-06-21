import { useState } from "react"
import { ChevronDown } from "lucide-react"
import { type AlternativeCbg } from "@/lib/api"
import { formatRp } from "@/lib/utils"

export function AlternativeCbgPanel({ alternatives, confidence, lookupMethod }: {
  alternatives: AlternativeCbg[]
  confidence: number
  lookupMethod: string
}) {
  const [open, setOpen] = useState(false)
  const shouldShow = alternatives.length > 0 && (confidence < 0.70 || lookupMethod !== 'exact')
  if (!shouldShow) return null
  return (
    <div className="rounded-lg border border-gray-200">
      <button
        onClick={() => setOpen(o => !o)}
        className="flex w-full cursor-pointer items-center justify-between px-4 py-3 text-sm text-gray-600 hover:text-gray-900 transition-colors"
      >
        <span className="font-medium">Lihat alternatif CBG ({alternatives.length})</span>
        <ChevronDown className={`h-4 w-4 transition-transform duration-200 ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="border-t border-gray-100 px-4 pb-4 pt-3 space-y-2">
          <p className="text-xs text-muted-foreground mb-3">
            Skenario CBG berdasarkan variasi tingkat keparahan untuk MDC yang sama.
          </p>
          {alternatives.map((alt, i) => (
            <div key={i} className="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2.5">
              <div>
                <span className="font-mono text-sm font-semibold text-primary">{alt.cbg_code}</span>
                <span className="ml-2 text-xs text-muted-foreground">{alt.severity_label}</span>
              </div>
              <div className="text-right">
                <p className="text-sm font-medium">{formatRp(alt.base_tariff)}</p>
                <p className="text-xs text-muted-foreground">{alt.basis}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
