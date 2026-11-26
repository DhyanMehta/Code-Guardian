import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { Button } from './Button';
import { EntryPanel, entryAlert } from './EntryPanel';
import { diagnosticText } from '../reviews/diagnosticText';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

/**
 * ProtectedRoute: checks auth state and redirects unauthenticated users to '/'
 * while preserving the intended destination in router location state (state.from).
 */
export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const { user, isAuthenticated, isLoading, authError, refreshSession } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <EntryPanel title="GitHub session"><p role="status" className="flex items-center gap-3 text-support text-fg-muted">
        <span aria-hidden="true" className="size-5 shrink-0 rounded-full border-2 border-status-active border-t-transparent motion-safe:animate-spin" />
        Checking your sign-in…
      </p></EntryPanel>
    );
  }

  if (authError) return <EntryPanel title="Check your GitHub session">
    <p role="alert" className={entryAlert}>{diagnosticText(authError)}</p>
    <Button variant="secondary" onClick={() => void refreshSession()}>Retry sign-in check</Button>
  </EntryPanel>;

  if (!isAuthenticated) {
    return <Navigate to="/" state={{ from: location }} replace />;
  }

  if (!user?.installations.length && !['/auth/install', '/profile'].includes(location.pathname)) {
    return <Navigate to="/auth/install" replace />;
  }

  return <>{children}</>;
};
