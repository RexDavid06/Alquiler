// =============================================================================
// Alquiler Super User — Activity Page
//
// Platform-wide audit log: search, filter by action/object type,
// pagination, detail view.
// =============================================================================

import { useState, useEffect, useCallback } from 'react';
import { getAdminAuditLogs } from '../api/admin';
import type { AuditLog, PaginatedResponse } from '../api/types';
import DataTable, { type Column } from '../components/DataTable';
import SearchInput from '../components/SearchInput';
import FilterSelect from '../components/FilterSelect';
import Pagination from '../components/Pagination';
import StatusBadge from '../components/StatusBadge';
import DetailPanel, { DetailRow } from '../components/DetailPanel';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorState from '../components/ErrorState';
import EmptyState from '../components/EmptyState';
import { Activity } from 'lucide-react';

const ACTION_OPTIONS = [
  { label: 'All Actions', value: '' },
  { label: 'Account Created', value: 'ACCOUNT_CREATED' },
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
];

const OBJECT_TYPE_OPTIONS = [
  { label: 'All Types', value: '' },
  { label: 'User', value: 'User' },
  { label: 'Property', value: 'Property' },
  { label: 'Unit', value: 'Unit' },
  { label: 'Lease', value: 'Lease' },
  { label: 'Payment', value: 'Payment' },
  { label: 'Subscription', value: 'Subscription' },
  { label: 'TenantInvitation', value: 'TenantInvitation' },
];

const PAGE_SIZE = 20;

export default function ActivityPage() {
  const [data, setData] = useState<PaginatedResponse<AuditLog> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [actionFilter, setActionFilter] = useState('');
  const [objectTypeFilter, setObjectTypeFilter] = useState('');
  const [page, setPage] = useState(1);
  const [selectedLog, setSelectedLog] = useState<AuditLog | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getAdminAuditLogs({
        search: search || undefined,
        action: actionFilter || undefined,
        object_type: objectTypeFilter || undefined,
        page,
        page_size: PAGE_SIZE,
      });
      setData(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load activity.');
    } finally {
      setLoading(false);
    }
  }, [search, actionFilter, objectTypeFilter, page]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const totalPages = data ? Math.ceil(data.count / PAGE_SIZE) : 0;

  const columns: Column<AuditLog>[] = [
    {
      key: 'created_at',
      header: 'Time',
      render: (log) => (
        <span className="text-gray-900 text-sm">
          {new Date(log.created_at).toLocaleString()}
        </span>
      ),
    },
    {
      key: 'actor_name',
      header: 'Actor',
      render: (log) => (
        <div>
          <div className="text-gray-900">{log.actor_name || 'System'}</div>
          {log.actor_email && (
            <div className="text-xs text-gray-500">{log.actor_email}</div>
          )}
        </div>
      ),
    },
    {
      key: 'action',
      header: 'Action',
      render: (log) => <StatusBadge status={log.action} />,
    },
    {
      key: 'object_type',
      header: 'Object',
      render: (log) => (
        <span className="text-gray-900">
          {log.object_type}{log.object_id ? ` #${log.object_id}` : ''}
        </span>
      ),
    },
    {
      key: 'detail',
      header: 'Detail',
      render: (log) => {
        const detail = log.detail;
        const keys = Object.keys(detail);
        if (keys.length === 0) return <span className="text-gray-400">—</span>;
        const summary = keys.slice(0, 2).map((k) => `${k}: ${String(detail[k])}`).join(', ');
        return <span className="text-sm text-gray-600 truncate max-w-xs block">{summary}</span>;
      },
    },
  ];

  if (loading && !data) return <LoadingSpinner message="Loading activity…" />;
  if (error && !data) return <ErrorState message={error} onRetry={fetchData} />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Activity</h1>
        <p className="mt-1 text-sm text-gray-500">
          Platform-wide audit log of all important events.
        </p>
      </div>

      <div className="flex flex-col sm:flex-row gap-3">
        <SearchInput
          value={search}
          onChange={(v) => { setSearch(v); setPage(1); }}
          placeholder="Search by action or object type…"
          className="flex-1"
        />
        <FilterSelect
          value={actionFilter}
          onChange={(v) => { setActionFilter(v); setPage(1); }}
          options={ACTION_OPTIONS}
          label="Action"
        />
        <FilterSelect
          value={objectTypeFilter}
          onChange={(v) => { setObjectTypeFilter(v); setPage(1); }}
          options={OBJECT_TYPE_OPTIONS}
          label="Object Type"
        />
      </div>

      {data && data.results.length === 0 ? (
        <EmptyState icon={Activity} title="No activity found" description="No audit logs match your filters." />
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

      {selectedLog && (
        <DetailPanel title={`Audit Log #${selectedLog.id}`} onClose={() => setSelectedLog(null)}>
          <div className="space-y-4">
            <DetailRow label="ID" value={selectedLog.id} />
            <DetailRow label="Time" value={new Date(selectedLog.created_at).toLocaleString()} />
            <DetailRow label="Actor" value={selectedLog.actor_name || 'System'} />
            <DetailRow label="Actor Email" value={selectedLog.actor_email || '—'} />
            <DetailRow label="Action" value={<StatusBadge status={selectedLog.action} />} />
            <DetailRow label="Object Type" value={selectedLog.object_type} />
            <DetailRow label="Object ID" value={selectedLog.object_id ?? '—'} />
            <DetailRow
              label="Detail"
              value={
                <pre className="text-xs bg-gray-50 rounded p-2 overflow-x-auto max-h-48">
                  {JSON.stringify(selectedLog.detail, null, 2)}
                </pre>
              }
            />
          </div>
        </DetailPanel>
      )}
    </div>
  );
}
