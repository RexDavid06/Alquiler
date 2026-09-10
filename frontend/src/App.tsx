// =============================================================================
// Alquiler Super User — App Root
//
// Configures React Router with protected routes and the application shell.
// All routes require authentication and PLATFORM_ADMIN role.
// =============================================================================

import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Layout from './components/Layout';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import UsersPage from './pages/UsersPage';
import PropertiesPage from './pages/PropertiesPage';
import LeasesPage from './pages/LeasesPage';
import PaymentsPage from './pages/PaymentsPage';
import SubscriptionsPage from './pages/SubscriptionsPage';
import PlansPage from './pages/PlansPage';
import IssuesPage from './pages/IssuesPage';
import ActivityPage from './pages/ActivityPage';
import NotificationsPage from './pages/NotificationsPage';
import HealthPage from './pages/HealthPage';
import NotFoundPage from './pages/NotFoundPage';

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public route */}
          <Route path="/login" element={<LoginPage />} />

          {/* Protected routes — require auth + PLATFORM_ADMIN */}
          <Route
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route index element={<DashboardPage />} />
            <Route path="users" element={<UsersPage />} />
            <Route path="properties" element={<PropertiesPage />} />
            <Route path="leases" element={<LeasesPage />} />
            <Route path="payments" element={<PaymentsPage />} />
            <Route path="subscriptions" element={<SubscriptionsPage />} />
            <Route path="plans" element={<PlansPage />} />
            <Route path="issues" element={<IssuesPage />} />
            <Route path="activity" element={<ActivityPage />} />
            <Route path="notifications" element={<NotificationsPage />} />
            <Route path="health" element={<HealthPage />} />
          </Route>

          {/* Catch-all */}
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
