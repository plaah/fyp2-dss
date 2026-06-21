import { useState } from "react"

const GLOSSARY: Record<string, { label: string; clinical: string; why: string }> = {
  icd_block: {
    label: "Blok ICD",
    clinical: "Kelompok 3-karakter kode ICD-10 dari diagnosis utama (mis: J18 = Pneumonia).",
    why: "Penentu utama pengelompokan CBG — blok ICD yang berbeda bisa menghasilkan tarif berbeda signifikan.",
  },
  icd_block_freq: {
    label: "Frekuensi Blok ICD",
    clinical: "Seberapa sering kode diagnosis ini muncul dalam data historis rumah sakit.",
    why: "Kode yang jarang muncul lebih sulit diprediksi dan berisiko dikelompokkan ke CBG yang salah.",
  },
  icd_chapter: {
    label: "Bab ICD",
    clinical: "Sistem organ atau kategori penyakit besar (Bab J = Pernapasan, Bab I = Sirkulasi, Bab K = Pencernaan).",
    why: "Model menggunakan bab ICD untuk menentukan MDC (Major Diagnostic Category) utama pasien.",
  },
  care_type_str: {
    label: "Jenis Layanan",
    clinical: "Tipe perawatan: Rawat Jalan, Rawat Inap, atau UGD.",
    why: "Rawat inap umumnya menghasilkan tarif BPJS lebih tinggi dibanding rawat jalan.",
  },
  care_type_enc: {
    label: "Jenis Layanan",
    clinical: "Tipe perawatan: Rawat Jalan, Rawat Inap, atau UGD.",
    why: "Rawat inap umumnya menghasilkan tarif BPJS lebih tinggi dibanding rawat jalan.",
  },
  kelas: {
    label: "Kelas BPJS",
    clinical: "Kelas layanan peserta BPJS (Kelas 1, 2, atau 3).",
    why: "Kelas menentukan pengali tarif dasar yang dibayarkan BPJS kepada rumah sakit.",
  },
  kelas_enc: {
    label: "Kelas BPJS",
    clinical: "Kelas layanan peserta BPJS (Kelas 1, 2, atau 3).",
    why: "Kelas menentukan pengali tarif dasar yang dibayarkan BPJS kepada rumah sakit.",
  },
  is_outpatient: {
    label: "Status Rawat Jalan",
    clinical: "Apakah pasien ditangani tanpa menginap di rumah sakit.",
    why: "Status rawat jalan vs rawat inap memiliki jalur tarif yang sangat berbeda dalam sistem BPJS.",
  },
  has_procedure: {
    label: "Ada Prosedur Medis",
    clinical: "Apakah ada kode tindakan medis (ICD-9-CM) yang diberikan bersama diagnosis.",
    why: "Prosedur dapat mengubah kelompok CBG dan besaran tarif secara signifikan.",
  },
  n_diagnoses: {
    label: "Jumlah Diagnosis",
    clinical: "Total jumlah kode diagnosis (primer + sekunder) yang diberikan.",
    why: "Lebih banyak diagnosis sekunder dapat menunjukkan kasus kompleks dengan tarif lebih tinggi.",
  },
  proc_count: {
    label: "Jumlah Prosedur",
    clinical: "Total jumlah tindakan medis (ICD-9-CM) yang tercatat.",
    why: "Banyaknya prosedur mencerminkan tingkat intervensi dan mempengaruhi severity level.",
  },
}

const lookup = (rawKey: string) =>
  GLOSSARY[rawKey] ?? {
    label: rawKey.replace(/_/g, " "),
    clinical: "Fitur klinis yang digunakan model untuk memprediksi kelompok CBG.",
    why: "Berpengaruh pada akurasi prediksi MDC dan estimasi tarif BPJS.",
  }

export const ShapBar = ({
  data,
}: {
  data: { feature: string; rawKey?: string; impact: number; direction: string }[]
}) => {
  const [hovered, setHovered] = useState<number | null>(null)

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      {data.map((d, i) => {
        const key = d.rawKey ?? d.feature.replace(/ /g, "_")
        const info = lookup(key)
        const isPos = d.direction === "positive"
        const pct = Math.min(100, (d.impact / 0.72) * 100)
        const isHov = hovered === i

        return (
          <div
            key={i}
            style={{ position: "relative", cursor: "help" }}
            onMouseEnter={() => setHovered(i)}
            onMouseLeave={() => setHovered(null)}
          >
            {/* Bar row */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "140px 1fr 48px",
                alignItems: "center",
                gap: 10,
                padding: "7px 8px",
                borderRadius: 6,
                background: isHov ? "rgba(0,117,222,0.04)" : "transparent",
                transition: "background .12s",
              }}
            >
              <span
                style={{
                  fontSize: 12,
                  color: isHov ? "var(--blue)" : "var(--gray-500)",
                  textAlign: "right",
                  letterSpacing: "0.01em",
                  fontWeight: isHov ? 600 : 400,
                  transition: "color .12s, font-weight .12s",
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}
                title={info.label}
              >
                {info.label}
              </span>
              <div
                style={{
                  position: "relative",
                  height: 8,
                  background: "rgba(0,0,0,0.06)",
                  borderRadius: 99,
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    position: "absolute",
                    left: 0,
                    top: 0,
                    height: "100%",
                    width: `${pct}%`,
                    background: isPos
                      ? "linear-gradient(90deg, #1aae39, #2a9d99)"
                      : "linear-gradient(90deg, #dd5b00, #e53e3e)",
                    borderRadius: 99,
                    transition: "width .5s cubic-bezier(0.34,1.56,0.64,1)",
                  }}
                />
              </div>
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  color: isPos ? "#1a7a4a" : "#c0392b",
                  fontFamily: "JetBrains Mono,monospace",
                }}
              >
                {isPos ? "+" : "−"}
                {(Math.abs(d.impact) * 100).toFixed(0)}%
              </span>
            </div>

            {/* Tooltip card */}
            {isHov && (
              <div
                style={{
                  position: "absolute",
                  top: "calc(100% + 4px)",
                  left: 148,
                  right: 0,
                  zIndex: 400,
                  background: "var(--white)",
                  border: "1px solid var(--border-color)",
                  borderLeft: `3px solid ${isPos ? "#1aae39" : "#dd5b00"}`,
                  borderRadius: "0 8px 8px 0",
                  boxShadow: "0 8px 24px rgba(0,0,0,0.10), 0 2px 6px rgba(0,0,0,0.06)",
                  padding: "11px 14px",
                  animation: "fadeUp .12s ease",
                  pointerEvents: "none",
                }}
              >
                {/* Direction badge + label */}
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 7 }}>
                  <span
                    style={{
                      fontSize: 9,
                      fontWeight: 700,
                      fontFamily: "JetBrains Mono,monospace",
                      color: isPos ? "#1a7a4a" : "#c0392b",
                      background: isPos ? "#e8f7ef" : "#fde8e8",
                      padding: "2px 7px",
                      borderRadius: 4,
                      letterSpacing: "0.06em",
                      textTransform: "uppercase",
                    }}
                  >
                    {isPos ? "↑ Mendorong naik" : "↓ Menahan turun"}
                  </span>
                  <span
                    style={{
                      fontSize: 12,
                      fontWeight: 600,
                      color: "var(--near-black)",
                      letterSpacing: "-0.01em",
                    }}
                  >
                    {info.label}
                  </span>
                </div>

                {/* Clinical explanation */}
                <p
                  style={{
                    fontSize: 12,
                    color: "var(--gray-500)",
                    lineHeight: 1.55,
                    marginBottom: 8,
                  }}
                >
                  {info.clinical}
                </p>

                {/* Why it matters */}
                <div
                  style={{
                    borderTop: "1px solid var(--border-color)",
                    paddingTop: 7,
                    display: "flex",
                    gap: 6,
                    alignItems: "flex-start",
                  }}
                >
                  <span style={{ fontSize: 11, flexShrink: 0 }}>💡</span>
                  <p
                    style={{
                      fontSize: 11,
                      color: "var(--gray-300)",
                      lineHeight: 1.5,
                      margin: 0,
                    }}
                  >
                    {info.why}
                  </p>
                </div>
              </div>
            )}
          </div>
        )
      })}

      {/* Hover hint — shown only before any hover */}
      <p
        style={{
          fontSize: 10,
          color: "var(--gray-300)",
          textAlign: "right",
          marginTop: 4,
          letterSpacing: "0.02em",
        }}
      >
        Arahkan kursor ke baris untuk penjelasan klinis
      </p>
    </div>
  )
}
