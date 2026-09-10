// =============================================================================
// Alquiler Super User — Auth API
// =============================================================================

import api from './client';
import type { LoginRequest, LoginResponse, User } from './types';

export async function loginUser(data: LoginRequest): Promise<LoginResponse> {
  const res = await api.post<LoginResponse>('/auth/login/', data);
  return res.data;
}

export async function logoutUser(): Promise<void> {
  await api.post('/auth/logout/');
}

export async function getCurrentUser(): Promise<User> {
  const res = await api.get<User>('/auth/me/');
  return res.data;
}
