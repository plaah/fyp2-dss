import React from 'react';

export const NotionBadge = ({ children, color, bg }: { children: React.ReactNode, color?: string, bg?: string }) => (
  <span style={{background:bg||"var(--blue-badge-bg)",color:color||"var(--blue-badge-text)",fontSize:12,fontWeight:600,padding:"3px 9px",borderRadius:9999,letterSpacing:"0.125px",display:"inline-block"}}>{children}</span>
);
