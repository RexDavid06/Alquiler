// =============================================================================
// Alquiler Super User — Protected Route
//
// Wraps routes that require authentication and PLATFORM_ADMIN role.
// Redirects unauthenticated users to /login.
// Shows an access-denied message for non-admin users.
// =============================================================================

import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { ShieldAlert } from 'lucide-react';

interface Props {
  children: React.ReactNode;
}

export default function ProtectedRoute({ children }: Props) {
  const { user, loading } = useAuth();
  const location = useLocation();

  // Still validating the stored token.
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-center">
          <div className="inline-block w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
          <p className="mt-3 text-sm text-gray-500">Loading…</p>
        </div>
      </div>
    );
  }

  // Not authenticated — redirect to login.
  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // Authenticated but not a platform admin.
  if (user.role !== 'PLATFORM_ADMIN') {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-center max-w-md">
          <ShieldAlert className="mx-auto h-12 w-12 text-red-500" />
          <h1 className="mt-4 text-xl font-semibold text-gray-900">Access Denied</h1>
          <p className="mt-2 text-sm text-gray-600">
            This application is restricted to platform administrators.
            Your account role (<span className="font-medium">{user.role}</span>) does not have access.
          </p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
