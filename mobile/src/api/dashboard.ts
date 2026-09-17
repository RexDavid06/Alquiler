import api from './client';
import { withCache } from './with-cache';
import { cacheKey } from '@/utils/cache';
import type { LandlordDashboard } from './types';

export async function getLandlordDashboard(params?: { period?: string }): Promise<LandlordDashboard> {
  return withCache(cacheKey('dashboard-landlord', params?.period ?? 'all'), async () => {
    const res = await api.get<LandlordDashboard>('/dashboard/landlord/', { params });
    return res.data;
  });
}