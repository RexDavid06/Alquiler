// =============================================================================
// Alquiler Super User — System Health Page
//
// Displays real-time platform health checks from the Django backend.
// Uses the admin dashboard's system_health section and the health check endpoint.
// =============================================================================

import { useState, useEffect, useCallback } from 'react';
import { getAdminDashboard } from '../api/dashboard';
import { getHealthCheck } from '../api/dashboard';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorState from '../components/ErrorState';
import { HeartPulse, RefreshCw, CheckCircle, XCircle } from 'lucide-react';

interface HealthData {
  api_status: string;
  database: string;
  django_check: string;
  migrations: string;
}

function HealthRow({ label, status }: { label: string; status: string }) {
  const isHealthy = status === 'healthy' || status === 'ok' || status === 'all applied';
  return (
    <div className="flex items-center justify-between rounded-md bg-gray-50 px-4 py-3">
      <div className="flex items-center gap-3">
        {isHealthy ? (
          <CheckCircle className="h-5 w-5 text-green-500" />
        ) : (
          <XCircle className="h-5 w-5 text-red-500" />
        )}
        <span className="text-sm font-medium text-gray-700">{label}</span>
      </div>
      <span
        className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${
          isHealthy
            ? 'bg-green-50 text-green-700'
            : 'bg-red-50 text-red-700'
        }`}
      >
        <span className={`h-1.5 w-1.5 rounded-full ${isHealthy ? 'bg-green-500' : 'bg-red-500'}`} />
        {status}
      </span>
    </div>
  );
}

export default function HealthPage() {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Fetch both health endpoints in parallel
      const [dashboardData, healthCheck] = await Promise.all([
        getAdminDashboard(),
        getHealthCheck().catch(() => ({ status: 'unreachable', database: 'unknown' })),
      ]);

      setHealth({
        api_status: healthCheck.status,
        database: healthCheck.database,
        django_check: dashboardData.system_health.django_check ?? 'unknown',
        migrations: dashboardData.system_health.migrations ?? 'unknown',
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load health data.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading) return <LoadingSpinner message="Checking system health…" />;
  if (error) return <ErrorState message={error} onRetry={fetchData} />;
  if (!health) return null;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">System Health</h1>
          <p className="mt-1 text-sm text-gray-500">
            Real-time platform health status.
          </p>
        </div>
        <button
          onClick={fetchData}
          className="inline-flex items-center gap-2 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50"
        >
          <RefreshCw className="h-4 w-4" />
          Refresh
        </button>
      </div>

      <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
        <div className="space-y-3">
          <HealthRow label="API Status" status={health.api_status} />
          <HealthRow label="Database" status={health.database} />
          <HealthRow label="Django System Check" status={health.django_check} />
          <HealthRow label="Migrations" status={health.migrations} />
        </div>
      </div>

      <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">
          <HeartPulse className="inline h-4 w-4 mr-1" />
          Health Check Details
        </h2>
        <div className="space-y-2 text-sm text-gray-600">
          <p>
            <strong>API Status:</strong> Verifies the Django application is responding to requests.
            Uses the <code>/api/v1/auth/health/</code> endpoint (unauthenticated).
          </p>
          <p>
            <strong>Database:</strong> Tests PostgreSQL/SQLite connectivity via a simple query.
          </p>
          <p>
            <strong>Django System Check:</strong> Runs Django's built-in system check framework
            to verify model definitions, settings, and configuration.
          </p>
          <p>
            <strong>Migrations:</strong> Checks whether all database migrations have been applied.
          </p>
        </div>
      </div>
    </div>
  );
}
