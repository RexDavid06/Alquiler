import * as Crypto from 'expo-crypto';
import axios, { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios';

import { storage } from '@/utils/storage';

// =============================================================================
// Alquiler Landlord — API client
//
// Multi-device aware: stores a stable device_id + refresh credential in
// secure storage, injects the access token on every request, and transparently
// rotates on 401 via POST /auth/refresh/.
// =============================================================================

export const API_BASE_URL =
  process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://localhost:8000/api/v1';

const STORAGE_KEYS = {
  accessToken: 'alquiler_access_token',
  refreshToken: 'alquiler_refresh_token',
  deviceId: 'alquiler_device_id',
  deviceName: 'alquiler_device_name',
  user: 'alquiler_user',
} as const;

export { STORAGE_KEYS };

export async function getStoredDevice() {
  let deviceId = await storage.getItemAsync(STORAGE_KEYS.deviceId);
  if (!deviceId) {
    deviceId = Crypto.randomUUID();
    await storage.setItemAsync(STORAGE_KEYS.deviceId, deviceId);
  }
  let deviceName = (await storage.getItemAsync(STORAGE_KEYS.deviceName)) ?? 'Alquiler mobile';
  return { deviceId, deviceName };
}

export async function persistSession(data: {
  token: string;
  refresh_token: string;
  device_id: string;
  expires_in?: number;
}) {
  await storage.setItemAsync(STORAGE_KEYS.accessToken, data.token);
  await storage.setItemAsync(STORAGE_KEYS.refreshToken, data.refresh_token);
  await storage.setItemAsync(STORAGE_KEYS.deviceId, data.device_id);
}

export async function clearSession() {
  await storage.deleteItemAsync(STORAGE_KEYS.accessToken);
  await storage.deleteItemAsync(STORAGE_KEYS.refreshToken);
  await storage.deleteItemAsync(STORAGE_KEYS.user);
  // Device id stays — same device keeps its session identity.
}

export async function getAccessToken() {
  return storage.getItemAsync(STORAGE_KEYS.accessToken);
}

export async function getRefreshCredential() {
  return {
    refreshToken: await storage.getItemAsync(STORAGE_KEYS.refreshToken),
    deviceId: await storage.getItemAsync(STORAGE_KEYS.deviceId),
  };
}

export async function saveUser(user: unknown) {
  await storage.setItemAsync(STORAGE_KEYS.user, JSON.stringify(user));
}

export async function loadUser(): Promise<unknown | null> {
  const raw = await storage.getItemAsync(STORAGE_KEYS.user);
  return raw ? JSON.parse(raw) : null;
}

// A single-flight lock, and a notifier for session expiry.
let refreshInFlight: Promise<boolean> | null = null;
let sessionExpiredHandler: (() => void) | null = null;

export function setSessionExpiredHandler(handler: (() => void) | null) {
  sessionExpiredHandler = handler;
}

function notifySessionExpired() {
  if (sessionExpiredHandler) sessionExpiredHandler();
}

export interface ApiErrorData {
  detail?: string;
  code?: string;
  errors?: Record<string, string[]>;
}

export class ApiRequestError extends Error {
  status: number;
  code?: string;
  errors?: Record<string, string[]>;

  constructor(data: ApiErrorData, status: number) {
    super(data?.detail ?? `Request failed with status ${status}`);
    this.name = 'ApiRequestError';
    this.status = status;
    this.code = data?.code;
    this.errors = data?.errors;
  }
}

async function tryRefresh(): Promise<boolean> {
  const { refreshToken, deviceId } = await getRefreshCredential();
  if (!refreshToken || !deviceId) return false;
  try {
    const resp = await axios.post<{ token: string; refresh_token: string; expires_in?: number }>(
      `${API_BASE_URL}/auth/refresh/`,
      { device_id: deviceId, refresh_token: refreshToken },
      { timeout: 15_000 },
    );
    await persistSession({ ...resp.data, device_id: deviceId });
    return true;
  } catch {
    await clearSession();
    notifySessionExpired();
    return false;
  }
}

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 20_000,
});

api.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
  const token = await getAccessToken();
  if (token) {
    config.headers.Authorization = `Token ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (res: AxiosResponse) => res,
  async (error: AxiosError<ApiErrorData>) => {
    const original = error.config as
      | (InternalAxiosRequestConfig & { _retried?: boolean })
      | undefined;

    if (!error.response || !original) {
      throw new ApiRequestError(
        { detail: 'Network error. Please check your connection.' },
        0,
      );
    }

    const status = error.response.status;
    const data = error.response.data ?? {};

    // 401 — attempt a single refresh then retry the original request once.
    if (status === 401 && !original._retried) {
      original._retried = true;
      refreshInFlight = refreshInFlight ?? tryRefresh().finally(() => {
        refreshInFlight = null;
      });
      const ok = await refreshInFlight;
      if (ok) {
        const token = await getAccessToken();
        if (token) {
          original.headers.Authorization = `Token ${token}`;
        }
        return api(original);
      }
      // Refresh failed — already cleared session + notified.
      throw new ApiRequestError(data, status);
    }

    throw new ApiRequestError(data, status);
  },
);

export default api;