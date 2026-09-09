// =============================================================================
// Alquiler Super User — Auth Context
//
// Manages authentication state across the application.
// Persists token and user in localStorage for session continuity.
// Enforces PLATFORM_ADMIN role on the frontend (backend is the real guard).
// =============================================================================

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from 'react';
import type { User } from '../api/types';
import { loginUser, logoutUser, getCurrentUser } from '../api/auth';
import { ApiRequestError } from '../api/client';

interface AuthState {
  user: User | null;
  token: string | null;
  loading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  clearError: () => void;
}

const AuthContext = createContext<AuthState | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => {
    const stored = localStorage.getItem('alquiler_user');
    return stored ? JSON.parse(stored) : null;
  });
  const [token, setToken] = useState<string | null>(() =>
    localStorage.getItem('alquiler_token'),
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // ---------------------------------------------------------------------------
  // On mount: validate stored token by fetching /me/.
  // ---------------------------------------------------------------------------
  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }

    getCurrentUser()
      .then((u) => {
        // Enforce PLATFORM_ADMIN role on the frontend.
        if (u.role !== 'PLATFORM_ADMIN') {
          localStorage.removeItem('alquiler_token');
          localStorage.removeItem('alquiler_user');
          setToken(null);
          setUser(null);
          setError('Access denied. This application is for platform administrators only.');
        } else {
          setUser(u);
          localStorage.setItem('alquiler_user', JSON.stringify(u));
        }
      })
      .catch(() => {
        // Token expired or invalid — clear everything.
        localStorage.removeItem('alquiler_token');
        localStorage.removeItem('alquiler_user');
        setToken(null);
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ---------------------------------------------------------------------------
  // Login
  // ---------------------------------------------------------------------------
  const login = useCallback(async (email: string, password: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await loginUser({ email, password });

      // Enforce PLATFORM_ADMIN role on the frontend.
      if (res.user.role !== 'PLATFORM_ADMIN') {
        const msg = 'Access denied. This application is for platform administrators only.';
        setError(msg);
        setLoading(false);
        return;
      }

      localStorage.setItem('alquiler_token', res.token);
      localStorage.setItem('alquiler_user', JSON.stringify(res.user));
      setToken(res.token);
      setUser(res.user);
    } catch (err) {
      if (err instanceof ApiRequestError) {
        setError(err.message);
      } else {
        setError('An unexpected error occurred.');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  // ---------------------------------------------------------------------------
  // Logout
  // ---------------------------------------------------------------------------
  const logout = useCallback(async () => {
    try {
      await logoutUser();
    } catch {
      // Silently ignore — clear local state regardless.
    } finally {
      localStorage.removeItem('alquiler_token');
      localStorage.removeItem('alquiler_user');
      setToken(null);
      setUser(null);
    }
  }, []);

  const clearError = useCallback(() => setError(null), []);

  return (
    <AuthContext.Provider value={{ user, token, loading, error, login, logout, clearError }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return ctx;
}
