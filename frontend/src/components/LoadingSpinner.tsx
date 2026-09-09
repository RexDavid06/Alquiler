// =============================================================================
// Alquiler Super User — Loading Spinner
// =============================================================================

interface Props {
  message?: string;
  fullScreen?: boolean;
}

export default function LoadingSpinner({ message = 'Loading…', fullScreen = false }: Props) {
  const wrapper = fullScreen
    ? 'flex items-center justify-center min-h-screen bg-gray-50'
    : 'flex items-center justify-center py-12';

  return (
    <div className={wrapper}>
      <div className="text-center">
        <div className="inline-block w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
        <p className="mt-3 text-sm text-gray-500">{message}</p>
      </div>
    </div>
  );
}
