import api, { getStoredDevice, persistSession, saveUser } from './client';
import type { LoginResponse, User } from './types';

export interface LoginInput {
  email: string;
  password: string;
  device_id?: string;
  device_name?: string;
}

export async function login(data: LoginInput): Promise<LoginResponse> {
  const device = await getStoredDevice();
  const res = await api.post<LoginResponse>('/auth/login/', {
    ...data,
    device_id: data.device_id ?? device.deviceId,
    device_name: data.device_name ?? device.deviceName,
    email: data.email.toLowerCase().trim(),
  });
  await persistSession(res.data);
  await saveUser(res.data.user);
  return res.data;
}

export async function register(data: LoginInput & {
  first_name: string;
  last_name: string;
  phone: string;
}): Promise<LoginResponse> {
  const device = await getStoredDevice();
  // Landlord-only endpoint: the backend assigns role=LANDLORD server-side,
  // so the client never sends a role.
  const res = await api.post<LoginResponse>('/auth/register/landlord/', {
    ...data,
    device_id: device.deviceId,
    device_name: device.deviceName,
    email: data.email.toLowerCase().trim(),
  });
  await persistSession(res.data);
  await saveUser(res.data.user);
  return res.data;
}

export async function logout() {
  try {
    await api.post('/auth/logout/');
  } catch {
    // Session may already be invalid — still clear local state.
  }
}

export async function getMe(): Promise<User> {
  const res = await api.get<User>('/auth/me/');
  return res.data;
}

export async function changePassword(old_password: string, new_password: string) {
  const res = await api.post<{ detail: string }>('/auth/change-password/', {
    old_password,
    new_password,
  });
  return res.data;
}