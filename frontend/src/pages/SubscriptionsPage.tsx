// =============================================================================
// Alquiler Super User — Subscriptions Page
//
// The Plans API supports PLATFORM_ADMIN for create/update/deactivate.
// This page displays all subscription plans with their details.
// =============================================================================

import { useState, useEffect, useCallback } from 'react';
import { getPlans } from '../api/dashboard';
import type { Plan } from '../api/types';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorState from '../components/ErrorState';
import EmptyState from '../components/EmptyState';
import { Layers } from 'lucide-react';

const TIER_COLORS: Record<string, string> = {
  FREE: 'bg-gray-100 text-gray-700',
  PROFESSIONAL: 'bg-blue-50 text-blue-700',
  BUSINESS: 'bg-purple-50 text-purple-700',
};

export default function SubscriptionsPage() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getPlans();
      setPlans(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load plans.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading) return <LoadingSpinner message="Loading subscriptions…" />;
  if (error) return <ErrorState message={error} onRetry={fetchData} />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Subscriptions</h1>
        <p className="mt-1 text-sm text-gray-500">
          Manage subscription plans offered to landlords.
        </p>
      </div>

      {plans.length === 0 ? (
        <EmptyState icon={Layers} title="No plans found" description="There are no subscription plans configured." />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {plans.map((plan) => (
            <div
              key={plan.id}
              className={`rounded-lg border p-5 shadow-sm ${
                plan.is_active ? 'border-gray-200 bg-white' : 'border-gray-200 bg-gray-50 opacity-60'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${TIER_COLORS[plan.tier] ?? 'bg-gray-100 text-gray-600'}`}>
                  {plan.tier}
                </span>
                {!plan.is_active && (
                  <span className="text-xs text-gray-400 font-medium">INACTIVE</span>
                )}
              </div>
              <h3 className="mt-3 text-lg font-semibold text-gray-900">{plan.name}</h3>
              {plan.description && (
                <p className="mt-1 text-sm text-gray-500 line-clamp-2">{plan.description}</p>
              )}
              <div className="mt-4 space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-500">Price</span>
                  <span className="font-medium text-gray-900">
                    {parseFloat(plan.price_ngn) === 0
                      ? 'Free'
                      : `₦${parseFloat(plan.price_ngn).toLocaleString()}/mo`}
                  </span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-500">Max Properties</span>
                  <span className="font-medium text-gray-900">{plan.max_properties}</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-500">Max Tenants</span>
                  <span className="font-medium text-gray-900">{plan.max_active_tenants}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Plan Management Gap Note */}
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
        <p className="text-xs text-amber-700">
          <strong>Note:</strong> Plan creation, editing, and deactivation are available via the API
          (<code>POST/PUT/DELETE /api/v1/subscriptions/plans/</code>) but the admin UI for managing
          plans has not been implemented yet. Plans can be managed through the API or Django admin.
        </p>
      </div>
    </div>
  );
}
