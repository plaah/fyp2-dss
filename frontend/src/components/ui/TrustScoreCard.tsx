import type { StatsResponse } from "@/lib/api"

function scoreLabel(score: number): string {
  if (score >= 90) return "Sangat Baik"
  if (score >= 80) return "Baik"
  if (score >= 60) return "Cukup"
  return "Perlu Perhatian"
}

function scoreColor(score: number): string {
  if (score >= 80) return "#a5b4fc"
  if (score >= 60) return "#fbbf24"
  return "#f87171"
}

export function TrustScoreCard({ stats }: { stats: StatsResponse }) {
  const { trust_score, trust_score_breakdown, feedback_total } = stats

  return (
    <div style={{ background: "linear-gradient(145deg, #1a1a1a 0%, #262626 100%)", borderRadius: "var(--radius-card)", border: "1px solid #333", padding: "20px 22px" }}>
      <div style={{ marginBottom: 16 }}>
        <span style={{ fontSize: 11, fontWeight: 600, background: "rgba(99,102,241,0.2)", color: "#a5b4fc", padding: "2px 8px", borderRadius: 12 }}>
          Clinical Trust Score
        </span>
        <p style={{ fontWeight: 700, fontSize: 15, color: "#f5f5f4", letterSpacing: "-0.25px", marginTop: 6 }}>
          Tingkat Kepercayaan Klinis
        </p>
        <p style={{ fontSize: 12, color: "#666", marginTop: 2 }}>Composite dari 3 sinyal kepercayaan</p>
      </div>

      {trust_score == null ? (
        <div>
          <p style={{ fontSize: 13, color: "#666", lineHeight: 1.5 }}>Belum cukup data.</p>
          <p style={{ fontSize: 12, color: "#444", marginTop: 4 }}>
            Minimal 1 konfirmasi casemix dibutuhkan untuk menghitung score.
          </p>
        </div>
      ) : (
        <>
          <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 18 }}>
            <div style={{
              width: 72, height: 72, borderRadius: "50%",
              border: `3px solid ${scoreColor(trust_score)}`,
              display: "flex", alignItems: "center", justifyContent: "center",
              background: "rgba(99,102,241,0.1)", flexShrink: 0,
            }}>
              <p style={{ fontFamily: "JetBrains Mono,monospace", fontSize: 22, fontWeight: 700, color: scoreColor(trust_score) }}>
                {trust_score}
              </p>
            </div>
            <div>
              <p style={{ fontSize: 14, fontWeight: 600, color: scoreColor(trust_score) }}>
                {scoreLabel(trust_score)}
              </p>
              <p style={{ fontSize: 11, color: "#555", marginTop: 2 }}>dari 100 poin maksimal</p>
              {feedback_total < 5 && (
                <p style={{ fontSize: 10, color: "#666", marginTop: 2 }}>n={feedback_total} — sample kecil</p>
              )}
            </div>
          </div>

          {trust_score_breakdown && (
            <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
              {([
                { label: "Model Confidence (MDC)", val: trust_score_breakdown.mdc_confidence, weight: "×0.4", color: "#6366f1" },
                { label: "Konfirmasi Casemix", val: trust_score_breakdown.confirmation_rate, weight: "×0.4", color: "#22c55e" },
                { label: "Grouping Valid Rate", val: trust_score_breakdown.grouping_valid, weight: "×0.2", color: "#f59e0b" },
              ] as const).map(row => (
                <div key={row.label}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
                    <p style={{ fontSize: 11, color: "#888" }}>{row.label}</p>
                    <p style={{ fontFamily: "JetBrains Mono,monospace", fontSize: 11, color: row.color }}>
                      {(row.val * 100).toFixed(0)}% {row.weight}
                    </p>
                  </div>
                  <div style={{ background: "#333", borderRadius: 4, height: 4, overflow: "hidden" }}>
                    <div style={{ background: row.color, width: `${row.val * 100}%`, height: "100%", borderRadius: 4 }} />
                  </div>
                </div>
              ))}
            </div>
          )}

          <p style={{ fontSize: 10, color: "#444", marginTop: 12, lineHeight: 1.5 }}>
            Score = ((MDC conf × 0.4) + (Konfirmasi × 0.4) + (Valid rate × 0.2)) × 100
          </p>
        </>
      )}
    </div>
  )
}
