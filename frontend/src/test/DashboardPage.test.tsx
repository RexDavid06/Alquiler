// =============================================================================
// DashboardPage Tests
//
// Verifies: loading state, error state, successful rendering with KPIs,
// growth charts, subscription breakdown, and system health.
// =============================================================================

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { AuthProvider } from '../contexts/AuthContext';
import DashboardPage from '../pages/DashboardPage';
import * as dashboardApi from '../api/dashboard';

const mockDashboardData = {
  users: {
    total: 10,
    landlords: 5,
    tenants: 4,
    admins: 1,
    active_landlords: 4,
    suspended_landlords: 1,
    active_tenants: 3,
    suspended_tenants: 1,
  },
  properties: { total: 12 },
  units: { total: 30, occupied: 25, vacant: 5, occupancy_rate: 83.3 },
  leases: {
    total: 20,
    active: 15,
    expiring: 2,
    expired: 2,
    terminated: 1,
    future: 0,
  },
  collected_rent: {
    total: '5000000',
    payment_count: 150,
    period_total: '5000000',
    period_payments: 150,
    previous_total: '4000000',
    previous_payments: 120,
    rent_growth: 25.0,
  },
  outstanding_rent: { total: '200000', period_count: 3 },
  overdue_rent: { total: '100000', period_count: 2 },
  subscriptions: {
    total: 5,
    active: 3,
    trial: 1,
    cancelled: 1,
    past_due: 0,
    expired: 0,
    free: 2,
    professional: 2,
    business: 1,
  },
  growth_trends: {
    landlords: [],
    tenants: [],
    properties: [],
    units: [],
    leases: [],
    payments: [],
    subscriptions: [],
  },
  system_health: {
    database: 'healthy',
    django_check: 'healthy',
    migrations: 'all applied',
  },
};

vi.mock('../api/dashboard', () => ({
  getAdminDashboard: vi.fn(),
  getHealthCheck: vi.fn(),
  getPlans: vi.fn(),
  getProperties: vi.fn(),
  getLeases: vi.fn(),
  getPayments: vi.fn(),
  getNotifications: vi.fn(),
  exportAdminDashboardCsv: vi.fn(),
}));

function renderDashboard() {
  return render(
    <BrowserRouter>
      <AuthProvider>
        <DashboardPage />
      </AuthProvider>
    </BrowserRouter>,
  );
}

describe('DashboardPage', () => {
  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem('alquiler_token', 'fake-token');
    localStorage.setItem('alquiler_user', JSON.stringify({
      id: 1,
      email: 'admin@test.com',
      role: 'PLATFORM_ADMIN',
      full_name: 'Admin User',
      first_name: 'Admin',
      last_name: 'User',
    }));
    vi.mocked(dashboardApi.getAdminDashboard).mockReset();
  });

  it('shows loading spinner initially', async () => {
    vi.mocked(dashboardApi.getAdminDashboard).mockImplementation(
      () => new Promise(() => {}),
    );

    renderDashboard();

    expect(screen.getByText(/loading dashboard/i)).toBeInTheDocument();
  });

  it('renders dashboard metrics on successful load', async () => {
    vi.mocked(dashboardApi.getAdminDashboard).mockResolvedValue(mockDashboardData);

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('Platform Dashboard')).toBeInTheDocument();
    });

    // Verify section headers
    expect(screen.getByText('Users')).toBeInTheDocument();
    expect(screen.getByText('Properties & Units')).toBeInTheDocument();
    expect(screen.getByText('Rent Collected & Financials')).toBeInTheDocument();
    expect(screen.getByText('Subscriptions')).toBeInTheDocument();
    expect(screen.getByText('Leases')).toBeInTheDocument();
    expect(screen.getByText('System Health')).toBeInTheDocument();

    // Verify user metrics
    expect(screen.getByText('Total Users')).toBeInTheDocument();
    expect(screen.getByText('Landlords')).toBeInTheDocument();
    expect(screen.getByText('Tenants')).toBeInTheDocument();
    expect(screen.getByText('Admins')).toBeInTheDocument();

    // Verify property/unit metrics
    expect(screen.getByText('Total Properties')).toBeInTheDocument();
    expect(screen.getByText('Total Units')).toBeInTheDocument();
    expect(screen.getByText('Occupied Units')).toBeInTheDocument();
    expect(screen.getByText('Vacant Units')).toBeInTheDocument();

    // Verify financial metrics
    expect(screen.getByText('Total Collected Rent')).toBeInTheDocument();
    expect(screen.getByText('Outstanding Rent')).toBeInTheDocument();
    expect(screen.getByText('Overdue Rent')).toBeInTheDocument();

    // Verify lease metrics
    expect(screen.getByText('Total Leases')).toBeInTheDocument();
    expect(screen.getAllByText('Active').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Expiring')).toBeInTheDocument();

    // Verify subscription metrics
    expect(screen.getByText('Free Plan')).toBeInTheDocument();
    expect(screen.getByText('Professional')).toBeInTheDocument();
    expect(screen.getByText('Business Plan')).toBeInTheDocument();
  });

  it('displays system health status', async () => {
    vi.mocked(dashboardApi.getAdminDashboard).mockResolvedValue(mockDashboardData);

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('System Health')).toBeInTheDocument();
    });

    // Health badges should be present
    const healthyBadges = screen.getAllByText('healthy');
    expect(healthyBadges.length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText('all applied')).toBeInTheDocument();
  });

  it('shows occupancy rate', async () => {
    vi.mocked(dashboardApi.getAdminDashboard).mockResolvedValue(mockDashboardData);

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('83.3% occupancy')).toBeInTheDocument();
    });
  });

  it('shows rent growth', async () => {
    vi.mocked(dashboardApi.getAdminDashboard).mockResolvedValue(mockDashboardData);

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('+25% vs previous')).toBeInTheDocument();
    });
  });

  it('shows period selector buttons', async () => {
    vi.mocked(dashboardApi.getAdminDashboard).mockResolvedValue(mockDashboardData);

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('All Time')).toBeInTheDocument();
      expect(screen.getByText('7 Days')).toBeInTheDocument();
      expect(screen.getByText('30 Days')).toBeInTheDocument();
      expect(screen.getByText('90 Days')).toBeInTheDocument();
      expect(screen.getByText('12 Months')).toBeInTheDocument();
    });
  });

  it('shows error state when API fails', async () => {
    vi.mocked(dashboardApi.getAdminDashboard).mockRejectedValue(
      new Error('Network error'),
    );

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });

    expect(screen.getByText(/retry/i)).toBeInTheDocument();
  });

  it('refreshes data when period changes', async () => {
    vi.mocked(dashboardApi.getAdminDashboard).mockResolvedValue(mockDashboardData);

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('Platform Dashboard')).toBeInTheDocument();
    });

    // Click 30 Days
    const btn = screen.getByText('30 Days');
    btn.click();

    await waitFor(() => {
      expect(vi.mocked(dashboardApi.getAdminDashboard)).toHaveBeenCalledTimes(2);
    });
  });

  it('shows subscription plan breakdown', async () => {
    vi.mocked(dashboardApi.getAdminDashboard).mockResolvedValue(mockDashboardData);

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('Free Plan')).toBeInTheDocument();
      expect(screen.getByText('Professional')).toBeInTheDocument();
      expect(screen.getByText('Business Plan')).toBeInTheDocument();
      expect(screen.getByText('Cancelled')).toBeInTheDocument();
    });
  });

  it('shows user status details in subtitle', async () => {
    vi.mocked(dashboardApi.getAdminDashboard).mockResolvedValue(mockDashboardData);

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('4 active · 1 suspended')).toBeInTheDocument();
    });
  });

  it('shows Export CSV button', async () => {
    vi.mocked(dashboardApi.getAdminDashboard).mockResolvedValue(mockDashboardData);

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Export CSV/ })).toBeInTheDocument();
    });
  });

  it('invokes the CSV export API when Export CSV is clicked', async () => {
    vi.mocked(dashboardApi.getAdminDashboard).mockResolvedValue(mockDashboardData);
    vi.mocked(dashboardApi.exportAdminDashboardCsv).mockResolvedValue(new Blob([]));
    Object.defineProperty(URL, 'createObjectURL', {
      writable: true,
      value: vi.fn(() => 'blob:mock'),
    });
    Object.defineProperty(URL, 'revokeObjectURL', {
      writable: true,
      value: vi.fn(),
    });

    const user = userEvent.setup();
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('Platform Dashboard')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /Export CSV/ }));

    await waitFor(() => {
      expect(dashboardApi.exportAdminDashboardCsv).toHaveBeenCalled();
    });
    expect(URL.createObjectURL).toHaveBeenCalled();
  });

  it('passes the active period date range to the CSV export API', async () => {
    vi.mocked(dashboardApi.getAdminDashboard).mockResolvedValue(mockDashboardData);
    vi.mocked(dashboardApi.exportAdminDashboardCsv).mockResolvedValue(new Blob([]));
    Object.defineProperty(URL, 'createObjectURL', {
      writable: true,
      value: vi.fn(() => 'blob:mock'),
    });
    Object.defineProperty(URL, 'revokeObjectURL', {
      writable: true,
      value: vi.fn(),
    });

    const user = userEvent.setup();
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('Platform Dashboard')).toBeInTheDocument();
    });

    await user.click(screen.getByText('7 Days'));
    await user.click(screen.getByRole('button', { name: /Export CSV/ }));

    await waitFor(() => {
      expect(dashboardApi.exportAdminDashboardCsv).toHaveBeenCalledWith(
        expect.any(String),
        expect.any(String),
      );
    });
  });
});
