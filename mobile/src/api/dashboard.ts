import api from './client';
import type { LandlordDashboard } from './types';

export async function getLandlordDashboard(): Promise<LandlordDashboard> {
  const res = await api.get<LandlordDashboard>('/dashboard/landlord/');
  return res.data;
}