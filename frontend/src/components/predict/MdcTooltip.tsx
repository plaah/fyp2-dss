import { useState } from "react"
import { Info } from "lucide-react"

const MDC_LABELS: Record<string, { name: string; indonesian: string }> = {
  A: { name: "Pre-MDC / Special",        indonesian: "Kasus khusus sebelum klasifikasi" },
  B: { name: "Neoplasms",                indonesian: "Neoplasma dan tumor" },
  D: { name: "Ear, Nose & Throat",       indonesian: "THT (Telinga, Hidung, Tenggorokan)" },
  E: { name: "Endocrine & Metabolic",    indonesian: "Endokrin dan metabolik" },
  F: { name: "Mental Health",            indonesian: "Kesehatan jiwa" },
  G: { name: "Nervous System",           indonesian: "Sistem saraf" },
  H: { name: "Eye & Ocular",             indonesian: "Mata dan okular" },
  I: { name: "Cardiovascular",           indonesian: "Jantung dan pembuluh darah" },
  J: { name: "Respiratory System",       indonesian: "Sistem pernapasan" },
  K: { name: "Digestive System",         indonesian: "Sistem pencernaan" },
  L: { name: "Musculoskeletal",          indonesian: "Tulang, sendi, dan otot" },
  M: { name: "Skin & Tissue",            indonesian: "Kulit dan jaringan lunak" },
  N: { name: "Kidney & Urinary",         indonesian: "Ginjal dan saluran kemih" },
  O: { name: "Obstetrics",               indonesian: "Kebidanan dan kandungan" },
  Q: { name: "Unclassified / Special",   indonesian: "Tidak terklasifikasi / prosedur khusus" },
  S: { name: "Burns",                    indonesian: "Luka bakar" },
  U: { name: "Infectious Disease",       indonesian: "Penyakit infeksi dan parasit" },
  V: { name: "Mental & Substance",       indonesian: "Jiwa dan penyalahgunaan zat" },
  W: { name: "Injury & Poisoning",       indonesian: "Cedera, trauma, dan keracunan" },
  Z: { name: "Surgical / Procedural",    indonesian: "Prosedur bedah dan tindakan" },
}

export function MdcTooltip({ mdc }: { mdc: string }) {
  const [open, setOpen] = useState(false)
  const info = MDC_LABELS[mdc]
  return (
    <span className="relative inline-flex items-center">
      <span className="inline-flex items-center gap-1 rounded-full border border-gray-200 bg-gray-50 px-2.5 py-0.5 text-xs font-medium text-gray-700">
        MDC {mdc}
        {info && (
          <button
            onMouseEnter={() => setOpen(true)}
            onMouseLeave={() => setOpen(false)}
            onClick={() => setOpen(o => !o)}
            className="ml-0.5 text-gray-400 hover:text-cyan-600 transition-colors cursor-pointer"
            aria-label={`Keterangan MDC ${mdc}`}
          >
            <Info className="w-3 h-3" />
          </button>
        )}
      </span>
      {open && info && (
        <div className="absolute bottom-full left-0 mb-2 z-50 w-56 rounded-xl border border-gray-100 bg-white p-3 shadow-lg">
          <p className="text-xs font-semibold text-gray-900">{mdc} — {info.name}</p>
          <p className="text-xs text-gray-500 mt-0.5">{info.indonesian}</p>
        </div>
      )}
    </span>
  )
}
