// =============================================================================
// Alquiler Landlord Mobile — API types
// Mirrors the backend serializers exactly.
// =============================================================================

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export type Role = 'LANDLORD' | 'TENANT' | 'PLATFORM_ADMIN';
export type AccountStatus = 'PENDING' | 'ACTIVE' | 'SUSPENDED' | 'DEACTIVATED';

export interface User {
  id: number;
  email: string;
  role: Role;
  first_name: string;
  last_name: string;
  phone: string;
  full_name: string;
  status: AccountStatus;
  email_verified: boolean;
  created_at: string;
  updated_at: string;
}

export interface LoginResponse {
  user: User;
  token: string;
  refresh_token: string;
  device_id: string;
  expires_in: number;
}

export interface RefreshResponse {
  token: string;
  refresh_token: string;
  expires_in: number;
}

// ---------------------------------------------------------------------------
// Generic pagination
// ---------------------------------------------------------------------------

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

// ---------------------------------------------------------------------------
// Properties / Units
// ---------------------------------------------------------------------------

export interface Property {
  id: number;
  landlord: number;
  landlord_name: string;
  name: string;
  property_type: string;
  address: string;
  city: string;
  state: string;
  country: string;
  description: string;
  currency: string;
  status: 'ACTIVE' | 'ARCHIVED';
  unit_count: number;
  occupied_units: number;
  vacant_units: number;
  created_at: string;
  updated_at: string;
}

export interface PropertyInput {
  name: string;
  property_type: string;
  address: string;
  city: string;
  state: string;
  country: string;
  description: string;
  currency: string;
  status?: 'ACTIVE' | 'ARCHIVED';
}

export interface Unit {
  id: number;
  property: number;
  property_name: string;
  property_address: string;
  name: string;
  description: string;
  status: 'VACANT' | 'OCCUPIED';
  created_at: string;
  updated_at: string;
}

export interface UnitInput {
  name: string;
  description: string;
}

// ---------------------------------------------------------------------------
// Tenants / Invitations
// ---------------------------------------------------------------------------

export interface TenantUser {
  id: number;
  email: string;
  full_name: string;
  first_name: string;
  last_name: string;
  phone: string;
  status: AccountStatus;
  email_verified: boolean;
  created_at: string;
  total_leases: number;
  active_leases: number;
}

export interface TenantDetail extends TenantUser {
  leases: TenantLeaseSummary[];
}

export interface TenantLeaseSummary {
  id: number;
  landlord_name: string;
  property_name: string;
  unit_name: string;
  status: string;
  start_date: string;
  expiry_date: string;
  rent_amount: string;
  currency: string;
  rent_frequency: string;
  created_at: string;
}

export type InvitationStatus = 'PENDING' | 'ACCEPTED' | 'REVOKED' | 'EXPIRED';

export interface Invitation {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  phone: string;
  property: number;
  property_name: string;
  unit: number;
  unit_name: string;
  status: InvitationStatus;
  expires_at: string;
  created_at: string;
}

export interface InvitationInput {
  email: string;
  first_name: string;
  last_name: string;
  phone: string;
  property: number;
  unit: number;
}

// ---------------------------------------------------------------------------
// Leases
// ---------------------------------------------------------------------------

export type LeaseStatus = 'FUTURE' | 'ACTIVE' | 'EXPIRING' | 'EXPIRED' | 'TERMINATED';
export type RentFrequency = 'MONTHLY' | 'QUARTERLY' | 'ANNUALLY';

export interface Lease {
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
  rent_frequency: RentFrequency;
  rent_due_day: number;
  status: LeaseStatus;
  previous_lease: number | null;
  notes: string;
  terminated_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface LeaseInput {
  tenant: number;
  property: number;
  unit: number;
  start_date: string;
  expiry_date: string;
  rent_amount: string;
  currency: string;
  rent_frequency: RentFrequency;
  rent_due_day: number;
  notes: string;
}

export interface RenewInput {
  start_date: string;
  expiry_date: string;
  rent_amount: string;
  rent_frequency: RentFrequency;
  rent_due_day: number;
  notes: string;
}

export interface LeaseDetail extends Lease {
  rent_schedule: RentScheduleItem[];
}

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
// Payments
// ---------------------------------------------------------------------------

export type PaymentStatus = 'PAID' | 'PENDING' | 'FAILED' | 'CANCELLED';

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
  status: PaymentStatus;
  idempotency_key: string | null;
  gateway: string;
  gateway_reference: string;
  verified: boolean;
  recorded_by: number;
  created_at: string;
  updated_at: string;
}

export interface PaymentInput {
  tenant: number;
  lease: number;
  rent_period: number | null;
  amount: string;
  currency: string;
  payment_date: string;
  payment_method: string;
  reference: string;
  notes: string;
  status: PaymentStatus;
}

export interface PaymentUpdateInput {
  amount?: string;
  payment_date?: string;
  payment_method?: string;
  reference?: string;
  notes?: string;
  status?: PaymentStatus;
}

// ---------------------------------------------------------------------------
// Notifications
// ---------------------------------------------------------------------------

export interface Notification {
  id: number;
  recipient: number;
  recipient_email: string;
  notification_type: string;
  notification_type_display: string;
  channel: string;
  status: string;
  lease: number | null;
  rent_period: number | null;
  payment: number | null;
  invitation: number | null;
  title: string;
  message: string;
  is_read: boolean;
  scheduled_for: string | null;
  sent_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface NotificationPreference {
  id: number;
  user: number;
  email_enabled: boolean;
  in_app_enabled: boolean;
  notify_rent_reminders: boolean;
  notify_lease_reminders: boolean;
  notify_invitations: boolean;
  notify_payment_confirmations: boolean;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Dashboard (landlord)
// ---------------------------------------------------------------------------

export interface LandlordDashboard {
  properties: Record<string, number>;
  units: Record<string, number>;
  leases: Record<string, number>;
  collected_rent: Record<string, number | string | null>;
  overdue_rent: Record<string, number | string>;
  upcoming_rent: Record<string, number | string>;
  lease_expiry_alerts: Array<Record<string, unknown>>;
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

export interface Subscription {
  id: number;
  plan: number;
  status: string;
  billing_cycle: string;
  started_at: string;
  current_period_start: string;
  current_period_end: string | null;
  trial_end: string | null;
  cancelled_at: string | null;
  cancel_reason: string;
  is_trial_expired: boolean;
  is_active_subscription: boolean;
  active_tenants_count: number;
  property_count: number;
  created_at: string;
  updated_at: string;
}

export interface SubscriptionUsage {
  active_tenants: number;
  active_leases: number;
  properties: number;
  active_units: number;
  plan_name: string;
  plan_tier: string;
  max_active_tenants: number;
  max_properties: number;
  max_active_leases?: number | null;
}