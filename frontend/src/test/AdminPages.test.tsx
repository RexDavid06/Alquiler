// =============================================================================
// Phase 10C — Platform Operations Pages Tests
//
// Tests: Users, Properties, Leases, Payments, Subscriptions, Issues pages.
// Covers: rendering, search, filters, pagination, detail views, loading,
// error, empty states, navigation.
// =============================================================================

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { AuthProvider } from '../contexts/AuthContext';
import type { ReactNode } from 'react';
import type {
  AdminUser,
  AdminProperty,
  AdminLease,
  AdminPayment,
  AdminSubscription,
  AdminIssuesResponse,
  PaginatedResponse,
} from '../api/types';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('../api/admin', () => ({
  getAdminUsers: vi.fn(),
  getAdminUserDetail: vi.fn(),
  getAdminProperties: vi.fn(),
  getAdminPropertyDetail: vi.fn(),
  getAdminLeases: vi.fn(),
  getAdminLeaseDetail: vi.fn(),
  getAdminPayments: vi.fn(),
  getAdminPaymentDetail: vi.fn(),
  getAdminSubscriptions: vi.fn(),
  getAdminIssues: vi.fn(),
}));

vi.mock('../api/auth', () => ({
  loginUser: vi.fn(),
  logoutUser: vi.fn(),
  getCurrentUser: vi.fn(),
}));

import * as adminApi from '../api/admin';
import * as authApi from '../api/auth';
import UsersPage from '../pages/UsersPage';
import PropertiesPage from '../pages/PropertiesPage';
import LeasesPage from '../pages/LeasesPage';
import PaymentsPage from '../pages/PaymentsPage';
import SubscriptionsPage from '../pages/SubscriptionsPage';
import IssuesPage from '../pages/IssuesPage';

function renderWithRouter(ui: ReactNode, initialEntries: string[] = ['/']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
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

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('alquiler_token', 'fake-token');
  localStorage.setItem('alquiler_user', JSON.stringify(adminUser));
  vi.mocked(authApi.getCurrentUser).mockReset();
  vi.mocked(authApi.getCurrentUser).mockResolvedValue(adminUser);
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Users Page
// ---------------------------------------------------------------------------

describe('UsersPage', () => {
  const mockUsers: PaginatedResponse<AdminUser> = {
    count: 2,
    next: null,
    previous: null,
    results: [
      {
        id: 1,
        email: 'landlord@test.com',
        role: 'LANDLORD' as const,
        first_name: 'Land',
        last_name: 'Lord',
        phone: '',
        full_name: 'Land Lord',
        status: 'ACTIVE' as const,
        email_verified: true,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
        property_count: 3,
        lease_count: 5,
        subscription_status: 'ACTIVE',
      },
      {
        id: 2,
        email: 'tenant@test.com',
        role: 'TENANT' as const,
        first_name: 'Ten',
        last_name: 'Ant',
        phone: '',
        full_name: 'Ten Ant',
        status: 'ACTIVE' as const,
        email_verified: true,
        created_at: '2026-01-02T00:00:00Z',
        updated_at: '2026-01-02T00:00:00Z',
        property_count: null,
        lease_count: 1,
        subscription_status: null,
      },
    ],
  };

  beforeEach(() => {
    vi.mocked(adminApi.getAdminUsers).mockResolvedValue(mockUsers);
  });

  it('renders page title and description', async () => {
    renderWithRouter(<UsersPage />);
    await waitFor(() => {
      expect(screen.getByText('Users')).toBeInTheDocument();
    });
    expect(screen.getByText(/Platform-wide user management/)).toBeInTheDocument();
  });

  it('loads and displays users in table', async () => {
    renderWithRouter(<UsersPage />);
    await waitFor(() => {
      expect(screen.getByText('Land Lord')).toBeInTheDocument();
    });
    expect(screen.getByText('Ten Ant')).toBeInTheDocument();
    expect(screen.getByText('landlord@test.com')).toBeInTheDocument();
  });

  it('displays role and status badges', async () => {
    renderWithRouter(<UsersPage />);
    await waitFor(() => {
      expect(screen.getByText('LANDLORD')).toBeInTheDocument();
    });
    expect(screen.getByText('TENANT')).toBeInTheDocument();
  });

  it('shows search input', async () => {
    renderWithRouter(<UsersPage />);
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/Search by name or email/)).toBeInTheDocument();
    });
  });

  it('calls API with search params', async () => {
    const user = userEvent.setup();
    renderWithRouter(<UsersPage />);
    await waitFor(() => {
      expect(adminApi.getAdminUsers).toHaveBeenCalled();
    });
    const searchInput = screen.getByPlaceholderText(/Search by name or email/);
    await user.type(searchInput, 'test');
    await waitFor(() => {
      expect(adminApi.getAdminUsers).toHaveBeenCalledWith(
        expect.objectContaining({ search: 'test' }),
      );
    });
  });

  it('shows role and status filter dropdowns', async () => {
    renderWithRouter(<UsersPage />);
    await waitFor(() => {
      expect(screen.getByDisplayValue('All Roles')).toBeInTheDocument();
    });
    expect(screen.getByDisplayValue('All Statuses')).toBeInTheDocument();
  });

  it('shows loading state', async () => {
    vi.mocked(adminApi.getAdminUsers).mockReturnValue(new Promise(() => {}));
    renderWithRouter(<UsersPage />);
    expect(screen.getByText(/Loading users/)).toBeInTheDocument();
  });

  it('shows error state', async () => {
    vi.mocked(adminApi.getAdminUsers).mockRejectedValue(new Error('Network error'));
    renderWithRouter(<UsersPage />);
    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });
  });

  it('shows empty state when no users', async () => {
    vi.mocked(adminApi.getAdminUsers).mockResolvedValue({
      count: 0, next: null, previous: null, results: [],
    } as PaginatedResponse<AdminUser>);
    renderWithRouter(<UsersPage />);
    await waitFor(() => {
      expect(screen.getByText('No users found')).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// Properties Page
// ---------------------------------------------------------------------------

describe('PropertiesPage', () => {
  const mockProperties: PaginatedResponse<AdminProperty> = {
    count: 1,
    next: null,
    previous: null,
    results: [
      {
        id: 1,
        landlord: 1,
        landlord_name: 'Land Lord',
        landlord_email: 'landlord@test.com',
        name: 'Sunset Apartments',
        property_type: 'APARTMENT',
        address: '123 Main St',
        city: 'Lagos',
        state: 'Lagos',
        country: 'Nigeria',
        currency: 'NGN',
        status: 'ACTIVE',
        unit_count: 5,
        occupied_units: 3,
        vacant_units: 2,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      },
    ],
  };

  beforeEach(() => {
    vi.mocked(adminApi.getAdminProperties).mockResolvedValue(mockProperties);
  });

  it('renders page title', async () => {
    renderWithRouter(<PropertiesPage />);
    await waitFor(() => {
      expect(screen.getByText('Properties')).toBeInTheDocument();
    });
  });

  it('loads and displays properties', async () => {
    renderWithRouter(<PropertiesPage />);
    await waitFor(() => {
      expect(screen.getByText('Sunset Apartments')).toBeInTheDocument();
    });
    expect(screen.getByText('Land Lord')).toBeInTheDocument();
    expect(screen.getByText('Lagos')).toBeInTheDocument();
  });

  it('shows type and status filters', async () => {
    renderWithRouter(<PropertiesPage />);
    await waitFor(() => {
      expect(screen.getByDisplayValue('All Types')).toBeInTheDocument();
    });
    expect(screen.getByDisplayValue('All Statuses')).toBeInTheDocument();
  });

  it('shows unit occupancy info', async () => {
    renderWithRouter(<PropertiesPage />);
    await waitFor(() => {
      expect(screen.getByText('3/5 occupied')).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// Leases Page
// ---------------------------------------------------------------------------

describe('LeasesPage', () => {
  const mockLeases: PaginatedResponse<AdminLease> = {
    count: 1,
    next: null,
    previous: null,
    results: [
      {
        id: 1,
        landlord: 1,
        landlord_name: 'Land Lord',
        tenant: 2,
        tenant_name: 'Ten Ant',
        tenant_email: 'tenant@test.com',
        property: 1,
        property_name: 'Sunset Apartments',
        unit: 1,
        unit_name: 'Unit A',
        start_date: '2026-01-01',
        expiry_date: '2026-12-31',
        rent_amount: '100000.00',
        currency: 'NGN',
        rent_frequency: 'MONTHLY',
        rent_due_day: 1,
        status: 'ACTIVE',
        notes: '',
        previous_lease: null,
        terminated_at: null,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      },
    ],
  };

  beforeEach(() => {
    vi.mocked(adminApi.getAdminLeases).mockResolvedValue(mockLeases);
  });

  it('renders page title', async () => {
    renderWithRouter(<LeasesPage />);
    await waitFor(() => {
      expect(screen.getByText('Leases')).toBeInTheDocument();
    });
  });

  it('loads and displays leases', async () => {
    renderWithRouter(<LeasesPage />);
    await waitFor(() => {
      expect(screen.getByText('Land Lord')).toBeInTheDocument();
    });
    expect(screen.getByText('Ten Ant')).toBeInTheDocument();
    expect(screen.getByText('Sunset Apartments — Unit A')).toBeInTheDocument();
  });

  it('displays rent amount formatted', async () => {
    renderWithRouter(<LeasesPage />);
    await waitFor(() => {
      expect(screen.getByText('₦100,000')).toBeInTheDocument();
    });
  });

  it('shows status filter', async () => {
    renderWithRouter(<LeasesPage />);
    await waitFor(() => {
      expect(screen.getByDisplayValue('All Statuses')).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// Payments Page
// ---------------------------------------------------------------------------

describe('PaymentsPage', () => {
  const mockPayments: PaginatedResponse<AdminPayment> = {
    count: 1,
    next: null,
    previous: null,
    results: [
      {
        id: 1,
        landlord: 1,
        landlord_name: 'Land Lord',
        tenant: 2,
        tenant_name: 'Ten Ant',
        lease: 1,
        rent_period: null,
        amount: '100000.00',
        currency: 'NGN',
        payment_date: '2026-01-15',
        payment_method: 'BANK_TRANSFER',
        reference: 'TXN001',
        notes: '',
        status: 'PAID',
        gateway: '',
        gateway_reference: '',
        verified: false,
        recorded_by: 1,
        created_at: '2026-01-15T00:00:00Z',
        updated_at: '2026-01-15T00:00:00Z',
      },
    ],
  };

  beforeEach(() => {
    vi.mocked(adminApi.getAdminPayments).mockResolvedValue(mockPayments);
  });

  it('renders page title', async () => {
    renderWithRouter(<PaymentsPage />);
    await waitFor(() => {
      expect(screen.getByText('Payments')).toBeInTheDocument();
    });
  });

  it('loads and displays payments', async () => {
    renderWithRouter(<PaymentsPage />);
    await waitFor(() => {
      expect(screen.getByText('Ten Ant')).toBeInTheDocument();
    });
    expect(screen.getByText('Land Lord')).toBeInTheDocument();
    expect(screen.getByText('₦100,000')).toBeInTheDocument();
  });

  it('shows payment status badge', async () => {
    renderWithRouter(<PaymentsPage />);
    await waitFor(() => {
      expect(screen.getByText('PAID')).toBeInTheDocument();
    });
  });

  it('shows status filter', async () => {
    renderWithRouter(<PaymentsPage />);
    await waitFor(() => {
      expect(screen.getByDisplayValue('All Statuses')).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// Subscriptions Page
// ---------------------------------------------------------------------------

describe('SubscriptionsPage', () => {
  const mockSubscriptions: PaginatedResponse<AdminSubscription> = {
    count: 1,
    next: null,
    previous: null,
    results: [
      {
        id: 1,
        landlord: 1,
        landlord_email: 'landlord@test.com',
        landlord_name: 'Land Lord',
        plan: 1,
        plan_name: 'Free',
        plan_tier: 'FREE',
        status: 'ACTIVE',
        billing_cycle: 'MONTHLY',
        started_at: '2026-01-01T00:00:00Z',
        current_period_start: '2026-01-01T00:00:00Z',
        current_period_end: null,
        trial_end: null,
        cancelled_at: null,
        cancel_reason: '',
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      },
    ],
  };

  beforeEach(() => {
    vi.mocked(adminApi.getAdminSubscriptions).mockResolvedValue(mockSubscriptions);
  });

  it('renders page title', async () => {
    renderWithRouter(<SubscriptionsPage />);
    await waitFor(() => {
      expect(screen.getByText('Subscriptions')).toBeInTheDocument();
    });
  });

  it('loads and displays subscriptions', async () => {
    renderWithRouter(<SubscriptionsPage />);
    await waitFor(() => {
      expect(screen.getByText('Land Lord')).toBeInTheDocument();
    });
    expect(screen.getByText('landlord@test.com')).toBeInTheDocument();
    expect(screen.getAllByText('Free').length).toBeGreaterThanOrEqual(1);
  });

  it('shows plan and status filters', async () => {
    renderWithRouter(<SubscriptionsPage />);
    await waitFor(() => {
      expect(screen.getByDisplayValue('All Plans')).toBeInTheDocument();
    });
    expect(screen.getByDisplayValue('All Statuses')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Issues Page
// ---------------------------------------------------------------------------

describe('IssuesPage', () => {
  const mockIssues: AdminIssuesResponse = {
    count: 2,
    issues: [
      {
        issue_type: 'failed_payment',
        severity: 'high',
        title: 'Failed payment #1',
        description: 'Payment of NGN 100,000 failed.',
        entity_type: 'payment',
        entity_id: 1,
        created_at: '2026-01-15',
      },
      {
        issue_type: 'suspended_user',
        severity: 'medium',
        title: 'Suspended account: John Doe',
        description: 'User john@test.com (LANDLORD) is suspended.',
        entity_type: 'user',
        entity_id: 2,
        created_at: '2026-01-10',
      },
    ],
  };

  beforeEach(() => {
    vi.mocked(adminApi.getAdminIssues).mockResolvedValue(mockIssues);
  });

  it('renders page title', async () => {
    renderWithRouter(<IssuesPage />);
    await waitFor(() => {
      expect(screen.getByText('Operational Issues')).toBeInTheDocument();
    });
  });

  it('loads and displays issues', async () => {
    renderWithRouter(<IssuesPage />);
    await waitFor(() => {
      expect(screen.getByText('Failed payment #1')).toBeInTheDocument();
    });
    expect(screen.getByText('Suspended account: John Doe')).toBeInTheDocument();
  });

  it('displays severity summary cards', async () => {
    renderWithRouter(<IssuesPage />);
    await waitFor(() => {
      expect(screen.getByText('Total Issues')).toBeInTheDocument();
    });
    expect(screen.getByText('High Severity')).toBeInTheDocument();
    expect(screen.getByText('Medium Severity')).toBeInTheDocument();
    expect(screen.getByText('Low Severity')).toBeInTheDocument();
  });

  it('shows issue descriptions', async () => {
    renderWithRouter(<IssuesPage />);
    await waitFor(() => {
      expect(screen.getByText(/Payment of NGN 100,000 failed/)).toBeInTheDocument();
    });
  });

  it('shows empty state when no issues', async () => {
    vi.mocked(adminApi.getAdminIssues).mockResolvedValue({
      count: 0, issues: [],
    });
    renderWithRouter(<IssuesPage />);
    await waitFor(() => {
      expect(screen.getByText('No issues found')).toBeInTheDocument();
    });
  });

  it('shows loading state', async () => {
    vi.mocked(adminApi.getAdminIssues).mockReturnValue(new Promise(() => {}));
    renderWithRouter(<IssuesPage />);
    expect(screen.getByText(/Loading operational issues/)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Layout Navigation
// ---------------------------------------------------------------------------

describe('Layout — Phase 10C Navigation', () => {
  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem('alquiler_token', 'fake-token');
    localStorage.setItem('alquiler_user', JSON.stringify(adminUser));
    vi.mocked(authApi.getCurrentUser).mockReset();
    vi.mocked(authApi.getCurrentUser).mockResolvedValue(adminUser);
  });

  it('includes Issues navigation link', async () => {
    const { default: Layout } = await import('../components/Layout');
    render(
      <MemoryRouter initialEntries={['/']}>
        <AuthProvider>
          <Layout />
        </AuthProvider>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText('Issues')).toBeInTheDocument();
    });
  });
});
