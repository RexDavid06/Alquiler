// =============================================================================
// ProtectedRoute Tests
//
// Verifies: redirect when unauthenticated, loading state while validating,
// rendering for PLATFORM_ADMIN, and redirect for non-admin users.
//
// Note: Non-admin users are redirected to /login by the AuthContext (which
// clears the token on role mismatch), so the "Access Denied" screen in
// ProtectedRoute is a safety fallback that is not normally reached.
// =============================================================================

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AuthProvider } from '../contexts/AuthContext';
import ProtectedRoute from '../components/ProtectedRoute';
import * as authApi from '../api/auth';

vi.mock('../api/auth', () => ({
  loginUser: vi.fn(),
  logoutUser: vi.fn(),
  getCurrentUser: vi.fn(),
}));

function renderWithProtectedRoute(initialEntries: string[] = ['/']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<div>Login Page</div>} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <div>Protected Content</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe('ProtectedRoute', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.mocked(authApi.getCurrentUser).mockReset();
  });

  it('redirects to login when no token exists', async () => {
    renderWithProtectedRoute();

    await waitFor(() => {
      expect(screen.getByText('Login Page')).toBeInTheDocument();
    });
  });

  it('shows loading spinner while validating token', async () => {
    localStorage.setItem('alquiler_token', 'fake-token');
    vi.mocked(authApi.getCurrentUser).mockImplementation(() => new Promise(() => {}));

    renderWithProtectedRoute();

    await waitFor(() => {
      expect(screen.getByText(/loading/i)).toBeInTheDocument();
    });
  });

  it('renders children when authenticated as PLATFORM_ADMIN', async () => {
    localStorage.setItem('alquiler_token', 'fake-token');
    vi.mocked(authApi.getCurrentUser).mockResolvedValue({
      id: 1,
      email: 'admin@test.com',
      role: 'PLATFORM_ADMIN',
      full_name: 'Admin User',
      first_name: 'Admin',
      last_name: 'User',
      phone: '',
      status: 'ACTIVE',
      email_verified: true,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    });

    renderWithProtectedRoute();

    await waitFor(() => {
      expect(screen.getByText('Protected Content')).toBeInTheDocument();
    });
  });

  it('redirects non-admin users to login', async () => {
    localStorage.setItem('alquiler_token', 'fake-token');
    vi.mocked(authApi.getCurrentUser).mockResolvedValue({
      id: 1,
      email: 'landlord@test.com',
      role: 'LANDLORD',
      full_name: 'Landlord User',
      first_name: 'Landlord',
      last_name: 'User',
      phone: '',
      status: 'ACTIVE',
      email_verified: true,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    });

    renderWithProtectedRoute();

    // AuthContext clears token on role mismatch, causing redirect to /login
    await waitFor(() => {
      expect(screen.getByText('Login Page')).toBeInTheDocument();
    });
  });
});
