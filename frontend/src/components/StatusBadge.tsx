// =============================================================================
// Reusable Status Badge Component
// =============================================================================

const STATUS_STYLES: Record<string, string> = {
  ACTIVE: 'bg-green-50 text-green-700',
  PAID: 'bg-green-50 text-green-700',
  TRIAL: 'bg-blue-50 text-blue-700',
  PENDING: 'bg-amber-50 text-amber-700',
  PAST_DUE: 'bg-amber-50 text-amber-700',
  EXPIRING: 'bg-amber-50 text-amber-700',
  FUTURE: 'bg-blue-50 text-blue-700',
  CANCELLED: 'bg-gray-100 text-gray-600',
  EXPIRED: 'bg-gray-100 text-gray-600',
  ARCHIVED: 'bg-gray-100 text-gray-600',
  TERMINATED: 'bg-red-50 text-red-700',
  FAILED: 'bg-red-50 text-red-700',
  SUSPENDED: 'bg-red-50 text-red-700',
  DEACTIVATED: 'bg-gray-100 text-gray-600',
  OCCUPIED: 'bg-green-50 text-green-700',
  VACANT: 'bg-amber-50 text-amber-700',
  LANDLORD: 'bg-blue-50 text-blue-700',
  TENANT: 'bg-purple-50 text-purple-700',
  PLATFORM_ADMIN: 'bg-red-50 text-red-700',
  FREE: 'bg-gray-100 text-gray-700',
  PROFESSIONAL: 'bg-blue-50 text-blue-700',
  BUSINESS: 'bg-purple-50 text-purple-700',
};

interface StatusBadgeProps {
  status: string;
  className?: string;
}

export default function StatusBadge({ status, className = '' }: StatusBadgeProps) {
  const style = STATUS_STYLES[status] ?? 'bg-gray-100 text-gray-600';
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${style} ${className}`}>
      {status.replace(/_/g, ' ')}
    </span>
  );
}
