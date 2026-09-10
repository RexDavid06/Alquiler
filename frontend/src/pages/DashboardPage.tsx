// =============================================================================
// Alquiler Super User — Dashboard Page
//
// Platform business intelligence dashboard.
// Consumes the enhanced admin_metrics endpoint from the Django backend.
// Phase 10B: Real KPIs, growth charts, date filtering, subscription breakdown.
// =============================================================================

import { useState, useEffect, useCallback } from 'react';
import { getAdminDashboard, exportAdminDashboardCsv } from '../api/dashboard';
import type { AdminDashboardResponse, GrowthPoint, PaymentGrowthPoint } from '../api/types';
import MetricCard from '../components/MetricCard';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorState from '../components/ErrorState';
import {
  Users,
  Building2,
  FileText,
  CreditCard,
  Layers,
  TrendingUp,
  Activity,
  AlertTriangle,
  RefreshCw,
  Download,
  Home,
  UserCheck,
  UserX,
} from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
} from 'recharts';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatCurrency(value: string): string {
  const num = parseFloat(value);
  if (isNaN(num)) return value;
  if (num >= 1_000_000) return `₦${(num / 1_000_000).toFixed(1)}M`;
  if (num >= 1_000) return `₦${(num / 1_000).toFixed(1)}K`;
  return `₦${num.toLocaleString()}`;
}

function formatNumber(value: number): string {
  return value.toLocaleString();
}

const PERIOD_OPTIONS = [
  { label: 'All Time', value: 'all' },
  { label: '7 Days', value: '7d' },
  { label: '30 Days', value: '30d' },
  { label: '90 Days', value: '90d' },
  { label: '12 Months', value: '12m' },
];

function getPeriodDates(period: string): { startDate?: string; endDate?: string } {
  const today = new Date();
  const endDate = today.toISOString().split('T')[0];
  if (period === 'all') return { endDate };
  const days = period === '7d' ? 7 : period === '30d' ? 30 : period === '90d' ? 90 : 365;
  const start = new Date(today);
  start.setDate(start.getDate() - days);
  return { startDate: start.toISOString().split('T')[0], endDate };
}

// ---------------------------------------------------------------------------
// Chart Components
// ---------------------------------------------------------------------------

const PIE_COLORS = ['#10b981', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6', '#6b7280'];

function SubscriptionPieChart({ data }: { data: AdminDashboardResponse['subscriptions'] }) {
  const chartData = [
    { name: 'Free', value: data.free },
    { name: 'Professional', value: data.professional },
    { name: 'Business', value: data.business },
  ].filter((d) => d.value > 0);

  if (chartData.length === 0) {
    return <p className="text-sm text-gray-500 text-center py-8">No subscription data</p>;
  }

  return (
    <ResponsiveContainer width="100%" height={220}>
      <PieChart>
        <Pie
          data={chartData}
          cx="50%"
          cy="50%"
          innerRadius={50}
          outerRadius={80}
          dataKey="value"
          label={({ name, percent }: { name?: string; percent?: number }) =>
            `${name ?? ''} ${((percent ?? 0) * 100).toFixed(0)}%`
          }
        >
          {chartData.map((_, i) => (
            <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
          ))}
        </Pie>
        <Tooltip />
      </PieChart>
    </ResponsiveContainer>
  );
}

function GrowthLineChart({
  data,
  lines,
  title,
}: {
  data: Record<string, unknown>[];
  lines: { key: string; color: string; name: string }[];
  title: string;
}) {
  if (data.length === 0) {
    return <p className="text-sm text-gray-500 text-center py-8">No growth data available</p>;
  }

  return (
    <div>
      <h4 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">{title}</h4>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="month" tick={{ fontSize: 11 }} />
          <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
          <Tooltip />
          {lines.map((line) => (
            <Line
              key={line.key}
              type="monotone"
              dataKey={line.key}
              stroke={line.color}
              strokeWidth={2}
              dot={false}
              name={line.name}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function PaymentVolumeChart({ data }: { data: PaymentGrowthPoint[] }) {
  if (data.length === 0) {
    return <p className="text-sm text-gray-500 text-center py-8">No payment data available</p>;
  }

  const chartData = data.map((d) => ({
    month: d.month,
    count: d.count,
    total: parseFloat(d.total) || 0,
  }));

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey="month" tick={{ fontSize: 11 }} />
        <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
        <Tooltip />
        <Bar dataKey="count" fill="#3b82f6" name="Payments" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

// ---------------------------------------------------------------------------
// Health Badge
// ---------------------------------------------------------------------------

function HealthBadge({ status }: { status: string }) {
  const isHealthy = status === 'healthy' || status === 'all applied';
  return (
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
  );
}

// ---------------------------------------------------------------------------
// Section Component
// ---------------------------------------------------------------------------

function Section({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon?: typeof Users;
  children: React.ReactNode;
}) {
  return (
    <section>
      <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3 flex items-center gap-1.5">
        {Icon && <Icon className="h-4 w-4" />}
        {title}
      </h2>
      {children}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Merge helper for growth chart data
// ---------------------------------------------------------------------------

function mergeGrowthData(
  primary: GrowthPoint[],
  secondary: GrowthPoint[],
): Record<string, unknown>[] {
  const allMonths = new Set([...primary.map((p) => p.month), ...secondary.map((p) => p.month)]);
  const sortedMonths = Array.from(allMonths).sort();

  return sortedMonths.map((month) => {
    const p = primary.find((x) => x.month === month);
    const s = secondary.find((x) => x.month === month);
    return {
      month,
      landlords: p?.count ?? 0,
      tenants: s?.count ?? 0,
      properties: p?.count ?? 0,
      units: s?.count ?? 0,
    };
  });
}

// ---------------------------------------------------------------------------
// Main Dashboard
// ---------------------------------------------------------------------------

export default function DashboardPage() {
  const [data, setData] = useState<AdminDashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [period, setPeriod] = useState('all');
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());
  const [exporting, setExporting] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { startDate, endDate } = getPeriodDates(period);
      const res = await getAdminDashboard(startDate, endDate);
      setData(res);
      setLastRefresh(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load dashboard.');
    } finally {
      setLoading(false);
    }
  }, [period]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleExport = useCallback(async () => {
    setExporting(true);
    try {
      const { startDate, endDate } = getPeriodDates(period);
      await exportAdminDashboardCsv(startDate, endDate);
    } catch {
      // Export failed silently
    } finally {
      setExporting(false);
    }
  }, [period]);

  if (loading && !data) return <LoadingSpinner message="Loading dashboard…" />;
  if (error && !data) return <ErrorState message={error} onRetry={fetchData} />;
  if (!data) return null;

  // Growth trend data
  const userGrowthData = mergeGrowthData(
    data.growth_trends.landlords,
    data.growth_trends.tenants,
  );
  const propertyGrowthData = mergeGrowthData(
    data.growth_trends.properties,
    data.growth_trends.units,
  );

  return (
    <div className="space-y-6">
      {/* Page header with period selector and refresh */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Platform Dashboard</h1>
          <p className="mt-1 text-sm text-gray-500">
            Business intelligence for the Alquiler rental management platform.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Period selector */}
          <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-1">
            {PERIOD_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setPeriod(opt.value)}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                  period === opt.value
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
          {/* Refresh */}
          <button
            onClick={fetchData}
            disabled={loading}
            className="p-2 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors disabled:opacity-50"
            title="Refresh"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
          {/* Export CSV */}
          <button
            onClick={handleExport}
            disabled={exporting}
            className="inline-flex items-center gap-2 px-3 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50"
            title="Export dashboard data as CSV"
          >
            <Download className={`h-4 w-4 ${exporting ? 'animate-spin' : ''}`} />
            {exporting ? 'Exporting…' : 'Export CSV'}
          </button>
        </div>
      </div>

      {/* Last refreshed */}
      <p className="text-xs text-gray-400">
        Last refreshed: {lastRefresh.toLocaleTimeString()}
      </p>

      {/* ================================================================== */}
      {/* TOP KPI ROW — Users                                                 */}
      {/* ================================================================== */}
      <Section title="Users" icon={Users}>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard label="Total Users" value={formatNumber(data.users.total)} icon={Users} />
          <MetricCard
            label="Landlords"
            value={formatNumber(data.users.landlords)}
            icon={Building2}
            subtitle={`${data.users.active_landlords} active · ${data.users.suspended_landlords} suspended`}
          />
          <MetricCard
            label="Tenants"
            value={formatNumber(data.users.tenants)}
            icon={UserCheck}
            subtitle={`${data.users.active_tenants} active · ${data.users.suspended_tenants} suspended`}
          />
          <MetricCard
            label="Admins"
            value={formatNumber(data.users.admins)}
            icon={UserX}
            subtitle="Platform administrators"
          />
        </div>
      </Section>

      {/* ================================================================== */}
      {/* SECOND KPI ROW — Properties, Units, Occupancy, Leases               */}
      {/* ================================================================== */}
      <Section title="Properties & Units" icon={Home}>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard label="Total Properties" value={formatNumber(data.properties.total)} icon={Building2} />
          <MetricCard label="Total Units" value={formatNumber(data.units.total)} icon={Layers} />
          <MetricCard
            label="Occupied Units"
            value={formatNumber(data.units.occupied)}
            icon={Layers}
            subtitle={`${data.units.occupancy_rate}% occupancy`}
          />
          <MetricCard
            label="Vacant Units"
            value={formatNumber(data.units.vacant)}
            icon={Layers}
            subtitle="Available for lease"
          />
        </div>
      </Section>

      {/* ================================================================== */}
      {/* LEASE STATUS                                                        */}
      {/* ================================================================== */}
      <Section title="Leases" icon={FileText}>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <MetricCard label="Total Leases" value={formatNumber(data.leases.total)} icon={FileText} />
          <MetricCard label="Active" value={formatNumber(data.leases.active)} subtitle="Currently active" />
          <MetricCard label="Expiring" value={formatNumber(data.leases.expiring)} subtitle="Within 30 days" />
          <MetricCard label="Expired" value={formatNumber(data.leases.expired)} subtitle="Past expiry date" />
          <MetricCard label="Terminated" value={formatNumber(data.leases.terminated)} subtitle="Early termination" />
        </div>
      </Section>

      {/* ================================================================== */}
      {/* FINANCIAL KPIs                                                      */}
      {/* ================================================================== */}
      <Section title="Rent Collected & Financials" icon={CreditCard}>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard
            label="Total Collected Rent"
            value={formatCurrency(data.collected_rent.total)}
            icon={CreditCard}
            subtitle={`${data.collected_rent.payment_count} total payments`}
          />
          <MetricCard
            label="Period Collected Rent"
            value={formatCurrency(data.collected_rent.period_total)}
            icon={TrendingUp}
            subtitle={
              data.collected_rent.rent_growth !== null
                ? `${data.collected_rent.rent_growth > 0 ? '+' : ''}${data.collected_rent.rent_growth}% vs previous`
                : `${data.collected_rent.period_payments} payments in period`
            }
          />
          <MetricCard
            label="Outstanding Rent"
            value={formatCurrency(data.outstanding_rent.total)}
            icon={AlertTriangle}
            subtitle={`${data.outstanding_rent.period_count} overdue periods`}
          />
          <MetricCard
            label="Overdue Rent"
            value={formatCurrency(data.overdue_rent.total)}
            icon={AlertTriangle}
            subtitle={`${data.overdue_rent.period_count} past-due periods`}
          />
        </div>
      </Section>

      {/* ================================================================== */}
      {/* CHARTS SECTION                                                      */}
      {/* ================================================================== */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* User Growth */}
        <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
          <GrowthLineChart
            data={userGrowthData}
            lines={[
              { key: 'landlords', color: '#3b82f6', name: 'Landlords' },
              { key: 'tenants', color: '#10b981', name: 'Tenants' },
            ]}
            title="User Growth (12 months)"
          />
        </div>

        {/* Property/Unit Growth */}
        <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
          <GrowthLineChart
            data={propertyGrowthData}
            lines={[
              { key: 'properties', color: '#8b5cf6', name: 'Properties' },
              { key: 'units', color: '#f59e0b', name: 'Units' },
            ]}
            title="Property & Unit Growth (12 months)"
          />
        </div>

        {/* Payment Volume */}
        <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
          <h4 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">
            Payment Volume (12 months)
          </h4>
          <PaymentVolumeChart data={data.growth_trends.payments} />
        </div>

        {/* Subscription Distribution */}
        <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
          <h4 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">
            Subscription Distribution
          </h4>
          <SubscriptionPieChart data={data.subscriptions} />
        </div>
      </div>

      {/* ================================================================== */}
      {/* SUBSCRIPTION DETAILS                                                */}
      {/* ================================================================== */}
      <Section title="Subscriptions" icon={Layers}>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard label="Total" value={formatNumber(data.subscriptions.total)} icon={Layers} />
          <MetricCard label="Active" value={formatNumber(data.subscriptions.active)} subtitle="Trial + Active" />
          <MetricCard label="Free Plan" value={formatNumber(data.subscriptions.free)} />
          <MetricCard label="Professional" value={formatNumber(data.subscriptions.professional)} />
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3 mt-4">
          <MetricCard label="Business Plan" value={formatNumber(data.subscriptions.business)} />
          <MetricCard label="Cancelled" value={formatNumber(data.subscriptions.cancelled)} />
          <MetricCard label="Past Due" value={formatNumber(data.subscriptions.past_due)} />
        </div>
      </Section>

      {/* ================================================================== */}
      {/* SYSTEM HEALTH                                                       */}
      {/* ================================================================== */}
      <Section title="System Health" icon={Activity}>
        <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
          {Object.entries(data.system_health).length === 0 ? (
            <p className="text-sm text-gray-500">No health data available.</p>
          ) : (
            <div className="space-y-3">
              {Object.entries(data.system_health).map(([key, value]) => (
                <div
                  key={key}
                  className="flex items-center justify-between rounded-md bg-gray-50 px-4 py-3"
                >
                  <span className="text-sm font-medium text-gray-700 capitalize">
                    {key.replace(/_/g, ' ')}
                  </span>
                  <HealthBadge status={value} />
                </div>
              ))}
            </div>
          )}
        </div>
      </Section>
    </div>
  );
}
