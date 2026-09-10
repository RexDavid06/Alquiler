// =============================================================================
// Alquiler Super User — Admin Platform Operations API
//
// All endpoints under /api/v1/admin/ enforce PLATFORM_ADMIN authorization
// at the backend level.
// =============================================================================

import api from './client';
import type {
  PaginatedResponse,
  AdminUser,
  AdminUserDetail,
  AdminProperty,
  AdminPropertyDetail,
  AdminSubscription,
  AdminLease,
  AdminPayment,
  AdminIssuesResponse,
  AdminPlan,
  PlanSubscriber,
  AdminAuditLog,
  AdminActivity,
} from './types';

// ---------------------------------------------------------------------------
// Query parameter types
// ---------------------------------------------------------------------------

export interface UserQueryParams {
  search?: string;
  role?: string;
  status?: string;
  page?: number;
  page_size?: number;
  ordering?: string;
}

export interface PropertyQueryParams {
  search?: string;
  landlord?: number;
  property_type?: string;
  status?: string;
  page?: number;
  page_size?: number;
  ordering?: string;
}

export interface LeaseQueryParams {
  search?: string;
  status?: string;
  landlord?: number;
  tenant?: number;
  property?: number;
  page?: number;
  page_size?: number;
  ordering?: string;
}

export interface PaymentQueryParams {
  search?: string;
  status?: string;
  lease?: number;
  tenant?: number;
  page?: number;
  page_size?: number;
  ordering?: string;
}

export interface SubscriptionQueryParams {
  search?: string;
  plan?: string;
  status?: string;
  landlord?: number;
  page?: number;
  page_size?: number;
  ordering?: string;
}

// ---------------------------------------------------------------------------
// Admin Users
// ---------------------------------------------------------------------------

export async function getAdminUsers(
  params: UserQueryParams = {},
): Promise<PaginatedResponse<AdminUser>> {
  const query: Record<string, string | number> = {};
  if (params.search) query.search = params.search;
  if (params.role) query.role = params.role;
  if (params.status) query.status = params.status;
  if (params.page) query.page = params.page;
  if (params.page_size) query.page_size = params.page_size;
  if (params.ordering) query.ordering = params.ordering;
  const res = await api.get<PaginatedResponse<AdminUser>>('/admin/users/', { params: query });
  return res.data;
}

export async function getAdminUserDetail(
  id: number,
): Promise<AdminUserDetail> {
  const res = await api.get<AdminUserDetail>(`/admin/users/${id}/`);
  return res.data;
}

export async function suspendAdminUser(id: number): Promise<AdminUser> {
  const res = await api.post<AdminUser>(`/admin/users/${id}/suspend/`);
  return res.data;
}

export async function reactivateAdminUser(id: number): Promise<AdminUser> {
  const res = await api.post<AdminUser>(`/admin/users/${id}/reactivate/`);
  return res.data;
}

// ---------------------------------------------------------------------------
// Admin Properties
// ---------------------------------------------------------------------------

export async function getAdminProperties(
  params: PropertyQueryParams = {},
): Promise<PaginatedResponse<AdminProperty>> {
  const query: Record<string, string | number> = {};
  if (params.search) query.search = params.search;
  if (params.landlord) query.landlord = params.landlord;
  if (params.property_type) query.property_type = params.property_type;
  if (params.status) query.status = params.status;
  if (params.page) query.page = params.page;
  if (params.page_size) query.page_size = params.page_size;
  if (params.ordering) query.ordering = params.ordering;
  const res = await api.get<PaginatedResponse<AdminProperty>>('/admin/properties/', { params: query });
  return res.data;
}

export async function getAdminPropertyDetail(
  id: number,
): Promise<AdminPropertyDetail> {
  const res = await api.get<AdminPropertyDetail>(`/admin/properties/${id}/`);
  return res.data;
}

// ---------------------------------------------------------------------------
// Admin Leases (uses existing lease endpoints with admin access)
// ---------------------------------------------------------------------------

export async function getAdminLeases(
  params: LeaseQueryParams = {},
): Promise<PaginatedResponse<AdminLease>> {
  const query: Record<string, string | number> = {};
  if (params.search) query.search = params.search;
  if (params.status) query.status = params.status;
  if (params.landlord) query.landlord = params.landlord;
  if (params.tenant) query.tenant = params.tenant;
  if (params.property) query.property = params.property;
  if (params.page) query.page = params.page;
  if (params.page_size) query.page_size = params.page_size;
  if (params.ordering) query.ordering = params.ordering;
  const res = await api.get<PaginatedResponse<AdminLease>>('/leases/', { params: query });
  return res.data;
}

export async function getAdminLeaseDetail(
  id: number,
): Promise<AdminLease> {
  const res = await api.get<AdminLease>(`/leases/${id}/`);
  return res.data;
}

// ---------------------------------------------------------------------------
// Admin Payments (uses existing payment endpoints with admin access)
// ---------------------------------------------------------------------------

export async function getAdminPayments(
  params: PaymentQueryParams = {},
): Promise<PaginatedResponse<AdminPayment>> {
  const query: Record<string, string | number> = {};
  if (params.search) query.search = params.search;
  if (params.status) query.status = params.status;
  if (params.lease) query.lease = params.lease;
  if (params.tenant) query.tenant = params.tenant;
  if (params.page) query.page = params.page;
  if (params.page_size) query.page_size = params.page_size;
  if (params.ordering) query.ordering = params.ordering;
  const res = await api.get<PaginatedResponse<AdminPayment>>('/payments/payments/', { params: query });
  return res.data;
}

export async function getAdminPaymentDetail(
  id: number,
): Promise<AdminPayment> {
  const res = await api.get<AdminPayment>(`/payments/payments/${id}/`);
  return res.data;
}

// ---------------------------------------------------------------------------
// Admin Subscriptions
// ---------------------------------------------------------------------------

export async function getAdminSubscriptions(
  params: SubscriptionQueryParams = {},
): Promise<PaginatedResponse<AdminSubscription>> {
  const query: Record<string, string | number> = {};
  if (params.search) query.search = params.search;
  if (params.plan) query.plan = params.plan;
  if (params.status) query.status = params.status;
  if (params.landlord) query.landlord = params.landlord;
  if (params.page) query.page = params.page;
  if (params.page_size) query.page_size = params.page_size;
  if (params.ordering) query.ordering = params.ordering;
  const res = await api.get<PaginatedResponse<AdminSubscription>>('/admin/subscriptions/', { params: query });
  return res.data;
}

// ---------------------------------------------------------------------------
// Admin Issues
// ---------------------------------------------------------------------------

export async function getAdminIssues(): Promise<AdminIssuesResponse> {
  const res = await api.get<AdminIssuesResponse>('/admin/issues/');
  return res.data;
}

// ---------------------------------------------------------------------------
// Plans
// ---------------------------------------------------------------------------

export async function getAdminPlans(params?: {
  search?: string;
  is_active?: boolean;
  tier?: string;
  page?: number;
  page_size?: number;
}): Promise<PaginatedResponse<AdminPlan>> {
  const response = await api.get('/admin/plans/', { params });
  return response.data;
}

export async function getAdminPlanDetail(id: number): Promise<AdminPlan> {
  const response = await api.get(`/admin/plans/${id}/`);
  return response.data;
}

export async function createAdminPlan(data: {
  tier: string;
  name: string;
  description?: string;
  max_active_tenants: number;
  max_properties: number;
  price_ngn: string;
  is_active?: boolean;
  display_order?: number;
}): Promise<AdminPlan> {
  const response = await api.post('/admin/plans/', data);
  return response.data;
}

export async function updateAdminPlan(id: number, data: Partial<{
  tier: string;
  name: string;
  description: string;
  max_active_tenants: number;
  max_properties: number;
  price_ngn: string;
  is_active: boolean;
  display_order: number;
}>): Promise<AdminPlan> {
  const response = await api.patch(`/admin/plans/${id}/`, data);
  return response.data;
}

export async function deactivateAdminPlan(id: number): Promise<AdminPlan> {
  const response = await api.delete(`/admin/plans/${id}/`);
  return response.data;
}

export async function activateAdminPlan(id: number): Promise<AdminPlan> {
  const response = await api.post(`/admin/plans/${id}/activate/`);
  return response.data;
}

export async function getAdminPlanSubscribers(planId: number, params?: {
  page?: number;
  page_size?: number;
}): Promise<PaginatedResponse<PlanSubscriber>> {
  const response = await api.get(`/admin/plans/${planId}/subscribers/`, { params });
  return response.data;
}

// ---------------------------------------------------------------------------
// Admin Audit Logs
// ---------------------------------------------------------------------------

export interface AuditLogQueryParams {
  search?: string;
  action?: string;
  actor?: number;
  object_type?: string;
  page?: number;
  page_size?: number;
  ordering?: string;
}

export async function getAdminAuditLogs(
  params: AuditLogQueryParams = {},
): Promise<PaginatedResponse<AdminAuditLog>> {
  const query: Record<string, string | number> = {};
  if (params.search) query.search = params.search;
  if (params.action) query.action = params.action;
  if (params.actor) query.actor = params.actor;
  if (params.object_type) query.object_type = params.object_type;
  if (params.page) query.page = params.page;
  if (params.page_size) query.page_size = params.page_size;
  if (params.ordering) query.ordering = params.ordering;
  const res = await api.get<PaginatedResponse<AdminAuditLog>>('/admin/audit-logs/', { params: query });
  return res.data;
}

// ---------------------------------------------------------------------------
// Admin Activity Feed
// ---------------------------------------------------------------------------

export async function getAdminActivityFeed(
  limit: number = 50,
): Promise<{ count: number; activities: AdminActivity[] }> {
  const res = await api.get<{ count: number; activities: AdminActivity[] }>('/admin/activity/', {
    params: { limit },
  });
  return res.data;
}
