// =============================================================================
// Alquiler Super User — Subscriptions Page
//
// Platform-wide subscription listing: search, filter by plan/status,
// pagination, detail view.
// =============================================================================

import { useState, useEffect, useCallback } from 'react';
import { getAdminSubscriptions } from '../api/admin';
import type { AdminSubscription, PaginatedResponse } from '../api/types';
import DataTable, { type Column } from '../components/DataTable';
import SearchInput from '../components/SearchInput';
import FilterSelect from '../components/FilterSelect';
import Pagination from '../components/Pagination';
import StatusBadge from '../components/StatusBadge';
import DetailPanel, { DetailRow } from '../components/DetailPanel';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorState from '../components/ErrorState';
import EmptyState from '../components/EmptyState';
import { Layers } from 'lucide-react';

const PLAN_OPTIONS = [
  { label: 'All Plans', value: '' },
  { label: 'Free', value: 'FREE' },
  { label: 'Professional', value: 'PROFESSIONAL' },
  { label: 'Business', value: 'BUSINESS' },
];

const STATUS_OPTIONS = [
  { label: 'All Statuses', value: '' },
  { label: 'Trial', value: 'TRIAL' },
  { label: 'Active', value: 'ACTIVE' },
  { label: 'Past Due', value: 'PAST_DUE' },
  { label: 'Cancelled', value: 'CANCELLED' },
  { label: 'Expired', value: 'EXPIRED' },
];

const PAGE_SIZE = 20;

export default function SubscriptionsPage() {
  const [data, setData] = useState<PaginatedResponse<AdminSubscription> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [plan, setPlan] = useState('');
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const [selectedSub, setSelectedSub] = useState<AdminSubscription | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getAdminSubscriptions({
        search: search || undefined,
        plan: plan || undefined,
        status: status || undefined,
        page,
        page_size: PAGE_SIZE,
      });
      setData(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load subscriptions.');
    } finally {
      setLoading(false);
    }
  }, [search, plan, status, page]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const totalPages = data ? Math.ceil(data.count / PAGE_SIZE) : 0;

  const columns: Column<AdminSubscription>[] = [
    {
      key: 'id',
      header: 'ID',
      render: (s) => <span className="font-medium text-gray-900">{s.id}</span>,
    },
    {
      key: 'landlord_name',
      header: 'Landlord',
      render: (s) => (
        <div>
          <div className="text-gray-900">{s.landlord_name}</div>
          <div className="text-xs text-gray-500">{s.landlord_email}</div>
        </div>
      ),
    },
    {
      key: 'plan_name',
      header: 'Plan',
      render: (s) => (
        <div>
          <div className="text-gray-900">{s.plan_name}</div>
          <div className="text-xs text-gray-500">{s.plan_tier}</div>
        </div>
      ),
    },
    {
      key: 'billing_cycle',
      header: 'Billing',
      render: (s) => s.billing_cycle,
    },
    {
      key: 'status',
      header: 'Status',
      render: (s) => <StatusBadge status={s.status} />,
    },
    {
      key: 'started_at',
      header: 'Started',
      render: (s) => new Date(s.started_at).toLocaleDateString(),
    },
    {
      key: 'trial_end',
      header: 'Trial End',
      render: (s) => s.trial_end ? new Date(s.trial_end).toLocaleDateString() : '—',
    },
  ];

  if (loading && !data) return <LoadingSpinner message="Loading subscriptions…" />;
  if (error && !data) return <ErrorState message={error} onRetry={fetchData} />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Subscriptions</h1>
        <p className="mt-1 text-sm text-gray-500">
          Platform-wide subscription listing and inspection.
        </p>
      </div>

      <div className="flex flex-col sm:flex-row gap-3">
        <SearchInput
          value={search}
          onChange={(v) => { setSearch(v); setPage(1); }}
          placeholder="Search by landlord or plan…"
          className="flex-1"
        />
        <FilterSelect
          value={plan}
          onChange={(v) => { setPlan(v); setPage(1); }}
          options={PLAN_OPTIONS}
          label="Plan"
        />
        <FilterSelect
          value={status}
          onChange={(v) => { setStatus(v); setPage(1); }}
          options={STATUS_OPTIONS}
          label="Status"
        />
      </div>

      {data && data.results.length === 0 ? (
        <EmptyState icon={Layers} title="No subscriptions found" description="No subscriptions match your filters." />
      ) : data ? (
        <>
          <DataTable
            columns={columns}
            data={data.results}
            onRowClick={(s) => setSelectedSub(s)}
          />
          <Pagination
            currentPage={page}
            totalPages={totalPages}
            onPageChange={setPage}
            totalItems={data.count}
          />
        </>
      ) : null}

      {selectedSub && (
        <DetailPanel title={`Subscription #${selectedSub.id}`} onClose={() => setSelectedSub(null)}>
          <div className="space-y-4">
            <DetailRow label="ID" value={selectedSub.id} />
            <DetailRow label="Status" value={<StatusBadge status={selectedSub.status} />} />
            <DetailRow label="Landlord" value={`${selectedSub.landlord_name} (${selectedSub.landlord_email})`} />
            <DetailRow label="Plan" value={selectedSub.plan_name} />
            <DetailRow label="Plan Tier" value={<StatusBadge status={selectedSub.plan_tier} />} />
            <DetailRow label="Billing Cycle" value={selectedSub.billing_cycle} />
            <DetailRow label="Started" value={new Date(selectedSub.started_at).toLocaleString()} />
            <DetailRow label="Period Start" value={new Date(selectedSub.current_period_start).toLocaleString()} />
            <DetailRow label="Period End" value={selectedSub.current_period_end ? new Date(selectedSub.current_period_end).toLocaleString() : '—'} />
            <DetailRow label="Trial End" value={selectedSub.trial_end ? new Date(selectedSub.trial_end).toLocaleString() : '—'} />
            <DetailRow label="Cancelled At" value={selectedSub.cancelled_at ? new Date(selectedSub.cancelled_at).toLocaleString() : '—'} />
            <DetailRow label="Cancel Reason" value={selectedSub.cancel_reason || '—'} />
            <DetailRow label="Created" value={new Date(selectedSub.created_at).toLocaleString()} />
          </div>
        </DetailPanel>
      )}
    </div>
  );
}
