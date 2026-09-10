// =============================================================================
// Alquiler Super User — Plans Page
//
// Platform plan management: list, create, edit, activate/deactivate.
// Uses PlanCard grid with PlanForm modal for create/edit.
// =============================================================================

import { useState, useEffect, useCallback } from 'react';
import {
  getAdminPlans,
  activateAdminPlan,
  deactivateAdminPlan,
  updateAdminPlan,
  createAdminPlan,
} from '../api/admin';
import type { AdminPlan, PaginatedResponse } from '../api/types';
import PlanCard from '../components/PlanCard';
import PlanForm, { type PlanFormData } from '../components/PlanForm';
import SearchInput from '../components/SearchInput';
import FilterSelect from '../components/FilterSelect';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorState from '../components/ErrorState';
import EmptyState from '../components/EmptyState';
import { Layers, Plus } from 'lucide-react';

const TIER_OPTIONS = [
  { label: 'All Tiers', value: '' },
  { label: 'Free', value: 'FREE' },
  { label: 'Professional', value: 'PROFESSIONAL' },
  { label: 'Business', value: 'BUSINESS' },
];

export default function PlansPage() {
  const [data, setData] = useState<PaginatedResponse<AdminPlan> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [tierFilter, setTierFilter] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [editingPlan, setEditingPlan] = useState<AdminPlan | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getAdminPlans({
        search: search || undefined,
        tier: tierFilter || undefined,
      });
      setData(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load plans.');
    } finally {
      setLoading(false);
    }
  }, [search, tierFilter]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleCreate = () => {
    setEditingPlan(null);
    setShowForm(true);
  };

  const handleEdit = (plan: AdminPlan) => {
    setEditingPlan(plan);
    setShowForm(true);
  };

  const handleActivate = async (plan: AdminPlan) => {
    try {
      await activateAdminPlan(plan.id);
      fetchData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to activate plan.');
    }
  };

  const handleDeactivate = async (plan: AdminPlan) => {
    try {
      await deactivateAdminPlan(plan.id);
      fetchData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to deactivate plan.');
    }
  };

  const handleFormSubmit = async (formData: PlanFormData) => {
    if (editingPlan) {
      await updateAdminPlan(editingPlan.id, formData);
    } else {
      await createAdminPlan(formData as Parameters<typeof createAdminPlan>[0]);
    }
    setShowForm(false);
    setEditingPlan(null);
    fetchData();
  };

  if (loading && !data) return <LoadingSpinner message="Loading plans…" />;
  if (error && !data) return <ErrorState message={error} onRetry={fetchData} />;

  const plans = data?.results ?? [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Plans</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage platform subscription plans.
          </p>
        </div>
        <button
          onClick={handleCreate}
          className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700 transition-colors"
        >
          <Plus className="h-4 w-4" />
          Create Plan
        </button>
      </div>

      <div className="flex flex-col sm:flex-row gap-3">
        <SearchInput
          value={search}
          onChange={(v) => setSearch(v)}
          placeholder="Search by name or tier…"
          className="flex-1"
        />
        <FilterSelect
          value={tierFilter}
          onChange={(v) => setTierFilter(v)}
          options={TIER_OPTIONS}
          label="Tier"
        />
      </div>

      {plans.length === 0 ? (
        <EmptyState icon={Layers} title="No plans found" description="No plans match your filters." />
      ) : (
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {plans.map((plan) => (
            <PlanCard
              key={plan.id}
              name={plan.name}
              tier={plan.tier}
              price={plan.price_ngn}
              description={plan.description}
              quotas={[
                { label: 'Max Active Tenants', value: plan.max_active_tenants },
                { label: 'Max Properties', value: plan.max_properties },
              ]}
              features={[
                { label: 'Active on platform', included: plan.is_active },
                { label: 'Subscriptions enabled', included: plan.is_active },
              ]}
              subscriberCount={plan.subscriber_count}
              isActive={plan.is_active}
              isPopular={plan.tier === 'PROFESSIONAL'}
              onSelect={() => handleEdit(plan)}
              actions={
                <div className="flex gap-4">
                  <button
                    onClick={(e) => { e.stopPropagation(); handleEdit(plan); }}
                    className="text-sm text-blue-600 hover:text-blue-800 font-medium"
                  >
                    Edit
                  </button>
                  {plan.is_active ? (
                    <button
                      onClick={(e) => { e.stopPropagation(); handleDeactivate(plan); }}
                      className="text-sm text-red-600 hover:text-red-800 font-medium"
                    >
                      Deactivate
                    </button>
                  ) : (
                    <button
                      onClick={(e) => { e.stopPropagation(); handleActivate(plan); }}
                      className="text-sm text-green-600 hover:text-green-800 font-medium"
                    >
                      Activate
                    </button>
                  )}
                </div>
              }
            />
          ))}
        </div>
      )}

      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-lg rounded-lg bg-white p-6 shadow-xl max-h-[90vh] overflow-y-auto">
            <PlanForm
              plan={editingPlan}
              onSubmit={handleFormSubmit}
              onCancel={() => { setShowForm(false); setEditingPlan(null); }}
            />
          </div>
        </div>
      )}
    </div>
  );
}