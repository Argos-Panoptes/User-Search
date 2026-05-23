import React, { useState } from 'react';
import { Outlet, useLocation } from 'react-router';
import Sidebar from './Sidebar';
import TopBar from './TopBar';
import { useAuth } from '../../context/AuthContext';
import useIsMobile from '../../hooks/useIsMobile';
import {
    PiMagnifyingGlassBold,
    PiSquaresFourDuotone,
    PiDatabaseDuotone,
    PiShieldCheckDuotone,
    PiKeyBold,
    PiCreditCardDuotone,
    PiNoteBold,
    PiFileCodeBold,
    PiSquaresFourBold,
} from "react-icons/pi";

export default function MainLayout() {
    const { logout, user } = useAuth();
    const [isSidebarOpen, setIsSidebarOpen] = useState(false);
    const location = useLocation();
    const isMobile = useIsMobile();

    const toggleSidebar = () => setIsSidebarOpen(!isSidebarOpen);

    React.useEffect(() => {
        if (!isMobile) {
            setIsSidebarOpen(true);
        }
    }, [isMobile]);

    React.useEffect(() => {
        if (!isMobile) {
            return undefined;
        }

        const handleKeyDown = (event) => {
            if (event.key === 'Escape') {
                setIsSidebarOpen(false);
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [isMobile]);

    const getPageTitle = (pathname) => {
        if (pathname.startsWith('/users')) return 'User Search';
        if (pathname.startsWith('/groups')) return 'Group Search';
        if (pathname.startsWith('/ingestion')) return 'Ingestion';
        if (pathname.startsWith('/admin')) return 'Admin Tools';
        if (pathname.startsWith('/account')) return 'API Keys';
        if (pathname.startsWith('/subscription')) return 'Subscription';
        if (pathname.startsWith('/documentation')) return 'Documentation';
        return 'Dashboard';
    };

    const getPageIcon = (pathname) => {
        if (pathname.startsWith('/users')) return PiMagnifyingGlassBold;
        if (pathname.startsWith('/groups')) return PiSquaresFourDuotone;
        if (pathname.startsWith('/ingestion')) return PiDatabaseDuotone;
        if (pathname.startsWith('/admin')) return PiShieldCheckDuotone;
        if (pathname.startsWith('/account')) return PiKeyBold;
        if (pathname.startsWith('/subscription')) return PiCreditCardDuotone;
        if (pathname.startsWith('/documentation')) return PiNoteBold;
        return PiSquaresFourBold;
    };

    return (
        <div className="si-shell">
            {/* Mobile Sidebar Overlay */}
            {isSidebarOpen && (
                <div
                    className="fixed inset-0 z-[90] si-mobile-block"
                    style={{ background: 'rgba(0, 0, 0, 0.6)' }}
                    onClick={() => setIsSidebarOpen(false)}
                />
            )}

            <Sidebar
                onLogout={logout}
                isOpen={isSidebarOpen}
                onClose={() => setIsSidebarOpen(false)}
                isMobile={isMobile}
            />

            <main className="flex-1 flex flex-col h-full relative overflow-hidden bg-bg-page">
                <TopBar
                    onMenuClick={toggleSidebar}
                    title={getPageTitle(location.pathname)}
                    icon={getPageIcon(location.pathname)}
                    onLogout={logout}
                    user={user}
                />
                <div className="flex-1 overflow-y-auto custom-scrollbar relative flex flex-col">
                    <Outlet />
                </div>
            </main>
        </div>
    );
}
