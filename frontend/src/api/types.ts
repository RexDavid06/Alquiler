// =============================================================================
// Alquiler Super User — TypeScript API Types
// Mirrors the backend's serialized response shapes exactly.
// =============================================================================

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export interface User {
  id: number;
  email: string;
  role: 'PLATFORM_ADMIN' | 'LANDLORD' | 'TENANT';
  first_name: string;
  last_name: string;
  phone: string;
  full_name: string;
  status: 'PENDING' | 'ACTIVE' | 'SUSPENDED' | 'DEACTIVATED';
  email_verified: boolean;
  created_at: string;
  updated_at: string;
}

export interface LoginResponse {
  user: User;
  token: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

// ---------------------------------------------------------------------------
// Dashboard — Admin (Phase 10B: comprehensive platform analytics)
// ---------------------------------------------------------------------------

export interface AdminDashboardResponse {
  users: {
    total: number;
    landlords: number;
    tenants: number;
    admins: number;
    active_landlords: number;
    suspended_landlords: number;
    active_tenants: number;
    suspended_tenants: number;
  };
  properties: {
    total: number;
  };
  units: {
    total: number;
    occupied: number;
    vacant: number;
    occupancy_rate: number;
  };
  leases: {
    total: number;
    active: number;
    expiring: number;
    expired: number;
    terminated: number;
    future: number;
  };
  collected_rent: {
    total: string;
    payment_count: number;
    period_total: string;
    period_payments: number;
    previous_total: string;
    previous_payments: number;
    rent_growth: number | null;
  };
  outstanding_rent: {
    total: string;
    period_count: number;
  };
  overdue_rent: {
    total: string;
    period_count: number;
  };
  subscriptions: {
    total: number;
    active: number;
    trial: number;
    cancelled: number;
    past_due: number;
    expired: number;
    free: number;
    professional: number;
    business: number;
  };
  growth_trends: {
    landlords: GrowthPoint[];
    tenants: GrowthPoint[];
    properties: GrowthPoint[];
    units: GrowthPoint[];
    leases: GrowthPoint[];
    payments: PaymentGrowthPoint[];
    subscriptions: GrowthPoint[];
  };
  system_health: {
    database: string;
    django_check: string;
    migrations: string;
  };
}

export interface GrowthPoint {
  month: string; // "YYYY-MM"
  count: number;
}

export interface PaymentGrowthPoint {
  month: string;
  count: number;
  total: string;
}

// ---------------------------------------------------------------------------
// Subscriptions / Plans
// ---------------------------------------------------------------------------

export interface Plan {
  id: number;
  tier: 'FREE' | 'PROFESSIONAL' | 'BUSINESS';
  name: string;
  description: string;
  max_active_tenants: number;
  max_properties: number;
  price_ngn: string;
  is_active: boolean;
  display_order: number;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Properties
// ---------------------------------------------------------------------------

export interface Property {
  id: number;
  landlord: number;
  name: string;
  property_type: string;
  address: string;
  city: string;
  state: string;
  country: string;
  description: string;
  currency: string;
  status: 'ACTIVE' | 'ARCHIVED';
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Leases
// ---------------------------------------------------------------------------

export interface Lease {
  id: number;
  landlord: number;
  tenant: number;
  property: number;
  unit: number;
  start_date: string;
  expiry_date: string;
  rent_amount: string;
  currency: string;
  rent_frequency: string;
  rent_due_day: number;
  status: 'FUTURE' | 'ACTIVE' | 'EXPIRING' | 'EXPIRED' | 'TERMINATED';
  notes: string;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Payments
// ---------------------------------------------------------------------------

export interface Payment {
  id: number;
  landlord: number;
  tenant: number;
  lease: number;
  rent_period: number | null;
  amount: string;
  currency: string;
  payment_date: string;
  payment_method: string;
  reference: string;
  notes: string;
  status: 'PAID' | 'PENDING' | 'FAILED' | 'CANCELLED';
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Notifications
// ---------------------------------------------------------------------------

export interface Notification {
  id: number;
  recipient: number;
  notification_type: string;
  channel: string;
  status: string;
  title: string;
  message: string;
  is_read: boolean;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Generic Paginated Response
// ---------------------------------------------------------------------------

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
