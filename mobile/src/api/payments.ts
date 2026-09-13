import api from './client';
import type {
  PaginatedResponse,
  Payment,
  PaymentInput,
  PaymentUpdateInput,
  RentScheduleItem,
} from './types';

export async function listPayments(params?: {
  status?: string;
  lease?: number;
  tenant?: number;
  search?: string;
  page?: number;
}) {
  const res = await api.get<PaginatedResponse<Payment>>('/payments/', { params });
  return res.data;
}

export async function getPayment(id: number): Promise<Payment> {
  const res = await api.get<Payment>(`/payments/${id}/`);
  return res.data;
}

export async function createPayment(
  data: PaymentInput,
  idempotencyKey?: string,
): Promise<Payment> {
  const res = await api.post<Payment>('/payments/', data, {
    headers: idempotencyKey
      ? { 'Idempotency-Key': idempotencyKey }
      : undefined,
  });
  return res.data;
}

export async function updatePayment(
  id: number,
  data: PaymentUpdateInput,
): Promise<Payment> {
  const res = await api.patch<Payment>(`/payments/${id}/`, data);
  return res.data;
}

export async function cancelPayment(id: number): Promise<Payment> {
  const res = await api.post<Payment>(`/payments/${id}/cancel/`);
  return res.data;
}

export async function listRentSchedules(params?: { lease?: number; page?: number }) {
  const res = await api.get<PaginatedResponse<RentScheduleItem>>('/rent-schedules/', { params });
  return res.data;
}