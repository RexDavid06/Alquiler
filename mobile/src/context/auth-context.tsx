import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import * as SecureStore from 'expo-secure-store';

import * as authApi from '@/api/auth';
import {
  STORAGE_KEYS,
  clearSession,
  loadUser,
  setSessionExpiredHandler,
} from '@/api/client';
import type { User } from '@/api/types';

interface AuthContextValue {
  user: User | null;
  initializing: boolean;
  login: (email: string, password: string) => Promise<User>;
  register: (data: {
    email: string;
    password: string;
    first_name: string;
    last_name: string;
    phone: string;
  }) => Promise<User>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [initializing, setInitializing] = useState(true);

  const handleSessionExpired = useCallback(async () => {
    await clearSession();
    setUser(null);
  }, []);

  useEffect(() => {
    setSessionExpiredHandler(() => {
      void handleSessionExpired();
    });

    void (async () => {
      const stored = (await loadUser()) as User | null;
      const token = await SecureStore.getItemAsync(STORAGE_KEYS.accessToken);
      if (stored && token) {
        setUser(stored);
      } else {
        await clearSession();
      }
      setInitializing(false);
    })();

    return () => setSessionExpiredHandler(null);
  }, [handleSessionExpired]);

  const login = useCallback(async (email: string, password: string) => {
    const data = await authApi.login({ email, password });
    setUser(data.user);
    return data.user;
  }, []);

  const register = useCallback(async (data: {
    email: string;
    password: string;
    first_name: string;
    last_name: string;
    phone: string;
  }) => {
    const res = await authApi.register(data);
    setUser(res.user);
    return res.user;
  }, []);

  const logout = useCallback(async () => {
    await authApi.logout();
    await clearSession();
    setUser(null);
  }, []);

  const refreshUser = useCallback(async () => {
    try {
      const fresh = await authApi.getMe();
      setUser(fresh);
      await SecureStore.setItemAsync(STORAGE_KEYS.user, JSON.stringify(fresh));
    } catch {
      // Token expired and refresh failed — handler above already fired.
    }
  }, []);

  const value = useMemo(
    () => ({ user, initializing, login, register, logout, refreshUser }),
    [user, initializing, login, register, logout, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return ctx;
}