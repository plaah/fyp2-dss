import { useState, useEffect, useRef, useCallback } from "react"
import { BarChart, Bar, XAxis, YAxis, Cell, ResponsiveContainer, Tooltip } from "recharts"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import { runFullAssessment, searchIcd, submitFeedback, type FullAssessmentResponse, type IcdResult } from "@/lib/api"

interface SelectedIcd {
  code: string
  description: string
}

function IcdSearchField({
  label,
  placeholder,
  type,
  onSelect,
}: {
  label: string
  placeholder: string
  type: "diagnosis" | "procedure"
  onSelect: (icd: SelectedIcd | null) => void
}) {
  const [query, setQuery] = useState("")
  const [results, setResults] = useState<IcdResult[]>([])
  const [selected, setSelected] = useState<SelectedIcd | null>(null)
  const [loading, setLoading] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const search = useCallback(async (q: string) => {
    if (!q || q.length < 2) { setResults([]); return }
    setLoading(true)
    try {
      const data = await searchIcd(q, type)
      setResults(data.slice(0, 6))
    } catch {
      setResults([])
    } finally {
      setLoading(false)
    }
  }, [type])

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => search(query), 300)
    return () => { if (timerRef.current) clearTimeout(timerRef.current) }
  }, [query, search])

  const pick = (r: IcdResult) => {
    const item = { code: r.code, description: r.description }
    setSelected(item)
    onSelect(item)
    setQuery("")
    setResults([])
  }

  const clear = () => {
    setSelected(null)
    onSelect(null)
    setQuery("")
    setResults([])
  }

  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      {selected ? (
        <div className="flex items-center gap-2 flex-wrap">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 text-primary border border-primary/20 px-3 py-1 text-sm font-medium">
            {selected.code} · {selected.description.slice(0, 40)}{selected.description.length > 40 ? "…" : ""}
            <button onClick={clear} className="ml-1 text-primary/60 hover:text-primary font-bold">×</button>
          </span>
        </div>
      ) : (
        <div className="relative">
          <Input
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder={placeholder}
          />
          {(results.length > 0 || loading) && (
            <div className="absolute z-10 top-full mt-1 w-full bg-popover border rounded-md shadow-lg overflow-hidden">
              {loading && <div className="px-3 py-2 text-sm text-muted-foreground">Mencari...</div>}
              {results.map(r => (
                <button
                  key={r.code}
                  onClick={() => pick(r)}
                  className="w-full text-left px-3 py-2 text-sm hover:bg-accent transition-colors border-b last:border-0"
                >
                  <span className="font-mono text-primary font-medium">{r.code}</span>
                  <span className="text-muted-foreground ml-2">{r.description}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function RiskBadge({ risk }: { risk: string }) {
  const level = (risk || "").toUpperCase()
  if (level === "LOW")  return <Badge variant="success">LOW Risk</Badge>
  if (level === "HIGH") return <Badge variant="destructive">HIGH Risk</Badge>
  return <Badge variant="warning">MEDIUM Risk</Badge>
}

function LookupBadge({ method }: { method: string }) {
  if (method === "exact")   return <Badge variant="success">Exact Match</Badge>
  if (method === "none")    return <Badge variant="destructive">No Match</Badge>
  return <Badge variant="warning">Fallback</Badge>
}

function formatRp(n: number | undefined | null) {
  if (n == null) return "—"
  return "Rp " + n.toLocaleString("id-ID")
}

export default function Predict() {
  const [diagIcd, setDiagIcd] = useState<SelectedIcd | null>(null)
  const [procIcd, setProcIcd] = useState<SelectedIcd | null>(null)
  const [careType, setCareType] = useState("outp")
  const [kelas, setKelas] = useState("kelas_3")
  const [actualTariff, setActualTariff] = useState("")
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<FullAssessmentResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Feedback state
  const [fbOpen, setFbOpen] = useState(false)
  const [fbCbg, setFbCbg] = useState("")
  const [fbNotes, setFbNotes] = useState("")
  const [fbSent, setFbSent] = useState(false)

  const handleSubmit = async () => {
    if (!diagIcd) { setError("Pilih diagnosis terlebih dahulu."); return }
    setError(null)
    setLoading(true)
    setResult(null)
    setFbOpen(false)
    setFbSent(false)
    try {
      const payload = {
        primary_icd10:   diagIcd.code,
        icd9_procedure:  procIcd?.code ?? "",
        inacbg_icd10:    diagIcd.code,
        care_type:       careType,
        entry_type:      careType === "outp" ? "gp" : "sp",
        kelas,
        episodes:        1,
        actual_tariff:   parseFloat(actualTariff) || 0,
      }
      const data = await runFullAssessment(payload)
      setResult(data)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Gagal menghubungi server.")
    } finally {
      setLoading(false)
    }
  }

  const handleFeedback = async () => {
    if (!fbCbg.trim()) return
    try {
      await submitFeedback({
        prediction_id:  null,
        submitted_cbg:  result?.prediction?.predicted_cbg_code ?? "",
        correct_cbg:    fbCbg.trim(),
        is_correct:     false,
        notes:          fbNotes,
      })
      setFbSent(true)
      setFbOpen(false)
    } catch {
      /* silent */
    }
  }

  const pred  = result?.prediction
  const fin   = result?.financial
  const rec   = result?.recommendation
  const isOver = (fin?.financial_gap ?? 0) > 0

  const shapData = (pred?.shap_explanation ?? []).map(s => ({
    feature: s.feature.replace(/_/g, " "),
    impact:  Math.abs(s.impact),
    direction: s.direction,
  }))

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Prediction Tool</h1>
        <p className="text-muted-foreground text-sm mt-1">Prediksi CBG &amp; Tarif BPJS sebelum koding Casemix</p>
      </div>

      {/* Input Form */}
      <Card>
        <CardHeader className="pb-4">
          <CardTitle className="text-base">Data Klinis</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <IcdSearchField
            label="Diagnosis Utama (ICD-10)"
            placeholder="Ketik diagnosis — contoh: hipertensi, pneumonia..."
            type="diagnosis"
            onSelect={setDiagIcd}
          />

          <IcdSearchField
            label="Prosedur (ICD-9-CM) — opsional"
            placeholder="Ketik prosedur — contoh: tensi, nebulisasi, TURP..."
            type="procedure"
            onSelect={setProcIcd}
          />

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label>Jenis Rawat</Label>
              <Select value={careType} onValueChange={setCareType}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="outp">Rawat Jalan</SelectItem>
                  <SelectItem value="inp">Rawat Inap</SelectItem>
                  <SelectItem value="emd">UGD / Gawat Darurat</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Kelas Perawatan</Label>
              <Select value={kelas} onValueChange={setKelas}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="kelas_1">Kelas 1</SelectItem>
                  <SelectItem value="kelas_2">Kelas 2</SelectItem>
                  <SelectItem value="kelas_3">Kelas 3</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-1.5">
            <Label>Tarif yang Diajukan (Rp)</Label>
            <Input
              type="number"
              placeholder="contoh: 196100"
              value={actualTariff}
              onChange={e => setActualTariff(e.target.value)}
            />
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}

          <Button onClick={handleSubmit} disabled={loading} className="w-full">
            {loading ? "Memproses..." : "Prediksi CBG & Tarif →"}
          </Button>
        </CardContent>
      </Card>

      {/* Result */}
      {result && pred && fin && rec && (
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs text-muted-foreground uppercase tracking-widest mb-1">CBG Terprediksi</p>
                <h2 className="text-4xl font-bold text-primary font-mono tracking-wide">{pred.predicted_cbg_code || "—"}</h2>
                <p className="text-sm text-muted-foreground mt-1">{pred.predicted_cbg_description || ""}</p>
              </div>
              <RiskBadge risk={fin.risk_level} />
            </div>

            <div className="flex flex-wrap gap-1.5 mt-3">
              <Badge variant="outline">MDC: {pred.predicted_mdc}</Badge>
              <Badge variant="outline">Severity: {pred.predicted_severity}</Badge>
              <LookupBadge method={pred.lookup_method} />
              <Badge variant="secondary">MDC {Math.round((pred.mdc_confidence ?? 0) * 100)}%</Badge>
              <Badge variant="secondary">Sev {Math.round((pred.severity_confidence ?? 0) * 100)}%</Badge>
            </div>
          </CardHeader>

          <CardContent className="space-y-4">
            <Separator />

            {/* Financial metrics */}
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-lg border p-3">
                <p className="text-xs text-muted-foreground mb-1">Tarif Dasar BPJS</p>
                <p className="text-lg font-semibold">{formatRp(pred.predicted_base_tariff)}</p>
              </div>
              <div className={`rounded-lg border p-3 ${isOver ? "border-amber-300 bg-amber-50" : "border-emerald-300 bg-emerald-50"}`}>
                <p className="text-xs text-muted-foreground mb-1">Status Tarif</p>
                <p className={`text-lg font-semibold ${isOver ? "text-amber-700" : "text-emerald-700"}`}>
                  {isOver ? `⚠ Selisih ${formatRp(fin.financial_gap)}` : "✓ Dalam Plafon"}
                </p>
              </div>
            </div>

            {/* Recommendation */}
            {rec.summary && (
              <div className="rounded-lg bg-muted/50 px-4 py-3">
                <p className="text-xs text-muted-foreground mb-1 font-medium uppercase tracking-wide">Rekomendasi</p>
                <p className="text-sm">{rec.summary}</p>
              </div>
            )}

            {/* SHAP chart */}
            {shapData.length > 0 && (
              <>
                <Separator />
                <div>
                  <p className="text-xs text-muted-foreground mb-3 font-medium uppercase tracking-wide">Faktor Penentu Prediksi MDC</p>
                  <ResponsiveContainer width="100%" height={90}>
                    <BarChart data={shapData} layout="vertical" margin={{ left: 0, right: 16, top: 0, bottom: 0 }}>
                      <XAxis type="number" hide />
                      <YAxis type="category" dataKey="feature" width={110} tick={{ fontSize: 11 }} />
                      <Tooltip contentStyle={{ fontSize: 12 }} />
                      <Bar dataKey="impact" radius={[0, 3, 3, 0]}>
                        {shapData.map((s, i) => (
                          <Cell key={i} fill={s.direction === "positive" ? "#16a34a" : "#dc2626"} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </>
            )}

            {/* Feedback */}
            <Separator />
            {fbSent ? (
              <p className="text-sm text-emerald-600">✓ Laporan diterima — terima kasih.</p>
            ) : (
              <div>
                <button
                  onClick={() => setFbOpen(o => !o)}
                  className="text-xs text-muted-foreground underline underline-offset-2 hover:text-foreground"
                >
                  Hasil tidak akurat? Laporkan {fbOpen ? "▴" : "▾"}
                </button>
                {fbOpen && (
                  <div className="mt-3 space-y-2">
                    <div className="flex items-center gap-2">
                      <Label className="shrink-0 text-xs">CBG yang benar:</Label>
                      <Input
                        value={fbCbg}
                        onChange={e => setFbCbg(e.target.value)}
                        placeholder="contoh: Q-5-44-0"
                        className="h-8 text-sm"
                      />
                    </div>
                    <div className="flex items-center gap-2">
                      <Label className="shrink-0 text-xs">Catatan:</Label>
                      <Input
                        value={fbNotes}
                        onChange={e => setFbNotes(e.target.value)}
                        placeholder="alasan (opsional)"
                        className="h-8 text-sm"
                      />
                    </div>
                    <Button size="sm" onClick={handleFeedback} disabled={!fbCbg.trim()}>
                      Kirim Laporan
                    </Button>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
