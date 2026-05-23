import React, { createContext, useState, useContext, useEffect } from 'react';
// import { GoogleOAuthProvider } from '@react-oauth/google';
import apiClient, { setJwtToken, clearJwtToken } from '../services/api';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);
    const [isAuthenticated, setIsAuthenticated] = useState(false);

    const ENABLE_AUTH = import.meta.env.VITE_ENABLE_AUTH !== 'false';
    console.log("ENABLE_AUTH", ENABLE_AUTH);
    const LOGOUT_URL = import.meta.env.VITE_LOGOUT_URL || "https://optools.io/logout";
    console.log("LOGOUT_URL", LOGOUT_URL);
    const CHECK_AUTH_URL = import.meta.env.VITE_CHECK_AUTH_URL || "https://optools.io/api/check-auth"; // Using local backend which now validates the token
    console.log("CHECK_AUTH_URL", CHECK_AUTH_URL);
    const LOGIN_URL = import.meta.env.VITE_LOGIN_URL || "https://optools.io/login";
    console.log("LOGIN_URL", LOGIN_URL);
    console.log("isAuthenticated outside", isAuthenticated);
    console.log("loading outside", loading);

    useEffect(() => {
        checkAuth();
    }, []);

    const checkAuth = async () => {
        if (!ENABLE_AUTH) {
            console.log("Auth disabled, using dev user");
            setUser({
                name: 'Dev User',
                email: 'dev@example.com',
                picture: null,
                is_superuser: true
            });
            setIsAuthenticated(true);
            setLoading(false);
            return;
        }

        try {
            // Using apiClient to leverage existing baseURL setup
            // or fetch with credentials: 'include' as per reference
            const response = await apiClient.get(CHECK_AUTH_URL);
            // Handle both wrapped {user: ...} and flat response
            const userData = response.data.user || response.data;
            setUser(userData);
            setIsAuthenticated(true);

            // Fetch a short-lived JWT for header-based auth (B2C programmatic access)
            try {
                const tokenRes = await apiClient.get('/v1/auth/token');
                setJwtToken(tokenRes.data.access_token);
            } catch {
                // Non-fatal — cookie auth still works
            }
        } catch (error) {
            console.error('Auth check failed:', error);
            setUser(null);
            setIsAuthenticated(false);
        } finally {
            setLoading(false);
        }
    };

    const logout = async () => {
        try {
            await apiClient.post(LOGOUT_URL, {});
        } catch (error) {
            console.error("Logout failed", error);
        } finally {
            clearJwtToken();
            setUser(null);
            setIsAuthenticated(false);
            window.location.href = "/app/login";
        }
    };

    return (
        <AuthContext.Provider value={{ user, loading, isAuthenticated, logout }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => useContext(AuthContext);
