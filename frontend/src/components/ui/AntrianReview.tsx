import { useState, useEffect } from "react"
import { submitFeedback } from "@/lib/api"
import type { StatsResponse, PendingReviewItem } from "@/lib/api"
import { RiskPill } from "@/components/ui/RiskPill"

export function AntrianReview({
  stats,
  onConfirmed,
}: {
  stats: StatsResponse
  onConfirmed?: () => void
}) {
  const [queue, setQueue] = useState<PendingReviewItem[]>(stats.pending_review)
  const [busy, setBusy] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setQueue(stats.pending_review)
  }, [stats.pending_review])

  const handleAction = async (item: PendingReviewItem, isCorrect: boolean) => {
    setBusy(item.id)
    setError(null)
    try {
      const result = await submitFeedback({
        prediction_id: item.id,
        submitted_cbg: item.cbg_prediction,
        correct_cbg: isCorrect ? item.cbg_prediction : "",
        is_correct: isCorrect,
        notes: isCorrect ? undefined : "Flagged for review from dashboard",
      })
      if (result.status !== 'success') throw new Error('Server error')
      setQueue(prev => prev.filter(r => r.id !== item.id))
      onConfirmed?.()
    } catch {
      setError("Gagal menyimpan. Coba lagi.")
    } finally {
      setBusy(null)
    }
  }

  return (
    <div style={{ background: "var(--white)", borderRadius: "var(--radius-card)", border: "2px solid #fde68a", boxShadow: "var(--shadow-card)", overflow: "hidden" }}>
      {/* Header */}
      <div style={{ padding: "16px 22px 12px", borderBottom: "1px solid #f5e7a0", background: "#fffdf0", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
            <span style={{ fontSize: 11, fontWeight: 600, background: "#fef3c7", color: "#b45309", padding: "2px 8px", borderRadius: 12 }}>⏳ Perlu Aksi</span>
            {queue.length > 0 && (
              <span style={{ fontSize: 11, fontWeight: 600, background: "#fef3c7", color: "#b45309", padding: "2px 8px", borderRadius: 12 }}>
                {queue.length} prediksi menunggu
              </span>
            )}
          </div>
          <p style={{ fontWeight: 700, fontSize: 15, color: "var(--near-black)" }}>Antrian Review Casemix</p>
          <p style={{ fontSize: 12, color: "var(--gray-300)", marginTop: 1 }}>
            Prediksi belum divalidasi — konfirmasi untuk update dashboard impact
          </p>
        </div>
      </div>

      {/* Empty state */}
      {queue.length === 0 ? (
        <div style={{ padding: "24px 22px", textAlign: "center", background: "#f0fdf4" }}>
          <p style={{ fontSize: 14, fontWeight: 600, color: "#16a34a" }}>✓ Semua prediksi sudah divalidasi</p>
          <p style={{ fontSize: 12, color: "#666", marginTop: 4 }}>Tidak ada prediksi yang menunggu review.</p>
        </div>
      ) : (
        <>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ background: "#fffdf0" }}>
                  {["ICD Codes", "Prediksi CBG", "Confidence", "Risk", "Tanggal", "Aksi"].map(h => (
                    <th key={h} style={{ padding: "8px 16px", textAlign: "left", fontSize: 11, fontWeight: 600, color: "var(--gray-300)", letterSpacing: "0.05em", textTransform: "uppercase", borderBottom: "1px solid #f5e7a0", whiteSpace: "nowrap" }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {queue.map(row => {
                  const isBusy = busy === row.id
                  const conf = row.mdc_confidence
                  const confPct = conf != null ? Math.round(conf * 100) : null
                  const confColor = conf != null && conf >= 0.8 ? "#16a34a" : "#d97706"
                  return (
                    <tr key={row.id} style={{ borderBottom: "1px solid rgba(0,0,0,0.05)" }}>
                      <td style={{ padding: "11px 16px" }}>
                        <span style={{ fontFamily: "JetBrains Mono,monospace", fontSize: 12, fontWeight: 600, color: "var(--blue)" }}>
                          {row.icd_codes}
                        </span>
                      </td>
                      <td style={{ padding: "11px 16px" }}>
                        <span style={{ fontFamily: "JetBrains Mono,monospace", fontSize: 13, fontWeight: 700, color: "var(--near-black)" }}>
                          {row.cbg_prediction}
                        </span>
                      </td>
                      <td style={{ padding: "11px 16px" }}>
                        {confPct != null ? (
                          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                            <div style={{ width: 44, height: 4, background: "#f0f0f0", borderRadius: 4, overflow: "hidden" }}>
                              <div style={{ width: `${confPct}%`, height: "100%", background: confColor, borderRadius: 4 }} />
                            </div>
                            <span style={{ fontFamily: "JetBrains Mono,monospace", fontSize: 11, color: confColor }}>{confPct}%</span>
                          </div>
                        ) : (
                          <span style={{ color: "var(--gray-300)", fontSize: 12 }}>—</span>
                        )}
                      </td>
                      <td style={{ padding: "11px 16px" }}>
                        <RiskPill risk={row.risk_level} />
                      </td>
                      <td style={{ padding: "11px 16px" }}>
                        <span style={{ fontFamily: "JetBrains Mono,monospace", fontSize: 11, color: "var(--gray-300)" }}>
                          {row.created_at?.slice(0, 10) ?? "—"}
                        </span>
                      </td>
                      <td style={{ padding: "11px 16px" }}>
                        <div style={{ display: "flex", gap: 6 }}>
                          <button
                            disabled={isBusy}
                            onClick={() => handleAction(row, true)}
                            style={{ padding: "5px 12px", borderRadius: 6, border: "none", background: isBusy ? "rgba(0,0,0,0.08)" : "#16a34a", color: isBusy ? "var(--gray-300)" : "white", fontSize: 12, fontWeight: 600, cursor: isBusy ? "not-allowed" : "pointer", transition: "background .12s" }}
                          >
                            {isBusy ? "..." : "✓ Konfirmasi"}
                          </button>
                          <button
                            disabled={isBusy}
                            onClick={() => handleAction(row, false)}
                            style={{ padding: "5px 10px", borderRadius: 6, border: "1px solid var(--border-color)", background: "var(--white)", color: "var(--gray-500)", fontSize: 12, fontWeight: 500, cursor: isBusy ? "not-allowed" : "pointer" }}
                          >
                            ⚑ Flag
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <div style={{ padding: "8px 22px 10px", background: "#fffdf0", borderTop: "1px solid #f5e7a0" }}>
            <p style={{ fontSize: 11, color: "#aaa" }}>
              Setelah dikonfirmasi, kasus otomatis masuk ke Impact Story & Trust Score di atas ↑
            </p>
          </div>
        </>
      )}

      {/* Error — always visible when set, outside the conditional */}
      {error && (
        <p style={{ fontSize: 12, color: "#c0392b", padding: "8px 22px" }}>{error}</p>
      )}
    </div>
  )
}
