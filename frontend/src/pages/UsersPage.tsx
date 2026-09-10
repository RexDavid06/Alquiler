// =============================================================================
// Alquiler Super User — Users Page
//
// Platform-wide user management: search, filter by role/status, pagination,
// detail view with related leases and payments.
// =============================================================================

import { useState, useEffect, useCallback } from 'react';
import { getAdminUsers, getAdminUserDetail } from '../api/admin';
import type { AdminUser, AdminUserDetail, PaginatedResponse } from '../api/types';
import DataTable, { type Column } from '../components/DataTable';
import SearchInput from '../components/SearchInput';
import FilterSelect from '../components/FilterSelect';
import Pagination from '../components/Pagination';
import StatusBadge from '../components/StatusBadge';
import DetailPanel, { DetailRow } from '../components/DetailPanel';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorState from '../components/ErrorState';
import EmptyState from '../components/EmptyState';
import { Users } from 'lucide-react';

const ROLE_OPTIONS = [
  { label: 'All Roles', value: '' },
  { label: 'Landlord', value: 'LANDLORD' },
  { label: 'Tenant', value: 'TENANT' },
  { label: 'Platform Admin', value: 'PLATFORM_ADMIN' },
];

const STATUS_OPTIONS = [
  { label: 'All Statuses', value: '' },
  { label: 'Active', value: 'ACTIVE' },
  { label: 'Pending', value: 'PENDING' },
  { label: 'Suspended', value: 'SUSPENDED' },
  { label: 'Deactivated', value: 'DEACTIVATED' },
];

const PAGE_SIZE = 20;

export default function UsersPage() {
  const [data, setData] = useState<PaginatedResponse<AdminUser> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [role, setRole] = useState('');
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const [selectedUser, setSelectedUser] = useState<AdminUserDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getAdminUsers({
        search: search || undefined,
        role: role || undefined,
        status: status || undefined,
        page,
        page_size: PAGE_SIZE,
      });
      setData(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load users.');
    } finally {
      setLoading(false);
    }
  }, [search, role, status, page]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleRowClick = async (user: AdminUser) => {
    setDetailLoading(true);
    try {
      const detail = await getAdminUserDetail(user.id);
      setSelectedUser(detail);
    } catch {
      // ignore — detail panel won't open
    } finally {
      setDetailLoading(false);
    }
  };

  const totalPages = data ? Math.ceil(data.count / PAGE_SIZE) : 0;

  const columns: Column<AdminUser>[] = [
    {
      key: 'id',
      header: 'ID',
      render: (u) => <span className="font-medium text-gray-900">{u.id}</span>,
    },
    {
      key: 'name',
      header: 'Name',
      render: (u) => u.full_name,
    },
    {
      key: 'email',
      header: 'Email',
      render: (u) => u.email,
    },
    {
      key: 'role',
      header: 'Role',
      render: (u) => <StatusBadge status={u.role} />,
    },
    {
      key: 'status',
      header: 'Status',
      render: (u) => <StatusBadge status={u.status} />,
    },
    {
      key: 'created_at',
      header: 'Created',
      render: (u) => new Date(u.created_at).toLocaleDateString(),
    },
  ];

  if (loading && !data) return <LoadingSpinner message="Loading users…" />;
  if (error && !data) return <ErrorState message={error} onRetry={fetchData} />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Users</h1>
        <p className="mt-1 text-sm text-gray-500">
          Platform-wide user management and inspection.
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <SearchInput
          value={search}
          onChange={(v) => { setSearch(v); setPage(1); }}
          placeholder="Search by name or email…"
          className="flex-1"
        />
        <FilterSelect
          value={role}
          onChange={(v) => { setRole(v); setPage(1); }}
          options={ROLE_OPTIONS}
          label="Role"
        />
        <FilterSelect
          value={status}
          onChange={(v) => { setStatus(v); setPage(1); }}
          options={STATUS_OPTIONS}
          label="Status"
        />
      </div>

      {/* Table */}
      {data && data.results.length === 0 ? (
        <EmptyState icon={Users} title="No users found" description="No users match your filters." />
      ) : data ? (
        <>
          <DataTable
            columns={columns}
            data={data.results}
            onRowClick={(u) => handleRowClick(u)}
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
      {selectedUser && (
        <DetailPanel title={`User #${selectedUser.id}`} onClose={() => setSelectedUser(null)}>
          {detailLoading ? (
            <LoadingSpinner message="Loading details…" />
          ) : (
            <div className="space-y-4">
              <DetailRow label="ID" value={selectedUser.id} />
              <DetailRow label="Name" value={selectedUser.full_name} />
              <DetailRow label="Email" value={selectedUser.email} />
              <DetailRow label="Phone" value={selectedUser.phone || '—'} />
              <DetailRow label="Role" value={<StatusBadge status={selectedUser.role} />} />
              <DetailRow label="Status" value={<StatusBadge status={selectedUser.status} />} />
              <DetailRow label="Email Verified" value={selectedUser.email_verified ? 'Yes' : 'No'} />
              <DetailRow label="Created" value={new Date(selectedUser.created_at).toLocaleString()} />
              <DetailRow label="Updated" value={new Date(selectedUser.updated_at).toLocaleString()} />

              {selectedUser.property_count !== null && (
                <DetailRow label="Properties" value={selectedUser.property_count} />
              )}
              {selectedUser.lease_count !== null && (
                <DetailRow label="Leases" value={selectedUser.lease_count} />
              )}
              {selectedUser.subscription_status && (
                <DetailRow label="Subscription" value={<StatusBadge status={selectedUser.subscription_status} />} />
              )}

              {selectedUser.recent_leases.length > 0 && (
                <div className="mt-6">
                  <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">Recent Leases</h3>
                  <div className="space-y-2">
                    {selectedUser.recent_leases.map((l) => (
                      <div key={l.id} className="rounded-md bg-gray-50 p-3 text-sm">
                        <div className="flex items-center justify-between">
                          <span className="font-medium">Lease #{l.id}</span>
                          <StatusBadge status={l.status} />
                        </div>
                        <p className="text-gray-600 mt-1">{l.property_name} — {l.unit_name}</p>
                        <p className="text-gray-600">Tenant: {l.tenant_name}</p>
                        <p className="text-gray-900 font-medium">₦{parseFloat(l.rent_amount).toLocaleString()}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {selectedUser.recent_payments.length > 0 && (
                <div className="mt-6">
                  <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">Recent Payments</h3>
                  <div className="space-y-2">
                    {selectedUser.recent_payments.map((p) => (
                      <div key={p.id} className="rounded-md bg-gray-50 p-3 text-sm">
                        <div className="flex items-center justify-between">
                          <span className="font-medium">Payment #{p.id}</span>
                          <StatusBadge status={p.status} />
                        </div>
                        <p className="text-gray-900 font-medium">₦{parseFloat(p.amount).toLocaleString()}</p>
                        <p className="text-gray-600">{p.payment_date} — {p.payment_method.replace('_', ' ')}</p>
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
