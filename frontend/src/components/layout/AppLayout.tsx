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
      <a
        href="#main-content"
        className="sr-only control-focus focus:not-sr-only focus:fixed focus:left-4 focus:top-3 focus:z-50 focus:rounded-lg focus:bg-panel-raised focus:px-4 focus:py-3 text-control text-link"
      >
        Skip to main content
      </a>
      <Navbar />
      {!online && (
        <div role="status" className="bg-risk-medium-bg border-b border-divider py-2 px-4 text-center text-support font-medium text-risk-medium">
          Offline. Automatic updates are paused until your connection returns.
        </div>
      )}
      {contextBar}
      <main id="main-content" tabIndex={-1} className="flex-1 min-w-0 w-full max-w-7xl mx-auto px-4 sm:px-6 py-6 scroll-mt-20 [overflow-wrap:anywhere]">
        {children}
      </main>
      <footer className="border-t border-divider py-6 text-meta md:text-meta-wide text-fg-muted">
        <div className="max-w-7xl mx-auto px-4 sm:px-6">CodeGuardian AI — Multi-agent code review</div>
      </footer>
    </div>
  );
};
