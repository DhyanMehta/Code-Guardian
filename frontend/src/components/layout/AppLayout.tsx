import React, { ReactNode, useEffect, useState } from 'react';
import { Navbar } from './Navbar';

export interface AppLayoutProps {
  children: ReactNode;
  contextBar?: ReactNode;
}

export const AppLayout: React.FC<AppLayoutProps> = ({ children, contextBar }) => {
  const [online, setOnline] = useState(navigator.onLine);
  useEffect(() => { const update = () => setOnline(navigator.onLine); window.addEventListener('online', update); window.addEventListener('offline', update); return () => { window.removeEventListener('online', update); window.removeEventListener('offline', update); }; }, []);
  return (
    <div className="min-h-screen flex flex-col bg-canvas text-neutral-100 font-sans selection:bg-primary-500/30 selection:text-primary-200 antialiased">
      <Navbar />
      {!online && (
        <div role="status" className="bg-severity-medium-bg border-b border-severity-medium-border py-2 px-4 text-center text-xs font-medium text-severity-medium">
          Offline. Automatic updates are paused until your connection returns.
        </div>
      )}
      {contextBar}
      <main className="flex-1 min-w-0 w-full max-w-7xl mx-auto px-4 sm:px-6 py-6 [overflow-wrap:anywhere]">
        {children}
      </main>
      <footer className="border-t border-neutral-800/80 bg-neutral-950/40 py-6 text-center text-xs font-mono text-neutral-400">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 flex flex-col sm:flex-row items-center justify-between gap-3">
          <span>CodeGuardian AI — Autonomous Multi-Agent DevSecOps</span>
          <span className="text-[11px] text-neutral-400">SOC2 Type II & OWASP ASVS Compliant Engine</span>
        </div>
      </footer>
    </div>
  );
};
