import { useEffect, useState, useCallback } from "react"
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, BarChart, Bar, Legend,
} from "recharts"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { getStats, type StatsResponse, type RecentPrediction } from "@/lib/api"

function formatRp(n: number | null | undefined) {
  if (n == null) return "—"
  return "Rp " + n.toLocaleString("id-ID")
}

function pct(n: number) {
  return (n * 100).toFixed(1) + "%"
}

function KpiCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <Card>
      <CardContent className="pt-5">
        <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">{label}</p>
        <p className="text-2xl font-bold">{value}</p>
        {sub && <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>}
      </CardContent>
    </Card>
  )
}

function RiskBadge({ risk }: { risk: string }) {
  const r = (risk || "").toUpperCase()
  if (r === "LOW")      return <Badge variant="success">LOW</Badge>
  if (r === "HIGH")     return <Badge variant="destructive">HIGH</Badge>
  if (r === "CRITICAL") return <Badge variant="destructive">CRITICAL</Badge>
  return <Badge variant="warning">MEDIUM</Badge>
}

const RISK_COLORS: Record<string, string> = {
  LOW: "#16a34a",
  MEDIUM: "#f59e0b",
  HIGH: "#dc2626",
  CRITICAL: "#7f1d1d",
}
const PIE_COLORS = ["#0891b2", "#0e7490", "#155e75", "#164e63"]

const PAGE_SIZE = 10

export default function Dashboard() {
  const [stats, setStats] = useState<StatsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(0)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getStats()
      setStats(data)
    } catch {
      setError("Gagal memuat data. Pastikan Flask server berjalan.")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const exportCsv = () => {
    if (!stats?.recent_predictions) return
    const rows = stats.recent_predictions
    const cols = ["id","created_at","idrg_primary_icd10","idrg_icd9_procedure",
                  "ml_prediction","risk_level","financial_gap","reimbursement_probability",
                  "primary_action","actual_tariff","base_tariff","care_type","kelas","source"]
    const csv = [cols.join(","), ...rows.map(r =>
      cols.map(c => JSON.stringify((r as unknown as Record<string, unknown>)[c] ?? "")).join(",")
    )].join("\n")
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }))
    const a = document.createElement("a"); a.href = url
    a.download = `predictions_${new Date().toISOString().slice(0,10)}.csv`
    a.click(); URL.revokeObjectURL(url)
  }

  if (loading) return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Analytics Dashboard</h1>
      <p className="text-muted-foreground text-sm animate-pulse">Memuat data...</p>
    </div>
  )

  if (error || !stats) return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Analytics Dashboard</h1>
      <p className="text-destructive text-sm">{error ?? "Tidak ada data."}</p>
      <Button size="sm" onClick={load}>Coba Lagi</Button>
    </div>
  )

  // Chart data
  const historyData = (stats.prediction_history ?? []).map(p => ({
    date: p.date.slice(5),  // MM-DD
    Prediksi: p.count,
    Valid: p.valid,
  }))

  const pieData = [
    { name: "Valid", value: stats.grouping_valid_count },
    { name: "Incomplete", value: stats.coding_incomplete_count },
    { name: "Invalid", value: stats.grouping_invalid_count },
  ].filter(d => d.value > 0)

  const riskData = Object.entries(stats.risk_distribution ?? {}).map(([name, value]) => ({
    name, value, fill: RISK_COLORS[name] ?? "#94a3b8",
  }))

  // Pagination
  const rows: RecentPrediction[] = stats.recent_predictions ?? []
  const totalPages = Math.ceil(rows.length / PAGE_SIZE)
  const pageRows = rows.slice(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Analytics Dashboard</h1>
          <p className="text-muted-foreground text-sm mt-1">Ringkasan prediksi CBG &amp; kinerja keuangan BPJS</p>
        </div>
        <Button size="sm" variant="outline" onClick={exportCsv}>⬇ Export CSV</Button>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <KpiCard
          label="Total Prediksi"
          value={stats.total_predictions.toLocaleString("id-ID")}
          sub={`+${stats.today_predictions} hari ini`}
        />
        <KpiCard
          label="Grouping Valid Rate"
          value={`${stats.grouping_valid_pct.toFixed(1)}%`}
          sub={`${stats.grouping_valid_count} valid dari ${stats.total_predictions}`}
        />
        <KpiCard
          label="Avg Reimb. Prob."
          value={pct(stats.avg_reimbursement_probability)}
          sub="rata-rata probabilitas klaim diterima"
        />
        <KpiCard
          label="Total Financial Gap"
          value={formatRp(stats.total_financial_gap_idr)}
          sub="total selisih tarif vs plafon BPJS"
        />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Line chart — predictions per day */}
        <Card className="lg:col-span-2">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Prediksi per Hari (7 hari terakhir)</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={historyData} margin={{ left: 0, right: 8, top: 4, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip contentStyle={{ fontSize: 12 }} />
                <Legend iconSize={10} wrapperStyle={{ fontSize: 11 }} />
                <Line type="monotone" dataKey="Prediksi" stroke="#0891b2" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="Valid" stroke="#16a34a" strokeWidth={2} dot={false} strokeDasharray="4 2" />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Pie — outcome distribution */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Distribusi Outcome</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={180}>
              <PieChart>
                <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={60} label={({ name, percent }) => `${name} ${((percent ?? 0) * 100).toFixed(0)}%`} labelLine={false} fontSize={10}>
                  {pieData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                </Pie>
                <Tooltip contentStyle={{ fontSize: 12 }} />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Risk distribution bar chart */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium">Distribusi Risiko Klaim</CardTitle>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={120}>
            <BarChart data={riskData} margin={{ left: 0, right: 8, top: 4, bottom: 0 }}>
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip contentStyle={{ fontSize: 12 }} />
              <Bar dataKey="value" radius={[3, 3, 0, 0]}>
                {riskData.map((d, i) => <Cell key={i} fill={d.fill} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {/* Recent predictions table */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-medium">Prediksi Terbaru</CardTitle>
            <span className="text-xs text-muted-foreground">{rows.length} rekaman</span>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b bg-muted/30">
                  {["ID","ICD-10","CBG","Risk","Gap","Reimb%","Aksi","Tanggal"].map(h => (
                    <th key={h} className="px-3 py-2 text-left font-medium text-muted-foreground">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {pageRows.map(r => (
                  <tr key={r.id} className="border-b hover:bg-muted/20 transition-colors">
                    <td className="px-3 py-2 font-mono text-muted-foreground">{r.id}</td>
                    <td className="px-3 py-2 font-mono">{r.idrg_primary_icd10 || "—"}</td>
                    <td className="px-3 py-2 font-mono font-medium text-primary">{r.ml_prediction || "—"}</td>
                    <td className="px-3 py-2"><RiskBadge risk={r.risk_level} /></td>
                    <td className="px-3 py-2">{r.financial_gap ? formatRp(r.financial_gap) : "—"}</td>
                    <td className="px-3 py-2">{r.reimbursement_probability != null ? pct(r.reimbursement_probability) : "—"}</td>
                    <td className="px-3 py-2 text-muted-foreground">{r.primary_action || "—"}</td>
                    <td className="px-3 py-2 text-muted-foreground">{r.created_at ? r.created_at.slice(0, 10) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t">
              <span className="text-xs text-muted-foreground">
                Hal {page + 1} / {totalPages}
              </span>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}>
                  ‹ Prev
                </Button>
                <Button size="sm" variant="outline" onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))} disabled={page === totalPages - 1}>
                  Next ›
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
