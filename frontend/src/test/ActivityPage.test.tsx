// =============================================================================
// Phase 10E — Activity Page Tests
//
// Tests: renders audit/activity data, filters, search call, empty state,
// detail panel.
// =============================================================================

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { AuthProvider } from '../contexts/AuthContext';
import type { ReactNode } from 'react';
import type { AuditLog, PaginatedResponse } from '../api/types';

vi.mock('../api/admin', () => ({
  getAdminAuditLogs: vi.fn(),
}));

vi.mock('../api/auth', () => ({
  loginUser: vi.fn(),
  logoutUser: vi.fn(),
  getCurrentUser: vi.fn(),
}));

import * as adminApi from '../api/admin';
import * as authApi from '../api/auth';
import ActivityPage from '../pages/ActivityPage';

function renderWithRouter(ui: ReactNode) {
  return render(
    <MemoryRouter>
      <AuthProvider>{ui}</AuthProvider>
    </MemoryRouter>,
  );
}

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

const mockLogs: PaginatedResponse<AuditLog> = {
  count: 2,
  next: null,
  previous: null,
  results: [
    {
      id: 1,
      actor: 2,
      actor_email: 'landlord@test.com',
      actor_name: 'Land Lord',
      action: 'LEASE_CREATED',
      object_type: 'Lease',
      object_id: 5,
      detail: { property: 1, unit: 2, tenant: 3 },
      created_at: '2026-01-15T09:00:00Z',
    },
    {
      id: 2,
      actor: 2,
      actor_email: 'landlord@test.com',
      actor_name: 'Land Lord',
      action: 'ACCOUNT_CREATED',
      object_type: 'User',
      object_id: 4,
      detail: { role: 'TENANT' },
      created_at: '2026-01-14T09:00:00Z',
    },
  ],
};

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('alquiler_token', 'fake-token');
  localStorage.setItem('alquiler_user', JSON.stringify(adminUser));
  vi.mocked(authApi.getCurrentUser).mockReset();
  vi.mocked(authApi.getCurrentUser).mockResolvedValue(adminUser);
  vi.mocked(adminApi.getAdminAuditLogs).mockResolvedValue(mockLogs);
  vi.clearAllMocks();
});

describe('ActivityPage', () => {
  it('renders page title and description', async () => {
    renderWithRouter(<ActivityPage />);
    await waitFor(() => {
      expect(screen.getByText('Activity')).toBeInTheDocument();
    });
    expect(screen.getByText(/Platform-wide audit log/)).toBeInTheDocument();
  });

  it('loads and displays audit/activity data', async () => {
    renderWithRouter(<ActivityPage />);
    await waitFor(() => {
      expect(screen.getByText('LEASE CREATED')).toBeInTheDocument();
    });
    expect(screen.getAllByText('Land Lord').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('LEASE CREATED')).toBeInTheDocument();
    expect(adminApi.getAdminAuditLogs).toHaveBeenCalled();
  });

  it('shows action and object-type filters', async () => {
    renderWithRouter(<ActivityPage />);
    await waitFor(() => {
      expect(screen.getByDisplayValue('All Actions')).toBeInTheDocument();
    });
    expect(screen.getByDisplayValue('All Types')).toBeInTheDocument();
  });

  it('calls the API with search params', async () => {
    const user = userEvent.setup();
    renderWithRouter(<ActivityPage />);
    await waitFor(() => {
      expect(adminApi.getAdminAuditLogs).toHaveBeenCalled();
    });

    const searchInput = screen.getByPlaceholderText(/Search by action or object type/);
    await user.type(searchInput, 'lease');
    await waitFor(() => {
      expect(adminApi.getAdminAuditLogs).toHaveBeenCalledWith(
        expect.objectContaining({ search: 'lease' }),
      );
    });
  });

  it('shows empty state when no logs', async () => {
    vi.mocked(adminApi.getAdminAuditLogs).mockResolvedValue({
      count: 0, next: null, previous: null, results: [],
    });
    renderWithRouter(<ActivityPage />);
    await waitFor(() => {
      expect(screen.getByText('No activity found')).toBeInTheDocument();
    });
  });

  it('shows loading state', async () => {
    vi.mocked(adminApi.getAdminAuditLogs).mockReturnValue(new Promise(() => {}));
    renderWithRouter(<ActivityPage />);
    expect(screen.getByText(/Loading activity/)).toBeInTheDocument();
  });

  it('opens the detail panel on row click', async () => {
    const user = userEvent.setup();
    renderWithRouter(<ActivityPage />);
    await waitFor(() => {
      expect(screen.getByText('LEASE CREATED')).toBeInTheDocument();
    });
    await user.click(screen.getAllByText('Land Lord')[0]);
    await waitFor(() => {
      expect(screen.getByText('Audit Log #1')).toBeInTheDocument();
    });
  });
});