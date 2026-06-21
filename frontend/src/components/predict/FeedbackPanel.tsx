import { useState } from "react"
import { submitFeedback } from "@/lib/api"
import { Icon } from "@/components/ui/icons"

type Phase = "idle" | "asking" | "correct" | "incorrect_form" | "submitting" | "done"

export function FeedbackPanel({
  predictedCbg,
  predictionId,
}: {
  predictedCbg: string
  predictionId?: number | null
}) {
  const [phase, setPhase] = useState<Phase>("idle")
  const [correctCbg, setCorrectCbg] = useState("")
  const [notes, setNotes] = useState("")
  const [feedbackId, setFeedbackId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleCorrect = async () => {
    setPhase("submitting")
    setError(null)
    try {
      const res = await submitFeedback({
        prediction_id: predictionId ?? null,
        submitted_cbg: predictedCbg,
        correct_cbg: predictedCbg,
        is_correct: true,
      })
      setFeedbackId(res.feedback_id)
      setPhase("done")
    } catch {
      setError("Gagal menyimpan feedback. Coba lagi.")
      setPhase("asking")
    }
  }

  const handleSubmitIncorrect = async () => {
    if (!correctCbg.trim()) return
    setPhase("submitting")
    setError(null)
    try {
      const res = await submitFeedback({
        prediction_id: predictionId ?? null,
        submitted_cbg: predictedCbg,
        correct_cbg: correctCbg.trim().toUpperCase(),
        is_correct: false,
        notes: notes.trim() || undefined,
      })
      setFeedbackId(res.feedback_id)
      setPhase("done")
    } catch {
      setError("Gagal menyimpan feedback. Coba lagi.")
      setPhase("incorrect_form")
    }
  }

  const inputStyle = {
    width: "100%",
    padding: "8px 11px",
    border: "1px solid rgba(0,0,0,0.12)",
    borderRadius: 6,
    fontSize: 13,
    outline: "none",
    background: "var(--white)",
    color: "var(--near-black)",
    fontFamily: "JetBrains Mono,monospace",
    boxSizing: "border-box" as const,
    transition: "border-color .12s, box-shadow .12s",
  }

  // ── Idle — collapsed prompt ──────────────────────────────────────────────
  if (phase === "idle") {
    return (
      <div
        style={{
          borderTop: "1px solid var(--border-color)",
          paddingTop: 16,
          marginTop: 4,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Icon name="feedback" size={14} color="var(--gray-300)" strokeWidth={1.5} />
          <span style={{ fontSize: 12, color: "var(--gray-300)" }}>
            Apakah prediksi ini membantu?
          </span>
        </div>
        <button
          onClick={() => setPhase("asking")}
          style={{
            fontSize: 12,
            color: "var(--blue)",
            background: "none",
            border: "none",
            cursor: "pointer",
            fontFamily: "Inter,sans-serif",
            padding: "4px 8px",
            borderRadius: 4,
            transition: "background .1s",
          }}
          onMouseEnter={e => (e.currentTarget.style.background = "var(--blue-badge-bg)")}
          onMouseLeave={e => (e.currentTarget.style.background = "none")}
        >
          Beri Feedback →
        </button>
      </div>
    )
  }

  // ── Asking — Yes / No buttons ────────────────────────────────────────────
  if (phase === "asking") {
    return (
      <div
        style={{
          borderTop: "1px solid var(--border-color)",
          paddingTop: 16,
          marginTop: 4,
          animation: "fadeUp .2s ease",
        }}
      >
        <p style={{ fontSize: 12, fontWeight: 600, color: "var(--near-black)", marginBottom: 10 }}>
          Apakah prediksi CBG{" "}
          <span
            style={{
              fontFamily: "JetBrains Mono,monospace",
              color: "var(--blue)",
              fontWeight: 700,
            }}
          >
            {predictedCbg}
          </span>{" "}
          sudah benar?
        </p>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            onClick={handleCorrect}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 7,
              padding: "8px 16px",
              borderRadius: 6,
              border: "1px solid rgba(26,174,57,0.3)",
              background: "#e8f7ef",
              color: "#1a7a4a",
              fontSize: 13,
              fontWeight: 600,
              cursor: "pointer",
              fontFamily: "Inter,sans-serif",
              transition: "all .12s",
            }}
            onMouseEnter={e => (e.currentTarget.style.background = "#d1f0de")}
            onMouseLeave={e => (e.currentTarget.style.background = "#e8f7ef")}
          >
            <Icon name="check" size={13} color="#1a7a4a" strokeWidth={2.5} />
            Ya, Sudah Benar
          </button>
          <button
            onClick={() => setPhase("incorrect_form")}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 7,
              padding: "8px 16px",
              borderRadius: 6,
              border: "1px solid rgba(221,91,0,0.3)",
              background: "#fff4e6",
              color: "#b45309",
              fontSize: 13,
              fontWeight: 600,
              cursor: "pointer",
              fontFamily: "Inter,sans-serif",
              transition: "all .12s",
            }}
            onMouseEnter={e => (e.currentTarget.style.background = "#ffe8cc")}
            onMouseLeave={e => (e.currentTarget.style.background = "#fff4e6")}
          >
            <Icon name="x" size={13} color="#b45309" strokeWidth={2.5} />
            Tidak, Ada Koreksi
          </button>
          <button
            onClick={() => setPhase("idle")}
            style={{
              marginLeft: "auto",
              background: "none",
              border: "none",
              cursor: "pointer",
              color: "var(--gray-300)",
              fontSize: 12,
              fontFamily: "Inter,sans-serif",
              padding: "4px 8px",
            }}
          >
            Lewati
          </button>
        </div>
        {error && (
          <p style={{ fontSize: 12, color: "#c0392b", marginTop: 8 }}>{error}</p>
        )}
      </div>
    )
  }

  // ── Correction form ──────────────────────────────────────────────────────
  if (phase === "incorrect_form" || phase === "submitting") {
    const busy = phase === "submitting"
    return (
      <div
        style={{
          borderTop: "1px solid var(--border-color)",
          paddingTop: 16,
          marginTop: 4,
          animation: "fadeUp .2s ease",
        }}
      >
        <p
          style={{
            fontSize: 12,
            fontWeight: 600,
            color: "var(--near-black)",
            marginBottom: 12,
            display: "flex",
            alignItems: "center",
            gap: 7,
          }}
        >
          <Icon name="feedback" size={13} color="var(--gray-500)" strokeWidth={1.5} />
          Koreksi Prediksi
        </p>

        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div>
            <label
              style={{
                fontSize: 11,
                fontWeight: 600,
                color: "var(--gray-500)",
                display: "block",
                marginBottom: 5,
                letterSpacing: "0.04em",
                textTransform: "uppercase",
              }}
            >
              CBG yang Benar{" "}
              <span style={{ color: "#c0392b", fontWeight: 400 }}>*</span>
            </label>
            <input
              value={correctCbg}
              onChange={e => setCorrectCbg(e.target.value)}
              placeholder="contoh: E-4-14-I"
              disabled={busy}
              style={inputStyle}
              onFocus={e => {
                e.target.style.borderColor = "var(--blue)"
                e.target.style.boxShadow = "0 0 0 2px rgba(0,117,222,0.12)"
              }}
              onBlur={e => {
                e.target.style.borderColor = "rgba(0,0,0,0.12)"
                e.target.style.boxShadow = "none"
              }}
            />
          </div>

          <div>
            <label
              style={{
                fontSize: 11,
                fontWeight: 600,
                color: "var(--gray-500)",
                display: "block",
                marginBottom: 5,
                letterSpacing: "0.04em",
                textTransform: "uppercase",
              }}
            >
              Catatan{" "}
              <span style={{ fontWeight: 400, color: "var(--gray-300)" }}>(Opsional)</span>
            </label>
            <textarea
              value={notes}
              onChange={e => setNotes(e.target.value)}
              placeholder="Jelaskan alasan koreksi, mis: diagnosis sekunder mempengaruhi severity…"
              disabled={busy}
              rows={2}
              style={{
                ...inputStyle,
                fontFamily: "Inter,sans-serif",
                resize: "vertical",
                lineHeight: 1.5,
              }}
              onFocus={e => {
                e.target.style.borderColor = "var(--blue)"
                e.target.style.boxShadow = "0 0 0 2px rgba(0,117,222,0.12)"
              }}
              onBlur={e => {
                e.target.style.borderColor = "rgba(0,0,0,0.12)"
                e.target.style.boxShadow = "none"
              }}
            />
          </div>

          {error && (
            <p style={{ fontSize: 12, color: "#c0392b" }}>{error}</p>
          )}

          <div style={{ display: "flex", gap: 8 }}>
            <button
              onClick={handleSubmitIncorrect}
              disabled={busy || !correctCbg.trim()}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 7,
                padding: "8px 16px",
                borderRadius: 6,
                border: "none",
                background:
                  busy || !correctCbg.trim() ? "rgba(0,0,0,0.08)" : "var(--blue)",
                color:
                  busy || !correctCbg.trim() ? "var(--gray-300)" : "white",
                fontSize: 13,
                fontWeight: 600,
                cursor: busy || !correctCbg.trim() ? "not-allowed" : "pointer",
                fontFamily: "Inter,sans-serif",
                transition: "all .12s",
              }}
            >
              {busy ? (
                <>
                  <div
                    style={{
                      width: 12,
                      height: 12,
                      border: "2px solid rgba(255,255,255,0.3)",
                      borderTopColor: "white",
                      borderRadius: "50%",
                      animation: "spin 0.8s linear infinite",
                    }}
                  />
                  Menyimpan…
                </>
              ) : (
                <>
                  <Icon name="send" size={12} color="white" strokeWidth={2} />
                  Kirim Koreksi
                </>
              )}
            </button>
            <button
              onClick={() => setPhase("asking")}
              disabled={busy}
              style={{
                padding: "8px 12px",
                borderRadius: 6,
                border: "1px solid rgba(0,0,0,0.1)",
                background: "none",
                color: "var(--gray-500)",
                fontSize: 13,
                cursor: busy ? "not-allowed" : "pointer",
                fontFamily: "Inter,sans-serif",
              }}
            >
              Kembali
            </button>
          </div>
        </div>
      </div>
    )
  }

  // ── Done ─────────────────────────────────────────────────────────────────
  return (
    <div
      style={{
        borderTop: "1px solid var(--border-color)",
        paddingTop: 16,
        marginTop: 4,
        animation: "fadeUp .25s ease",
        display: "flex",
        alignItems: "flex-start",
        gap: 12,
      }}
    >
      <div
        style={{
          width: 32,
          height: 32,
          borderRadius: 8,
          background: "#e8f7ef",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}
      >
        <Icon name="check" size={15} color="#1a7a4a" strokeWidth={2.5} />
      </div>
      <div>
        <p
          style={{
            fontSize: 13,
            fontWeight: 600,
            color: "#1a7a4a",
            marginBottom: 3,
          }}
        >
          Feedback tersimpan
          {feedbackId != null && (
            <span
              style={{
                fontFamily: "JetBrains Mono,monospace",
                fontSize: 10,
                fontWeight: 700,
                color: "var(--gray-300)",
                background: "rgba(0,0,0,0.05)",
                padding: "1px 6px",
                borderRadius: 4,
                marginLeft: 8,
              }}
            >
              #{feedbackId}
            </span>
          )}
        </p>
        <p style={{ fontSize: 12, color: "var(--gray-500)", lineHeight: 1.5 }}>
          Terima kasih. Data ini akan digunakan untuk melatih ulang model AI pada iterasi berikutnya.
        </p>
      </div>
    </div>
  )
}
