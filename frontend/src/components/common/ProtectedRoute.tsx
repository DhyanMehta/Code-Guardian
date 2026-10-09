import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

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
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="w-6 h-6 border-2 border-primary-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (authError) return <div role="alert">{authError} <button onClick={() => void refreshSession()}>Retry sign-in check</button></div>;

  if (!isAuthenticated) {
    return <Navigate to="/" state={{ from: location }} replace />;
  }

  if (!user?.installations.length && !['/auth/install', '/profile'].includes(location.pathname)) {
    return <Navigate to="/auth/install" replace />;
  }

  return <>{children}</>;
};
