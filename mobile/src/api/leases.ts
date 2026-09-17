import api from './client';
import { withCache } from './with-cache';
import { cacheKey } from '@/utils/cache';
import type {
  Lease,
  LeaseDetail,
  PaginatedResponse,
  RentScheduleItem,
  RenewInput,
} from './types';

const LEASES = '/leases/';

export async function listLeases(params?: {
  status?: string;
  search?: string;
  page?: number;
}) {
  return withCache(cacheKey('leases', params?.status, params?.search, params?.page ?? 1), async () => {
    const res = await api.get<PaginatedResponse<Lease>>(LEASES, { params });
    return res.data;
  });
}

export async function getLease(id: number): Promise<LeaseDetail> {
  return withCache(cacheKey('lease', id), async () => {
    const res = await api.get<LeaseDetail>(`${LEASES}${id}/`);
    return res.data;
  });
}

export async function createLease(data: unknown): Promise<LeaseDetail> {
  const res = await api.post<LeaseDetail>(LEASES, data);
  return res.data;
}

export async function renewLease(id: number, data: RenewInput): Promise<LeaseDetail> {
  const res = await api.post<LeaseDetail>(`${LEASES}${id}/renew/`, data);
  return res.data;
}

export async function terminateLease(id: number): Promise<LeaseDetail> {
  const res = await api.post<LeaseDetail>(`${LEASES}${id}/terminate/`);
  return res.data;
}

export async function getLeaseHistory(id: number): Promise<Lease[]> {
  const res = await api.get<Lease[]>(`${LEASES}${id}/history/`);
  return res.data;
}

export async function listRentSchedules(params?: { lease?: number; page?: number }) {
  return withCache(cacheKey('rent-schedules', params?.lease, params?.page ?? 1), async () => {
    const res = await api.get<PaginatedResponse<RentScheduleItem>>('/rent-schedules/', { params });
    return res.data;
  });
}