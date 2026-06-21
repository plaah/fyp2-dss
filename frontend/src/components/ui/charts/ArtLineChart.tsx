export const ArtLineChart = ({ series, labels, W=500, H=160 }: { series: {label:string, color:string, data:number[]}[], labels: string[], W?: number, H?: number }) => {
  const allVals = series.flatMap(s => s.data);
  const max = Math.max(...allVals)||1;
  const pad = {l:32,r:16,t:16,b:28};
  const iW = W-pad.l-pad.r, iH = H-pad.t-pad.b;
  const toXY = (data: number[]) => data.map((v,i)=>[pad.l+(i/(data.length-1))*iW, pad.t+iH-(v/max)*iH]);
  const bezier = (pts: number[][]) => pts.reduce((d,pt,i)=>{
    if(i===0) return `M ${pt[0]} ${pt[1]}`;
    const prev=pts[i-1];
    const cx=(prev[0]+pt[0])/2;
    return d+` C ${cx} ${prev[1]} ${cx} ${pt[1]} ${pt[0]} ${pt[1]}`;
  },"");
  const yTicks = [0, Math.round(max/2), max];
  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{display:"block",overflow:"visible"}}>
      <defs>
        {series.map((s,i)=>(
          <linearGradient key={i} id={`alg${i}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={s.color} stopOpacity="0.22"/>
            <stop offset="80%" stopColor={s.color} stopOpacity="0.04"/>
          </linearGradient>
        ))}
      </defs>
      {yTicks.map((v,i)=>{
        const y=pad.t+iH-(v/max)*iH;
        return <line key={i} x1={pad.l} y1={y} x2={W-pad.r} y2={y} stroke="rgba(0,0,0,0.06)" strokeWidth={1} strokeDasharray={i===0?"0":"4 3"}/>;
      })}
      {yTicks.map((v,i)=>{
        const y=pad.t+iH-(v/max)*iH;
        return <text key={i} x={pad.l-6} y={y+4} textAnchor="end" fontSize={9} fill="var(--gray-300)" fontFamily="Inter,sans-serif">{v}</text>;
      })}
      {labels.map((l,i)=>{
        const x=pad.l+(i/(labels.length-1))*iW;
        return <text key={i} x={x} y={H-6} textAnchor="middle" fontSize={9} fill="var(--gray-300)" fontFamily="Inter,sans-serif">{l}</text>;
      })}
      {series.map((s,si)=>{
        const pts = toXY(s.data);
        const d = bezier(pts);
        const areaClose = ` L ${pts[pts.length-1][0]} ${pad.t+iH} L ${pts[0][0]} ${pad.t+iH} Z`;
        return (
          <g key={si}>
            <path d={d+areaClose} fill={`url(#alg${si})`}/>
            <path d={d} fill="none" stroke={s.color} strokeWidth={si===0?2.5:1.8} strokeLinecap="round" strokeLinejoin="round" strokeDasharray={si===1?"5 3":"none"}/>
            {pts.map((pt,i)=>(
              <circle key={i} cx={pt[0]} cy={pt[1]} r={si===0?3.5:2.5} fill={s.color} stroke="white" strokeWidth={1.5}/>
            ))}
          </g>
        );
      })}
      {series.map((s,i)=>(
        <g key={i} transform={`translate(${pad.l + i*120}, 6)`}>
          <line x1={0} y1={4} x2={14} y2={4} stroke={s.color} strokeWidth={2} strokeDasharray={i===1?"4 2":"none"} strokeLinecap="round"/>
          <circle cx={7} cy={4} r={2.5} fill={s.color}/>
          <text x={18} y={8} fontSize={10} fill="var(--gray-500)" fontFamily="Inter,sans-serif" fontWeight={500}>{s.label}</text>
        </g>
      ))}
    </svg>
  );
};
