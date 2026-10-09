import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ProtectedRoute } from './components/common/ProtectedRoute';
import { AppLayout } from './components/layout/AppLayout';
import { HomePage } from './pages/HomePage';
import { RepoListPage } from './pages/RepoListPage';
import { RepoDashboardPage } from './pages/RepoDashboardPage';
import { ReviewDetailPage } from './pages/ReviewDetailPage';
import { AuthCallbackPage } from './pages/AuthCallbackPage';
import { InstallationProvider } from './context/InstallationContext';
import { ProfilePage } from './pages/ProfilePage';
import { OnboardingPage } from './pages/OnboardingPage';

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <InstallationProvider>
      <AppLayout>
        <Routes>
          {/* Public Home Page */}
          <Route path="/" element={<HomePage />} />
          <Route path="/auth/callback" element={<AuthCallbackPage />} />
          <Route path="/auth/install" element={<ProtectedRoute><OnboardingPage /></ProtectedRoute>} />
          <Route path="/profile" element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />
          <Route path="/reviews/:reviewId" element={<ProtectedRoute><ReviewDetailPage /></ProtectedRoute>} />

          {/* Protected Routes */}
          <Route
            path="/repos"
            element={
              <ProtectedRoute>
                <RepoListPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/repos/:owner/:repo"
            element={
              <ProtectedRoute>
                <RepoDashboardPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/repos/:owner/:repo/pulls/:number"
            element={
              <ProtectedRoute>
                <ReviewDetailPage />
              </ProtectedRoute>
            }
          />

          {/* Catch-all fallback */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AppLayout>
      </InstallationProvider>
    </AuthProvider>
  );
};

export default App;
