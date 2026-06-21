import type { StatsResponse } from "@/lib/api"

const fmtRpJt = (n: number) =>
  n >= 1_000_000 ? `Rp ${(n / 1_000_000).toFixed(1)}jt` : `Rp ${n.toLocaleString("id-ID")}`

export function ImpactFunnel({ stats }: { stats: StatsResponse }) {
  const rate = stats.feedback_confirmation_rate
  const pctStr = (rate * 100).toFixed(0) + "%"

  const nodes = [
    {
      label: "Total Prediksi",
      value: stats.total_predictions.toLocaleString("id-ID"),
      sub: "semua kasus diproses",
      bg: "#eef4ff", border: "#bfdbfe", textColor: "#2563eb", dark: false,
    },
    {
      label: "Grouping Valid",
      value: stats.grouping_valid_count.toLocaleString("id-ID"),
      sub: `${stats.grouping_valid_pct.toFixed(1)}% dari total`,
      bg: "#f0fdf4", border: "#bbf7d0", textColor: "#16a34a", dark: false,
    },
    {
      label: "Divalidasi Casemix",
      value: stats.feedback_confirmed > 0 ? stats.feedback_confirmed.toLocaleString("id-ID") : "—",
      sub: stats.feedback_total > 0 ? `${pctStr} akurasi klinis` : "Belum ada validasi",
      bg: "#fffbeb", border: "#fde68a", textColor: "#d97706", dark: false,
    },
    {
      label: "Gap Teridentifikasi",
      value: stats.total_financial_gap_idr > 0 ? fmtRpJt(stats.total_financial_gap_idr) : "—",
      sub: "financial gap ter-flag",
      bg: "#1a1a1a", border: "#333", textColor: "#ff6b6b", dark: true,
    },
  ]

  const summaryParts: string[] = []
  if (stats.feedback_total > 0) {
    summaryParts.push(
      `${pctStr} akurasi — ${stats.feedback_confirmed} dari ${stats.feedback_total} review casemix dikonfirmasi benar`
    )
  }
  if (stats.avg_mdc_confidence != null) {
    summaryParts.push(`rata-rata confidence model ${(stats.avg_mdc_confidence * 100).toFixed(1)}%`)
  }

  return (
    <div style={{ background: "var(--white)", borderRadius: "var(--radius-card)", border: "1px solid var(--border-color)", boxShadow: "var(--shadow-card)", padding: "20px 24px" }}>
      <div style={{ display: "flex", alignItems: "flex-start", marginBottom: 18 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5 }}>
            <span style={{ fontSize: 11, fontWeight: 600, color: "#2563eb", background: "#eef4ff", padding: "2px 8px", borderRadius: 12 }}>Impact Story</span>
            <span style={{ fontSize: 11, fontWeight: 600, color: "#16a34a", background: "#f0fdf4", padding: "2px 8px", borderRadius: 12 }}>✓ Hanya prediksi tervalidasi</span>
          </div>
          <p style={{ fontWeight: 700, fontSize: 15, color: "var(--near-black)", letterSpacing: "-0.25px" }}>
            Perjalanan Prediksi → Dampak Klinis
          </p>
          <p style={{ fontSize: 12, color: "var(--gray-300)", marginTop: 2 }}>
            Dari input ICD sampai konfirmasi casemix — end-to-end
          </p>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 28px 1fr 28px 1fr 28px 1fr", alignItems: "center" }}>
        {nodes.map((n, i) => (
          <div key={n.label} style={{ display: "contents" }}>
            <div style={{ background: n.bg, borderRadius: 10, padding: "14px 16px", textAlign: "center", border: `1px solid ${n.border}` }}>
              <p style={{ fontSize: 10, fontWeight: 600, color: n.textColor, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 5 }}>{n.label}</p>
              <p style={{ fontFamily: "JetBrains Mono,monospace", fontSize: n.dark ? 18 : 24, fontWeight: 700, color: n.dark ? n.textColor : "var(--near-black)", letterSpacing: "-1px", lineHeight: 1 }}>{n.value}</p>
              <p style={{ fontSize: 10, color: n.dark ? "#666" : "var(--gray-300)", marginTop: 4 }}>{n.sub}</p>
            </div>
            {i < 3 && (
              <div style={{ textAlign: "center", color: "#ccc", fontSize: 16 }}>→</div>
            )}
          </div>
        ))}
      </div>

      {summaryParts.length > 0 && (
        <div style={{ marginTop: 14, padding: "9px 13px", background: "#f7f6f3", borderRadius: 7, borderLeft: "3px solid #2563eb" }}>
          <p style={{ fontSize: 12, color: "#555" }}>{summaryParts.join(". ")}.</p>
        </div>
      )}
    </div>
  )
}
