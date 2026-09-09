// =============================================================================
// Alquiler Super User — Notifications Page
//
// Displays notifications for the authenticated admin user.
// The notifications API is scoped to the requesting user only.
// =============================================================================

import { useState, useEffect, useCallback } from 'react';
import { getNotifications } from '../api/dashboard';
import type { Notification } from '../api/types';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorState from '../components/ErrorState';
import EmptyState from '../components/EmptyState';
import { Bell } from 'lucide-react';

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-NG', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getNotifications();
      setNotifications(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load notifications.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading) return <LoadingSpinner message="Loading notifications…" />;
  if (error) return <ErrorState message={error} onRetry={fetchData} />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Notifications</h1>
        <p className="mt-1 text-sm text-gray-500">
          Your platform notifications ({notifications.length} total).
        </p>
      </div>

      {notifications.length === 0 ? (
        <EmptyState icon={Bell} title="No notifications" description="You have no notifications at this time." />
      ) : (
        <div className="rounded-lg border border-gray-200 bg-white shadow-sm divide-y divide-gray-200">
          {notifications.map((n) => (
            <div
              key={n.id}
              className={`px-4 py-3 ${n.is_read ? 'bg-white' : 'bg-blue-50'}`}
            >
              <div className="flex items-start gap-3">
                <div className={`mt-1 h-2 w-2 flex-shrink-0 rounded-full ${n.is_read ? 'bg-gray-300' : 'bg-blue-500'}`} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-medium text-gray-900">{n.title}</h3>
                    <span className="text-xs text-gray-400">{n.channel}</span>
                  </div>
                  <p className="mt-0.5 text-sm text-gray-600">{n.message}</p>
                  <p className="mt-1 text-xs text-gray-400">{formatDate(n.created_at)}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
