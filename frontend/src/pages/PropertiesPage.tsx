// =============================================================================
// Alquiler Super User — Properties Page
//
// Platform-wide property listing: search, filter by landlord/type/status,
// pagination, detail view with units.
// =============================================================================

import { useState, useEffect, useCallback } from 'react';
import { getAdminProperties, getAdminPropertyDetail } from '../api/admin';
import type { AdminProperty, AdminPropertyDetail, PaginatedResponse } from '../api/types';
import DataTable, { type Column } from '../components/DataTable';
import SearchInput from '../components/SearchInput';
import FilterSelect from '../components/FilterSelect';
import Pagination from '../components/Pagination';
import StatusBadge from '../components/StatusBadge';
import DetailPanel, { DetailRow } from '../components/DetailPanel';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorState from '../components/ErrorState';
import EmptyState from '../components/EmptyState';
import { Building2 } from 'lucide-react';

const TYPE_OPTIONS = [
  { label: 'All Types', value: '' },
  { label: 'Apartment', value: 'APARTMENT' },
  { label: 'House', value: 'HOUSE' },
  { label: 'Duplex', value: 'DUPLEX' },
  { label: 'Shop', value: 'SHOP' },
  { label: 'Office', value: 'OFFICE' },
  { label: 'Warehouse', value: 'WAREHOUSE' },
  { label: 'Other', value: 'OTHER' },
];

const STATUS_OPTIONS = [
  { label: 'All Statuses', value: '' },
  { label: 'Active', value: 'ACTIVE' },
  { label: 'Archived', value: 'ARCHIVED' },
];

const PAGE_SIZE = 20;

export default function PropertiesPage() {
  const [data, setData] = useState<PaginatedResponse<AdminProperty> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [propertyType, setPropertyType] = useState('');
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const [selectedProperty, setSelectedProperty] = useState<AdminPropertyDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getAdminProperties({
        search: search || undefined,
        property_type: propertyType || undefined,
        status: status || undefined,
        page,
        page_size: PAGE_SIZE,
      });
      setData(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load properties.');
    } finally {
      setLoading(false);
    }
  }, [search, propertyType, status, page]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleRowClick = async (property: AdminProperty) => {
    setDetailLoading(true);
    try {
      const detail = await getAdminPropertyDetail(property.id);
      setSelectedProperty(detail);
    } catch {
      // ignore
    } finally {
      setDetailLoading(false);
    }
  };

  const totalPages = data ? Math.ceil(data.count / PAGE_SIZE) : 0;

  const columns: Column<AdminProperty>[] = [
    {
      key: 'id',
      header: 'ID',
      render: (p) => <span className="font-medium text-gray-900">{p.id}</span>,
    },
    {
      key: 'name',
      header: 'Name',
      render: (p) => p.name,
    },
    {
      key: 'landlord_name',
      header: 'Landlord',
      render: (p) => (
        <div>
          <div className="text-gray-900">{p.landlord_name}</div>
          <div className="text-xs text-gray-500">{p.landlord_email}</div>
        </div>
      ),
    },
    {
      key: 'property_type',
      header: 'Type',
      render: (p) => p.property_type,
    },
    {
      key: 'city',
      header: 'City',
      render: (p) => p.city || '—',
    },
    {
      key: 'units',
      header: 'Units',
      render: (p) => (
        <span>
          {p.occupied_units}/{p.unit_count} occupied
        </span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (p) => <StatusBadge status={p.status} />,
    },
  ];

  if (loading && !data) return <LoadingSpinner message="Loading properties…" />;
  if (error && !data) return <ErrorState message={error} onRetry={fetchData} />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Properties</h1>
        <p className="mt-1 text-sm text-gray-500">
          Platform-wide property listing and inspection.
        </p>
      </div>

      <div className="flex flex-col sm:flex-row gap-3">
        <SearchInput
          value={search}
          onChange={(v) => { setSearch(v); setPage(1); }}
          placeholder="Search by name, address, or landlord…"
          className="flex-1"
        />
        <FilterSelect
          value={propertyType}
          onChange={(v) => { setPropertyType(v); setPage(1); }}
          options={TYPE_OPTIONS}
          label="Type"
        />
        <FilterSelect
          value={status}
          onChange={(v) => { setStatus(v); setPage(1); }}
          options={STATUS_OPTIONS}
          label="Status"
        />
      </div>

      {data && data.results.length === 0 ? (
        <EmptyState icon={Building2} title="No properties found" description="No properties match your filters." />
      ) : data ? (
        <>
          <DataTable
            columns={columns}
            data={data.results}
            onRowClick={(p) => handleRowClick(p)}
          />
          <Pagination
            currentPage={page}
            totalPages={totalPages}
            onPageChange={setPage}
            totalItems={data.count}
          />
        </>
      ) : null}

      {selectedProperty && (
        <DetailPanel title={`Property #${selectedProperty.id}`} onClose={() => setSelectedProperty(null)}>
          {detailLoading ? (
            <LoadingSpinner message="Loading details…" />
          ) : (
            <div className="space-y-4">
              <DetailRow label="ID" value={selectedProperty.id} />
              <DetailRow label="Name" value={selectedProperty.name} />
              <DetailRow label="Type" value={selectedProperty.property_type} />
              <DetailRow label="Address" value={selectedProperty.address} />
              <DetailRow label="City" value={selectedProperty.city || '—'} />
              <DetailRow label="State" value={selectedProperty.state || '—'} />
              <DetailRow label="Country" value={selectedProperty.country} />
              <DetailRow label="Currency" value={selectedProperty.currency} />
              <DetailRow label="Status" value={<StatusBadge status={selectedProperty.status} />} />
              <DetailRow label="Description" value={selectedProperty.description || '—'} />
              <DetailRow label="Landlord" value={`${selectedProperty.landlord_name} (${selectedProperty.landlord_email})`} />
              <DetailRow label="Units" value={`${selectedProperty.occupied_units} occupied / ${selectedProperty.vacant_units} vacant / ${selectedProperty.unit_count} total`} />
              <DetailRow label="Created" value={new Date(selectedProperty.created_at).toLocaleString()} />

              {selectedProperty.units.length > 0 && (
                <div className="mt-6">
                  <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">Units</h3>
                  <div className="space-y-2">
                    {selectedProperty.units.map((u) => (
                      <div key={u.id} className="rounded-md bg-gray-50 p-3 text-sm flex items-center justify-between">
                        <div>
                          <span className="font-medium">{u.name}</span>
                          {u.description && <p className="text-gray-500 text-xs mt-0.5">{u.description}</p>}
                        </div>
                        <StatusBadge status={u.status} />
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </DetailPanel>
      )}
    </div>
  );
}
