import { BrowserRouter, NavLink, Routes, Route, Navigate } from "react-router-dom"
import Predict from "@/pages/Predict"
import Dashboard from "@/pages/Dashboard"
import { Icon } from "@/components/ui/icons"
import "./App.css"

function Sidebar() {
  const nav = [
    {id:"predict",icon:"brain",label:"Prediksi CBG"},
    {id:"dashboard",icon:"dashboard",label:"Dashboard"},
  ];
  
  return (
    <aside style={{width:"var(--sidebar-w)",background:"#31302e",display:"flex",flexDirection:"column",position:"fixed",left:0,top:0,bottom:0,zIndex:50}}>
      {/* Brand */}
      <div style={{padding:"24px 20px 20px",borderBottom:"1px solid rgba(255,255,255,0.07)"}}>
        <div style={{display:"flex",alignItems:"center",gap:10}}>
          <Icon name="logo" size={28}/>
          <div>
            <div style={{fontWeight:700,fontSize:14,color:"#f6f5f4",letterSpacing:"-0.25px"}}>CBG Predict</div>
            <div style={{fontSize:11,color:"rgba(255,255,255,0.3)",marginTop:1,letterSpacing:"0.02em"}}>Clinical DSS · BPJS</div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav style={{flex:1,padding:"16px 10px",display:"flex",flexDirection:"column",gap:2}}>
        <p style={{fontSize:10,color:"rgba(255,255,255,0.25)",fontWeight:600,letterSpacing:"0.08em",marginBottom:8,paddingLeft:10}}>NAVIGASI</p>
        {nav.map(n=>{
          return (
            <NavLink key={n.id} to={`/${n.id}`} style={({ isActive }) => ({
              display:"flex",alignItems:"center",gap:10,padding:"9px 10px",borderRadius:6,border:"none",
              background:isActive?"rgba(0,117,222,0.2)":"transparent",
              color:isActive?"#62aef0":"rgba(255,255,255,0.45)",
              fontWeight:isActive?600:400,fontSize:14,textAlign:"left",width:"100%",
              transition:"all .12s",letterSpacing:"0.01em", textDecoration:"none"
            })}
            >
              {({ isActive }) => (
                <>
                  <Icon name={n.icon} size={16} color={isActive?"#62aef0":"rgba(255,255,255,0.4)"} strokeWidth={isActive?2:1.5}/>
                  {n.label}
                  {isActive&&<div style={{marginLeft:"auto",width:5,height:5,borderRadius:"50%",background:"#62aef0"}}/>}
                </>
              )}
            </NavLink>
          );
        })}
      </nav>

      {/* System info */}
      <div style={{padding:"14px 18px 20px",borderTop:"1px solid rgba(255,255,255,0.07)"}}>
        <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:8}}>
          <div style={{width:28,height:28,borderRadius:"50%",background:"rgba(0,117,222,0.3)",display:"flex",alignItems:"center",justifyContent:"center"}}>
            <Icon name="shield" size={14} color="#62aef0" strokeWidth={1.5}/>
          </div>
          <div>
            <p style={{fontSize:12,fontWeight:600,color:"rgba(255,255,255,0.55)", margin:0}}>dr. Administrator</p>
            <p style={{fontSize:10,color:"rgba(255,255,255,0.25)", margin:0}}>RSUD Umum · Dokter</p>
          </div>
        </div>
        <p style={{fontSize:10,color:"rgba(255,255,255,0.2)",marginTop:4, margin:0}}>v2.4.1 · 29 April 2026</p>
      </div>
    </aside>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <div style={{ display: "flex", minHeight: "100vh", background: "var(--warm-white)", fontFamily: "Inter, sans-serif" }}>
        <Sidebar />
        <main style={{ flex: 1, padding: "40px 60px", marginLeft: "var(--sidebar-w)" }}>
          <div style={{ maxWidth: 1040, margin: "0 auto" }}>
            <Routes>
              <Route path="/" element={<Navigate to="/predict" replace />} />
              <Route path="/predict" element={<Predict />} />
              <Route path="/dashboard" element={<Dashboard />} />
            </Routes>
          </div>
        </main>
      </div>
    </BrowserRouter>
  )
}
