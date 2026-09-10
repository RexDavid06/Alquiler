// =============================================================================
// Premium Plan Form Component (Create / Edit)
// =============================================================================

import { useState, useEffect } from 'react';
import { Save, X } from 'lucide-react';
import type { AdminPlan } from '../api/types';

interface PlanFormProps {
  plan?: AdminPlan | null;
  onSubmit: (data: PlanFormData) => Promise<void>;
  onCancel: () => void;
}

export interface PlanFormData {
  tier: string;
  name: string;
  description: string;
  max_active_tenants: number;
  max_properties: number;
  price_ngn: string;
  is_active: boolean;
  display_order: number;
}

const TIER_OPTIONS = [
  { value: 'FREE', label: 'Free' },
  { value: 'PROFESSIONAL', label: 'Professional' },
  { value: 'BUSINESS', label: 'Business' },
];

export default function PlanForm({ plan, onSubmit, onCancel }: PlanFormProps) {
  const [formData, setFormData] = useState<PlanFormData>({
    tier: plan?.tier ?? 'FREE',
    name: plan?.name ?? '',
    description: plan?.description ?? '',
    max_active_tenants: plan?.max_active_tenants ?? 3,
    max_properties: plan?.max_properties ?? 1,
    price_ngn: plan?.price_ngn ?? '0',
    is_active: plan?.is_active ?? true,
    display_order: plan?.display_order ?? 0,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    if (plan) {
      setFormData({
        tier: plan.tier,
        name: plan.name,
        description: plan.description,
        max_active_tenants: plan.max_active_tenants,
        max_properties: plan.max_properties,
        price_ngn: plan.price_ngn,
        is_active: plan.is_active,
        display_order: plan.display_order,
      });
    }
  }, [plan]);

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {};
    if (!formData.name.trim()) newErrors.name = 'Plan name is required.';
    if (!formData.tier) newErrors.tier = 'Tier is required.';
    if (formData.max_active_tenants < 0) newErrors.max_active_tenants = 'Must be 0 or greater.';
    if (formData.max_properties < 0) newErrors.max_properties = 'Must be 0 or greater.';
    if (Number(formData.price_ngn) < 0) newErrors.price_ngn = 'Price must be 0 or greater.';
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      await onSubmit(formData);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Failed to save plan.');
    } finally {
      setSubmitting(false);
    }
  };

  const updateField = (field: keyof PlanFormData, value: string | number | boolean) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    if (errors[field]) setErrors((prev) => ({ ...prev, [field]: '' }));
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {submitError && (
        <div className="rounded-xl bg-red-50 border border-red-200 p-4 text-sm text-red-700">
          {submitError}
        </div>
      )}

      {/* Plan Identity */}
      <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
        <h3 className="text-sm font-semibold text-gray-900 uppercase tracking-wider mb-4">
          Plan Identity
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Tier</label>
            <select
              value={formData.tier}
              onChange={(e) => updateField('tier', e.target.value)}
              disabled={!!plan}
              className="w-full rounded-xl border-gray-300 text-sm focus:border-blue-500 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-500"
            >
              {TIER_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
            {plan && <p className="mt-1 text-xs text-gray-400">Tier cannot be changed after creation.</p>}
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => updateField('name', e.target.value)}
              className={`w-full rounded-xl border-gray-300 text-sm focus:border-blue-500 focus:ring-blue-500 ${errors.name ? 'border-red-300' : ''}`}
              placeholder="e.g. Professional"
            />
            {errors.name && <p className="mt-1 text-xs text-red-600">{errors.name}</p>}
          </div>
        </div>
        <div className="mt-4">
          <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
          <textarea
            value={formData.description}
            onChange={(e) => updateField('description', e.target.value)}
            rows={3}
            className="w-full rounded-xl border-gray-300 text-sm focus:border-blue-500 focus:ring-blue-500"
            placeholder="Describe the plan features and benefits..."
          />
        </div>
      </div>

      {/* Pricing */}
      <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
        <h3 className="text-sm font-semibold text-gray-900 uppercase tracking-wider mb-4">
          Pricing
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Price (NGN/month)</label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 text-sm">₦</span>
              <input
                type="number"
                step="0.01"
                min="0"
                value={formData.price_ngn}
                onChange={(e) => updateField('price_ngn', e.target.value)}
                className={`w-full pl-8 rounded-xl border-gray-300 text-sm focus:border-blue-500 focus:ring-blue-500 ${errors.price_ngn ? 'border-red-300' : ''}`}
              />
            </div>
            {errors.price_ngn && <p className="mt-1 text-xs text-red-600">{errors.price_ngn}</p>}
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Display Order</label>
            <input
              type="number"
              min="0"
              value={formData.display_order}
              onChange={(e) => updateField('display_order', parseInt(e.target.value) || 0)}
              className="w-full rounded-xl border-gray-300 text-sm focus:border-blue-500 focus:ring-blue-500"
            />
          </div>
        </div>
      </div>

      {/* Quotas */}
      <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
        <h3 className="text-sm font-semibold text-gray-900 uppercase tracking-wider mb-4">
          Resource Limits
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Max Active Tenants</label>
            <input
              type="number"
              min="0"
              value={formData.max_active_tenants}
              onChange={(e) => updateField('max_active_tenants', parseInt(e.target.value) || 0)}
              className={`w-full rounded-xl border-gray-300 text-sm focus:border-blue-500 focus:ring-blue-500 ${errors.max_active_tenants ? 'border-red-300' : ''}`}
            />
            {errors.max_active_tenants && <p className="mt-1 text-xs text-red-600">{errors.max_active_tenants}</p>}
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Max Properties</label>
            <input
              type="number"
              min="0"
              value={formData.max_properties}
              onChange={(e) => updateField('max_properties', parseInt(e.target.value) || 0)}
              className={`w-full rounded-xl border-gray-300 text-sm focus:border-blue-500 focus:ring-blue-500 ${errors.max_properties ? 'border-red-300' : ''}`}
            />
            {errors.max_properties && <p className="mt-1 text-xs text-red-600">{errors.max_properties}</p>}
          </div>
        </div>
      </div>

      {/* Status */}
      <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
        <h3 className="text-sm font-semibold text-gray-900 uppercase tracking-wider mb-4">
          Status
        </h3>
        <label className="flex items-center gap-3 cursor-pointer">
          <div
            className={`relative w-11 h-6 rounded-full transition-colors ${formData.is_active ? 'bg-blue-600' : 'bg-gray-300'}`}
            onClick={() => updateField('is_active', !formData.is_active)}
          >
            <div
              className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform ${formData.is_active ? 'translate-x-5' : ''}`}
            />
          </div>
          <span className="text-sm font-medium text-gray-700">
            {formData.is_active ? 'Active' : 'Inactive'}
          </span>
        </label>
        <p className="mt-2 text-xs text-gray-500">
          Inactive plans are hidden from landlords and cannot be subscribed to.
        </p>
      </div>

      {/* Actions */}
      <div className="flex gap-3 justify-end">
        <button
          type="button"
          onClick={onCancel}
          className="px-5 py-2.5 text-sm font-medium text-gray-700 bg-gray-100 rounded-xl hover:bg-gray-200 transition-colors"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={submitting}
          className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-medium text-white bg-blue-600 rounded-xl hover:bg-blue-700 transition-colors disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
        >
          <Save className="w-4 h-4" />
          {submitting ? 'Saving...' : plan ? 'Save Changes' : 'Create Plan'}
        </button>
      </div>
    </form>
  );
}
