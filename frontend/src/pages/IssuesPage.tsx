// =============================================================================
// Alquiler Super User — Issues Page
//
// Operational issues aggregated from existing domain data:
// failed payments, overdue rent, expired leases, suspended users,
// expired/past-due subscriptions.
// =============================================================================

import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { getAdminIssues } from '../api/admin';
import type { AdminIssuesResponse } from '../api/types';
import StatusBadge from '../components/StatusBadge';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorState from '../components/ErrorState';
import EmptyState from '../components/EmptyState';
import { AlertTriangle, AlertCircle, Info } from 'lucide-react';

const SEVERITY_CONFIG: Record<string, { icon: typeof AlertTriangle; color: string; bg: string }> = {
  high: { icon: AlertTriangle, color: 'text-red-600', bg: 'bg-red-50 border-red-200' },
  medium: { icon: AlertCircle, color: 'text-amber-600', bg: 'bg-amber-50 border-amber-200' },
  low: { icon: Info, color: 'text-blue-600', bg: 'bg-blue-50 border-blue-200' },
};

const ISSUE_TYPE_LABELS: Record<string, string> = {
  failed_payment: 'Failed Payment',
  overdue_rent: 'Overdue Rent',
  expired_lease: 'Expired Lease',
  suspended_user: 'Suspended User',
  expired_subscription: 'Expired Subscription',
  past_due_subscription: 'Past Due Subscription',
};

function navigateForIssue(entityType: string, navigate: ReturnType<typeof useNavigate>) {
  switch (entityType) {
    case 'payment':
      navigate('/payments');
      break;
    case 'rent_schedule':
      navigate('/payments');
      break;
    case 'lease':
      navigate('/leases');
      break;
    case 'user':
      navigate('/users');
      break;
    case 'subscription':
      navigate('/subscriptions');
      break;
    default:
      break;
  }
}

export default function IssuesPage() {
  const [data, setData] = useState<AdminIssuesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>('all');
  const navigate = useNavigate();

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getAdminIssues();
      setData(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load issues.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading && !data) return <LoadingSpinner message="Loading operational issues…" />;
  if (error && !data) return <ErrorState message={error} onRetry={fetchData} />;
  if (!data) return null;

  const filtered = filter === 'all'
    ? data.issues
    : data.issues.filter((i) => i.severity === filter);

  const highCount = data.issues.filter((i) => i.severity === 'high').length;
  const mediumCount = data.issues.filter((i) => i.severity === 'medium').length;
  const lowCount = data.issues.filter((i) => i.severity === 'low').length;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Operational Issues</h1>
        <p className="mt-1 text-sm text-gray-500">
          Platform health issues derived from authoritative domain data.
        </p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
        <button
          onClick={() => setFilter('all')}
          className={`rounded-lg border p-4 text-left transition-colors ${
            filter === 'all' ? 'border-blue-300 bg-blue-50' : 'border-gray-200 bg-white hover:bg-gray-50'
          }`}
        >
          <div className="text-2xl font-bold text-gray-900">{data.count}</div>
          <div className="text-sm text-gray-500">Total Issues</div>
        </button>
        <button
          onClick={() => setFilter('high')}
          className={`rounded-lg border p-4 text-left transition-colors ${
            filter === 'high' ? 'border-red-300 bg-red-50' : 'border-gray-200 bg-white hover:bg-gray-50'
          }`}
        >
          <div className="text-2xl font-bold text-red-600">{highCount}</div>
          <div className="text-sm text-gray-500">High Severity</div>
        </button>
        <button
          onClick={() => setFilter('medium')}
          className={`rounded-lg border p-4 text-left transition-colors ${
            filter === 'medium' ? 'border-amber-300 bg-amber-50' : 'border-gray-200 bg-white hover:bg-gray-50'
          }`}
        >
          <div className="text-2xl font-bold text-amber-600">{mediumCount}</div>
          <div className="text-sm text-gray-500">Medium Severity</div>
        </button>
        <button
          onClick={() => setFilter('low')}
          className={`rounded-lg border p-4 text-left transition-colors ${
            filter === 'low' ? 'border-blue-300 bg-blue-50' : 'border-gray-200 bg-white hover:bg-gray-50'
          }`}
        >
          <div className="text-2xl font-bold text-blue-600">{lowCount}</div>
          <div className="text-sm text-gray-500">Low Severity</div>
        </button>
      </div>

      {/* Issues list */}
      {filtered.length === 0 ? (
        <EmptyState
          icon={AlertTriangle}
          title="No issues found"
          description={filter === 'all' ? 'No operational issues detected.' : `No ${filter} severity issues.`}
        />
      ) : (
        <div className="space-y-3">
          {filtered.map((issue, idx) => {
            const config = SEVERITY_CONFIG[issue.severity] ?? SEVERITY_CONFIG.low;
            const Icon = config.icon;
            return (
              <div
                key={`${issue.entity_type}-${issue.entity_id}-${idx}`}
                className={`rounded-lg border p-4 ${config.bg} cursor-pointer hover:shadow-sm transition-shadow`}
                onClick={() => navigateForIssue(issue.entity_type, navigate)}
              >
                <div className="flex items-start gap-3">
                  <Icon className={`h-5 w-5 flex-shrink-0 mt-0.5 ${config.color}`} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="text-sm font-medium text-gray-900">{issue.title}</h3>
                      <StatusBadge status={ISSUE_TYPE_LABELS[issue.issue_type] ?? issue.issue_type} />
                      <span className="text-xs text-gray-500 capitalize">{issue.severity}</span>
                    </div>
                    <p className="mt-1 text-sm text-gray-700">{issue.description}</p>
                    <p className="mt-1 text-xs text-gray-500">
                      {issue.entity_type} #{issue.entity_id} — {issue.created_at}
                    </p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
