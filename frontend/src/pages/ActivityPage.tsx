// =============================================================================
// Alquiler Super User — Activity Feed Page
//
// Platform-wide recent activity feed showing audit logs, payments, leases,
// user registrations, and subscription changes in a unified timeline.
// =============================================================================

import { useState, useEffect, useCallback } from 'react';
import { getAdminActivityFeed } from '../api/admin';
import type { AdminActivity } from '../api/types';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorState from '../components/ErrorState';
import EmptyState from '../components/EmptyState';
import { Activity, CreditCard, FileText, Users, Layers, Clock } from 'lucide-react';

const TYPE_CONFIG: Record<string, { icon: typeof Activity; color: string; bgColor: string }> = {
  audit_log: { icon: Clock, color: 'text-gray-600', bgColor: 'bg-gray-100' },
  payment: { icon: CreditCard, color: 'text-green-600', bgColor: 'bg-green-100' },
  lease: { icon: FileText, color: 'text-blue-600', bgColor: 'bg-blue-100' },
  user: { icon: Users, color: 'text-purple-600', bgColor: 'bg-purple-100' },
  subscription: { icon: Layers, color: 'text-orange-600', bgColor: 'bg-orange-100' },
};

function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

export default function ActivityPage() {
  const [activities, setActivities] = useState<AdminActivity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [limit, setLimit] = useState(50);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getAdminActivityFeed(limit);
      setActivities(res.activities);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load activity feed.');
    } finally {
      setLoading(false);
    }
  }, [limit]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading && activities.length === 0) return <LoadingSpinner message="Loading activity feed…" />;
  if (error && activities.length === 0) return <ErrorState message={error} onRetry={fetchData} />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Activity Feed</h1>
          <p className="mt-1 text-sm text-gray-500">
            Recent platform activity across all modules.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-500">Show:</label>
          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="rounded-md border-gray-300 text-sm focus:border-blue-500 focus:ring-blue-500"
          >
            <option value={25}>25</option>
            <option value={50}>50</option>
            <option value={100}>100</option>
          </select>
        </div>
      </div>

      {activities.length === 0 ? (
        <EmptyState
          icon={Activity}
          title="No activity yet"
          description="Activity will appear here as users interact with the platform."
        />
      ) : (
        <div className="flow-root">
          <ul className="-mb-8">
            {activities.map((activity, idx) => {
              const config = TYPE_CONFIG[activity.type] || TYPE_CONFIG.audit_log;
              const Icon = config.icon;
              const isLast = idx === activities.length - 1;

              return (
                <li key={activity.id}>
                  <div className="relative pb-8">
                    {!isLast && (
                      <span className="absolute left-4 top-4 -ml-px h-full w-0.5 bg-gray-200" aria-hidden="true" />
                    )}
                    <div className="relative flex items-start space-x-3">
                      <div className={`relative ${config.bgColor} rounded-full p-2`}>
                        <Icon className={`h-5 w-5 ${config.color}`} />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div>
                          <div className="text-sm">
                            <span className="font-medium text-gray-900">{activity.description}</span>
                          </div>
                          <p className="mt-0.5 text-sm text-gray-500">
                            {activity.actor_name && (
                              <span>by {activity.actor_name}</span>
                            )}
                            {activity.actor_name && ' · '}
                            <span>{formatTimestamp(activity.timestamp)}</span>
                          </p>
                        </div>
                        <div className="mt-2 text-xs text-gray-400">
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800">
                            {activity.type.replace('_', ' ')}
                          </span>
                          {activity.entity_type && (
                            <span className="ml-2">
                              {activity.entity_type}#{activity.entity_id}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}
