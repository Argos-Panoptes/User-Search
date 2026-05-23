import React, { useState } from "react";
import useIsMobile from "../../hooks/useIsMobile";
import { PiDotsThreeBold } from "react-icons/pi";

const MOBILE_NAV_HEIGHT = 60;
const MAX_VISIBLE_TABS = 4;

/**
 * PageTabBar
 *
 * Props:
 *  tabs        - Array of { id, label, shortLabel?, icon }
 *  activeTab   - string
 *  onChange    - (id) => void
 *  actions     - Optional ReactNode rendered right of desktop tabs (desktop only)
 */
export default function PageTabBar({ tabs, activeTab, onChange, actions }) {
    const isMobile = useIsMobile();
    const [showMoreSheet, setShowMoreSheet] = useState(false);

    if (isMobile) {
        const hasOverflow = tabs.length > MAX_VISIBLE_TABS;
        const visibleTabs = hasOverflow ? tabs.slice(0, MAX_VISIBLE_TABS - 1) : tabs;
        const overflowTabs = hasOverflow ? tabs.slice(MAX_VISIBLE_TABS - 1) : [];
        const overflowActive = overflowTabs.some(t => t.id === activeTab);

        return (
            <>
                {/* More tab bottom sheet */}
                {showMoreSheet && (
                    <>
                        <div
                            onClick={() => setShowMoreSheet(false)}
                            style={{
                                position: 'fixed', inset: 0, zIndex: 60,
                                background: 'rgba(0,0,0,0.45)',
                            }}
                        />
                        <div style={{
                            position: 'fixed', bottom: MOBILE_NAV_HEIGHT, left: 0, right: 0,
                            zIndex: 70,
                            background: 'var(--bg-card)',
                            borderTop: '1px solid var(--border)',
                            borderRadius: '16px 16px 0 0',
                            padding: '8px 0 4px',
                        }}>
                            <div
                                style={{
                                    width: 36, height: 4,
                                    background: 'var(--border)',
                                    borderRadius: 2,
                                    margin: '0 auto 12px',
                                }}
                            />
                            {overflowTabs.map(tab => (
                                <button
                                    key={tab.id}
                                    onClick={() => { onChange(tab.id); setShowMoreSheet(false); }}
                                    style={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: 12,
                                        width: '100%',
                                        padding: '12px 20px',
                                        background: activeTab === tab.id ? 'var(--bg-accent-muted)' : 'transparent',
                                        color: activeTab === tab.id ? 'var(--accent)' : 'var(--text-primary)',
                                        border: 'none',
                                        cursor: 'pointer',
                                        fontSize: 14,
                                        fontWeight: activeTab === tab.id ? 600 : 400,
                                        textAlign: 'left',
                                    }}
                                >
                                    <tab.icon style={{ fontSize: 18, flexShrink: 0 }} />
                                    {tab.label}
                                </button>
                            ))}
                        </div>
                    </>
                )}

                {/* Fixed bottom nav bar */}
                <div
                    style={{
                        position: 'fixed',
                        bottom: 0, left: 0, right: 0,
                        height: MOBILE_NAV_HEIGHT,
                        zIndex: 50,
                        background: 'var(--bg-sidebar)',
                        borderTop: '1px solid var(--border)',
                        display: 'flex',
                        alignItems: 'stretch',
                    }}
                >
                    {visibleTabs.map(tab => {
                        const isActive = activeTab === tab.id;
                        return (
                            <button
                                key={tab.id}
                                onClick={() => onChange(tab.id)}
                                style={{
                                    flex: 1,
                                    display: 'flex',
                                    flexDirection: 'column',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    gap: 4,
                                    border: 'none',
                                    background: 'transparent',
                                    cursor: 'pointer',
                                    color: isActive ? 'var(--accent)' : 'var(--text-tertiary)',
                                    transition: 'color 150ms ease',
                                    position: 'relative',
                                    padding: '8px 4px 6px',
                                }}
                            >
                                {/* Active indicator line */}
                                {isActive && (
                                    <span style={{
                                        position: 'absolute',
                                        top: 0, left: '25%', right: '25%',
                                        height: 2,
                                        background: 'var(--accent)',
                                        borderRadius: '0 0 2px 2px',
                                    }} />
                                )}
                                <tab.icon style={{ fontSize: 20 }} />
                                <span style={{
                                    fontSize: 10,
                                    fontWeight: isActive ? 600 : 400,
                                    letterSpacing: '0.01em',
                                    lineHeight: 1,
                                }}>
                                    {tab.shortLabel || tab.label}
                                </span>
                            </button>
                        );
                    })}

                    {/* More button */}
                    {hasOverflow && (
                        <button
                            onClick={() => setShowMoreSheet(s => !s)}
                            style={{
                                flex: 1,
                                display: 'flex',
                                flexDirection: 'column',
                                alignItems: 'center',
                                justifyContent: 'center',
                                gap: 4,
                                border: 'none',
                                background: 'transparent',
                                cursor: 'pointer',
                                color: overflowActive ? 'var(--accent)' : 'var(--text-tertiary)',
                                transition: 'color 150ms ease',
                                position: 'relative',
                                padding: '8px 4px 6px',
                            }}
                        >
                            {overflowActive && (
                                <span style={{
                                    position: 'absolute',
                                    top: 0, left: '25%', right: '25%',
                                    height: 2,
                                    background: 'var(--accent)',
                                    borderRadius: '0 0 2px 2px',
                                }} />
                            )}
                            <PiDotsThreeBold style={{ fontSize: 20 }} />
                            <span style={{ fontSize: 10, fontWeight: 400, letterSpacing: '0.01em', lineHeight: 1 }}>
                                More
                            </span>
                        </button>
                    )}
                </div>
            </>
        );
    }

    // Desktop: horizontal top tabs with border-b
    return (
        <div className="mb-8" style={{ borderBottom: '1px solid var(--border)' }}>
            <div className="flex items-center justify-between">
                <div className="flex overflow-x-auto no-scrollbar">
                    {tabs.map((tab) => (
                        <button
                            key={tab.id}
                            onClick={() => onChange(tab.id)}
                            className="flex items-center gap-2 px-6 py-3 font-medium text-sm transition-colors border-b-2 whitespace-nowrap flex-shrink-0"
                            style={{
                                borderColor: activeTab === tab.id ? 'var(--accent)' : 'transparent',
                                color: activeTab === tab.id ? 'var(--accent)' : 'var(--text-secondary)',
                            }}
                            onMouseEnter={(e) => { if (activeTab !== tab.id) e.currentTarget.style.color = 'var(--text-primary)'; }}
                            onMouseLeave={(e) => { if (activeTab !== tab.id) e.currentTarget.style.color = 'var(--text-secondary)'; }}
                        >
                            <tab.icon /> {tab.label}
                        </button>
                    ))}
                </div>
                {actions && (
                    <div className="flex items-center gap-2 mb-1 flex-shrink-0">{actions}</div>
                )}
            </div>
        </div>
    );
}
