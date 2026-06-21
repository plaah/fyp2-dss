import { Icon } from './icons';

export const KpiCard = ({ label, value, sub, trend, sparkData, accentColor }: { label: string, value: string | number, sub?: string, trend?: number | null, sparkData?: number[], accentColor?: string }) => {
  const color = accentColor||"var(--blue)";
  const counts = (sparkData||[40,45,38,52,48,60,47]).map(v=>Number.isFinite(v)?v:0);
  const max = Math.max(...counts)||1;
  const pts = counts.map((v,i)=>`${counts.length<2?40:(i/(counts.length-1))*80},${24-(v/max)*20}`).join(" ");
  return (
    <div style={{background:"var(--white)",borderRadius:12,border:"1px solid var(--border-color)",boxShadow:"var(--shadow-card)",padding:"20px 22px",position:"relative",overflow:"hidden"}}>
      <div style={{position:"absolute",right:16,bottom:16,opacity:0.18}}>
        <svg width={80} height={24} viewBox="0 0 80 24" style={{display:"block"}}>
          <polyline points={pts} fill="none" stroke={color} strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </div>
      <p style={{fontSize:11,fontWeight:600,color:"var(--gray-300)",letterSpacing:"0.06em",textTransform:"uppercase",marginBottom:10}}>{label}</p>
      <p style={{fontSize:30,fontWeight:700,color:"var(--near-black)",lineHeight:1,letterSpacing:"-0.5px",marginBottom:4}}>{value}</p>
      {sub&&<p style={{fontSize:12,color:"var(--gray-500)",marginTop:4}}>{sub}</p>}
      {trend!=null&&(
        <div style={{display:"flex",alignItems:"center",gap:4,marginTop:8}}>
          <Icon name={trend>0?"arrowUp":"arrowDown"} size={12} color={trend>0?"#1aae39":"#dd5b00"} strokeWidth={2.5}/>
          <span style={{fontSize:11,fontWeight:600,color:trend>0?"#1a7a4a":"#b45309"}}>{Math.abs(trend)}% vs kemarin</span>
        </div>
      )}
    </div>
  );
};
