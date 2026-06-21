export const ArtDonut = ({ segments, size=130 }: { segments: {name:string, value:number, color:string}[], size?: number }) => {
  const cx=65, cy=65, r=50, ir=32;
  const total=segments.reduce((a,s)=>a+s.value,0)||1;
  let cumAngle = -Math.PI/2;
  const gap = 0.04;
  const arcs = segments.map(seg=>{
    const angle=(seg.value/total)*Math.PI*2-gap;
    const x1=cx+r*Math.cos(cumAngle+gap/2);
    const y1=cy+r*Math.sin(cumAngle+gap/2);
    cumAngle+=angle+gap;
    const x2=cx+r*Math.cos(cumAngle-gap/2);
    const y2=cy+r*Math.sin(cumAngle-gap/2);
    const xi1=cx+ir*Math.cos(cumAngle-gap/2);
    const yi1=cy+ir*Math.sin(cumAngle-gap/2);
    const xi2=cx+ir*Math.cos(cumAngle-angle-gap/2);
    const yi2=cy+ir*Math.sin(cumAngle-angle-gap/2);
    const large=angle>Math.PI?1:0;
    return {...seg, d:`M ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2} L ${xi1} ${yi1} A ${ir} ${ir} 0 ${large} 0 ${xi2} ${yi2} Z`, pct:((seg.value/total)*100).toFixed(0)};
  });
  return (
    <svg width={size} height={size} viewBox="0 0 130 130">
      <defs>
        {arcs.map((a,i)=>(
          <radialGradient key={i} id={`dg${i}`} cx="50%" cy="50%" r="50%">
            <stop offset="30%" stopColor={a.color} stopOpacity="1"/>
            <stop offset="100%" stopColor={a.color} stopOpacity="0.7"/>
          </radialGradient>
        ))}
      </defs>
      {arcs.map((a,i)=>(
        <path key={i} d={a.d} fill={`url(#dg${i})`} opacity={0.92}>
          <title>{a.name}: {a.pct}%</title>
        </path>
      ))}
      <circle cx={cx} cy={cy} r={ir} fill="white"/>
      <text x={cx} y={cy-4} textAnchor="middle" fontSize={18} fontWeight="700" fill="var(--near-black)" fontFamily="Inter,sans-serif">{arcs[0]?.pct||0}%</text>
      <text x={cx} y={cy+13} textAnchor="middle" fontSize={9} fill="var(--gray-300)" fontFamily="Inter,sans-serif">{arcs[0]?.name||"Valid"}</text>
    </svg>
  );
};
