// =============================================================================
// Alquiler Super User — Dashboard API
// =============================================================================

import api from './client';
import type { AdminDashboardResponse, PaginatedResponse, Plan, Property, Lease, Payment, Notification } from './types';

// ---------------------------------------------------------------------------
// Admin Dashboard
// ---------------------------------------------------------------------------

export async function getAdminDashboard(
  startDate?: string,
  endDate?: string,
): Promise<AdminDashboardResponse> {
  const params: Record<string, string> = {};
  if (startDate) params.start_date = startDate;
  if (endDate) params.end_date = endDate;
  const res = await api.get<AdminDashboardResponse>('/dashboard/admin/', { params });
  return res.data;
}

// ---------------------------------------------------------------------------
// CSV Export
// ---------------------------------------------------------------------------

export async function exportAdminDashboardCsv(
  startDate?: string,
  endDate?: string,
): Promise<void> {
  const params: Record<string, string> = {};
  if (startDate) params.start_date = startDate;
  if (endDate) params.end_date = endDate;
  const res = await api.get('/dashboard/admin/export/', {
    params,
    responseType: 'blob',
  });
  const url = window.URL.createObjectURL(new Blob([res.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', 'admin_dashboard.csv');
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------------------
// Plans
// ---------------------------------------------------------------------------

export async function getPlans(): Promise<Plan[]> {
  const res = await api.get<Plan[] | PaginatedResponse<Plan>>('/subscriptions/plans/');
  // Handle both paginated and non-paginated responses
  const data = res.data;
  if (Array.isArray(data)) return data;
  return data.results ?? [];
}

// ---------------------------------------------------------------------------
// Properties (read-only for admin)
// ---------------------------------------------------------------------------

export async function getProperties(): Promise<Property[]> {
  const res = await api.get<PaginatedResponse<Property>>('/properties/');
  return res.data.results ?? [];
}

// ---------------------------------------------------------------------------
// Leases (read-only for admin)
// ---------------------------------------------------------------------------

export async function getLeases(): Promise<Lease[]> {
  const res = await api.get<PaginatedResponse<Lease>>('/leases/');
  return res.data.results ?? [];
}

// ---------------------------------------------------------------------------
// Payments (read-only for admin)
// ---------------------------------------------------------------------------

export async function getPayments(): Promise<Payment[]> {
  const res = await api.get<PaginatedResponse<Payment>>('/payments/');
  return res.data.results ?? [];
}

// ---------------------------------------------------------------------------
// Notifications (admin's own)
// ---------------------------------------------------------------------------

export async function getNotifications(): Promise<Notification[]> {
  const res = await api.get<PaginatedResponse<Notification>>('/notifications/');
  return res.data.results ?? [];
}

// ---------------------------------------------------------------------------
// Health Check (unauthenticated)
// ---------------------------------------------------------------------------

export async function getHealthCheck(): Promise<{ status: string; database: string }> {
  const res = await api.get<{ status: string; database: string }>('/auth/health/');
  return res.data;
}
