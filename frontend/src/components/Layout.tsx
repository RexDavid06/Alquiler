// =============================================================================
// Alquiler Super User — Application Shell
//
// Provides the persistent layout: sidebar navigation, top header bar,
// and a main content area where routed pages render.
// =============================================================================

import { useState } from 'react';
import { Outlet, NavLink, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import {
  LayoutDashboard,
  Users,
  Building2,
  FileText,
  CreditCard,
  Layers,
  AlertTriangle,
  Bell,
  HeartPulse,
  Activity,
  LogOut,
  Menu,
  X,
  ChevronRight,
} from 'lucide-react';

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/users', label: 'Users', icon: Users },
  { to: '/properties', label: 'Properties', icon: Building2 },
  { to: '/leases', label: 'Leases', icon: FileText },
  { to: '/payments', label: 'Payments', icon: CreditCard },
  { to: '/subscriptions', label: 'Subscriptions', icon: Layers },
  { to: '/plans', label: 'Plans', icon: Layers },
  { to: '/issues', label: 'Issues', icon: AlertTriangle },
  { to: '/activity', label: 'Activity', icon: Activity },
  { to: '/notifications', label: 'Notifications', icon: Bell },
  { to: '/health', label: 'System Health', icon: HeartPulse },
] as const;

function Breadcrumb() {
  const location = useLocation();
  const segments = location.pathname.split('/').filter(Boolean);
  if (segments.length === 0) return null;

  return (
    <nav className="flex items-center gap-1 text-sm text-gray-500">
      <span className="text-gray-400">/</span>
      {segments.map((seg, i) => (
        <span key={i} className="flex items-center gap-1">
          <ChevronRight className="h-3 w-3 text-gray-300" />
          <span className="capitalize font-medium text-gray-700">
            {seg.replace(/-/g, ' ')}
          </span>
        </span>
      ))}
    </nav>
  );
}

export default function Layout() {
  const { user, logout } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="flex h-screen bg-gray-50">
      {/* ------------------------------------------------------------------ */}
      {/* Sidebar — desktop: fixed width | mobile: slide-over overlay        */}
      {/* ------------------------------------------------------------------ */}

      {/* Mobile backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <aside
        className={`
          fixed inset-y-0 left-0 z-40 flex w-64 flex-col bg-gray-900 text-white
          transition-transform duration-200
          lg:static lg:translate-x-0
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
        `}
      >
        {/* Brand */}
        <div className="flex h-16 items-center justify-between px-5 border-b border-gray-800">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 text-sm font-bold">
              A
            </div>
            <span className="text-lg font-semibold tracking-tight">Alquiler</span>
          </div>
          <button
            className="lg:hidden text-gray-400 hover:text-white"
            onClick={() => setSidebarOpen(false)}
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              onClick={() => setSidebarOpen(false)}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                }`
              }
            >
              <item.icon className="h-5 w-5 flex-shrink-0" />
              {item.label}
            </NavLink>
          ))}
        </nav>

        {/* User footer */}
        <div className="border-t border-gray-800 p-4">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-600 text-xs font-bold">
              {user?.first_name?.[0] ?? 'U'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">{user?.full_name ?? 'User'}</p>
              <p className="text-xs text-gray-400 truncate">{user?.email ?? ''}</p>
            </div>
            <button
              onClick={logout}
              className="text-gray-400 hover:text-white transition-colors"
              title="Sign out"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* ------------------------------------------------------------------ */}
      {/* Main content area                                                  */}
      {/* ------------------------------------------------------------------ */}
      <div className="flex flex-1 flex-col min-w-0">
        {/* Top bar */}
        <header className="flex h-16 items-center gap-4 border-b border-gray-200 bg-white px-4 lg:px-6">
          <button
            className="lg:hidden text-gray-500 hover:text-gray-700"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu className="h-6 w-6" />
          </button>
          <Breadcrumb />
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-4 lg:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
