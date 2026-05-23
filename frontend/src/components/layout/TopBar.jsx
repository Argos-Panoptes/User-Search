import React, { useState } from 'react';
import {
    PiListBold,
    PiMoonBold,
    PiSignOutBold,
    PiShieldCheckBold,
    PiSunBold,
    PiUserBold,
    PiXBold,
    PiEnvelopeSimpleBold,
    PiIdentificationCardBold
} from "react-icons/pi";
import { useTheme } from '../../context/ThemeContext';

export default function TopBar({ onMenuClick, title, icon: Icon, onLogout, user }) {
    const [showProfilePopup, setShowProfilePopup] = useState(false);
    const { theme, toggleTheme } = useTheme();

    return (
        <header className="si-topbar flex items-center justify-between px-4 md:px-6 z-30 flex-shrink-0 relative">
            <div className="flex items-center">
                <button
                    onClick={onMenuClick}
                    className="si-icon-button si-mobile-menu-button si-mobile-only mr-3 -ml-1"
                >
                    <PiListBold className="text-base" />
                </button>
                <h1 className="si-page-title flex items-center gap-2">
                    {Icon && <Icon className="text-base text-accent" />}
                    {title}
                </h1>
            </div>

            <div className="flex items-center gap-2">
                <button
                    onClick={toggleTheme}
                    className="si-icon-button si-desktop-inline-flex"
                    title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
                    aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
                >
                    {theme === 'dark' ? <PiSunBold className="text-base" /> : <PiMoonBold className="text-base" />}
                </button>

                <div
                    className="flex items-center gap-3 cursor-pointer md:border-r md:border-border md:pr-4"
                    onClick={() => setShowProfilePopup(!showProfilePopup)}
                >
                    <div className="text-right si-desktop-block">
                        <div className="text-[13px] font-medium text-text-primary">
                            {user?.email || 'Guest'}
                        </div>
                        <div className={`si-label flex items-center justify-end gap-1 ${user?.is_superuser ? 'text-danger' : 'text-text-secondary'}`}>
                            {user?.is_superuser ? <PiShieldCheckBold /> : <PiUserBold />}
                            {user?.is_superuser ? 'Admin' : 'User'}
                        </div>
                    </div>
                    <div className="si-avatar">
                        <div className="si-avatar-fallback">
                            <PiUserBold className="text-base" />
                        </div>
                    </div>
                </div>

                <button
                    onClick={onLogout}
                    className="si-icon-button"
                    title="Sign Out"
                >
                    <PiSignOutBold className="text-base" />
                </button>
            </div>

            {/* Mobile/Quick Profile Popup */}
            {showProfilePopup && (
                <>
                    <div className="fixed inset-0 z-20 si-mobile-block" onClick={() => setShowProfilePopup(false)} />
                    <div className="absolute top-[56px] right-4 sm:right-6 w-72 bg-bg-card border border-border rounded-lg p-4 z-50">
                        <div className="flex justify-between items-start mb-4">
                            <h3 className="si-section-title">Profile Details</h3>
                            <button onClick={() => setShowProfilePopup(false)} className="si-icon-button h-8 w-8">
                                <PiXBold />
                            </button>
                        </div>

                        <div className="flex items-center gap-3 mb-4 p-3 bg-bg-hover rounded-lg border border-border">
                            <div className="si-avatar">
                                <div className="si-avatar-fallback">
                                    <PiUserBold className="text-base" />
                                </div>
                            </div>
                            <div className="min-w-0">
                                <div className="text-[13px] font-medium text-text-primary truncate">{user?.email || 'Guest'}</div>
                                <div className={`si-label flex items-center gap-1 ${user?.is_superuser ? 'text-danger' : 'text-text-secondary'}`}>
                                    {user?.is_superuser ? <PiShieldCheckBold /> : <PiUserBold />}
                                    {user?.is_superuser ? 'Admin' : 'User'}
                                </div>
                            </div>
                        </div>

                        <div className="space-y-3 px-1">
                            <div className="flex items-center gap-2 text-[12px] text-text-secondary">
                                <PiEnvelopeSimpleBold className="text-sm shrink-0" />
                                <span className="truncate">{user?.email || 'N/A'}</span>
                            </div>
                            <div className="flex items-center gap-2 text-[12px] text-text-secondary">
                                <PiIdentificationCardBold className="text-sm shrink-0" />
                                <span>ID: <span className="si-identifier">#{user?.id || '0'}</span></span>
                            </div>
                        </div>

                        <div className="mt-4 pt-4 border-t border-border space-y-2">
                            <button
                                onClick={toggleTheme}
                                className="si-button-secondary w-full justify-start"
                            >
                                {theme === 'dark' ? <PiSunBold className="text-sm" /> : <PiMoonBold className="text-sm" />}
                                {theme === 'dark' ? 'Light Mode' : 'Dark Mode'}
                            </button>
                            <button
                                onClick={onLogout}
                                className="si-button-secondary w-full justify-center"
                            >
                                <PiSignOutBold /> Sign Out
                            </button>
                        </div>
                    </div>
                </>
            )}
        </header>
    );
}
