export const RiskPill = ({ risk, size="sm" }: { risk: string | null | undefined, size?: "sm" | "lg" }) => {
  const r = (risk||"").toUpperCase();
  const map: Record<string, {bg:string, color:string, dot:string}> = {
    LOW:{bg:"#e8f7ef",color:"#1a7a4a",dot:"#1aae39"},
    MEDIUM:{bg:"#fff4e6",color:"#b45309",dot:"#dd5b00"},
    HIGH:{bg:"#fde8e8",color:"#c0392b",dot:"#e53e3e"},
    CRITICAL:{bg:"#2d1515",color:"#ff8c82",dot:"#ff4040"},
  };
  const s = map[r]||map.MEDIUM;
  const fs = size==="lg" ? 13 : 11;
  return (
    <span style={{display:"inline-flex",alignItems:"center",gap:5,background:s.bg,color:s.color,fontSize:fs,fontWeight:600,padding:size==="lg"?"5px 12px":"3px 9px",borderRadius:9999,letterSpacing:"0.04em"}}>
      <span style={{width:6,height:6,borderRadius:"50%",background:s.dot,flexShrink:0}}/>
      {r}
    </span>
  );
};
