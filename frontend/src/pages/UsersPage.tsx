// =============================================================================
// Alquiler Super User — Users Page (Backend Gap)
//
// This page documents a backend gap: no user listing endpoint exists for
// platform admins. The admin dashboard shows aggregate user counts, but
// individual user management requires new API endpoints.
// =============================================================================

import { AlertTriangle, Users } from 'lucide-react';

export default function UsersPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Users</h1>
        <p className="mt-1 text-sm text-gray-500">
          Manage landlords, tenants, and platform administrators.
        </p>
      </div>

      <div className="rounded-lg border border-amber-200 bg-amber-50 p-6">
        <div className="flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-amber-500 flex-shrink-0 mt-0.5" />
          <div>
            <h3 className="text-sm font-medium text-amber-800">Backend Gap — No User Management API</h3>
            <p className="mt-1 text-sm text-amber-700">
              The Django backend does not yet expose a user listing or management endpoint for
              platform admins. The available data is:
            </p>
            <ul className="mt-2 list-disc list-inside text-sm text-amber-700 space-y-1">
              <li><strong>Aggregate counts</strong> — available via <code>GET /api/v1/dashboard/admin/</code></li>
              <li><strong>Own profile</strong> — available via <code>GET /api/v1/auth/me/</code></li>
            </ul>
            <p className="mt-2 text-sm text-amber-700">
              To enable this page, the backend needs:
            </p>
            <ul className="mt-1 list-disc list-inside text-sm text-amber-700 space-y-1">
              <li>A new admin-only user listing endpoint (e.g., <code>GET /api/v1/admin/users/</code>)</li>
              <li>User management actions (suspend, reactivate, deactivate)</li>
              <li>The <code>IsPlatformAdmin</code> permission on these new endpoints</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Placeholder content */}
      <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <div className="flex flex-col items-center py-12 text-center">
          <Users className="h-12 w-12 text-gray-300" />
          <h3 className="mt-4 text-sm font-medium text-gray-900">User Management — Coming Soon</h3>
          <p className="mt-1 text-sm text-gray-500">
            This page will display a searchable, filterable list of all platform users
            once the backend user management API is implemented.
          </p>
        </div>
      </div>
    </div>
  );
}
