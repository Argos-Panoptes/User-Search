import React from 'react';
import {
    PiMagnifyingGlassBold,
    PiDatabaseDuotone,
    PiMoonBold,
    PiPowerBold,
    PiSquaresFourDuotone,
    PiXBold,
    PiCreditCardDuotone,
    PiNoteBold,
    PiShieldCheckDuotone,
    PiSunBold,
    PiFileCodeBold,
} from "react-icons/pi";
import { LuScanSearch } from "react-icons/lu";
import { NavLink } from 'react-router';
import { useAuth } from '../../context/AuthContext';
import { useTheme } from '../../context/ThemeContext';

const NavItem = ({ to, label, icon: Icon, onClick }) => {
    return (
        <div className="w-full">
            <NavLink
                to={to}
                onClick={onClick}
                className={({ isActive }) => `si-nav-item ${isActive ? 'is-active' : ''}`}
                title={label}
            >
                <div className="flex items-center min-w-0">
                    <Icon className="text-base" />
                    <span className="ml-2 truncate">{label}</span>
                </div>
            </NavLink>
        </div>
    );
};

export default function Sidebar({ onLogout, isOpen, onClose, isMobile }) {
    const { user } = useAuth();
    const { theme, toggleTheme } = useTheme();
    const subStatus = user?.subscription_status || user?.subscription?.status;
    const isSubscribed = subStatus === 'active' || subStatus === 'trialing';
    const handleNavClick = isMobile ? onClose : undefined;

    return (
        <aside className={`si-sidebar si-desktop-sidebar fixed inset-y-0 left-0 z-[100] transition-transform duration-300 transform flex flex-col justify-between ${isOpen ? "translate-x-0" : "-translate-x-full si-desktop-translate-x-0"} flex-shrink-0`}>
            <div className="flex flex-col h-full min-h-0">
                {/* Logo Area */}
                <div className="h-[72px] flex-none flex items-center justify-between px-4 border-b border-border">
                    <div className="flex items-center gap-3">
                        <div className="si-logo-mark">
                            <LuScanSearch />
                        </div>
                        <span className="si-sidebar-logo">
                            Signal<span className="text-accent">Intel</span>
                        </span>
                    </div>
                    {/* Close Button Mobile */}
                    <button onClick={onClose} className="si-icon-button si-mobile-only">
                        <PiXBold className="text-base" />
                    </button>
                </div>

                {/* Navigation Area */}
                <div className="flex-1 overflow-y-auto custom-scrollbar flex flex-col min-h-0">
                    {/* Debug Info (Temporary) */}

                    <nav className="mt-4 space-y-1 px-3 flex-none">
                        <NavItem
                            to="/users"
                            label="User Search"
                            icon={PiMagnifyingGlassBold}
                            onClick={handleNavClick}
                        />
                        <NavItem
                            to="/groups"
                            label="Group Search"
                            icon={PiSquaresFourDuotone}
                            onClick={handleNavClick}
                        />
                        {user?.is_superuser && (
                            <NavItem
                                to="/ingestion"
                                label="Ingestion"
                                icon={PiDatabaseDuotone}
                                onClick={handleNavClick}
                            />
                        )}
                        {user?.is_superuser && (
                            <NavItem
                                to="/admin"
                                label="Admin Tools"
                                icon={PiShieldCheckDuotone}
                                onClick={handleNavClick}
                            />
                        )}

{isSubscribed && (
                            <NavItem
                                to="/api/documentation"
                                label="API Documentation"
                                icon={PiFileCodeBold}
                                onClick={handleNavClick}
                            />
                        )}

                        {/* Subscription Link - Only for subscribed users who are NOT admins */}
                        {isSubscribed && !user?.is_superuser && (
                            <NavItem
                                to="/subscription"
                                label="Subscription"
                                icon={PiCreditCardDuotone}
                                onClick={handleNavClick}
                            />
                        )}

                        <NavItem
                            to="/documentation"
                            label="Documentation"
                            icon={PiNoteBold}
                            onClick={handleNavClick}
                        />
                    </nav>
                </div>
            </div>

            {/* Bottom Actions - Mobile Only */}
            <div className="p-3 border-t border-border flex-none si-mobile-only space-y-3">
                <button
                    onClick={toggleTheme}
                    className="si-button-secondary w-full justify-start"
                    title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
                >
                    {theme === 'dark' ? <PiSunBold className="text-sm" /> : <PiMoonBold className="text-sm" />}
                    <span>{theme === 'dark' ? 'Light Mode' : 'Dark Mode'}</span>
                </button>
                <button
                    onClick={onLogout}
                    className="si-button-secondary w-full justify-start"
                    title="Sign Out"
                >
                    <PiPowerBold className="text-sm" />
                    <span>Sign Out</span>
                </button>
            </div>
        </aside>
    );
}
