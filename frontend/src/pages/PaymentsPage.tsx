// =============================================================================
// Alquiler Super User — Payments Page
//
// Platform-wide payment listing: search, filter by status/lease/tenant,
// pagination, detail view.
// =============================================================================

import { useState, useEffect, useCallback } from 'react';
import { getAdminPayments, getAdminPaymentDetail } from '../api/admin';
import type { AdminPayment, PaginatedResponse } from '../api/types';
import DataTable, { type Column } from '../components/DataTable';
import SearchInput from '../components/SearchInput';
import FilterSelect from '../components/FilterSelect';
import Pagination from '../components/Pagination';
import StatusBadge from '../components/StatusBadge';
import DetailPanel, { DetailRow } from '../components/DetailPanel';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorState from '../components/ErrorState';
import EmptyState from '../components/EmptyState';
import { CreditCard } from 'lucide-react';

const STATUS_OPTIONS = [
  { label: 'All Statuses', value: '' },
  { label: 'Paid', value: 'PAID' },
  { label: 'Pending', value: 'PENDING' },
  { label: 'Failed', value: 'FAILED' },
  { label: 'Cancelled', value: 'CANCELLED' },
];

const PAGE_SIZE = 20;

export default function PaymentsPage() {
  const [data, setData] = useState<PaginatedResponse<AdminPayment> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const [selectedPayment, setSelectedPayment] = useState<AdminPayment | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getAdminPayments({
        search: search || undefined,
        status: status || undefined,
        page,
        page_size: PAGE_SIZE,
      });
      setData(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load payments.');
    } finally {
      setLoading(false);
    }
  }, [search, status, page]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleRowClick = async (payment: AdminPayment) => {
    setDetailLoading(true);
    try {
      const detail = await getAdminPaymentDetail(payment.id);
      setSelectedPayment(detail);
    } catch {
      // ignore
    } finally {
      setDetailLoading(false);
    }
  };

  const totalPages = data ? Math.ceil(data.count / PAGE_SIZE) : 0;

  const columns: Column<AdminPayment>[] = [
    {
      key: 'id',
      header: 'ID',
      render: (p) => <span className="font-medium text-gray-900">{p.id}</span>,
    },
    {
      key: 'tenant_name',
      header: 'Tenant',
      render: (p) => p.tenant_name ?? `#${p.tenant}`,
    },
    {
      key: 'landlord_name',
      header: 'Landlord',
      render: (p) => p.landlord_name ?? `#${p.landlord}`,
    },
    {
      key: 'lease',
      header: 'Lease',
      render: (p) => `#${p.lease}`,
    },
    {
      key: 'amount',
      header: 'Amount',
      render: (p) => <span className="font-medium">₦{parseFloat(p.amount).toLocaleString()}</span>,
    },
    {
      key: 'payment_date',
      header: 'Date',
      render: (p) => p.payment_date,
    },
    {
      key: 'payment_method',
      header: 'Method',
      render: (p) => p.payment_method.replace('_', ' '),
    },
    {
      key: 'status',
      header: 'Status',
      render: (p) => <StatusBadge status={p.status} />,
    },
  ];

  if (loading && !data) return <LoadingSpinner message="Loading payments…" />;
  if (error && !data) return <ErrorState message={error} onRetry={fetchData} />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Payments</h1>
        <p className="mt-1 text-sm text-gray-500">
          Platform-wide payment records and inspection.
        </p>
      </div>

      <div className="flex flex-col sm:flex-row gap-3">
        <SearchInput
          value={search}
          onChange={(v) => { setSearch(v); setPage(1); }}
          placeholder="Search by tenant or reference…"
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
        <EmptyState icon={CreditCard} title="No payments found" description="No payments match your filters." />
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

      {selectedPayment && (
        <DetailPanel title={`Payment #${selectedPayment.id}`} onClose={() => setSelectedPayment(null)}>
          {detailLoading ? (
            <LoadingSpinner message="Loading details…" />
          ) : (
            <div className="space-y-4">
              <DetailRow label="ID" value={selectedPayment.id} />
              <DetailRow label="Status" value={<StatusBadge status={selectedPayment.status} />} />
              <DetailRow label="Amount" value={`₦${parseFloat(selectedPayment.amount).toLocaleString()}`} />
              <DetailRow label="Currency" value={selectedPayment.currency} />
              <DetailRow label="Payment Date" value={selectedPayment.payment_date} />
              <DetailRow label="Method" value={selectedPayment.payment_method.replace('_', ' ')} />
              <DetailRow label="Reference" value={selectedPayment.reference || '—'} />
              <DetailRow label="Notes" value={selectedPayment.notes || '—'} />
              <DetailRow label="Landlord" value={`#${selectedPayment.landlord}`} />
              <DetailRow label="Tenant" value={`#${selectedPayment.tenant}`} />
              <DetailRow label="Lease" value={`#${selectedPayment.lease}`} />
              <DetailRow label="Rent Period" value={selectedPayment.rent_period ? `#${selectedPayment.rent_period}` : '—'} />
              <DetailRow label="Gateway" value={selectedPayment.gateway || '—'} />
              <DetailRow label="Gateway Ref" value={selectedPayment.gateway_reference || '—'} />
              <DetailRow label="Verified" value={selectedPayment.verified ? 'Yes' : 'No'} />
              <DetailRow label="Recorded By" value={`#${selectedPayment.recorded_by}`} />
              <DetailRow label="Created" value={new Date(selectedPayment.created_at).toLocaleString()} />
            </div>
          )}
        </DetailPanel>
      )}
    </div>
  );
}
