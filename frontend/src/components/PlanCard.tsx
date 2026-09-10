// =============================================================================
// Premium 3D-Inspired Plan Card Component
// =============================================================================

import type { ReactNode } from 'react';
import { Check, X } from 'lucide-react';
import StatusBadge from './StatusBadge';

interface PlanFeature {
  label: string;
  included: boolean;
}

interface PlanCardProps {
  name: string;
  tier: string;
  price: string;
  description: string;
  features: PlanFeature[];
  quotas: { label: string; value: number | string }[];
  subscriberCount: number;
  isActive: boolean;
  isPopular?: boolean;
  onSelect?: () => void;
  actions?: ReactNode;
}

const TIER_GRADIENTS: Record<string, string> = {
  FREE: 'from-gray-50 via-white to-gray-100',
  PROFESSIONAL: 'from-blue-50 via-white to-indigo-50',
  BUSINESS: 'from-purple-50 via-white to-violet-50',
};

const TIER_ACCENTS: Record<string, string> = {
  FREE: 'text-gray-700',
  PROFESSIONAL: 'text-blue-700',
  BUSINESS: 'text-purple-700',
};

const TIER_BORDERS: Record<string, string> = {
  FREE: 'border-gray-200 hover:border-gray-300',
  PROFESSIONAL: 'border-blue-200 hover:border-blue-300',
  BUSINESS: 'border-purple-200 hover:border-purple-300',
};

const TIER_HIGHLIGHTS: Record<string, string> = {
  FREE: '',
  PROFESSIONAL: 'ring-2 ring-blue-400/30',
  BUSINESS: 'ring-2 ring-purple-400/30',
};

export default function PlanCard({
  name,
  tier,
  price,
  description,
  features,
  quotas,
  subscriberCount,
  isActive,
  isPopular = false,
  onSelect,
  actions,
}: PlanCardProps) {
  const gradient = TIER_GRADIENTS[tier] ?? TIER_GRADIENTS.FREE;
  const accent = TIER_ACCENTS[tier] ?? TIER_ACCENTS.FREE;
  const border = TIER_BORDERS[tier] ?? TIER_BORDERS.FREE;
  const highlight = TIER_HIGHLIGHTS[tier] ?? '';

  return (
    <div
      className={`
        relative group
        rounded-2xl border ${border} ${highlight}
        bg-gradient-to-br ${gradient}
        shadow-[0_1px_3px_rgba(0,0,0,0.04),0_4px_12px_rgba(0,0,0,0.03)]
        hover:shadow-[0_4px_16px_rgba(0,0,0,0.08),0_8px_32px_rgba(0,0,0,0.04)]
        hover:-translate-y-1
        transition-all duration-300 ease-out
        ${onSelect ? 'cursor-pointer' : ''}
        ${!isActive ? 'opacity-60 grayscale-[30%]' : ''}
      `}
      onClick={onSelect}
      role={onSelect ? 'button' : undefined}
      tabIndex={onSelect ? 0 : undefined}
      onKeyDown={onSelect ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(); } } : undefined}
    >
      {/* Popular badge */}
      {isPopular && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2 z-10">
          <span className="inline-flex items-center rounded-full bg-gradient-to-r from-blue-600 to-indigo-600 px-4 py-1 text-xs font-semibold text-white shadow-lg shadow-blue-500/25">
            Most Popular
          </span>
        </div>
      )}

      {/* Inactive overlay */}
      {!isActive && (
        <div className="absolute inset-0 rounded-2xl bg-white/40 z-10 flex items-center justify-center">
          <span className="inline-flex items-center rounded-full bg-gray-200 px-3 py-1 text-xs font-medium text-gray-600">
            Inactive
          </span>
        </div>
      )}

      <div className="p-6 lg:p-8">
        {/* Header */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-2">
            <h3 className={`text-lg font-bold ${accent}`}>{name}</h3>
            <StatusBadge status={tier} />
          </div>
          <p className="text-sm text-gray-500 line-clamp-2">{description}</p>
        </div>

        {/* Price */}
        <div className="mb-6 pb-6 border-b border-gray-200/60">
          <div className="flex items-baseline gap-1">
            <span className="text-sm text-gray-500">₦</span>
            <span className="text-4xl font-extrabold tracking-tight text-gray-900">
              {Number(price).toLocaleString()}
            </span>
            <span className="text-sm text-gray-500">/month</span>
          </div>
        </div>

        {/* Quotas */}
        <div className="mb-6 space-y-3">
          {quotas.map((q) => (
            <div key={q.label} className="flex items-center justify-between text-sm">
              <span className="text-gray-600">{q.label}</span>
              <span className="font-semibold text-gray-900">
                {typeof q.value === 'number' ? q.value.toLocaleString() : q.value}
              </span>
            </div>
          ))}
        </div>

        {/* Features */}
        <div className="mb-6 space-y-2.5">
          {features.map((f) => (
            <div key={f.label} className="flex items-start gap-2.5">
              {f.included ? (
                <div className="mt-0.5 flex-shrink-0 w-4 h-4 rounded-full bg-green-100 flex items-center justify-center">
                  <Check className="w-2.5 h-2.5 text-green-600" strokeWidth={3} />
                </div>
              ) : (
                <div className="mt-0.5 flex-shrink-0 w-4 h-4 rounded-full bg-gray-100 flex items-center justify-center">
                  <X className="w-2.5 h-2.5 text-gray-400" strokeWidth={3} />
                </div>
              )}
              <span className={`text-sm ${f.included ? 'text-gray-700' : 'text-gray-400'}`}>
                {f.label}
              </span>
            </div>
          ))}
        </div>

        {/* Subscribers */}
        <div className="mb-6 flex items-center gap-2 text-sm text-gray-500">
          <div className="w-2 h-2 rounded-full bg-green-400" />
          <span>
            <span className="font-semibold text-gray-700">{subscriberCount}</span>{' '}
            {subscriberCount === 1 ? 'subscriber' : 'subscribers'}
          </span>
        </div>

        {/* Actions */}
        {actions && (
          <div className="pt-4 border-t border-gray-200/60">
            {actions}
          </div>
        )}
      </div>
    </div>
  );
}
