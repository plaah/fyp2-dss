export const RiskBubbleChart = ({ data, W=340, H=130 }: { data: {name:string, value:number}[], W?: number, H?: number }) => {
  const max = Math.max(...data.map(d=>d.value))||1;
  const colors: Record<string, string> = {LOW:"#1aae39",MEDIUM:"#dd5b00",HIGH:"#e53e3e",CRITICAL:"#7f1d1d",UNKNOWN:"#9ca3af"};
  // Positions are derived from data length so any number of risk levels fits
  // (e.g. a 5th "UNKNOWN" bucket) without overflowing the hardcoded layout.
  const n = data.length;
  const positions = data.map((_,i)=>({
    x: n<=1 ? W/2 : 40+(i/(n-1))*(W-80),
    y: i%2===0 ? H*0.5 : H*0.35,
  }));
  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{display:"block",overflow:"visible"}}>
      <defs>
        {data.map((d,i)=>(
          <radialGradient key={i} id={`bg${i}`} cx="35%" cy="35%" r="65%">
            <stop offset="0%" stopColor={colors[d.name]||"#ccc"} stopOpacity="0.3"/>
            <stop offset="100%" stopColor={colors[d.name]||"#ccc"} stopOpacity="0.08"/>
          </radialGradient>
        ))}
      </defs>
      {data.map((_,i)=>i<data.length-1&&(
        <line key={i} x1={positions[i].x} y1={positions[i].y} x2={positions[i+1].x} y2={positions[i+1].y} stroke="rgba(0,0,0,0.06)" strokeWidth={1} strokeDasharray="3 3"/>
      ))}
      {data.map((d,i)=>{
        const r = 18+Math.round((d.value/max)*38);
        const pos = positions[i]||{x:60+i*80,y:65};
        const c = colors[d.name]||"#ccc";
        return (
          <g key={i}>
            <circle cx={pos.x} cy={pos.y} r={r+8} fill={`url(#bg${i})`}/>
            <circle cx={pos.x} cy={pos.y} r={r} fill={c} opacity={0.15}/>
            <circle cx={pos.x} cy={pos.y} r={r-4} fill={c} opacity={0.25}/>
            <circle cx={pos.x} cy={pos.y} r={r-10} fill={c} opacity={0.7}/>
            <text x={pos.x} y={pos.y+1} textAnchor="middle" dominantBaseline="middle" fontSize={r>30?13:11} fontWeight="700" fill="white" fontFamily="Inter,sans-serif">{d.value}</text>
            <text x={pos.x} y={pos.y+r+13} textAnchor="middle" fontSize={10} fill={c} fontFamily="Inter,sans-serif" fontWeight="600">{d.name}</text>
          </g>
        );
      })}
    </svg>
  );
};
