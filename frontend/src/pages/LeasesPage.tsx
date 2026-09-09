// =============================================================================
// Alquiler Super User — Leases Page
//
// The Leases API supports PLATFORM_ADMIN access (all leases visible).
// This page displays a table of all leases across the platform.
// =============================================================================

import { useState, useEffect, useCallback } from 'react';
import { getLeases } from '../api/dashboard';
import type { Lease } from '../api/types';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorState from '../components/ErrorState';
import EmptyState from '../components/EmptyState';
import { FileText } from 'lucide-react';

const STATUS_COLORS: Record<string, string> = {
  ACTIVE: 'bg-green-50 text-green-700',
  FUTURE: 'bg-blue-50 text-blue-700',
  EXPIRING: 'bg-amber-50 text-amber-700',
  EXPIRED: 'bg-gray-100 text-gray-600',
  TERMINATED: 'bg-red-50 text-red-700',
};

export default function LeasesPage() {
  const [leases, setLeases] = useState<Lease[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getLeases();
      setLeases(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load leases.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading) return <LoadingSpinner message="Loading leases…" />;
  if (error) return <ErrorState message={error} onRetry={fetchData} />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Leases</h1>
        <p className="mt-1 text-sm text-gray-500">
          All leases across the platform ({leases.length} total).
        </p>
      </div>

      {leases.length === 0 ? (
        <EmptyState icon={FileText} title="No leases found" description="There are no leases in the system yet." />
      ) : (
        <div className="rounded-lg border border-gray-200 bg-white shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">ID</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Landlord</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Tenant</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Property</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Unit</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Start</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Expiry</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Rent</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {leases.map((lease) => (
                  <tr key={lease.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm text-gray-900 font-medium">{lease.id}</td>
                    <td className="px-4 py-3 text-sm text-gray-600">{lease.landlord}</td>
                    <td className="px-4 py-3 text-sm text-gray-600">{lease.tenant}</td>
                    <td className="px-4 py-3 text-sm text-gray-600">{lease.property}</td>
                    <td className="px-4 py-3 text-sm text-gray-600">{lease.unit}</td>
                    <td className="px-4 py-3 text-sm text-gray-600">{lease.start_date}</td>
                    <td className="px-4 py-3 text-sm text-gray-600">{lease.expiry_date}</td>
                    <td className="px-4 py-3 text-sm text-gray-900">₦{parseFloat(lease.rent_amount).toLocaleString()}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[lease.status] ?? 'bg-gray-100 text-gray-600'}`}>
                        {lease.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
