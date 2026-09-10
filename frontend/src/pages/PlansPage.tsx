// =============================================================================
// Alquiler Super User — Plans Page
//
// Platform plan management: create, edit, activate/deactivate plans,
// view subscribers per plan. Uses PlanCard and PlanForm components.
// =============================================================================

import { useState, useEffect, useCallback } from 'react';
import {
  getAdminPlans,
  getAdminPlanDetail,
  createAdminPlan,
  updateAdminPlan,
  deactivateAdminPlan,
  activateAdminPlan,
  getAdminPlanSubscribers,
} from '../api/admin';
import type { AdminPlan, PlanSubscriber, PaginatedResponse } from '../api/types';
import PlanCard from '../components/PlanCard';
import PlanForm from '../components/PlanForm';
import ConfirmActionDialog from '../components/ConfirmActionDialog';
import Pagination from '../components/Pagination';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorState from '../components/ErrorState';
import EmptyState from '../components/EmptyState';
import { Layers, Plus, X } from 'lucide-react';

const PAGE_SIZE = 20;

export default function PlansPage() {
  const [plans, setPlans] = useState<AdminPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editingPlan, setEditingPlan] = useState<AdminPlan | null>(null);
  const [formLoading, setFormLoading] = useState(false);
  const [confirmAction, setConfirmAction] = useState<{
    type: 'deactivate' | 'activate';
    plan: AdminPlan;
  } | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [subscribersPlan, setSubscribersPlan] = useState<AdminPlan | null>(null);
  const [subscribers, setSubscribers] = useState<PaginatedResponse<PlanSubscriber> | null>(null);
  const [subscribersLoading, setSubscribersLoading] = useState(false);
  const [subscribersPage, setSubscribersPage] = useState(1);

  const fetchPlans = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getAdminPlans({ page_size: 100 });
      setPlans(res.results);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load plans.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPlans();
  }, [fetchPlans]);

  const fetchSubscribers = useCallback(async () => {
    if (!subscribersPlan) return;
    setSubscribersLoading(true);
    try {
      const res = await getAdminPlanSubscribers(subscribersPlan.id, {
        page: subscribersPage,
        page_size: PAGE_SIZE,
      });
      setSubscribers(res);
    } catch {
      // ignore
    } finally {
      setSubscribersLoading(false);
    }
  }, [subscribersPlan, subscribersPage]);

  useEffect(() => {
    if (subscribersPlan) {
      fetchSubscribers();
    }
  }, [subscribersPlan, fetchSubscribers]);

  const handleCreatePlan = async (data: Parameters<typeof createAdminPlan>[0]) => {
    setFormLoading(true);
    try {
      await createAdminPlan(data);
      setShowForm(false);
      await fetchPlans();
    } catch (err) {
      throw err;
    } finally {
      setFormLoading(false);
    }
  };

  const handleUpdatePlan = async (data: Parameters<typeof updateAdminPlan>[1]) => {
    if (!editingPlan) return;
    setFormLoading(true);
    try {
      await updateAdminPlan(editingPlan.id, data);
      setEditingPlan(null);
      await fetchPlans();
    } catch (err) {
      throw err;
    } finally {
      setFormLoading(false);
    }
  };

  const handleDeactivate = async () => {
    if (!confirmAction || confirmAction.type !== 'deactivate') return;
    setActionLoading(true);
    try {
      await deactivateAdminPlan(confirmAction.plan.id);
      setConfirmAction(null);
      await fetchPlans();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to deactivate plan.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleActivate = async () => {
    if (!confirmAction || confirmAction.type !== 'activate') return;
    setActionLoading(true);
    try {
      await activateAdminPlan(confirmAction.plan.id);
      setConfirmAction(null);
      await fetchPlans();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to activate plan.');
    } finally {
      setActionLoading(false);
    }
  };

  if (loading && plans.length === 0) return <LoadingSpinner message="Loading plans…" />;
  if (error && plans.length === 0) return <ErrorState message={error} onRetry={fetchPlans} />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Plans</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage subscription plans and view subscribers.
          </p>
        </div>
        <button
          onClick={() => { setEditingPlan(null); setShowForm(true); }}
          className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
        >
          <Plus className="h-4 w-4 mr-2" />
          Create Plan
        </button>
      </div>

      {/* Plan Form Modal */}
      {(showForm || editingPlan) && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-full items-end justify-center p-4 text-center sm:items-center sm:p-0">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" onClick={() => { setShowForm(false); setEditingPlan(null); }} />
            <div className="relative transform overflow-hidden rounded-lg bg-white px-4 pt-5 pb-4 text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-lg sm:p-6">
              <div className="absolute top-0 right-0 pt-4 pr-4">
                <button
                  type="button"
                  className="rounded-md bg-white text-gray-400 hover:text-gray-500"
                  onClick={() => { setShowForm(false); setEditingPlan(null); }}
                >
                  <X className="h-6 w-6" />
                </button>
              </div>
              <PlanForm
                plan={editingPlan || undefined}
                onSubmit={editingPlan ? handleUpdatePlan : handleCreatePlan}
                onCancel={() => { setShowForm(false); setEditingPlan(null); }}
                loading={formLoading}
              />
            </div>
          </div>
        </div>
      )}

      {/* Subscribers Modal */}
      {subscribersPlan && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-full items-end justify-center p-4 text-center sm:items-center sm:p-0">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" onClick={() => setSubscribersPlan(null)} />
            <div className="relative transform overflow-hidden rounded-lg bg-white px-4 pt-5 pb-4 text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-lg sm:p-6">
              <div className="absolute top-0 right-0 pt-4 pr-4">
                <button
                  type="button"
                  className="rounded-md bg-white text-gray-400 hover:text-gray-500"
                  onClick={() => setSubscribersPlan(null)}
                >
                  <X className="h-6 w-6" />
                </button>
              </div>
              <h3 className="text-lg font-medium text-gray-900 mb-4">
                Subscribers — {subscribersPlan.name}
              </h3>
              {subscribersLoading ? (
                <LoadingSpinner message="Loading subscribers…" />
              ) : subscribers && subscribers.results.length > 0 ? (
                <div className="space-y-3">
                  {subscribers.results.map((sub) => (
                    <div key={sub.id} className="rounded-md bg-gray-50 p-3 text-sm">
                      <div className="flex items-center justify-between">
                        <span className="font-medium">{sub.landlord_name}</span>
                        <span className="text-gray-500">{sub.status}</span>
                      </div>
                      <p className="text-gray-600">{sub.landlord_email}</p>
                      <p className="text-gray-500 text-xs mt-1">Billing: {sub.billing_cycle}</p>
                    </div>
                  ))}
                  <Pagination
                    currentPage={subscribersPage}
                    totalPages={Math.ceil(subscribers.count / PAGE_SIZE)}
                    onPageChange={setSubscribersPage}
                    totalItems={subscribers.count}
                  />
                </div>
              ) : (
                <p className="text-sm text-gray-500">No subscribers for this plan.</p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Plans Grid */}
      {plans.length === 0 ? (
        <EmptyState icon={Layers} title="No plans" description="Create your first subscription plan." />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {plans.map((plan) => (
            <PlanCard
              key={plan.id}
              name={plan.name}
              tier={plan.tier}
              price={plan.price_ngn}
              description={plan.description}
              quotas={{
                'Max Tenants': plan.max_active_tenants,
                'Max Properties': plan.max_properties,
              }}
              subscriberCount={plan.subscriber_count}
              isActive={plan.is_active}
              isPopular={plan.tier === 'PROFESSIONAL'}
              actions={
                <div className="flex gap-2">
                  <button
                    onClick={() => setEditingPlan(plan)}
                    className="text-sm text-blue-600 hover:text-blue-800"
                  >
                    Edit
                  </button>
                  {plan.is_active ? (
                    <button
                      onClick={() => setConfirmAction({ type: 'deactivate', plan })}
                      className="text-sm text-red-600 hover:text-red-800"
                    >
                      Deactivate
                    </button>
                  ) : (
                    <button
                      onClick={() => setConfirmAction({ type: 'activate', plan })}
                      className="text-sm text-green-600 hover:text-green-800"
                    >
                      Activate
                    </button>
                  )}
                  <button
                    onClick={() => { setSubscribersPlan(plan); setSubscribersPage(1); }}
                    className="text-sm text-gray-600 hover:text-gray-800"
                  >
                    Subscribers
                  </button>
                </div>
              }
            />
          ))}
        </div>
      )}

      {/* Confirm Action Dialog */}
      <ConfirmActionDialog
        isOpen={!!confirmAction}
        onClose={() => setConfirmAction(null)}
        onConfirm={confirmAction?.type === 'deactivate' ? handleDeactivate : handleActivate}
        title={confirmAction?.type === 'deactivate' ? 'Deactivate Plan' : 'Activate Plan'}
        message={
          confirmAction?.type === 'deactivate'
            ? `Are you sure you want to deactivate "${confirmAction.plan.name}"? No new subscriptions will be allowed.`
            : `Are you sure you want to activate "${confirmAction?.plan.name}"?`
        }
        confirmLabel={confirmAction?.type === 'deactivate' ? 'Deactivate' : 'Activate'}
        confirmVariant={confirmAction?.type === 'deactivate' ? 'danger' : 'success'}
        loading={actionLoading}
      />
    </div>
  );
}
