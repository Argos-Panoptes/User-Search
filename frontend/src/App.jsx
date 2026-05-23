import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, Outlet } from 'react-router';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Login from './pages/Login';
import SubscriptionPage from './pages/SubscriptionPage';
import MainLayout from './components/layout/MainLayout';
import UserSearch from './features/UserSearch';
import GroupSearch from './features/GroupSearch';
import IngestionContainer from './components/features/ingestions/IngestionContainer';
import AdminDashboard from './components/features/admin/AdminDashboard';
import AccountPage from './pages/AccountPage';
import NotesPage from './pages/NotesPage';
import IngestionDocsPage from './pages/IngestionDocsPage';

function App() {
  return (
    <Router basename="/app">
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/"
            element={
              <ProtectedRoute requireSubscription={false}>
                <MainLayout />
              </ProtectedRoute>
            }
          >
            {/* Routes requiring active subscription */}
            <Route element={<ProtectedRoute requireSubscription={true}><Outlet /></ProtectedRoute>}>
              <Route index element={<Navigate to="/users" replace />} />
              <Route path="users" element={<UserSearch />} />
              <Route path="groups" element={<GroupSearch />} />
              <Route path="account" element={<AccountPage />} />
            </Route>
            <Route element={<ProtectedRoute requireAdmin={true}><Outlet /></ProtectedRoute>}>
              <Route path="ingestion" element={<IngestionContainer />} />
              <Route path="admin" element={<AdminDashboard />} />
            </Route>

            {/* Routes available without subscription (but authenticated) */}
            <Route path="subscription" element={<SubscriptionPage />} />
            <Route path="documentation" element={<NotesPage />} />

            {/* API docs — requires subscription; ingestion section gated inside by admin check */}
            <Route element={<ProtectedRoute requireSubscription={true}><Outlet /></ProtectedRoute>}>
              <Route path="api/documentation" element={<IngestionDocsPage />} />
            </Route>
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </Router>
  );
}

export default App;
