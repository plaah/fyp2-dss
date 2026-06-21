import React from 'react';

export const Icon = ({ name, size=16, color="currentColor", strokeWidth=1.5 }: { name: string, size?: number, color?: string, strokeWidth?: number }) => {
  const s = { width:size, height:size, display:"block", flexShrink:0 };
  const p = { fill:"none", stroke:color, strokeWidth, strokeLinecap:"round", strokeLinejoin:"round" } as const;
  
  const icons: Record<string, React.ReactElement> = {
    dashboard: <svg style={s} viewBox="0 0 24 24" {...p}><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>,
    brain: <svg style={s} viewBox="0 0 24 24" {...p}><path d="M12 4C10.3 4 9 5.3 9 7c0 .5.1 1 .4 1.4C7.5 8.9 6 10.6 6 12.5c0 1.2.5 2.3 1.4 3.1-.3.4-.4.9-.4 1.4 0 1.7 1.3 3 3 3 .5 0 1-.1 1.4-.4.5.3 1 .4 1.6.4s1.1-.1 1.6-.4c.4.3.9.4 1.4.4 1.7 0 3-1.3 3-3 0-.5-.1-1-.4-1.4.9-.8 1.4-1.9 1.4-3.1 0-1.9-1.5-3.6-3.4-4.1.3-.4.4-.9.4-1.4C18 5.3 16.7 4 15 4c-.9 0-1.7.4-2.3 1C12.5 4.4 12.3 4 12 4z"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="9" y1="12" x2="15" y2="12"/></svg>,
    chart: <svg style={s} viewBox="0 0 24 24" {...p}><polyline points="3 17 9 11 13 15 21 7"/><line x1="3" y1="21" x2="21" y2="21"/></svg>,
    download: <svg style={s} viewBox="0 0 24 24" {...p}><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>,
    shield: <svg style={s} viewBox="0 0 24 24" {...p}><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>,
    check: <svg style={s} viewBox="0 0 24 24" {...p}><polyline points="20 6 9 17 4 12"/></svg>,
    alert: <svg style={s} viewBox="0 0 24 24" {...p}><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>,
    info: <svg style={s} viewBox="0 0 24 24" {...p}><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>,
    plus: <svg style={s} viewBox="0 0 24 24" {...p}><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>,
    x: <svg style={s} viewBox="0 0 24 24" {...p}><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>,
    search: <svg style={s} viewBox="0 0 24 24" {...p}><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>,
    send: <svg style={s} viewBox="0 0 24 24" {...p}><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>,
    activity: <svg style={s} viewBox="0 0 24 24" {...p}><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>,
    star: <svg style={s} viewBox="0 0 24 24" {...p}><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>,
    file: <svg style={s} viewBox="0 0 24 24" {...p}><path d="M13 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V9z"/><polyline points="13 2 13 9 20 9"/></svg>,
    tag: <svg style={s} viewBox="0 0 24 24" {...p}><path d="M20.59 13.41l-7.17 7.17a2 2 0 01-2.83 0L2 12V2h10l8.59 8.59a2 2 0 010 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>,
    zap: <svg style={s} viewBox="0 0 24 24" {...p}><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>,
    clock: <svg style={s} viewBox="0 0 24 24" {...p}><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>,
    chevDown: <svg style={s} viewBox="0 0 24 24" {...p}><polyline points="6 9 12 15 18 9"/></svg>,
    arrowUp: <svg style={s} viewBox="0 0 24 24" {...p}><line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/></svg>,
    arrowDown: <svg style={s} viewBox="0 0 24 24" {...p}><line x1="12" y1="5" x2="12" y2="19"/><polyline points="19 12 12 19 5 12"/></svg>,
    logo: <svg style={{...s,width:28,height:28}} viewBox="0 0 100 100"><rect x="10" y="10" width="35" height="35" rx="6" fill="var(--blue)"/><rect x="55" y="10" width="35" height="35" rx="6" fill="rgba(0,117,222,0.4)"/><rect x="10" y="55" width="35" height="35" rx="6" fill="rgba(0,117,222,0.25)"/><rect x="55" y="55" width="35" height="35" rx="6" fill="rgba(0,117,222,0.6)"/></svg>,
    feedback: <svg style={s} viewBox="0 0 24 24" {...p}><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>,
  };
  return icons[name] || <svg style={s} viewBox="0 0 24 24" {...p}><circle cx="12" cy="12" r="10"/></svg>;
};
