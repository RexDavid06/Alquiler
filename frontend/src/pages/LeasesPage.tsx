// =============================================================================
// Alquiler Super User — Leases Page
//
// Platform-wide lease listing: search, filter by status/landlord/tenant,
// pagination, detail view with rent schedule.
// =============================================================================

import { useState, useEffect, useCallback } from 'react';
import { getAdminLeases, getAdminLeaseDetail } from '../api/admin';
import type { AdminLease, PaginatedResponse } from '../api/types';
import DataTable, { type Column } from '../components/DataTable';
import SearchInput from '../components/SearchInput';
import FilterSelect from '../components/FilterSelect';
import Pagination from '../components/Pagination';
import StatusBadge from '../components/StatusBadge';
import DetailPanel, { DetailRow } from '../components/DetailPanel';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorState from '../components/ErrorState';
import EmptyState from '../components/EmptyState';
import { FileText } from 'lucide-react';

const STATUS_OPTIONS = [
  { label: 'All Statuses', value: '' },
  { label: 'Active', value: 'ACTIVE' },
  { label: 'Expiring', value: 'EXPIRING' },
  { label: 'Expired', value: 'EXPIRED' },
  { label: 'Future', value: 'FUTURE' },
  { label: 'Terminated', value: 'TERMINATED' },
];

const PAGE_SIZE = 20;

export default function LeasesPage() {
  const [data, setData] = useState<PaginatedResponse<AdminLease> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const [selectedLease, setSelectedLease] = useState<AdminLease | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getAdminLeases({
        search: search || undefined,
        status: status || undefined,
        page,
        page_size: PAGE_SIZE,
      });
      setData(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load leases.');
    } finally {
      setLoading(false);
    }
  }, [search, status, page]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleRowClick = async (lease: AdminLease) => {
    setDetailLoading(true);
    try {
      const detail = await getAdminLeaseDetail(lease.id);
      setSelectedLease(detail);
    } catch {
      // ignore
    } finally {
      setDetailLoading(false);
    }
  };

  const totalPages = data ? Math.ceil(data.count / PAGE_SIZE) : 0;

  const columns: Column<AdminLease>[] = [
    {
      key: 'id',
      header: 'ID',
      render: (l) => <span className="font-medium text-gray-900">{l.id}</span>,
    },
    {
      key: 'landlord_name',
      header: 'Landlord',
      render: (l) => l.landlord_name,
    },
    {
      key: 'tenant_name',
      header: 'Tenant',
      render: (l) => (
        <div>
          <div className="text-gray-900">{l.tenant_name}</div>
          <div className="text-xs text-gray-500">{l.tenant_email}</div>
        </div>
      ),
    },
    {
      key: 'property_name',
      header: 'Property',
      render: (l) => `${l.property_name} — ${l.unit_name}`,
    },
    {
      key: 'start_date',
      header: 'Start',
      render: (l) => l.start_date,
    },
    {
      key: 'expiry_date',
      header: 'Expiry',
      render: (l) => l.expiry_date,
    },
    {
      key: 'rent_amount',
      header: 'Rent',
      render: (l) => <span className="font-medium">₦{parseFloat(l.rent_amount).toLocaleString()}</span>,
    },
    {
      key: 'status',
      header: 'Status',
      render: (l) => <StatusBadge status={l.status} />,
    },
  ];

  if (loading && !data) return <LoadingSpinner message="Loading leases…" />;
  if (error && !data) return <ErrorState message={error} onRetry={fetchData} />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Leases</h1>
        <p className="mt-1 text-sm text-gray-500">
          Platform-wide lease listing and inspection.
        </p>
      </div>

      <div className="flex flex-col sm:flex-row gap-3">
        <SearchInput
          value={search}
          onChange={(v) => { setSearch(v); setPage(1); }}
          placeholder="Search by tenant, property, or unit…"
          className="flex-1"
        />
        <FilterSelect
          value={status}
          onChange={(v) => { setStatus(v); setPage(1); }}
          options={STATUS_OPTIONS}
          label="Status"
        />
      </div>

      {data && data.results.length === 0 ? (
        <EmptyState icon={FileText} title="No leases found" description="No leases match your filters." />
      ) : data ? (
        <>
          <DataTable
            columns={columns}
            data={data.results}
            onRowClick={(l) => handleRowClick(l)}
          />
          <Pagination
            currentPage={page}
            totalPages={totalPages}
            onPageChange={setPage}
            totalItems={data.count}
          />
        </>
      ) : null}

      {selectedLease && (
        <DetailPanel title={`Lease #${selectedLease.id}`} onClose={() => setSelectedLease(null)}>
          {detailLoading ? (
            <LoadingSpinner message="Loading details…" />
          ) : (
            <div className="space-y-4">
              <DetailRow label="ID" value={selectedLease.id} />
              <DetailRow label="Status" value={<StatusBadge status={selectedLease.status} />} />
              <DetailRow label="Landlord" value={selectedLease.landlord_name} />
              <DetailRow label="Tenant" value={`${selectedLease.tenant_name} (${selectedLease.tenant_email})`} />
              <DetailRow label="Property" value={selectedLease.property_name} />
              <DetailRow label="Unit" value={selectedLease.unit_name} />
              <DetailRow label="Start Date" value={selectedLease.start_date} />
              <DetailRow label="Expiry Date" value={selectedLease.expiry_date} />
              <DetailRow label="Rent Amount" value={`₦${parseFloat(selectedLease.rent_amount).toLocaleString()}`} />
              <DetailRow label="Currency" value={selectedLease.currency} />
              <DetailRow label="Frequency" value={selectedLease.rent_frequency} />
              <DetailRow label="Rent Due Day" value={selectedLease.rent_due_day} />
              <DetailRow label="Notes" value={selectedLease.notes || '—'} />
              {selectedLease.terminated_at && (
                <DetailRow label="Terminated At" value={selectedLease.terminated_at} />
              )}
              <DetailRow label="Created" value={new Date(selectedLease.created_at).toLocaleString()} />

              {selectedLease.rent_schedule && selectedLease.rent_schedule.length > 0 && (
                <div className="mt-6">
                  <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">Rent Schedule</h3>
                  <div className="space-y-2">
                    {selectedLease.rent_schedule.map((rs) => (
                      <div key={rs.id} className="rounded-md bg-gray-50 p-3 text-sm">
                        <div className="flex items-center justify-between">
                          <span className="font-medium">{rs.period_start} — {rs.period_end}</span>
                          <StatusBadge status={rs.status} />
                        </div>
                        <p className="text-gray-600">Due: {rs.due_date}</p>
                        <p className="text-gray-900">₦{parseFloat(rs.amount).toLocaleString()} | Paid: ₦{parseFloat(rs.paid_amount).toLocaleString()} | Remaining: ₦{parseFloat(rs.remaining_amount).toLocaleString()}</p>
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
