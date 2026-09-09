// =============================================================================
// Alquiler Super User — Axios API Client
//
// Centralizes all HTTP communication with the Django REST Framework backend.
// Handles token injection, error normalization, and base URL configuration.
// =============================================================================

import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 15_000,
});

// ---------------------------------------------------------------------------
// Request interceptor — attach the auth token from localStorage.
// ---------------------------------------------------------------------------
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('alquiler_token');
  if (token) {
    config.headers.Authorization = `Token ${token}`;
  }
  return config;
});

// ---------------------------------------------------------------------------
// Response interceptor — normalize errors and handle 401.
// ---------------------------------------------------------------------------
export interface ApiError {
  detail: string;
  code?: string;
  errors?: Record<string, string[]>;
}

export class ApiRequestError extends Error {
  status: number;
  code?: string;
  errors?: Record<string, string[]>;

  constructor(status: number, message: string, code?: string, errors?: Record<string, string[]>) {
    super(message);
    this.name = 'ApiRequestError';
    this.status = status;
    this.code = code;
    this.errors = errors;
  }
}

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response) {
      const data = err.response.data as ApiError;
      // If 401, clear token — the auth context will detect this.
      if (err.response.status === 401) {
        localStorage.removeItem('alquiler_token');
        localStorage.removeItem('alquiler_user');
      }
      throw new ApiRequestError(
        err.response.status,
        data?.detail ?? 'An unexpected error occurred.',
        data?.code,
        data?.errors,
      );
    }
    // Network error or timeout
    throw new ApiRequestError(0, 'Network error. Please check your connection.');
  },
);

export default api;
