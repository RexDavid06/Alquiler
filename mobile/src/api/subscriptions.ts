import api from './client';
import type { PaginatedResponse, Plan, Subscription, SubscriptionUsage } from './types';

export async function listPlans(params?: { is_active?: boolean }) {
  const res = await api.get<PaginatedResponse<Plan>>('/plans/', { params });
  return res.data;
}

export async function getSubscription(): Promise<Subscription> {
  const res = await api.get<Subscription>('/subscription/');
  return res.data;
}

export async function getUsage(): Promise<SubscriptionUsage> {
  const res = await api.get<SubscriptionUsage>('/subscription/usage/');
  return res.data;
}

export async function subscribeToPlan(planId: number, billingCycle?: string) {
  const res = await api.post<Subscription>('/subscription/', {
    plan: planId,
    billing_cycle: billingCycle ?? 'MONTHLY',
  });
  return res.data;
}