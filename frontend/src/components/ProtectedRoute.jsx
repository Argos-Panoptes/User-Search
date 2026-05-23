import React, { useEffect } from 'react';
import { Navigate } from 'react-router';
import { useAuth } from '../context/AuthContext';

export default function ProtectedRoute({ children, requireSubscription = true, requireAdmin = false }) {
    // console.log("ProtectedRoute");

    const { isAuthenticated, loading, user } = useAuth();

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-screen">
                <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2" style={{ borderColor: 'var(--accent)' }}></div>
            </div>
        );
    }

    if (!isAuthenticated) {
        return <Navigate to="/login" replace />;
    }

    // Check subscription if required
    if (requireSubscription && user) {
        // Debugging subscription status
        // console.log("User subscription:", user.subscription);
        const subStatus = user.subscription_status || user.subscription?.status;
        const isPaid = user.is_superuser || subStatus === 'active' || subStatus === 'trialing';
        // console.log("isPaid:", isPaid);
        if (!isPaid) {
            console.log("Redirecting to subscription page because isPaid is false");
            return <Navigate to="/subscription" replace />;
        }
    }

    // Check admin if required
    if (requireAdmin && user) {
        if (!user.is_superuser) {
            console.log("Redirecting to users because requireAdmin is true and user is not superuser");
            return <Navigate to="/users" replace />;
        }
    }

    return <>{children}</>;
}
