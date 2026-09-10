// =============================================================================
// Alquiler Super User — Audit Log Page
//
// Platform-wide audit log listing with search, filtering by action/actor,
// and pagination. Read-only view of all platform events.
// =============================================================================

import { useState, useEffect, useCallback } from 'react';
import { getAdminAuditLogs } from '../api/admin';
import type { AdminAuditLog, PaginatedResponse } from '../api/types';
import DataTable, { type Column } from '../components/DataTable';
import SearchInput from '../components/SearchInput';
import FilterSelect from '../components/FilterSelect';
import Pagination from '../components/Pagination';
import StatusBadge from '../components/StatusBadge';
import DetailPanel, { DetailRow } from '../components/DetailPanel';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorState from '../components/ErrorState';
import EmptyState from '../components/EmptyState';
import { ScrollText } from 'lucide-react';

const ACTION_OPTIONS = [
  { label: 'All Actions', value: '' },
  { label: 'Invitation Created', value: 'INVITATION_CREATED' },
  { label: 'Invitation Accepted', value: 'INVITATION_ACCEPTED' },
  { label: 'Lease Created', value: 'LEASE_CREATED' },
  { label: 'Lease Renewed', value: 'LEASE_RENEWED' },
  { label: 'Lease Terminated', value: 'LEASE_TERMINATED' },
  { label: 'Payment Created', value: 'PAYMENT_CREATED' },
  { label: 'Payment Updated', value: 'PAYMENT_UPDATED' },
  { label: 'Subscription Changed', value: 'SUBSCRIPTION_CHANGED' },
  { label: 'Property Created', value: 'PROPERTY_CREATED' },
  { label: 'Unit Created', value: 'UNIT_CREATED' },
  { label: 'Account Created', value: 'ACCOUNT_CREATED' },
  { label: 'User Suspended', value: 'USER_SUSPENDED' },
  { label: 'User Reactivated', value: 'USER_REACTIVATED' },
];

const OBJECT_TYPE_OPTIONS = [
  { label: 'All Types', value: '' },
  { label: 'User', value: 'user' },
  { label: 'Property', value: 'property' },
  { label: 'Unit', value: 'unit' },
  { label: 'Lease', value: 'lease' },
  { label: 'Payment', value: 'payment' },
  { label: 'Subscription', value: 'subscription' },
  { label: 'Invitation', value: 'invitation' },
];

const PAGE_SIZE = 20;

export default function AuditLogPage() {
  const [data, setData] = useState<PaginatedResponse<AdminAuditLog> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [action, setAction] = useState('');
  const [objectType, setObjectType] = useState('');
  const [page, setPage] = useState(1);
  const [selectedLog, setSelectedLog] = useState<AdminAuditLog | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getAdminAuditLogs({
        search: search || undefined,
        action: action || undefined,
        object_type: objectType || undefined,
        page,
        page_size: PAGE_SIZE,
      });
      setData(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load audit logs.');
    } finally {
      setLoading(false);
    }
  }, [search, action, objectType, page]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const totalPages = data ? Math.ceil(data.count / PAGE_SIZE) : 0;

  const columns: Column<AdminAuditLog>[] = [
    {
      key: 'id',
      header: 'ID',
      render: (log) => <span className="font-medium text-gray-900">{log.id}</span>,
    },
    {
      key: 'action',
      header: 'Action',
      render: (log) => <StatusBadge status={log.action} />,
    },
    {
      key: 'actor',
      header: 'Actor',
      render: (log) => log.actor_name || log.actor_email || '—',
    },
    {
      key: 'object_type',
      header: 'Object Type',
      render: (log) => log.object_type || '—',
    },
    {
      key: 'object_id',
      header: 'Object ID',
      render: (log) => log.object_id ?? '—',
    },
    {
      key: 'created_at',
      header: 'Timestamp',
      render: (log) => new Date(log.created_at).toLocaleString(),
    },
  ];

  if (loading && !data) return <LoadingSpinner message="Loading audit logs…" />;
  if (error && !data) return <ErrorState message={error} onRetry={fetchData} />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Audit Log</h1>
        <p className="mt-1 text-sm text-gray-500">
          Complete history of platform events and actions.
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <SearchInput
          value={search}
          onChange={(v) => { setSearch(v); setPage(1); }}
          placeholder="Search by actor or action…"
          className="flex-1"
        />
        <FilterSelect
          value={action}
          onChange={(v) => { setAction(v); setPage(1); }}
          options={ACTION_OPTIONS}
          label="Action"
        />
        <FilterSelect
          value={objectType}
          onChange={(v) => { setObjectType(v); setPage(1); }}
          options={OBJECT_TYPE_OPTIONS}
          label="Object Type"
        />
      </div>

      {/* Table */}
      {data && data.results.length === 0 ? (
        <EmptyState icon={ScrollText} title="No audit logs found" description="No events match your filters." />
      ) : data ? (
        <>
          <DataTable
            columns={columns}
            data={data.results}
            onRowClick={(log) => setSelectedLog(log)}
          />
          <Pagination
            currentPage={page}
            totalPages={totalPages}
            onPageChange={setPage}
            totalItems={data.count}
          />
        </>
      ) : null}

      {/* Detail Panel */}
      {selectedLog && (
        <DetailPanel title={`Audit Log #${selectedLog.id}`} onClose={() => setSelectedLog(null)}>
          <div className="space-y-4">
            <DetailRow label="ID" value={selectedLog.id} />
            <DetailRow label="Action" value={<StatusBadge status={selectedLog.action} />} />
            <DetailRow label="Actor" value={selectedLog.actor_name || selectedLog.actor_email || '—'} />
            <DetailRow label="Actor Email" value={selectedLog.actor_email || '—'} />
            <DetailRow label="Object Type" value={selectedLog.object_type || '—'} />
            <DetailRow label="Object ID" value={selectedLog.object_id ?? '—'} />
            <DetailRow label="Timestamp" value={new Date(selectedLog.created_at).toLocaleString()} />

            {selectedLog.detail && Object.keys(selectedLog.detail).length > 0 && (
              <div className="mt-6">
                <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">Detail</h3>
                <pre className="rounded-md bg-gray-50 p-3 text-sm text-gray-700 overflow-auto">
                  {JSON.stringify(selectedLog.detail, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </DetailPanel>
      )}
    </div>
  );
}
