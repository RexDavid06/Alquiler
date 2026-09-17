import api from './client';
import { withCache } from './with-cache';
import { cacheKey } from '@/utils/cache';
import type { PaginatedResponse, Property, PropertyInput, Unit, UnitInput } from './types';

const PROPERTIES = '/properties/';

export async function listProperties(params?: { search?: string; status?: string; page?: number }) {
  return withCache(cacheKey('properties', params?.search, params?.status, params?.page ?? 1), async () => {
    const res = await api.get<PaginatedResponse<Property>>(PROPERTIES, { params });
    return res.data;
  });
}

export async function getProperty(id: number): Promise<Property> {
  return withCache(cacheKey('property', id), async () => {
    const res = await api.get<Property>(`${PROPERTIES}${id}/`);
    return res.data;
  });
}

export async function createProperty(data: PropertyInput): Promise<Property> {
  const res = await api.post<Property>(PROPERTIES, data);
  return res.data;
}

export async function updateProperty(id: number, data: Partial<PropertyInput>): Promise<Property> {
  const res = await api.patch<Property>(`${PROPERTIES}${id}/`, data);
  return res.data;
}

export async function listUnits(propertyId: number, params?: { page?: number }) {
  return withCache(cacheKey('units', propertyId, params?.page ?? 1), async () => {
    const res = await api.get<PaginatedResponse<Unit>>(
      `${PROPERTIES}${propertyId}/units/`,
      { params },
    );
    return res.data;
  });
}

export async function createUnit(propertyId: number, data: UnitInput): Promise<Unit> {
  const res = await api.post<Unit>(`${PROPERTIES}${propertyId}/units/`, data);
  return res.data;
}

export async function updateUnit(
  propertyId: number,
  unitId: number,
  data: Partial<UnitInput>,
): Promise<Unit> {
  const res = await api.patch<Unit>(`${PROPERTIES}${propertyId}/units/${unitId}/`, data);
  return res.data;
}