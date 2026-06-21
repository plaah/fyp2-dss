import type { StatsResponse } from "@/lib/api"

export function ConfirmationPanel({ stats }: { stats: StatsResponse }) {
  const { feedback_total, feedback_confirmed, feedback_confirmation_rate, recent_feedback } = stats
  const rate = Number.isFinite(feedback_confirmation_rate) ? feedback_confirmation_rate : 0
  const pct = (rate * 100).toFixed(0) + "%"

  if (feedback_total === 0) {
    return (
      <div style={{ background: "var(--white)", borderRadius: "var(--radius-card)", border: "1px solid var(--border-color)", boxShadow: "var(--shadow-card)", padding: "20px 22px" }}>
        <p style={{ fontWeight: 700, fontSize: 15, color: "var(--near-black)", letterSpacing: "-0.25px", marginBottom: 4 }}>
          Konfirmasi Petugas Casemix
        </p>
        <p style={{ fontSize: 12, color: "var(--gray-300)", marginBottom: 16 }}>
          Akurasi prediksi berdasarkan review casemix
        </p>
        <p style={{ fontSize: 13, color: "var(--gray-500)", lineHeight: 1.5 }}>
          Belum ada feedback casemix. Gunakan Antrian Review di bawah untuk mulai validasi.
        </p>
      </div>
    )
  }

  return (
    <div style={{ background: "var(--white)", borderRadius: "var(--radius-card)", border: "1px solid var(--border-color)", boxShadow: "var(--shadow-card)", padding: "20px 22px" }}>
      <p style={{ fontWeight: 700, fontSize: 15, color: "var(--near-black)", letterSpacing: "-0.25px", marginBottom: 2 }}>
        Konfirmasi Petugas Casemix
      </p>
      <p style={{ fontSize: 12, color: "var(--gray-300)", marginBottom: 14 }}>
        Akurasi prediksi berdasarkan review casemix
      </p>

      <div style={{ display: "flex", alignItems: "flex-end", gap: 12, marginBottom: 10 }}>
        <p style={{ fontFamily: "JetBrains Mono,monospace", fontSize: 44, fontWeight: 700, color: "#16a34a", letterSpacing: "-2px", lineHeight: 1 }}>
          {pct}
        </p>
        <div style={{ paddingBottom: 4 }}>
          <p style={{ fontSize: 13, fontWeight: 600, color: "var(--near-black)" }}>Clinical Accuracy</p>
          <p style={{ fontSize: 12, color: "var(--gray-300)" }}>
            {feedback_confirmed} benar / {feedback_total} review
          </p>
          {feedback_total < 5 && (
            <p style={{ fontSize: 10, color: "var(--orange)", marginTop: 2 }}>
              n={feedback_total} — sample kecil
            </p>
          )}
        </div>
      </div>

      <div style={{ background: "#f0f0f0", borderRadius: 100, height: 7, marginBottom: 16, overflow: "hidden" }}>
        <div style={{
          background: "#16a34a",
          width: `${Math.min(100, Math.max(0, rate * 100))}%`,
          height: "100%",
          borderRadius: 100,
          transition: "width .5s ease",
        }} />
      </div>

      <p style={{ fontSize: 10, fontWeight: 600, color: "var(--gray-300)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>
        Feedback Terbaru
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {recent_feedback.map((fb, i) => (
          <div key={i} style={{
            display: "flex", alignItems: "center", justifyContent: "space-between",
            padding: "7px 10px", borderRadius: 7,
            background: fb.confirmed ? "#f0fdf4" : "#fff5f5",
            border: `1px solid ${fb.confirmed ? "#bbf7d0" : "#fecaca"}`,
          }}>
            <div>
              <span style={{ fontFamily: "JetBrains Mono,monospace", fontSize: 12, fontWeight: 600, color: fb.confirmed ? "#16a34a" : "#dc2626" }}>
                {fb.icd_codes}
              </span>
              <span style={{ fontSize: 11, color: "var(--gray-300)", marginLeft: 8 }}>→ {fb.cbg_prediction}</span>
            </div>
            <span style={{ fontSize: 11, fontWeight: 600, color: fb.confirmed ? "#16a34a" : "#dc2626" }}>
              {fb.confirmed ? "✓ Benar" : "✗ Perlu Review"}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
