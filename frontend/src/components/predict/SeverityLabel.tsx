export function SeverityLabel({ severity }: { severity: string }) {
  const map: Record<string, { label: string; className: string }> = {
    "0":   { label: "Rawat Jalan",           className: "border-cyan-200 bg-cyan-50 text-cyan-700" },
    "I":   { label: "Rawat Inap — Ringan",   className: "border-green-200 bg-green-50 text-green-700" },
    "II":  { label: "Rawat Inap — Sedang",   className: "border-amber-200 bg-amber-50 text-amber-700" },
    "III": { label: "Rawat Inap — Berat",    className: "border-red-200 bg-red-50 text-red-700" },
  }
  const s = map[severity] ?? { label: severity, className: "border-gray-200 bg-gray-50 text-gray-700" }
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${s.className}`}>
      {s.label}
    </span>
  )
}
