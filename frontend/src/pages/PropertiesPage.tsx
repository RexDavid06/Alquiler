// =============================================================================
// Alquiler Super User — Properties Page (Backend Gap)
//
// The existing Properties API is landlord-scoped: admins cannot list
// all properties across landlords. The dashboard shows aggregate counts,
// but individual property records require a new admin-scoped endpoint.
// =============================================================================

import { AlertTriangle, Building2 } from 'lucide-react';

export default function PropertiesPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Properties</h1>
        <p className="mt-1 text-sm text-gray-500">
          View all properties across the platform.
        </p>
      </div>

      <div className="rounded-lg border border-amber-200 bg-amber-50 p-6">
        <div className="flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-amber-500 flex-shrink-0 mt-0.5" />
          <div>
            <h3 className="text-sm font-medium text-amber-800">Backend Gap — Landlord-Scoped Properties</h3>
            <p className="mt-1 text-sm text-amber-700">
              The <code>PropertyViewSet</code> is scoped to <code>IsLandlord</code> — platform admins
              cannot list properties across all landlords. The admin dashboard shows only
              aggregate property counts via <code>GET /api/v1/dashboard/admin/</code>.
            </p>
            <p className="mt-2 text-sm text-amber-700">
              To enable this page, the backend needs an admin-only property listing endpoint
              with landlord information.
            </p>
          </div>
        </div>
      </div>

      <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <div className="flex flex-col items-center py-12 text-center">
          <Building2 className="h-12 w-12 text-gray-300" />
          <h3 className="mt-4 text-sm font-medium text-gray-900">Property Listing — Coming Soon</h3>
          <p className="mt-1 text-sm text-gray-500">
            This page will display a searchable, filterable list of all platform properties
            once the backend admin property endpoint is implemented.
          </p>
        </div>
      </div>
    </div>
  );
}
