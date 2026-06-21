import { useEffect, useState, useCallback } from "react"
import { Icon } from "@/components/ui/icons"
import { KpiCard } from "@/components/ui/KpiCard"
import { ArtLineChart } from "@/components/ui/charts/ArtLineChart"
import { ArtDonut } from "@/components/ui/charts/ArtDonut"
import { RiskBubbleChart } from "@/components/ui/charts/RiskBubbleChart"
import { RiskPill } from "@/components/ui/RiskPill"
import { NotionBadge } from "@/components/ui/notion-badge"
import { ImpactFunnel } from "@/components/ui/ImpactFunnel"
import { ConfirmationPanel } from "@/components/ui/ConfirmationPanel"
import { TrustScoreCard } from "@/components/ui/TrustScoreCard"
import { AntrianReview } from "@/components/ui/AntrianReview"
import { getStats, type StatsResponse, type RecentPrediction } from "@/lib/api"

const PAGE_SIZE = 5;

const fmtRp = (n: number | null | undefined) => n == null ? "—" : "Rp " + Number(n).toLocaleString("id-ID");
const fmtPct = (n: number | null | undefined) => n == null ? "—" : (n * 100).toFixed(1) + "%";

export default function Dashboard() {
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [hovRow, setHovRow] = useState<number | string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getStats();
      setStats(data);
    } catch {
      setError("Gagal memuat data. Pastikan Flask server berjalan.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load() }, [load]);

  const exportCsv = () => {
    if (!stats?.recent_predictions) return;
    const rows = stats.recent_predictions;
    const cols: (keyof RecentPrediction)[] = ["id","created_at","idrg_primary_icd10","idrg_icd9_procedure","ml_prediction","risk_level","financial_gap","reimbursement_probability","primary_action","actual_tariff","base_tariff","care_type","kelas","source"];
    const csv = [cols.join(","), ...rows.map(r => cols.map(c => JSON.stringify(r[c] ?? "")).join(","))].join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    const a = document.createElement("a"); a.href = url;
    a.download = `predictions_${new Date().toISOString().slice(0,10)}.csv`;
    a.click(); URL.revokeObjectURL(url);
  };

  if (loading) return (
    <div style={{display:"flex",flexDirection:"column",gap:24,animation:"fadeUp .3s ease"}}>
      <h1 style={{fontSize:32,fontWeight:700,color:"var(--near-black)",letterSpacing:"-0.75px",lineHeight:1.1}}>Analytics Dashboard</h1>
      <p style={{fontSize:15,color:"var(--gray-500)",marginTop:6,fontWeight:500,animation:"pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite"}}>Memuat data...</p>
    </div>
  );

  if (error || !stats) return (
    <div style={{display:"flex",flexDirection:"column",gap:24,animation:"fadeUp .3s ease"}}>
      <h1 style={{fontSize:32,fontWeight:700,color:"var(--near-black)",letterSpacing:"-0.75px",lineHeight:1.1}}>Analytics Dashboard</h1>
      <p style={{color:"#c0392b"}}>{error ?? "Tidak ada data."}</p>
      <button onClick={load} style={{width:120,padding:"8px 14px",background:"var(--blue)",color:"white",borderRadius:"var(--radius-btn)",border:"none",fontWeight:600,cursor:"pointer"}}>Coba Lagi</button>
    </div>
  );

  const rows = stats.recent_predictions || [];
  const totalPages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const pageRows = rows.slice(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE);

  const hist = stats.prediction_history || [];
  const lineSeries = [
    { label: "Total Prediksi", color: "var(--blue)", data: hist.map(h => h.count) },
    { label: "Valid", color: "var(--teal)", data: hist.map(h => h.valid) },
  ];
  const lineLabels = hist.map(h => {
    const parts = h.date.split("-");
    return parts.length >= 2 ? `${parts[1]}/${parts[2] || "01"}` : h.date;
  });

  const donutSegs = [
    { name: "Valid", value: stats.grouping_valid_count, color: "var(--teal)" },
    { name: "Incomplete", value: stats.coding_incomplete_count, color: "var(--orange)" },
    { name: "Invalid", value: stats.grouping_invalid_count, color: "#e53e3e" },
  ].filter(d => d.value > 0);

  const riskBubbles = Object.entries(stats.risk_distribution || {}).map(([name, value]) => ({ name, value }));

  const criticalCount = stats.risk_distribution?.CRITICAL || 0;
  const highCount = stats.risk_distribution?.HIGH || 0;
  const incCount = stats.coding_incomplete_count || 0;

  return (
    <div style={{display:"flex",flexDirection:"column",gap:24,animation:"fadeUp .3s ease"}}>
      {/* Header */}
      <div style={{display:"flex",alignItems:"flex-start",justifyContent:"space-between"}}>
        <div>
          <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:6}}>
            <NotionBadge>Data Real-time</NotionBadge>
            <NotionBadge bg="#e8f7ef" color="#1a7a4a">+{stats.today_predictions} prediksi hari ini</NotionBadge>
          </div>
          <h1 style={{fontSize:32,fontWeight:700,color:"var(--near-black)",letterSpacing:"-0.75px",lineHeight:1.1}}>Analytics Dashboard</h1>
          <p style={{fontSize:15,color:"var(--gray-500)",marginTop:6,fontWeight:500}}>Ringkasan prediksi CBG & kinerja keuangan BPJS</p>
        </div>
        <button onClick={exportCsv} style={{display:"flex",alignItems:"center",gap:7,padding:"8px 14px",borderRadius:"var(--radius-btn)",border:"1px solid rgba(0,0,0,0.12)",background:"var(--white)",fontSize:13,fontWeight:600,cursor:"pointer",color:"var(--near-black)",boxShadow:"var(--shadow-card)",transition:"all .12s"}}
          onMouseEnter={e=>{e.currentTarget.style.background="var(--warm-white)"}}
          onMouseLeave={e=>{e.currentTarget.style.background="var(--white)"}}>
          <Icon name="download" size={14} color="var(--gray-500)" strokeWidth={2}/>
          Export CSV
        </button>
      </div>

      {/* KPI grid */}
      <div style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:12}}>
        <KpiCard label="Total Prediksi" value={stats.total_predictions.toLocaleString("id-ID")} sub={`+${stats.today_predictions} hari ini`} sparkData={hist.map(h=>h.count)} accentColor="var(--blue)"/>
        <KpiCard label="Grouping Valid Rate" value={`${stats.grouping_valid_pct.toFixed(1)}%`} sub={`${stats.grouping_valid_count} dari ${stats.total_predictions} valid`} sparkData={hist.map(h=>Math.round((h.valid/h.count)*100))} accentColor="var(--teal)"/>
        <KpiCard label="Avg Reimb. Prob." value={fmtPct(stats.avg_reimbursement_probability)} sub="Rata-rata probabilitas klaim diterima" accentColor="var(--orange)"/>
        <KpiCard label="Financial Gap" value={fmtRp(stats.total_financial_gap_idr)} sub="Selisih tarif vs plafon BPJS" accentColor="#e53e3e"/>
      </div>

      {/* Charts row */}
      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr 1fr",gap:12}}>
        <div style={{gridColumn:"1/3",background:"var(--white)",borderRadius:"var(--radius-card)",border:"1px solid var(--border-color)",boxShadow:"var(--shadow-card)",padding:"20px 24px"}}>
          <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",marginBottom:16}}>
            <div>
              <p style={{fontWeight:700,fontSize:15,color:"var(--near-black)",letterSpacing:"-0.25px"}}>Prediksi per Hari</p>
              <p style={{fontSize:12,color:"var(--gray-300)",marginTop:2}}>Volume & akurasi 7 hari terakhir</p>
            </div>
            <Icon name="chart" size={18} color="var(--gray-300)" strokeWidth={1.5}/>
          </div>
          {lineLabels.length > 0 ? <ArtLineChart series={lineSeries} labels={lineLabels} W={520} H={160}/> : <p style={{fontSize:12,color:"var(--gray-500)"}}>Belum ada data history.</p>}
        </div>

        <div style={{background:"var(--white)",borderRadius:"var(--radius-card)",border:"1px solid var(--border-color)",boxShadow:"var(--shadow-card)",padding:"20px 22px"}}>
          <p style={{fontWeight:700,fontSize:15,color:"var(--near-black)",letterSpacing:"-0.25px",marginBottom:2}}>Distribusi Outcome</p>
          <p style={{fontSize:12,color:"var(--gray-300)",marginBottom:14}}>Status grouping INA-CBGs</p>
          <div style={{display:"flex",alignItems:"center",gap:16}}>
            {donutSegs.length > 0 ? <ArtDonut segments={donutSegs} size={120}/> : <p style={{fontSize:12,color:"var(--gray-500)"}}>Belum ada data distribusi.</p>}
            <div style={{display:"flex",flexDirection:"column",gap:8}}>
              {donutSegs.map(s=>(
                <div key={s.name} style={{display:"flex",alignItems:"center",gap:8}}>
                  <div style={{width:8,height:8,borderRadius:2,background:s.color,flexShrink:0}}/>
                  <div>
                    <p style={{fontSize:12,fontWeight:600,color:"var(--near-black)"}}>{s.name}</p>
                    <p style={{fontSize:11,color:"var(--gray-300)"}}>{s.value.toLocaleString("id-ID")}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Risk bubbles + Action panel */}
      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12}}>
        <div style={{background:"var(--white)",borderRadius:"var(--radius-card)",border:"1px solid var(--border-color)",boxShadow:"var(--shadow-card)",padding:"20px 24px"}}>
          <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",marginBottom:4}}>
            <p style={{fontWeight:700,fontSize:15,color:"var(--near-black)",letterSpacing:"-0.25px"}}>Distribusi Risiko Klaim</p>
            <Icon name="shield" size={16} color="var(--gray-300)" strokeWidth={1.5}/>
          </div>
          <p style={{fontSize:12,color:"var(--gray-300)",marginBottom:16}}>Volume kasus per level risiko</p>
          {riskBubbles.length > 0 ? <RiskBubbleChart data={riskBubbles} W={340} H={135}/> : <p style={{fontSize:12,color:"var(--gray-500)"}}>Belum ada data risiko.</p>}
        </div>

        <div style={{background:"var(--warm-white)",borderRadius:"var(--radius-card)",border:"1px solid var(--border-color)",boxShadow:"var(--shadow-card)",padding:"20px 24px"}}>
          <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",marginBottom:16}}>
            <div>
              <p style={{fontWeight:700,fontSize:15,color:"var(--near-black)",letterSpacing:"-0.25px"}}>Perlu Tindakan</p>
              <p style={{fontSize:12,color:"var(--gray-300)",marginTop:2}}>Kasus memerlukan review segera</p>
            </div>
            <Icon name="alert" size={16} color="var(--orange)" strokeWidth={1.5}/>
          </div>
          {[
            {icon:"zap",label:"CRITICAL — Eskalasi",count:criticalCount,color:"#7f1d1d",bg:"#fee2e2",sub:"Perlu perhatian supervisor"},
            {icon:"alert",label:"HIGH — Review Dokumen",count:highCount,color:"var(--orange)",bg:"#fff4e6",sub:"Lengkapi berkas klaim"},
            {icon:"file",label:"Koding Tidak Lengkap",count:incCount,color:"var(--blue)",bg:"var(--blue-badge-bg)",sub:"Update kode ICD"},
          ].map(item=>(
            <div key={item.label} style={{background:item.bg,borderRadius:8,padding:"10px 14px",display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:8,border:"1px solid rgba(0,0,0,0.06)"}}>
              <div style={{display:"flex",alignItems:"flex-start",gap:10}}>
                <Icon name={item.icon} size={14} color={item.color} strokeWidth={2}/>
                <div>
                  <p style={{fontSize:12,fontWeight:600,color:item.color}}>{item.label}</p>
                  <p style={{fontSize:11,color:"var(--gray-500)",marginTop:1}}>{item.sub}</p>
                </div>
              </div>
              <span style={{fontSize:22,fontWeight:700,color:item.color,fontFamily:"JetBrains Mono,monospace",letterSpacing:"-1px"}}>{item.count}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Impact Funnel */}
      <ImpactFunnel stats={stats} />

      {/* Confirmation Panel + Trust Score — side by side */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <ConfirmationPanel stats={stats} />
        <TrustScoreCard stats={stats} />
      </div>

      {/* Antrian Review Casemix — full width */}
      <AntrianReview stats={stats} onConfirmed={load} />

      {/* Table */}
      <div style={{background:"var(--white)",borderRadius:"var(--radius-card)",border:"1px solid var(--border-color)",boxShadow:"var(--shadow-card)",overflow:"hidden"}}>
        <div style={{padding:"18px 22px 14px",display:"flex",justifyContent:"space-between",alignItems:"center",borderBottom:"1px solid var(--border-color)"}}>
          <div>
            <p style={{fontWeight:700,fontSize:15,color:"var(--near-black)",letterSpacing:"-0.25px"}}>Prediksi Terbaru</p>
            <p style={{fontSize:12,color:"var(--gray-300)",marginTop:1}}>{rows.length} rekaman</p>
          </div>
          <div style={{display:"flex",alignItems:"center",gap:8}}>
            <button onClick={()=>setPage(p=>Math.max(0,p-1))} disabled={page===0}
              style={{padding:"5px 11px",borderRadius:"var(--radius-btn)",border:"1px solid rgba(0,0,0,0.12)",background:"var(--white)",fontSize:12,fontWeight:500,cursor:page===0?"not-allowed":"pointer",color:page===0?"var(--gray-300)":"var(--near-black)",transition:"all .1s"}}>← Prev</button>
            <span style={{fontSize:12,color:"var(--gray-500)"}}>{page+1}/{totalPages}</span>
            <button onClick={()=>setPage(p=>Math.min(totalPages-1,p+1))} disabled={page===totalPages-1}
              style={{padding:"5px 11px",borderRadius:"var(--radius-btn)",border:"1px solid rgba(0,0,0,0.12)",background:"var(--white)",fontSize:12,fontWeight:500,cursor:page===totalPages-1?"not-allowed":"pointer",color:page===totalPages-1?"var(--gray-300)":"var(--near-black)"}}>Next →</button>
          </div>
        </div>
        <div style={{overflowX:"auto"}}>
          <table style={{width:"100%",borderCollapse:"collapse"}}>
            <thead>
              <tr style={{background:"var(--warm-white)"}}>
                {["#","ICD-10","CBG","Risiko","Financial Gap","Reimb. %","Tindakan","Tanggal"].map(h=>(
                  <th key={h} style={{padding:"9px 16px",textAlign:"left",fontSize:11,fontWeight:600,color:"var(--gray-300)",letterSpacing:"0.05em",textTransform:"uppercase",whiteSpace:"nowrap",borderBottom:"1px solid var(--border-color)"}}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {pageRows.map(r=>(
                <tr key={r.id} onMouseEnter={()=>setHovRow(r.id)} onMouseLeave={()=>setHovRow(null)}
                  style={{borderBottom:"1px solid rgba(0,0,0,0.05)",background:hovRow===r.id?"var(--blue-badge-bg)":"var(--white)",transition:"background .1s"}}>
                  <td style={{padding:"12px 16px",fontSize:12,fontFamily:"JetBrains Mono,monospace",color:"var(--gray-300)"}}>#{r.id}</td>
                  <td style={{padding:"12px 16px",fontSize:13,fontFamily:"JetBrains Mono,monospace",fontWeight:500,color:"var(--blue)"}}>{r.idrg_primary_icd10 || "—"}</td>
                  <td style={{padding:"12px 16px",fontSize:13,fontFamily:"JetBrains Mono,monospace",fontWeight:700,color:"var(--near-black)"}}>{r.ml_prediction || "—"}</td>
                  <td style={{padding:"12px 16px"}}><RiskPill risk={r.risk_level}/></td>
                  <td style={{padding:"12px 16px",fontSize:13,fontWeight:600,color:(r.financial_gap||0)>0?"#c0392b":"#1a7a4a"}}>{(r.financial_gap||0)>0?fmtRp(r.financial_gap):"✓ Dalam Plafon"}</td>
                  <td style={{padding:"12px 16px",fontSize:13,fontFamily:"JetBrains Mono,monospace",color:"var(--near-black)"}}>{fmtPct(r.reimbursement_probability)}</td>
                  <td style={{padding:"12px 16px",fontSize:12,color:"var(--gray-500)"}}>{r.primary_action || "—"}</td>
                  <td style={{padding:"12px 16px",fontSize:12,fontFamily:"JetBrains Mono,monospace",color:"var(--gray-300)"}}>{r.created_at?.slice(0,10) || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
