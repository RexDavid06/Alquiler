// =============================================================================
// Phase 10D — Plans Page Tests
//
// Tests: renders plans, create/edit flow wiring, activate/deactivate actions.
// =============================================================================

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { AuthProvider } from '../contexts/AuthContext';
import type { ReactNode } from 'react';
import type { AdminPlan, PaginatedResponse } from '../api/types';

vi.mock('../api/admin', () => ({
  getAdminPlans: vi.fn(),
  createAdminPlan: vi.fn(),
  updateAdminPlan: vi.fn(),
  activateAdminPlan: vi.fn(),
  deactivateAdminPlan: vi.fn(),
}));

vi.mock('../api/auth', () => ({
  loginUser: vi.fn(),
  logoutUser: vi.fn(),
  getCurrentUser: vi.fn(),
}));

import * as adminApi from '../api/admin';
import * as authApi from '../api/auth';
import PlansPage from '../pages/PlansPage';

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

const mockPlans: PaginatedResponse<AdminPlan> = {
  count: 2,
  next: null,
  previous: null,
  results: [
    {
      id: 1,
      tier: 'FREE',
      name: 'Free',
      description: 'Entry level plan',
      max_active_tenants: 1,
      max_properties: 1,
      price_ngn: '0',
      is_active: true,
      display_order: 1,
      subscriber_count: 3,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    },
    {
      id: 2,
      tier: 'PROFESSIONAL',
      name: 'Professional',
      description: 'For growing landlords',
      max_active_tenants: 10,
      max_properties: 5,
      price_ngn: '15000',
      is_active: false,
      display_order: 2,
      subscriber_count: 1,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    },
  ],
};

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('alquiler_token', 'fake-token');
  localStorage.setItem('alquiler_user', JSON.stringify(adminUser));
  vi.mocked(authApi.getCurrentUser).mockReset();
  vi.mocked(authApi.getCurrentUser).mockResolvedValue(adminUser);
  vi.mocked(adminApi.getAdminPlans).mockResolvedValue(mockPlans);
  vi.mocked(adminApi.createAdminPlan).mockResolvedValue(mockPlans.results[0]);
  vi.mocked(adminApi.updateAdminPlan).mockResolvedValue(mockPlans.results[1]);
  vi.mocked(adminApi.activateAdminPlan).mockResolvedValue(mockPlans.results[1]);
  vi.mocked(adminApi.deactivateAdminPlan).mockResolvedValue(mockPlans.results[0]);
  vi.clearAllMocks();
});

describe('PlansPage', () => {
  it('renders page title and description', async () => {
    renderWithRouter(<PlansPage />);
    await waitFor(() => {
      expect(screen.getByText('Plans')).toBeInTheDocument();
    });
    expect(screen.getByText(/Manage platform subscription plans/)).toBeInTheDocument();
  });

  it('loads and displays plans', async () => {
    renderWithRouter(<PlansPage />);
    await waitFor(() => {
      expect(screen.getByText('Entry level plan')).toBeInTheDocument();
    });
    expect(screen.getByText('For growing landlords')).toBeInTheDocument();
    expect(screen.getAllByText('Free').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Professional').length).toBeGreaterThanOrEqual(1);
    expect(adminApi.getAdminPlans).toHaveBeenCalled();
  });

  it('wires the create plan flow', async () => {
    const user = userEvent.setup();
    renderWithRouter(<PlansPage />);
    await waitFor(() => {
      expect(screen.getByText('Entry level plan')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /Create Plan/ }));
    await waitFor(() => {
      expect(screen.getByPlaceholderText('e.g. Professional')).toBeInTheDocument();
    });

    await user.type(screen.getByPlaceholderText('e.g. Professional'), 'Team');
    const submitButtons = screen.getAllByRole('button', { name: /Create Plan/ });
    await user.click(submitButtons[1]);

    await waitFor(() => {
      expect(adminApi.createAdminPlan).toHaveBeenCalledWith(
        expect.objectContaining({ name: 'Team' }),
      );
    });
  });

  it('wires the edit plan flow', async () => {
    const user = userEvent.setup();
    renderWithRouter(<PlansPage />);
    await waitFor(() => {
      expect(screen.getByText('Entry level plan')).toBeInTheDocument();
    });

    const editButtons = screen.getAllByRole('button', { name: 'Edit', exact: true });
    await user.click(editButtons[0]);

    const nameInput = screen.getByPlaceholderText('e.g. Professional');
    await waitFor(() => {
      expect(nameInput).toHaveValue('Free');
    });

    await user.clear(nameInput);
    await user.type(nameInput, 'Free Plus');
    await user.click(screen.getByRole('button', { name: /Save Changes/ }));

    await waitFor(() => {
      expect(adminApi.updateAdminPlan).toHaveBeenCalledWith(
        1,
        expect.objectContaining({ name: 'Free Plus' }),
      );
    });
  });

  it('wires the deactivate action for active plans', async () => {
    const user = userEvent.setup();
    renderWithRouter(<PlansPage />);
    await waitFor(() => {
      expect(screen.getByText('Entry level plan')).toBeInTheDocument();
    });

    const deactivateButton = screen.getByRole('button', { name: 'Deactivate', exact: true });
    await user.click(deactivateButton);

    await waitFor(() => {
      expect(adminApi.deactivateAdminPlan).toHaveBeenCalledWith(1);
    });
  });

  it('wires the activate action for inactive plans', async () => {
    const user = userEvent.setup();
    renderWithRouter(<PlansPage />);
    await waitFor(() => {
      expect(screen.getByText('Entry level plan')).toBeInTheDocument();
    });

    const activateButton = screen.getByRole('button', { name: 'Activate', exact: true });
    await user.click(activateButton);

    await waitFor(() => {
      expect(adminApi.activateAdminPlan).toHaveBeenCalledWith(2);
    });
  });
});