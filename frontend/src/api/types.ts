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
// Admin — Users
// ---------------------------------------------------------------------------

export interface AdminUser {
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
  property_count: number | null;
  lease_count: number | null;
  subscription_status: string | null;
}

export interface AdminUserDetail extends AdminUser {
  recent_leases: AdminLeaseSummary[];
  recent_payments: AdminPaymentSummary[];
}

export interface AdminLeaseSummary {
  id: number;
  status: string;
  tenant_name: string;
  property_name: string;
  unit_name: string;
  rent_amount: string;
  start_date: string;
  expiry_date: string;
}

export interface AdminPaymentSummary {
  id: number;
  amount: string;
  currency: string;
  status: string;
  payment_date: string;
  payment_method: string;
}

// ---------------------------------------------------------------------------
// Admin — Properties
// ---------------------------------------------------------------------------

export interface AdminProperty {
  id: number;
  landlord: number;
  landlord_name: string;
  landlord_email: string;
  name: string;
  property_type: string;
  address: string;
  city: string;
  state: string;
  country: string;
  currency: string;
  status: 'ACTIVE' | 'ARCHIVED';
  unit_count: number;
  occupied_units: number;
  vacant_units: number;
  created_at: string;
  updated_at: string;
}

export interface AdminPropertyDetail extends AdminProperty {
  description: string;
  units: AdminUnitSummary[];
}

export interface AdminUnitSummary {
  id: number;
  name: string;
  description: string;
  status: 'VACANT' | 'OCCUPIED';
  created_at: string;
}

// ---------------------------------------------------------------------------
// Admin — Subscriptions
// ---------------------------------------------------------------------------

export interface AdminSubscription {
  id: number;
  landlord: number;
  landlord_email: string;
  landlord_name: string;
  plan: number;
  plan_name: string;
  plan_tier: 'FREE' | 'PROFESSIONAL' | 'BUSINESS';
  status: 'TRIAL' | 'ACTIVE' | 'PAST_DUE' | 'CANCELLED' | 'EXPIRED';
  billing_cycle: string;
  started_at: string;
  current_period_start: string;
  current_period_end: string | null;
  trial_end: string | null;
  cancelled_at: string | null;
  cancel_reason: string;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Admin — Plans
// ---------------------------------------------------------------------------

export interface AdminPlan {
  id: number;
  tier: 'FREE' | 'PROFESSIONAL' | 'BUSINESS';
  name: string;
  description: string;
  max_active_tenants: number;
  max_properties: number;
  price_ngn: string;
  is_active: boolean;
  display_order: number;
  subscriber_count: number;
  created_at: string;
  updated_at: string;
}

export interface PlanSubscriber {
  id: number;
  landlord: number;
  landlord_email: string;
  landlord_name: string;
  status: 'TRIAL' | 'ACTIVE' | 'PAST_DUE' | 'CANCELLED' | 'EXPIRED';
  billing_cycle: 'MONTHLY' | 'QUARTERLY' | 'ANNUALLY';
  started_at: string;
  trial_end: string | null;
  cancelled_at: string | null;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Admin — Audit Log
// ---------------------------------------------------------------------------

export interface AuditLog {
  id: number;
  actor: number | null;
  actor_email: string | null;
  actor_name: string | null;
  action: string;
  object_type: string;
  object_id: number | null;
  detail: Record<string, unknown>;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Admin — Leases (enhanced)
// ---------------------------------------------------------------------------

export interface AdminLease {
  id: number;
  landlord: number;
  landlord_name: string;
  tenant: number;
  tenant_name: string;
  tenant_email: string;
  property: number;
  property_name: string;
  unit: number;
  unit_name: string;
  start_date: string;
  expiry_date: string;
  rent_amount: string;
  currency: string;
  rent_frequency: string;
  rent_due_day: number;
  status: 'FUTURE' | 'ACTIVE' | 'EXPIRING' | 'EXPIRED' | 'TERMINATED';
  notes: string;
  previous_lease: number | null;
  terminated_at: string | null;
  created_at: string;
  updated_at: string;
  rent_schedule?: RentScheduleItem[];
}

// ---------------------------------------------------------------------------
// Admin — Payments (enhanced)
// ---------------------------------------------------------------------------

export interface AdminPayment {
  id: number;
  landlord: number;
  landlord_name?: string;
  tenant: number;
  tenant_name?: string;
  lease: number;
  rent_period: number | null;
  amount: string;
  currency: string;
  payment_date: string;
  payment_method: string;
  reference: string;
  notes: string;
  status: 'PAID' | 'PENDING' | 'FAILED' | 'CANCELLED';
  gateway: string;
  gateway_reference: string;
  verified: boolean;
  recorded_by: number;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Rent Schedule
// ---------------------------------------------------------------------------

export interface RentScheduleItem {
  id: number;
  period_start: string;
  period_end: string;
  due_date: string;
  amount: string;
  currency: string;
  status: string;
  paid_amount: string;
  remaining_amount: string;
}

// ---------------------------------------------------------------------------
// Admin — Issues
// ---------------------------------------------------------------------------

export interface OperationalIssue {
  issue_type: string;
  severity: 'high' | 'medium' | 'low';
  title: string;
  description: string;
  entity_type: string;
  entity_id: number;
  related_url?: string;
  created_at: string;
}

export interface AdminIssuesResponse {
  count: number;
  issues: OperationalIssue[];
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
