import { useState, useEffect, useRef, useCallback } from "react"
import { Icon } from "@/components/ui/icons"
import { RiskPill } from "@/components/ui/RiskPill"
import { NotionBadge } from "@/components/ui/notion-badge"
import { ShapBar } from "@/components/ui/charts/ShapBar"
import { runFullAssessment, searchIcd, type FullAssessmentResponse, type IcdResult } from "@/lib/api"
import { MdcTooltip } from "@/components/predict/MdcTooltip"
import { SeverityLabel } from "@/components/predict/SeverityLabel"
import { ConfidenceBadge } from "@/components/predict/ConfidenceBadge"
import { IcdCombinationAlert } from "@/components/predict/IcdCombinationAlert"
import { AlternativeCbgPanel } from "@/components/predict/AlternativeCbgPanel"
import { SecondaryAnalysisAlert } from "@/components/predict/SecondaryAnalysisAlert"
import { FeedbackPanel } from "@/components/predict/FeedbackPanel"

const fmtRp = (n: number | null | undefined) => n == null ? "—" : "Rp " + Number(n).toLocaleString("id-ID");

interface SelectedIcd {
  code: string
  description: string
}

function IcdSearch({ label, note, placeholder, type, onSelect }: { label?: string, note?: string, placeholder: string, type: "diagnosis" | "procedure", onSelect: (icd: SelectedIcd | null) => void }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<IcdResult[]>([]);
  const [selected, setSelected] = useState<SelectedIcd | null>(null);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const search = useCallback(async (query: string) => {
    if (!query || query.length < 2) { setResults([]); setOpen(false); return }
    setLoading(true);
    try {
      const data = await searchIcd(query, type);
      setResults(data.slice(0, 6));
      setOpen(true);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, [type]);

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    if (!selected && q) timerRef.current = setTimeout(() => search(q), 300);
    return () => { if (timerRef.current) clearTimeout(timerRef.current) }
  }, [q, search, selected]);

  const pick = (r: IcdResult) => {
    const item = { code: r.code, description: r.description };
    setSelected(item); onSelect(item); setQ(""); setOpen(false);
  };
  const clear = () => { setSelected(null); onSelect(null); setQ(""); };

  const inputStyle = { width: "100%", padding: "9px 12px", border: "1px solid rgba(0,0,0,0.12)", borderRadius: "var(--radius-btn)", fontSize: 14, outline: "none", background: "var(--white)", color: "var(--near-black)", fontFamily: "Inter,sans-serif", lineHeight: 1.5, transition: "border-color .12s,box-shadow .12s" };

  return (
    <div>
      {label && <label style={{ fontSize: 13, fontWeight: 500, color: "var(--near-black)", display: "block", marginBottom: 6 }}>{label}{note && <span style={{ fontWeight: 400, color: "var(--gray-300)", marginLeft: 5, fontSize: 12 }}>{note}</span>}</label>}
      {selected ? (
        <div style={{ display: "flex", alignItems: "center", gap: 8, border: "1px solid var(--blue)", borderRadius: "var(--radius-btn)", padding: "8px 12px", background: "var(--blue-badge-bg)" }}>
          <Icon name="tag" size={13} color="var(--blue)" strokeWidth={2} />
          <span style={{ fontFamily: "JetBrains Mono,monospace", fontWeight: 600, fontSize: 13, color: "var(--blue)" }}>{selected.code}</span>
          <span style={{ fontSize: 12, color: "var(--gray-500)", flex: 1 }}>— {selected.description.slice(0, 44)}{selected.description.length > 44 ? "…" : ""}</span>
          <button onClick={clear} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--gray-300)", padding: 2, display: "flex", borderRadius: 3 }}>
            <Icon name="x" size={13} strokeWidth={2} />
          </button>
        </div>
      ) : (
        <div style={{ position: "relative" }}>
          <input value={q} onChange={e => setQ(e.target.value)} placeholder={placeholder} style={inputStyle}
            onFocus={e => { e.target.style.borderColor = "var(--blue)"; e.target.style.boxShadow = "0 0 0 2px rgba(0,117,222,0.12)"; if(results.length>0) setOpen(true); }}
            onBlur={e => { e.target.style.borderColor = "rgba(0,0,0,0.12)"; e.target.style.boxShadow = "none"; setTimeout(() => setOpen(false), 150) }} />
          {open && (
            <div style={{ position: "absolute", zIndex: 200, top: "calc(100% + 4px)", left: 0, right: 0, background: "var(--white)", border: "1px solid rgba(0,0,0,0.1)", borderRadius: 8, boxShadow: "var(--shadow-deep)", overflow: "hidden" }}>
              {loading && <div style={{ padding: "9px 13px", fontSize: 12, color: "var(--gray-500)" }}>Mencari...</div>}
              {results.map(r => (
                <button key={r.code} onMouseDown={() => pick(r)} style={{ display: "block", width: "100%", textAlign: "left", padding: "9px 13px", background: "none", border: "none", cursor: "pointer", borderBottom: "1px solid rgba(0,0,0,0.05)", fontSize: 13, fontFamily: "Inter,sans-serif", transition: "background .08s" }}
                  onMouseEnter={e => e.currentTarget.style.background = "var(--blue-badge-bg)"}
                  onMouseLeave={e => e.currentTarget.style.background = "none"}>
                  <span style={{ fontFamily: "JetBrains Mono,monospace", color: "var(--blue)", fontWeight: 600, marginRight: 10, fontSize: 12 }}>{r.code}</span>
                  <span style={{ color: "var(--gray-500)" }}>{r.description}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

const SelectF = ({ label, value, onChange, options }: { label: string, value: string, onChange: (v: string) => void, options: { v: string, l: string }[] }) => (
  <div>
    <label style={{ fontSize: 13, fontWeight: 500, color: "var(--near-black)", display: "block", marginBottom: 6 }}>{label}</label>
    <select value={value} onChange={e => onChange(e.target.value)} style={{ width: "100%", padding: "9px 12px", border: "1px solid rgba(0,0,0,0.12)", borderRadius: "var(--radius-btn)", fontSize: 14, outline: "none", background: "var(--white)", color: "var(--near-black)", cursor: "pointer", fontFamily: "Inter,sans-serif", WebkitAppearance:"none", MozAppearance:"none", appearance:"none" }}>
      {options.map(o => <option key={o.v} value={o.v}>{o.l}</option>)}
    </select>
  </div>
);

export default function Predict() {
  const [diagIcd, setDiagIcd] = useState<SelectedIcd | null>(null);
  const [secondaryDiags, setSecondaryDiags] = useState<SelectedIcd[]>([]);
  const [procedures, setProcedures] = useState<SelectedIcd[]>([]);
  const [secSlots, setSecSlots] = useState(0);
  const [procSlots, setProcSlots] = useState(1);
  const [careType, setCareType] = useState("outp");
  const [kelas, setKelas] = useState("kelas_3");
  const [tariff, setTariff] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<FullAssessmentResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!diagIcd) { setError("Pilih diagnosis utama terlebih dahulu."); return; }
    setError(null); setLoading(true); setResult(null);
    try {
      const payload = {
        primary_icd10: diagIcd.code,
        secondary_icd10: secondaryDiags.map(d => d?.code).filter(Boolean),
        icd9_procedures: procedures.map(p => p?.code).filter(Boolean),
        inacbg_icd10: diagIcd.code,
        care_type: careType,
        entry_type: careType === "outp" ? "gp" : "sp",
        kelas,
        episodes: 1,
        actual_tariff: parseFloat(tariff) || 0,
      }
      const data = await runFullAssessment(payload);
      setResult(data);
    } catch (e: any) {
      setError(e.message || "Gagal menghubungi server.");
    } finally {
      setLoading(false);
    }
  };

  const pred = result?.prediction;
  const fin = result?.financial;
  const rec = result?.recommendation;
  const isOver = (fin?.financial_gap ?? 0) > 0;

  const shapData = (pred?.shap_explanation ?? []).map(s => ({
    feature: s.feature.replace(/_/g, " "),
    rawKey: s.feature,
    impact: Math.abs(s.impact),
    direction: s.direction,
  }));

  return (
    <div style={{ display: "grid", gridTemplateColumns: "380px 1fr", gap: 20, alignItems: "start", animation: "fadeUp .3s ease" }}>
      {/* INPUT FORM */}
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
            <NotionBadge>Alat Prediksi Klinis</NotionBadge>
          </div>
          <h1 style={{ fontSize: 28, fontWeight: 700, color: "var(--near-black)", letterSpacing: "-0.75px", lineHeight: 1.1 }}>Prediksi CBG & Tarif</h1>
          <p style={{ fontSize: 14, color: "var(--gray-500)", marginTop: 6, lineHeight: 1.5 }}>Masukkan data klinis untuk mendapat prediksi kode INA-CBGs dan estimasi tarif BPJS</p>
        </div>

        {/* Form card */}
        <div style={{ background: "var(--white)", borderRadius: "var(--radius-card)", border: "1px solid var(--border-color)", boxShadow: "var(--shadow-card)", overflow: "hidden" }}>
          <div style={{ padding: "16px 20px 12px", borderBottom: "1px solid var(--border-color)", background: "var(--warm-white)", display: "flex", alignItems: "center", gap: 10 }}>
            <Icon name="file" size={15} color="var(--gray-500)" strokeWidth={2} />
            <p style={{ fontWeight: 600, fontSize: 14, color: "var(--near-black)" }}>Data Klinis Pasien</p>
          </div>
          <div style={{ padding: "18px 20px", display: "flex", flexDirection: "column", gap: 14 }}>
            <IcdSearch label="Diagnosis Utama (ICD-10)" note="*Wajib" placeholder="Ketik kode atau nama — contoh: J18.9, pneumonia…" type="diagnosis" onSelect={setDiagIcd} />

            {Array.from({ length: secSlots }).map((_, idx) => (
              <div key={`s${idx}`} style={{ display: "flex", gap: 8, alignItems: "flex-end" }}>
                <div style={{ flex: 1 }}>
                  <IcdSearch label={idx === 0 ? "Diagnosis Sekunder" : ""} placeholder={`Diagnosis sekunder ${idx + 1}…`} type="diagnosis" onSelect={(icd) => {
                    setSecondaryDiags(prev => { const next = [...prev]; if (icd) { next[idx] = icd; } else { next.splice(idx, 1); } return next; });
                  }} />
                </div>
                <button onClick={() => { setSecSlots(n => n - 1); setSecondaryDiags(prev => prev.filter((_, i) => i !== idx)); }} style={{ padding: "9px", border: "1px solid rgba(0,0,0,0.1)", borderRadius: "var(--radius-btn)", background: "none", cursor: "pointer", color: "var(--gray-300)", display: "flex", marginBottom: 0 }}>
                  <Icon name="x" size={13} strokeWidth={2} />
                </button>
              </div>
            ))}
            {secSlots < 4 && (
              <button onClick={() => setSecSlots(n => n + 1)} style={{ display: "flex", alignItems: "center", gap: 7, background: "none", border: "1px dashed rgba(0,0,0,0.15)", borderRadius: "var(--radius-btn)", padding: "7px 12px", fontSize: 13, color: "var(--gray-300)", cursor: "pointer", fontFamily: "Inter,sans-serif", transition: "all .12s" }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = "var(--blue)"; e.currentTarget.style.color = "var(--blue)" }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = "rgba(0,0,0,0.15)"; e.currentTarget.style.color = "var(--gray-300)" }}>
                <Icon name="plus" size={13} strokeWidth={2} />
                Tambah diagnosis sekunder {secSlots > 0 ? `(${secSlots}/4)` : ""}
              </button>
            )}

            <div style={{ borderTop: "1px solid rgba(0,0,0,0.07)", paddingTop: 14 }}>
              {Array.from({ length: procSlots }).map((_, idx) => (
                <div key={`p${idx}`} style={{ display: "flex", gap: 8, alignItems: "flex-end", marginBottom: 10 }}>
                  <div style={{ flex: 1 }}>
                    <IcdSearch label={idx === 0 ? "Prosedur (ICD-9-CM)" : ""} note={idx === 0 ? "Opsional" : ""} placeholder={`Prosedur ${idx + 1} — contoh: 88.72, hemodialisis…`} type="procedure" onSelect={(icd) => {
                      setProcedures(prev => { const next = [...prev]; if (icd) { next[idx] = icd; } else { next.splice(idx, 1); } return next; });
                    }} />
                  </div>
                  {procSlots > 1 && <button onClick={() => { setProcSlots(n => n - 1); setProcedures(prev => prev.filter((_, i) => i !== idx)); }} style={{ padding: "9px", border: "1px solid rgba(0,0,0,0.1)", borderRadius: "var(--radius-btn)", background: "none", cursor: "pointer", color: "var(--gray-300)", display: "flex" }}>
                    <Icon name="x" size={13} strokeWidth={2} />
                  </button>}
                </div>
              ))}
              {procSlots < 5 && (
                <button onClick={() => setProcSlots(n => n + 1)} style={{ display: "flex", alignItems: "center", gap: 7, background: "none", border: "1px dashed rgba(0,0,0,0.15)", borderRadius: "var(--radius-btn)", padding: "7px 12px", fontSize: 13, color: "var(--gray-300)", cursor: "pointer", fontFamily: "Inter,sans-serif", transition: "all .12s" }}
                  onMouseEnter={e => { e.currentTarget.style.borderColor = "var(--blue)"; e.currentTarget.style.color = "var(--blue)" }}
                  onMouseLeave={e => { e.currentTarget.style.borderColor = "rgba(0,0,0,0.15)"; e.currentTarget.style.color = "var(--gray-300)" }}>
                  <Icon name="plus" size={13} strokeWidth={2} />
                  Tambah prosedur ({procSlots}/5)
                </button>
              )}
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <SelectF label="Jenis Rawat" value={careType} onChange={setCareType} options={[{ v: "outp", l: "Rawat Jalan" }, { v: "inp", l: "Rawat Inap" }, { v: "emd", l: "UGD / Gawat Darurat" }]} />
              <SelectF label="Kelas" value={kelas} onChange={setKelas} options={[{ v: "kelas_1", l: "Kelas 1" }, { v: "kelas_2", l: "Kelas 2" }, { v: "kelas_3", l: "Kelas 3" }]} />
            </div>

            <div>
              <label style={{ fontSize: 13, fontWeight: 500, color: "var(--near-black)", display: "block", marginBottom: 6 }}>Tarif Diajukan (Rp) <span style={{ fontWeight: 400, color: "var(--gray-300)", fontSize: 12 }}>Opsional</span></label>
              <input type="number" value={tariff} onChange={e => setTariff(e.target.value)} placeholder="contoh: 1960000"
                style={{ width: "100%", padding: "9px 12px", border: "1px solid rgba(0,0,0,0.12)", borderRadius: "var(--radius-btn)", fontSize: 14, outline: "none", background: "var(--white)", color: "var(--near-black)", fontFamily: "JetBrains Mono,monospace", transition: "border-color .12s,box-shadow .12s" }}
                onFocus={e => { e.target.style.borderColor = "var(--blue)"; e.target.style.boxShadow = "0 0 0 2px rgba(0,117,222,0.12)" }}
                onBlur={e => { e.target.style.borderColor = "rgba(0,0,0,0.12)"; e.target.style.boxShadow = "none" }} />
            </div>

            {error && <div style={{ background: "#fde8e8", border: "1px solid rgba(192,57,43,0.2)", borderRadius: "var(--radius-btn)", padding: "9px 13px", fontSize: 13, color: "#c0392b", display: "flex", gap: 8, alignItems: "center" }}>
              <Icon name="alert" size={14} color="#c0392b" strokeWidth={2} />{error}
            </div>}

            <button onClick={handleSubmit} disabled={loading} style={{ width: "100%", padding: "11px", borderRadius: "var(--radius-btn)", border: "none", background: loading ? "rgba(0,0,0,0.08)" : "var(--blue)", color: loading ? "var(--gray-300)" : "white", fontSize: 14, fontWeight: 600, cursor: loading ? "not-allowed" : "pointer", transition: "all .12s", display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}
              onMouseEnter={e => { if (!loading) e.currentTarget.style.background = "var(--blue-hover)" }}
              onMouseLeave={e => { if (!loading) e.currentTarget.style.background = "var(--blue)" }}>
              {loading ? <><div style={{ width: 14, height: 14, border: "2px solid rgba(255,255,255,0.3)", borderTopColor: "white", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />Memproses…</> : <><Icon name="send" size={14} color="white" strokeWidth={2} />Prediksi CBG & Tarif</>}
            </button>
          </div>
        </div>

        {/* Guide */}
        <div style={{ background: "var(--warm-white)", borderRadius: "var(--radius-card)", border: "1px solid var(--border-color)", padding: "14px 18px" }}>
          <p style={{ fontSize: 12, fontWeight: 600, color: "var(--near-black)", marginBottom: 10, display: "flex", alignItems: "center", gap: 7 }}>
            <Icon name="info" size={13} color="var(--gray-500)" strokeWidth={2} />
            Panduan Level Risiko
          </p>
          {[
            { r: "LOW", l: "Proses Normal — tarif dalam plafon", c: "#1a7a4a", b: "#e8f7ef", d: "#1aae39" },
            { r: "MEDIUM", l: "Verifikasi Koding Sebelum Submit", c: "#b45309", b: "#fff4e6", d: "#dd5b00" },
            { r: "HIGH", l: "Review Dokumen Pendukung", c: "#c0392b", b: "#fde8e8", d: "#e53e3e" },
            { r: "CRITICAL", l: "Eskalasi ke Supervisor", c: "#7f1d1d", b: "#fee2e2", d: "#7f1d1d" },
          ].map(r => (
            <div key={r.r} style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 7 }}>
              <span style={{ background: r.b, color: r.c, fontSize: 10, fontWeight: 700, padding: "2px 9px", borderRadius: 9999, minWidth: 64, textAlign: "center", letterSpacing: "0.04em", display: "flex", alignItems: "center", gap: 4 }}>
                <span style={{ width: 5, height: 5, borderRadius: "50%", background: r.d, flexShrink: 0 }} />
                {r.r}
              </span>
              <span style={{ fontSize: 12, color: "var(--gray-500)" }}>{r.l}</span>
            </div>
          ))}
        </div>
      </div>

      {/* RESULT PANEL */}
      <div>
        {!result && !loading && (
          <div style={{ background: "var(--warm-white)", borderRadius: "var(--radius-lg)", border: "1px dashed rgba(0,0,0,0.12)", padding: "60px 40px", textAlign: "center" }}>
            <div style={{ width: 56, height: 56, borderRadius: 14, background: "var(--blue-badge-bg)", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 16px" }}>
              <Icon name="brain" size={26} color="var(--blue)" strokeWidth={1.5} />
            </div>
            <p style={{ fontSize: 20, fontWeight: 700, color: "var(--near-black)", letterSpacing: "-0.25px", marginBottom: 8 }}>Siap Memprediksi</p>
            <p style={{ fontSize: 14, color: "var(--gray-500)", maxWidth: 320, margin: "0 auto", lineHeight: 1.6 }}>Isi data klinis di panel kiri, lalu klik tombol Prediksi untuk melihat hasil analisis CBG, tarif, dan rekomendasi klinis.</p>
            <div style={{ marginTop: 28, display: "flex", flexDirection: "column", gap: 7, alignItems: "center" }}>
              {["Prediksi kode INA-CBGs", "Estimasi tarif BPJS", "Analisis risiko finansial", "Penjelasan AI (SHAP values)", "Rekomendasi tindakan klinis"].map(f => (
                <div key={f} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Icon name="check" size={13} color="var(--teal)" strokeWidth={2.5} />
                  <span style={{ fontSize: 13, color: "var(--gray-500)" }}>{f}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {loading && (
          <div style={{ background: "var(--white)", borderRadius: "var(--radius-lg)", border: "1px solid var(--border-color)", boxShadow: "var(--shadow-card)", padding: "60px 40px", textAlign: "center" }}>
            <div style={{ width: 44, height: 44, border: "3px solid rgba(0,0,0,0.08)", borderTopColor: "var(--blue)", borderRadius: "50%", margin: "0 auto 20px", animation: "spin 0.9s linear infinite" }} />
            <p style={{ fontSize: 16, fontWeight: 600, color: "var(--near-black)", letterSpacing: "-0.25px", marginBottom: 6 }}>Menganalisis data klinis…</p>
            <p style={{ fontSize: 13, color: "var(--gray-500)" }}>Model ML sedang memproses kode ICD dan parameter perawatan</p>
          </div>
        )}

        {result && pred && fin && rec && (
          <div style={{ background: "var(--white)", borderRadius: "var(--radius-lg)", border: "1px solid var(--border-color)", boxShadow: "var(--shadow-card)", overflow: "hidden", animation: "fadeUp .4s ease" }}>
            <div style={{ padding: "24px 28px", borderBottom: "1px solid var(--border-color)" }}>
              <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 12 }}>
                <div>
                  <p style={{ fontSize: 11, fontWeight: 600, color: "var(--gray-300)", letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 4 }}>CBG Terprediksi</p>
                  <h2 style={{ fontSize: 42, fontWeight: 700, color: "var(--blue)", fontFamily: "JetBrains Mono,monospace", letterSpacing: "-1.5px", lineHeight: 1 }}>{pred.predicted_cbg_code || "—"}</h2>
                  <p style={{ fontSize: 14, color: "var(--gray-500)", marginTop: 6, fontWeight: 500 }}>{pred.predicted_cbg_description || ""}</p>
                </div>
                <RiskPill risk={fin.risk_level} size="lg" />
              </div>

              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 16 }}>
                <MdcTooltip mdc={pred.predicted_mdc} />
                <SeverityLabel severity={pred.predicted_severity} />
                <ConfidenceBadge confidence={pred.mdc_confidence ?? 0} label="MDC" />
                <ConfidenceBadge confidence={pred.severity_confidence ?? 0} label="Sev" />
              </div>

              {pred.combination_rarity != null && (
                <div style={{ marginTop: 12 }}>
                  <IcdCombinationAlert rarity={pred.combination_rarity} />
                </div>
              )}

              {pred.secondary_analysis && (
                <div style={{ marginTop: 12 }}>
                  <SecondaryAnalysisAlert analysis={pred.secondary_analysis} currentSeverity={pred.predicted_severity_label} />
                </div>
              )}
            </div>

            <div style={{ padding: "24px 28px" }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 20 }}>
                <div style={{ border: "1px solid var(--border-color)", borderRadius: "var(--radius-card)", padding: "16px" }}>
                  <p style={{ fontSize: 11, fontWeight: 600, color: "var(--gray-300)", letterSpacing: "0.04em", textTransform: "uppercase", marginBottom: 4 }}>Tarif Dasar BPJS</p>
                  <p style={{ fontSize: 20, fontWeight: 700, color: "var(--near-black)" }}>{fmtRp(pred.predicted_base_tariff)}</p>
                </div>
                <div style={{ border: isOver ? "1px solid rgba(221,91,0,0.3)" : "1px solid rgba(26,174,57,0.3)", borderRadius: "var(--radius-card)", padding: "16px", background: isOver ? "#fff4e6" : "#e8f7ef" }}>
                  <p style={{ fontSize: 11, fontWeight: 600, color: isOver ? "#b45309" : "#1a7a4a", letterSpacing: "0.04em", textTransform: "uppercase", marginBottom: 4 }}>Status Tarif</p>
                  <p style={{ fontSize: 20, fontWeight: 700, color: isOver ? "#c0392b" : "#1a7a4a" }}>{isOver ? `⚠ Selisih ${fmtRp(fin.financial_gap)}` : "✓ Dalam Plafon"}</p>
                </div>
              </div>

              {rec.summary && (
                <div style={{ background: "var(--warm-white)", borderRadius: "var(--radius-card)", padding: "16px", marginBottom: 24, border: "1px solid var(--border-color)" }}>
                  <p style={{ fontSize: 11, fontWeight: 600, color: "var(--gray-500)", letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 6 }}>Rekomendasi Tindakan</p>
                  <p style={{ fontSize: 14, color: "var(--near-black)", lineHeight: 1.5 }}>{rec.summary}</p>
                </div>
              )}

              {pred.alternative_cbgs && (
                <div style={{ marginBottom: 24 }}>
                  <AlternativeCbgPanel alternatives={pred.alternative_cbgs} confidence={pred.mdc_confidence ?? 0} lookupMethod={pred.lookup_method} />
                </div>
              )}

              {shapData.length > 0 && (
                <div>
                  <p style={{ fontSize: 11, fontWeight: 600, color: "var(--gray-300)", letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 12, borderTop: "1px solid var(--border-color)", paddingTop: 20 }}>Penjelasan Model (SHAP)</p>
                  <ShapBar data={shapData} />
                </div>
              )}

              <FeedbackPanel
                predictedCbg={pred.predicted_cbg_code}
                predictionId={null}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
