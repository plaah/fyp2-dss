import { BrowserRouter, NavLink, Routes, Route, Navigate } from "react-router-dom"
import { Activity, LayoutDashboard, Stethoscope } from "lucide-react"
import Predict from "@/pages/Predict"
import Dashboard from "@/pages/Dashboard"
import "./App.css"

function Sidebar() {
  const base = "flex items-center gap-2.5 px-3 py-2 rounded-md text-sm font-medium transition-colors text-muted-foreground hover:text-foreground hover:bg-accent"
  const activeClass = "bg-primary/10 text-primary hover:bg-primary/10 hover:text-primary"
  return (
    <aside className="w-56 shrink-0 border-r bg-card h-screen sticky top-0 flex flex-col">
      <div className="flex items-center gap-2 px-4 py-5 border-b">
        <div className="w-7 h-7 rounded-md bg-primary flex items-center justify-center">
          <Activity className="w-4 h-4 text-primary-foreground" />
        </div>
        <div>
          <p className="text-sm font-semibold leading-tight">FYP2 DSS</p>
          <p className="text-[10px] text-muted-foreground leading-tight">BPJS CBG Predictor</p>
        </div>
      </div>

      <nav className="flex-1 px-2 py-3 space-y-0.5">
        <NavLink to="/predict" className={({ isActive }) => `${base} ${isActive ? activeClass : ""}`}>
          <Stethoscope className="w-4 h-4" />
          Prediksi CBG
        </NavLink>
        <NavLink to="/dashboard" className={({ isActive }) => `${base} ${isActive ? activeClass : ""}`}>
          <LayoutDashboard className="w-4 h-4" />
          Dashboard
        </NavLink>
      </nav>

      <div className="px-4 py-3 border-t">
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-[11px] text-muted-foreground">Flask :5001</span>
        </div>
        <p className="text-[10px] text-muted-foreground mt-0.5">Neurovi: disconnected</p>
      </div>
    </aside>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex min-h-screen bg-background">
        <Sidebar />
        <main className="flex-1 p-6 max-w-3xl">
          <Routes>
            <Route path="/" element={<Navigate to="/predict" replace />} />
            <Route path="/predict" element={<Predict />} />
            <Route path="/dashboard" element={<Dashboard />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
