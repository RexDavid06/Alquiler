// =============================================================================
// Layout Tests
//
// Verifies: sidebar navigation, user display, logout functionality.
// =============================================================================

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AuthProvider } from '../contexts/AuthContext';
import Layout from '../components/Layout';
import * as authApi from '../api/auth';

vi.mock('../api/auth', () => ({
  loginUser: vi.fn(),
  logoutUser: vi.fn(),
  getCurrentUser: vi.fn(),
}));

const adminUser = {
  id: 1,
  email: 'admin@test.com',
  role: 'PLATFORM_ADMIN' as const,
  full_name: 'Admin User',
  first_name: 'Admin',
  last_name: 'User',
  phone: '',
  status: 'ACTIVE' as const,
  email_verified: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

function renderLayout() {
  return render(
    <MemoryRouter initialEntries={['/']}>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<div>Dashboard Content</div>} />
          </Route>
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe('Layout', () => {
  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem('alquiler_token', 'fake-token');
    localStorage.setItem('alquiler_user', JSON.stringify(adminUser));
    vi.mocked(authApi.getCurrentUser).mockReset();
    vi.mocked(authApi.getCurrentUser).mockResolvedValue(adminUser);
  });

  it('displays the Alquiler brand', async () => {
    renderLayout();
    await waitFor(() => {
      expect(screen.getByText('Alquiler')).toBeInTheDocument();
    });
  });

  it('displays all navigation items', async () => {
    renderLayout();
    await waitFor(() => {
      expect(screen.getByText('Dashboard')).toBeInTheDocument();
    });
    expect(screen.getByText('Users')).toBeInTheDocument();
    expect(screen.getByText('Properties')).toBeInTheDocument();
    expect(screen.getByText('Leases')).toBeInTheDocument();
    expect(screen.getByText('Payments')).toBeInTheDocument();
    expect(screen.getByText('Subscriptions')).toBeInTheDocument();
    expect(screen.getByText('Notifications')).toBeInTheDocument();
    expect(screen.getByText('System Health')).toBeInTheDocument();
  });

  it('displays the user name and email', async () => {
    renderLayout();
    await waitFor(() => {
      expect(screen.getByText('Admin User')).toBeInTheDocument();
    });
    expect(screen.getByText('admin@test.com')).toBeInTheDocument();
  });

  it('renders child content in the outlet', async () => {
    renderLayout();
    await waitFor(() => {
      expect(screen.getByText('Dashboard Content')).toBeInTheDocument();
    });
  });

  it('has a logout button', async () => {
    renderLayout();
    await waitFor(() => {
      expect(screen.getByTitle('Sign out')).toBeInTheDocument();
    });
  });
});
