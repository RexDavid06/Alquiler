import api from './client';
import type {
  Invitation,
  InvitationInput,
  PaginatedResponse,
  TenantDetail,
  TenantUser,
} from './types';

const TENANTS = '/tenants/';
const INVITATIONS = '/tenants/invitations/';

export async function listTenants(params?: { search?: string; status?: string; page?: number }) {
  const res = await api.get<PaginatedResponse<TenantUser>>(TENANTS, { params });
  return res.data;
}

export async function getTenant(id: number): Promise<TenantDetail> {
  const res = await api.get<TenantDetail>(`${TENANTS}${id}/`);
  return res.data;
}

export async function listInvitations(params?: { status?: string; page?: number }) {
  const res = await api.get<PaginatedResponse<Invitation>>(INVITATIONS, { params });
  return res.data;
}

export async function createInvitation(data: InvitationInput): Promise<Invitation> {
  const res = await api.post<Invitation>(INVITATIONS, data);
  return res.data;
}

export async function revokeInvitation(id: number): Promise<Invitation> {
  const res = await api.post<Invitation>(`${INVITATIONS}${id}/revoke/`);
  return res.data;
}

export async function resendInvitation(id: number): Promise<Invitation> {
  const res = await api.post<Invitation>(`${INVITATIONS}${id}/resend/`);
  return res.data;
}