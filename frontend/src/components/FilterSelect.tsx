// =============================================================================
// Reusable Filter Select Component
// =============================================================================

interface FilterOption {
  label: string;
  value: string;
}

interface FilterSelectProps {
  value: string;
  onChange: (value: string) => void;
  options: FilterOption[];
  label?: string;
  className?: string;
}

export default function FilterSelect({
  value,
  onChange,
  options,
  label,
  className = '',
}: FilterSelectProps) {
  return (
    <div className={className}>
      {label && (
        <label className="block text-xs font-medium text-gray-500 mb-1">{label}</label>
      )}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}
