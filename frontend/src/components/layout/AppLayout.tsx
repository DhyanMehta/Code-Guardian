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
    <div className="min-h-screen flex flex-col bg-canvas text-neutral-100 font-sans selection:bg-primary-500/30 selection:text-primary-200">
      <Navbar />
      {!online && <p role="status" className="p-3 text-center text-severity-medium">Offline. Automatic updates are paused until your connection returns.</p>}
      {contextBar}
      <main className="flex-1 min-w-0 w-full max-w-7xl mx-auto px-4 sm:px-6 py-6 [overflow-wrap:anywhere]">
        {children}
      </main>
      <footer className="border-t border-neutral-800/80 py-4 text-center text-xs font-mono text-neutral-400">
        CodeGuardian AI — Autonomous Multi-Agent DevSecOps
      </footer>
    </div>
  );
};
