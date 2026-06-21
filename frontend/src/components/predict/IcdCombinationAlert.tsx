import { AlertTriangle } from "lucide-react"

export function IcdCombinationAlert({ rarity }: { rarity: number }) {
  if (rarity >= 5) return null
  return (
    <div className="flex items-start gap-2.5 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
      <div>
        <p className="text-sm font-medium text-amber-800">Kombinasi ICD jarang ditemukan</p>
        <p className="text-xs text-amber-700 mt-0.5">
          Pasangan diagnosis + prosedur ini tercatat {rarity === 0 ? "0×" : `${rarity}×`} dalam data historis.
          Verifikasi ulang kode sebelum melanjutkan.
        </p>
      </div>
    </div>
  )
}
