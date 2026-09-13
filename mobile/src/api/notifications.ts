import api from './client';
import type { Notification, NotificationPreference, PaginatedResponse } from './types';

export async function listNotifications(params?: {
  is_read?: boolean;
  page?: number;
}) {
  const res = await api.get<PaginatedResponse<Notification>>('/notifications/', { params });
  return res.data;
}

export async function getUnreadCount(params?: { notification_type?: string }) {
  const res = await api.get<{ unread_count: number }>('/notifications/unread-count/', { params });
  return res.data;
}

export async function markRead(id: number, is_read = true) {
  const res = await api.post<Notification>(`/notifications/${id}/read/`, { is_read });
  return res.data;
}

export async function markAllRead() {
  const res = await api.post<{ updated: number }>('/notifications/mark-all-read/');
  return res.data;
}

export async function getPreferences(): Promise<NotificationPreference> {
  const res = await api.get<NotificationPreference>('/notifications/preferences/');
  return res.data;
}

export async function updatePreferences(
  data: Partial<NotificationPreference>,
): Promise<NotificationPreference> {
  const res = await api.patch<NotificationPreference>('/notifications/preferences/', data);
  return res.data;
}