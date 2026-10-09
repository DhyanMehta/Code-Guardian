import React from 'react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from '../context/AuthContext';
import { ProtectedRoute } from '../components/common/ProtectedRoute';

const TestProtectedContent: React.FC = () => {
  return <div>Protected Content Visible</div>;
};

describe('ProtectedRoute component', () => {
  afterEach(() => vi.unstubAllGlobals());
  it('waits for bootstrap then redirects to root when unauthenticated', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 401 })));
    render(
      <AuthProvider>
        <MemoryRouter initialEntries={['/repos']}>
          <Routes>
            <Route path="/" element={<div>Public Home</div>} />
            <Route
              path="/repos"
              element={
                <ProtectedRoute>
                  <TestProtectedContent />
                </ProtectedRoute>
              }
            />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    );

    expect(await screen.findByText('Public Home')).toBeInTheDocument();
    expect(screen.queryByText('Protected Content Visible')).not.toBeInTheDocument();
  });
});
