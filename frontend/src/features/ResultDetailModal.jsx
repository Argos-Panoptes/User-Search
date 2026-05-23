import React, { useState, useEffect, useCallback } from 'react';
import { useInView } from 'react-intersection-observer';
import apiClient from '../services/api';
import useMediaUrl from '../hooks/useMediaUrl';
import AuthenticatedMediaImage from '../components/common/AuthenticatedMediaImage';
import GroupMembershipTable from './ResultDetail/GroupMembershipTable';
import { PiCopyBold, PiDownloadBold } from 'react-icons/pi';

const ResultDetailModal = ({ isOpen, onClose, type, id, onDrillDown: parentDrillDown }) => {
    const [data, setData] = useState(null);
    const [navStack, setNavStack] = useState([]); // Stack for back navigation

    // Custom interceptor to maintain local history for back button
    const onDrillDown = (newType, newId) => {
        setNavStack(prev => [...prev, { id, type }]);
        parentDrillDown(newType, newId);
    };

    const handleBack = () => {
        if (navStack.length > 0) {
            const previous = navStack[navStack.length - 1];
            setNavStack(prev => prev.slice(0, -1));
            parentDrillDown(previous.type, previous.id);
        }
    };
    const [historyData, setHistoryData] = useState([]); // New history state
    const [historyTotalCount, setHistoryTotalCount] = useState(0); // Timeline total count
    const [timelineOffset, setTimelineOffset] = useState(0); // Pagination offset
    const [loading, setLoading] = useState(false);
    const [historyLoading, setHistoryLoading] = useState(false); // New history loading state
    const [loadingMore, setLoadingMore] = useState(false); // New state for loading more history
    const [error, setError] = useState(null);
    const [showRaw, setShowRaw] = useState(false);
    const [activeTab, setActiveTab] = useState('overview'); // 'overview', 'connections', 'timeline', 'raw'
    const [expandedHistoryId, setExpandedHistoryId] = useState(null);
    const [viewingHistoryItem, setViewingHistoryItem] = useState(null); // State for full historical profile view
    const [groupSearchQuery, setGroupSearchQuery] = useState(''); // Search for groups within history
    const [memberSearchQuery, setMemberSearchQuery] = useState(''); // Search for members within a group
    const [expandedSections, setExpandedSections] = useState({ admin: true, member: true, left: true, extra: false, secretParams: false }); // Accordion state
    const [sidebarCollapsed, setSidebarCollapsed] = useState(false); // Collapsible left sidebar

    const { ref: loadMoreRef, inView } = useInView({
        threshold: 0,
        rootMargin: '100px', // Pre-fetch slightly before it enters screen
    });

    // Auto load more when scrolled into view
    useEffect(() => {
        if (inView && !loadingMore && historyData.length > 0 && historyData.length < historyTotalCount) {
            loadMoreHistory();
        }
    }, [inView, loadingMore, historyData.length, historyTotalCount]);

    // Fetch details when modal opens
    useEffect(() => {
        if (isOpen && id && type) {
            fetchDetails();
            setActiveTab('overview');
            setHistoryData([]); // Reset history
            setViewingHistoryItem(null);
            setMemberSearchQuery('');
        } else {
            setData(null);
            setError(null);
            setNavStack([]); // Clear back stack on explicit close
        }
    }, [isOpen, id, type]);

    // Fetch history when tab changes to history
    useEffect(() => {
        if (isOpen && id && type && activeTab === 'timeline' && historyData.length === 0) {
            fetchHistory();
        }
    }, [activeTab, isOpen, id, type]);

    // Auto-select first history item when loaded
    useEffect(() => {
        if (historyData && historyData.length > 0 && !viewingHistoryItem) {
            setViewingHistoryItem(historyData[0]);
        }
    }, [historyData]);

    const loadMoreHistory = async () => {
        if (loadingMore) return;
        setLoadingMore(true);
        const nextOffset = timelineOffset + 10;

        try {
            if (type === 'user') {
                const payload = { serviceId: String(id) };
                const [timelineRes, profilesRes, membershipsRes] = await Promise.all([
                    apiClient.post(`/users/timeline`, { ...payload, limit: 10, offset: nextOffset }),
                    apiClient.post(`/users/history/profile`, payload),
                    apiClient.post(`/users/history/memberships`, payload)
                ]);

                const timelineData = timelineRes.data || {};
                const timeline = Array.isArray(timelineData) ? timelineData : (timelineData.items || []);
                const profiles = profilesRes.data || [];
                const memberships = membershipsRes.data || [];

                timeline.sort((a, b) => b.exportTimestamp - a.exportTimestamp);

                const constructedHistory = timeline.map(event => {
                    const ts = event.exportTimestamp;
                    const profileSnapshot = [...profiles]
                        .sort((a, b) => b.timelineId - a.timelineId)
                        .find(p => p.timelineId <= event.timelineId) || {};

                    const activeMemberships = memberships.filter(m => {
                        const from = m.validFrom;
                        const to = m.validTo;
                        return (from <= ts) && (!to || to > ts);
                    });

                    const currentData = {
                        ...profileSnapshot,
                        exportTimestamp: ts,
                        groupMemberships: activeMemberships.map(m => ({
                            id: m.groupId,
                            groupId: m.groupId,
                            groupName: m.groupName,
                            role: m.role,
                        }))
                    };

                    let opLabel = 'System Snapshot';
                    if (event.hasProfileChange && event.hasMembershipChange) opLabel = 'Full Update';
                    else if (event.hasProfileChange) opLabel = 'Profile Update';
                    else if (event.hasMembershipChange) opLabel = 'Groups Update';
                    else if (event.hasAvatarChange) opLabel = 'Photo Update';

                    return {
                        historyId: event.timelineId,
                        historyDate: ts,
                        operation: opLabel,
                        currentData: currentData,
                        hasProfileChange: event.hasProfileChange,
                        hasMembershipChange: event.hasMembershipChange,
                        hasAvatarChange: event.hasAvatarChange
                    };
                });

                setHistoryData(prev => [...prev, ...constructedHistory]);
            } else if (type === 'group') {
                const [timelineRes, detailsRes] = await Promise.all([
                    apiClient.post('/groups/timeline', { groupId: String(id), limit: 10, offset: nextOffset }),
                    apiClient.post('/groups/history', { groupId: String(id) })
                ]);

                const timelineData = timelineRes.data || {};
                const timelineEvents = Array.isArray(timelineData) ? timelineData : (timelineData.items || []);
                const detailsHistory = detailsRes.data || [];

                const constructedHistory = timelineEvents.map(event => {
                    const ts = event.exportTimestamp;
                    const snapshot = [...detailsHistory]
                        .sort((a, b) => b.timelineId - a.timelineId)
                        .find(d => d.timelineId <= event.timelineId) || {};

                    let opLabel = 'Snapshot';
                    if (event.hasDetailChange && event.hasMembershipChange) opLabel = 'Full Update';
                    else if (event.hasDetailChange) opLabel = 'Details Update';
                    else if (event.hasMembershipChange) opLabel = 'Members Update';

                    return {
                        historyId: event.timelineId,
                        historyDate: ts,
                        exportTimestamp: ts,
                        operation: opLabel,
                        currentData: {
                            ...snapshot.currentData,
                            exportTimestamp: ts,
                        },
                        hasDetailChange: event.hasDetailChange,
                        hasMembershipChange: event.hasMembershipChange,
                        membershipDiff: event.membershipDiff,
                        _isHistorical: true
                    };
                });
                setHistoryData(prev => [...prev, ...constructedHistory]);
            }
            setTimelineOffset(nextOffset);
        } catch (err) {
            console.error("Failed to load more history", err);
        } finally {
            setLoadingMore(false);
        }
    };


    const renderHistory = () => {
        if (historyLoading) return (
            <div className="flex justify-center items-center h-40">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500"></div>
            </div>
        );

        if (!historyData || historyData.length === 0) return (
            <div className="flex flex-col items-center justify-center py-12 text-gray-500">
                <svg className="w-12 h-12 mb-3 opacity-20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <p>No history records found.</p>
            </div>
        );

        return (
            <>
                {/* Mobile: stacked accordion (no nested scroll) */}
                <div className="md:hidden p-4 space-y-3">
                    {(() => {
                        const sortedByDate = [...historyData].sort((a, b) => b.historyDate - a.historyDate);
                        return sortedByDate.map((h, idx) => {
                            const isSelected = viewingHistoryItem?.historyId === h.historyId;
                            const prevItem = idx < sortedByDate.length - 1 ? sortedByDate[idx + 1] : null;
                            return (
                                <div key={h.historyId} className="rounded-xl overflow-hidden" style={{ border: `1px solid ${isSelected ? 'var(--accent)' : 'var(--border)'}` }}>
                                    <button
                                        className="w-full text-left p-3 flex items-start gap-3"
                                        style={{ background: isSelected ? 'color-mix(in srgb, var(--accent) 8%, var(--bg-card))' : 'var(--bg-card)' }}
                                        onClick={() => setViewingHistoryItem(isSelected ? null : h)}
                                    >
                                        <div className={`mt-1 h-3 w-3 rounded-full flex-shrink-0 ${h.hasProfileChange ? 'bg-amber-500' : h.hasMembershipChange ? 'bg-indigo-500' : 'bg-blue-500'}`} />
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center justify-between gap-2 mb-1">
                                                <span className="text-xs font-bold uppercase tracking-wider" style={{ color: isSelected ? 'var(--accent)' : 'var(--text-primary)' }}>{h.operation}</span>
                                                <div className="flex gap-1 flex-shrink-0">
                                                    {h.hasProfileChange && <span className="text-[9px] px-1.5 py-0.5 rounded font-medium bg-amber-900 text-amber-200">Profile</span>}
                                                    {h.hasMembershipChange && <span className="text-[9px] px-1.5 py-0.5 rounded font-medium bg-indigo-900 text-indigo-200">Groups</span>}
                                                    {h.hasAvatarChange && <span className="text-[9px] px-1.5 py-0.5 rounded font-medium bg-purple-900 text-purple-200">Photo</span>}
                                                </div>
                                            </div>
                                            {h.membershipDiff && (h.membershipDiff.joined?.length > 0 || h.membershipDiff.left?.length > 0) && (
                                                <div className="flex gap-3 mb-1">
                                                    {h.membershipDiff.joined?.length > 0 && <span className="text-[10px] font-bold text-green-300">+{h.membershipDiff.joined.length} joined</span>}
                                                    {h.membershipDiff.left?.length > 0 && <span className="text-[10px] font-bold text-red-300">−{h.membershipDiff.left.length} left</span>}
                                                </div>
                                            )}
                                            <div className="text-[11px]" style={{ color: 'var(--text-tertiary)' }}>{formatDate(h.historyDate)}</div>
                                        </div>
                                        <svg className={`w-4 h-4 flex-shrink-0 mt-0.5 transition-transform duration-200 ${isSelected ? 'rotate-180' : ''}`} style={{ color: 'var(--text-tertiary)' }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                        </svg>
                                    </button>
                                    {isSelected && (
                                        <div className="p-4" style={{ background: 'var(--bg-page)', borderTop: '1px solid var(--border)' }}>
                                            {(() => {
                                                const currentProfile = mapHistoryToProfile(h);
                                                const prevProfile = prevItem ? mapHistoryToProfile(prevItem) : null;
                                                const changedFields = getChangedFields(currentProfile, prevProfile);
                                                const addedGroupIds = getAddedGroups(currentProfile, prevProfile);
                                                const leftGroups = getLeftGroups(currentProfile, prevProfile);
                                                return renderProfileView(currentProfile, changedFields, addedGroupIds, leftGroups, prevProfile);
                                            })()}
                                        </div>
                                    )}
                                </div>
                            );
                        });
                    })()}
                    {historyData.length < historyTotalCount && (
                        <div className="py-4 text-center">
                            {loadingMore ? (
                                <div className="flex items-center justify-center gap-2 text-xs font-bold uppercase" style={{ color: 'var(--accent)' }}>
                                    <div className="w-4 h-4 border-2 border-t-transparent rounded-full animate-spin" style={{ borderColor: 'var(--accent)', borderTopColor: 'transparent' }} />
                                    Loading...
                                </div>
                            ) : (
                                <button
                                    onClick={loadMoreHistory}
                                    className="text-xs font-bold uppercase px-4 py-2 rounded-lg transition-colors"
                                    style={{ color: 'var(--accent)', border: '1px solid var(--accent)', background: 'transparent' }}
                                >
                                    Load More ({historyData.length} / {historyTotalCount})
                                </button>
                            )}
                        </div>
                    )}
                </div>

                {/* Desktop: two-column fixed layout */}
                <div className="hidden md:flex flex-row h-full overflow-hidden">
                {/* Left Sidebar: Timeline Selector */}
                <div
                    className="w-60 h-full overflow-y-auto custom-scrollbar min-h-0 flex-shrink-0"
                    style={{ borderBottom: '1px solid var(--border)', borderRight: '1px solid var(--border)', background: 'var(--bg-card)' }}
                >
                    <div className="p-4 space-y-1">
                        <div className="text-xs font-bold uppercase tracking-wider mb-3 px-2" style={{ color: 'var(--text-secondary)' }}>
                            Timeline {historyTotalCount > 0 ? `(${historyTotalCount} Total)` : ''}
                        </div>
                        {historyData.map((h, idx) => {
                            const date = new Date(h.historyDate * 1000);
                            const isSelected = viewingHistoryItem?.historyId === h.historyId;

                            return (
                                <div
                                    key={h.historyId}
                                    onClick={() => setViewingHistoryItem(h)}
                                    className="relative p-3 rounded-lg cursor-pointer transition-all border shadow-sm"
                                    style={{
                                        background: isSelected ? 'var(--bg-accent-muted)' : 'transparent',
                                        borderColor: isSelected ? 'var(--accent)' : 'transparent',
                                    }}
                                    onMouseEnter={(e) => {
                                        if (!isSelected) {
                                            e.currentTarget.style.background = 'var(--bg-hover)';
                                            e.currentTarget.style.borderColor = 'var(--border)';
                                        }
                                    }}
                                    onMouseLeave={(e) => {
                                        if (!isSelected) {
                                            e.currentTarget.style.background = 'transparent';
                                            e.currentTarget.style.borderColor = 'transparent';
                                        }
                                    }}
                                >
                                    {/* Connection Line */}
                                    {idx !== historyData.length - 1 && (
                                        <div className="absolute left-[19px] top-10 bottom-[-14px] w-[1px] pointer-events-none" style={{ background: 'var(--border)' }}></div>
                                    )}

                                    <div className="flex items-start gap-3">
                                        {/* Status Dot / Icon Container */}
                                        <div className="mt-1 relative flex-shrink-0 z-10" style={{ background: 'var(--bg-card)' }}>
                                            <div className={`h-3 w-3 rounded-full ${h.hasProfileChange ? 'bg-amber-500 shadow-amber-500/50' :
                                                (h.hasMembershipChange ? 'bg-indigo-500 shadow-indigo-500/50' : 'bg-blue-500 shadow-blue-500/50')
                                                } shadow-md`}></div>
                                        </div>

                                        <div className="flex-1 min-w-0">
                                            <div className="flex justify-between items-center mb-1">
                                                <span className="text-xs font-bold uppercase tracking-wider truncate mr-2" style={{ color: isSelected ? 'var(--accent)' : 'var(--text-secondary)' }}>
                                                    {h.operation}
                                                </span>
                                            </div>

                                            {/* Change Type Icons */}
                                            <div className="flex gap-1.5 mb-2">
                                                {h.hasProfileChange && (
                                                    <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-900 text-amber-200 border border-amber-500/20" title="Profile Changed">
                                                        <svg className="w-3 h-3 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                                                        </svg>
                                                        Profile
                                                    </span>
                                                )}
                                                {h.hasMembershipChange && (
                                                    <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-indigo-900 text-indigo-200 border border-indigo-500/20" title="Memberships Changed">
                                                        <svg className="w-3 h-3 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                                                        </svg>
                                                        Groups
                                                    </span>
                                                )}
                                                {h.hasAvatarChange && (
                                                    <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-purple-900 text-purple-200 border border-purple-500/20" title="Avatar Changed">
                                                        <svg className="w-3 h-3 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                                                        </svg>
                                                        Photo
                                                    </span>
                                                )}
                                            </div>

                                            {/* Membership Diffs Summary */}
                                            {h.membershipDiff && (
                                                <div className="mt-2 flex flex-wrap gap-2">
                                                    {h.membershipDiff.joined?.length > 0 && (
                                                        <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-green-900 text-green-200 border border-green-500/20 shadow-sm shadow-green-900/20">
                                                            <svg className="w-3 h-3 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                                                            </svg>
                                                            Joined: {h.membershipDiff.joined.length}
                                                        </span>
                                                    )}
                                                    {h.membershipDiff.left?.length > 0 && (
                                                        <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-red-900 text-red-200 border border-red-500/20 shadow-sm shadow-red-900/20">
                                                            <svg className="w-3 h-3 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
                                                            </svg>
                                                            Left: {h.membershipDiff.left.length}
                                                        </span>
                                                    )}
                                                    {h.membershipDiff.roleChanged?.length > 0 && (
                                                        <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-amber-900 text-amber-200 border border-amber-500/20 shadow-sm shadow-amber-900/20">
                                                            <svg className="w-3 h-3 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                                                            </svg>
                                                            Roles: {h.membershipDiff.roleChanged.length}
                                                        </span>
                                                    )}
                                                </div>
                                            )}

                                            {/* Groups count for Photo Update events */}
                                            {h.hasAvatarChange && !h.hasMembershipChange && (() => {
                                                const groupCount = h.currentData?.groupMemberships?.length || 0;
                                                if (groupCount === 0) return null;
                                                return (
                                                    <div className="mt-2 flex flex-wrap gap-2">
                                                        <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-900 text-indigo-200 border border-indigo-500/20">
                                                            <svg className="w-3 h-3 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                                                            </svg>
                                                            In {groupCount} group{groupCount !== 1 ? 's' : ''}
                                                        </span>
                                                    </div>
                                                );
                                            })()}

                                            {/* Export Date (Primary) */}
                                            {(() => {
                                                const exportTs = h.currentData?.exportTimestamp || h.currentData?.export_timestamp || h.prevData?.exportTimestamp || h.prevData?.export_timestamp || h?.exportTimestamp || h?.historyDate;
                                                if (exportTs) {
                                                    let exportDate;
                                                    if (typeof exportTs === 'string' && exportTs.includes('-')) {
                                                        exportDate = new Date(exportTs);
                                                    } else {
                                                        const num = Number(exportTs);
                                                        exportDate = new Date(num * (String(num).length > 10 ? 1 : 1000));
                                                    }

                                                    if (!isNaN(exportDate.getTime())) {
                                                        return (
                                                            <div className="text-sm font-medium truncate mb-0.5" style={{ color: 'var(--text-primary)' }}>
                                                                <span className="opacity-75 text-xs mr-1" style={{ color: 'var(--text-secondary)' }}>Export:</span>
                                                                {exportDate.toLocaleDateString()} {exportDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                                            </div>
                                                        );
                                                    }
                                                }
                                                return <div className="text-sm italic" style={{ color: 'var(--text-tertiary)' }}>No Export Date</div>
                                            })()}
                                        </div>

                                        {isSelected && (
                                            <svg className="w-4 h-4 mt-1" style={{ color: 'var(--accent)' }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                            </svg>
                                        )}
                                    </div>
                                </div>
                            );
                        })}
                        {historyData.length < historyTotalCount && (
                            <div ref={loadMoreRef} className="pt-2 pb-6 px-2 text-center h-16 flex items-center justify-center">
                                {loadingMore ? (
                                    <div className="flex items-center justify-center gap-2 text-xs font-bold uppercase" style={{ color: 'var(--accent)' }}>
                                        <div className="w-4 h-4 border-2 border-t-transparent rounded-full animate-spin" style={{ borderColor: 'var(--accent)', borderTopColor: 'transparent' }}></div>
                                        Fetching More...
                                    </div>
                                ) : (
                                    <span className="text-xs italic" style={{ color: 'var(--text-tertiary)' }}>Scroll for more history</span>
                                )}
                            </div>
                        )}
                    </div>
                </div>

                {/* Right Pane: Profile Preview */}
                <div className="flex-1 overflow-y-auto custom-scrollbar h-full min-h-0" style={{ background: 'var(--bg-page)' }}>
                    {viewingHistoryItem ? (
                        <div className="p-6">
                            {(() => {
                                const sortedHistory = [...historyData].sort((a, b) => b.historyDate - a.historyDate);
                                const currentIndex = sortedHistory.findIndex(h => h.historyId === viewingHistoryItem.historyId);
                                const prevItem = currentIndex >= 0 && currentIndex < sortedHistory.length - 1
                                    ? sortedHistory[currentIndex + 1]
                                    : null;

                                const currentProfile = mapHistoryToProfile(viewingHistoryItem);
                                const prevProfile = prevItem
                                    ? mapHistoryToProfile(prevItem)
                                    : null;

                                const changedFields = getChangedFields(currentProfile, prevProfile);
                                const addedGroupIds = getAddedGroups(currentProfile, prevProfile); // Works for users
                                const leftGroups = getLeftGroups(currentProfile, prevProfile);     // Works for users

                                return renderProfileView(currentProfile, changedFields, addedGroupIds, leftGroups, prevProfile);
                            })()}
                        </div>
                    ) : (
                        <div className="flex flex-col items-center justify-center h-full opacity-50" style={{ color: 'var(--text-secondary)' }}>
                            <svg className="w-16 h-16 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            <p className="text-lg">Select a version to view details</p>
                        </div>
                    )}
                </div>
                </div>
            </>
        );
    };

    const fetchDetails = async () => {
        setLoading(true);
        setError(null);
        try {
            const endpoint = type === 'user' ? '/users/details' : '/groups/details';
            const payload = type === 'user' ? { serviceId: String(id) } : { groupId: String(id) };
            const response = await apiClient.post(endpoint, payload);

            // Normalize data if it's a user to ensure technical fields show up
            const rawData = response.data;
            if (type === 'user' && rawData) {
                setData(normalizeProfileData(rawData));
            } else {
                setData(rawData);
            }

        } catch (err) {
            console.error("Failed to fetch details", err);
            setError("Failed to load details. Please try again.");
        } finally {
            setLoading(false);
        }
    };

    // Helper to normalize snake_case DB fields to camelCase for the UI
    const normalizeProfileData = (raw) => {
        if (!raw) return raw;
        return {
            ...raw,
            // Ensure technical fields are available in camelCase
            lastUpdatedJobId: raw.lastUpdatedJobId || raw.last_updated_job_id,
            snapshotHash: raw.snapshotHash || raw.snapshot_hash,
            profileLastFetchedAt: raw.profileLastFetchedAt || raw.profile_last_fetched_at,
            serviceId: raw.serviceId || raw.service_id,

            // Ensure standard profile fields are also normalized for consistency
            profileName: raw.profileName || raw.profile_name,
            profileFamilyName: raw.profileFamilyName || raw.profile_family_name,
            profileFullName: raw.profileFullName || raw.profile_full_name,
            isAdmin: raw.isAdmin || raw.is_admin,
            avatarId: raw.avatarId || raw.avatar_id,
            remoteAvatarUrl: raw.remoteAvatarUrl || raw.remote_avatar_url,
        };
    };

    const fetchHistory = async () => {
        setHistoryLoading(true);
        setTimelineOffset(0); // Reset offset on new fetch
        try {
            if (type === 'user') {
                // Parallel fetch of granular data (switch to POST as requested)
                const payload = { serviceId: String(id) };

                const [timelineRes, profilesRes, membershipsRes] = await Promise.all([
                    apiClient.post(`/users/timeline`, { ...payload, limit: 10, offset: 0 }),
                    apiClient.post(`/users/history/profile`, payload),
                    apiClient.post(`/users/history/memberships`, payload)
                ]);

                const timelineData = timelineRes.data || {};
                const timeline = Array.isArray(timelineData) ? timelineData : (timelineData.items || []);
                setHistoryTotalCount(timelineData.total || timeline.length);
                const profiles = profilesRes.data || [];
                const memberships = membershipsRes.data || [];

                // Reconstruct the unified history view on the Client Side
                // Sort timeline by date
                timeline.sort((a, b) => b.exportTimestamp - a.exportTimestamp);

                const constructedHistory = timeline.map(event => {
                    const ts = event.exportTimestamp;

                    // 1. Find Profile Snapshot (Find largest timelineId <= event.timelineId)
                    const profileSnapshot = [...profiles]
                        .sort((a, b) => b.timelineId - a.timelineId)
                        .find(p => p.timelineId <= event.timelineId) || {};

                    // 2. Find Active Memberships at this timestamp
                    // SCD2: validFrom <= ts < validTo (or validTo is null)
                    const activeMemberships = memberships.filter(m => {
                        const from = m.validFrom;
                        const to = m.validTo;
                        return (from <= ts) && (!to || to > ts);
                    });

                    // 3. Construct the "currentData" object to match what UI expects
                    // UI expects: { ...profileFields, groupMemberships: [...] }
                    const currentData = {
                        ...profileSnapshot,
                        exportTimestamp: ts,
                        groupMemberships: activeMemberships.map(m => ({
                            id: m.groupId, // Use groupId as ID
                            groupId: m.groupId,
                            groupName: m.groupName,
                            role: m.role,
                            // Add other fields if available in membership history
                        }))
                    };

                    // Construct meaningful operation label
                    let opLabel = 'System Snapshot';
                    if (event.hasProfileChange && event.hasMembershipChange) opLabel = 'Full Update';
                    else if (event.hasProfileChange) opLabel = 'Profile Update';
                    else if (event.hasMembershipChange) opLabel = 'Groups Update';
                    else if (event.hasAvatarChange) opLabel = 'Photo Update';

                    return {
                        historyId: event.timelineId,
                        historyDate: ts,
                        operation: opLabel,
                        currentData: currentData,
                        hasProfileChange: event.hasProfileChange,
                        hasMembershipChange: event.hasMembershipChange,
                        hasAvatarChange: event.hasAvatarChange
                    };
                });

                setHistoryData(constructedHistory);

            } else if (type === 'group') {
                // Parallel Fetch for Group Timeline
                const [timelineRes, detailsRes] = await Promise.all([
                    // Ensure idempotency / payload match
                    apiClient.post('/groups/timeline', { groupId: String(id), limit: 10, offset: 0 }),
                    apiClient.post('/groups/history', { groupId: String(id) })
                ]);

                const timelineData = timelineRes.data || {};
                const timelineEvents = Array.isArray(timelineData) ? timelineData : (timelineData.items || []);
                setHistoryTotalCount(timelineData.total || timelineEvents.length);
                const detailsHistory = detailsRes.data || [];

                // Construct History
                const constructedHistory = timelineEvents.map(event => {
                    const ts = event.exportTimestamp;

                    // 1. Find Detail Snapshot (if detail changed)
                    // The API '/groups/history' returns list of GroupHistory.
                    const snapshot = [...detailsHistory]
                        .sort((a, b) => b.timelineId - a.timelineId)
                        .find(d => d.timelineId <= event.timelineId) || {};

                    let opLabel = 'Snapshot';
                    if (event.hasDetailChange && event.hasMembershipChange) opLabel = 'Full Update';
                    else if (event.hasDetailChange) opLabel = 'Details Update';
                    else if (event.hasMembershipChange) opLabel = 'Members Update';

                    return {
                        historyId: event.timelineId, // Unique ID for the row
                        historyDate: ts,
                        exportTimestamp: ts,
                        operation: opLabel,
                        currentData: {
                            ...snapshot.currentData, // Merge the detail data
                            exportTimestamp: ts, // Ensure it's inside currentData too for consistency
                            // We don't have memberships here yet, they are fetched on demand
                        },
                        hasDetailChange: event.hasDetailChange,
                        hasMembershipChange: event.hasMembershipChange,
                        membershipDiff: event.membershipDiff,
                        _isHistorical: true
                    };
                });

                setHistoryData(constructedHistory);
            }

        } catch (err) {
            console.error("Failed to fetch history", err);
            // Non-blocking error for history
        } finally {
            setHistoryLoading(false);
        }
    };

    // --- GROUP HISTORY DETAIL LOGIC ---
    const [groupStats, setGroupStats] = useState(null);
    const [loadingGroupStats, setLoadingGroupStats] = useState(false);

    useEffect(() => {
        if (type === 'group' && viewingHistoryItem && viewingHistoryItem.historyDate) {
            fetchGroupStats(viewingHistoryItem.historyDate);
        } else {
            setGroupStats(null);
        }
    }, [viewingHistoryItem, type]);

    const fetchGroupStats = async (timestamp) => {
        setLoadingGroupStats(true);
        try {
            const res = await apiClient.post('/groups/history-members', {
                groupId: String(id),
                timestamp: Number(timestamp)
            });
            const members = res.data || [];
            // Calculate stats
            const total = members.length;
            const admins = members.filter(m => m.isAdmin || m.role?.toLowerCase() === 'admin').length;
            setGroupStats({ total, admins, members });
        } catch (err) {
            console.error("Failed to fetch group stats", err);
        } finally {
            setLoadingGroupStats(false);
        }
    };


    

    const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

    if (!isOpen) return null;

    const mapHistoryToProfile = (historyItem) => {
        const raw = historyItem.currentData || {};

        if (type === 'group') {
            // Mapping for Group History
            return {
                ...raw, // Start with raw data

                // Essential Fields
                groupId: raw.groupId || raw.group_id,
                groupName: raw.groupName || raw.group_name || raw.title,
                numberOfMembers: raw.numberOfMembers || raw.number_of_members,
                retentionPeriod: raw.retentionPeriod || raw.retention_period,
                publicParams: raw.publicParams || raw.public_params,
                adminApprovalRequired: raw.adminApprovalRequired || raw.admin_approval_required,
                groupLink: raw.groupLink || raw.group_link,
                reconstructedLink: raw.reconstructedLink || raw.reconstructed_link,
                description: raw.description,

                // Members list: If we are viewing this specific history item, use the fetched historical members
                members: (viewingHistoryItem?.historyId === historyItem.historyId && groupStats?.members)
                    ? groupStats.members
                    : [],
                // Note: For "Previous Profile" comparison, "members" diffing might be tricky without fetching members for previous too.
                // For now, we focus on showing the current selected history members.

                groupMemberships: [], // Groups don't have memberships in other groups typically

                // Flags
                _isHistorical: true,
                _historyDate: historyItem.historyDate,
                membershipDiff: historyItem.membershipDiff,
            };
        }

        // --- User History Mapping (Existing Logic) ---
        let groups = [];
        // If groupMemberships is already an array (from new frontend logic), use it directly
        if (Array.isArray(raw.groupMemberships)) {
            groups = raw.groupMemberships;
        } else if (raw.group_memberships) {
            try {
                // DB stores it as JSON string or sometimes list if already parsed by ingestion? 
                // Ingestion models say "Text", so it is string.
                const parsed = typeof raw.group_memberships === 'string'
                    ? JSON.parse(raw.group_memberships)
                    : raw.group_memberships;

                if (Array.isArray(parsed)) {
                    groups = parsed.map(g => ({
                        id: g.id || g.group_id,      // Ensure we have an ID for clicking
                        groupId: g.group_id || g.groupId,
                        groupName: g.group_name || g.groupName || g.title,
                        title: g.group_name || g.groupName || g.title,
                        description: g.description,
                        memberCount: g.number_of_members || g.memberCount,
                        role: g.role
                    }));
                }
            } catch (e) {
                console.warn("Failed to parse history groups", e);
            }
        }

        // Map snake_case DB fields to CamelCase UI DTO (Matching user_controller.py get_user)
        // SUPPORT BOTH snake_case (Old API) and CamelCase (New API)
        return {
            id: raw.id,
            serviceId: raw.service_id || raw.serviceId,
            e164: raw.e164,
            profileName: raw.profile_name || raw.profileName,
            name: raw.name,
            profileFamilyName: raw.profile_family_name || raw.profileFamilyName,
            profileFullName: raw.profile_full_name || raw.profileFullName,
            about: raw.about,
            isAdmin: raw.is_admin || raw.isAdmin,
            avatarId: raw.avatar_id || raw.avatarId,
            remoteAvatarUrl: raw.remote_avatar_url || raw.remoteAvatarUrl,
            exportTimestamp: (raw.exportTimestamp || raw.export_timestamp)
                ? (typeof (raw.exportTimestamp || raw.export_timestamp) === 'string'
                    ? new Date(raw.exportTimestamp || raw.export_timestamp).getTime() / 1000
                    : (raw.exportTimestamp || raw.export_timestamp))
                : null,
            activeAt: raw.active_at || raw.activeAt,
            capabilities: raw.capabilities,

            // Critical: Normalized groups
            groupMemberships: groups,

            // Flags
            _isHistorical: true,
            _historyDate: historyItem.historyDate,

            // Extra Technical Details
            profileLastFetchedAt: raw.profileLastFetchedAt,
            lastUpdatedJobId: raw.lastUpdatedJobId,
            snapshotHash: raw.snapshotHash
        };
    };

    const getChangedFields = (current, previous) => {
        if (!previous) {
            // Treat all non-internal fields as changed if there is no previous history
            return Object.keys(current).filter(k => !k.startsWith('_'));
        }
        const changes = [];
        const keys = Object.keys(current);

        keys.forEach(key => {
            if (key.startsWith('_')) return; // Ignore internal flags
            if (key === 'groupMemberships') {
                // Simple length check or JSON string comparison for now
                // A deep set comparison would be better but expensive
                if (JSON.stringify(current[key]) !== JSON.stringify(previous[key])) {
                    changes.push(key);
                }
                return;
            }

            // Simple equality check
            if (current[key] !== previous[key]) {
                changes.push(key);
            }
        });
        return changes;
    };

    const getAddedGroups = (current, previous) => {
        if (!previous || !previous.groupMemberships) {
            return (current.groupMemberships || []).map(g => g.groupId || g.id);
        }
        const prevIds = new Set(previous.groupMemberships.map(g => g.groupId || g.id));
        return current.groupMemberships
            .filter(g => !prevIds.has(g.groupId || g.id))
            .map(g => g.groupId || g.id);
    };

    const getLeftGroups = (current, previous) => {
        if (!previous || !previous.groupMemberships) return [];
        if (!current || !current.groupMemberships) return previous.groupMemberships;

        const currIds = new Set(current.groupMemberships.map(g => g.groupId || g.id));
        return previous.groupMemberships.filter(g => !currIds.has(g.groupId || g.id));
    };

    const renderGroupMembers = (members, options = {}) => {
        const { diff = {}, isLeftList = false } = options;
        if (!members || !members.length) return <div className="text-sm" style={{ color: 'var(--text-secondary)' }}>No members found.</div>;

        // Sort: Joined > Role Changed > Others (Only if not Left list)
        // If Left list, maybe sort by name?
        let displayMembers = [...members];
        if (!isLeftList && (diff.joined?.length || diff.roleChanged?.length)) {
            const joinedIds = new Set((diff.joined || []).map(u => u.serviceId));
            const roleChangedIds = new Set((diff.roleChanged || []).map(u => u.serviceId));

            displayMembers.sort((a, b) => {
                const aJoined = joinedIds.has(a.serviceId);
                const bJoined = joinedIds.has(b.serviceId);
                if (aJoined && !bJoined) return -1;
                if (!aJoined && bJoined) return 1;

                const aRole = roleChangedIds.has(a.serviceId);
                const bRole = roleChangedIds.has(b.serviceId);
                if (aRole && !bRole) return -1;
                if (!aRole && bRole) return 1;

                return 0;
            });
        }

        const joinedSet = new Set((diff.joined || []).map(u => u.serviceId));
        const roleChangedSet = new Set((diff.roleChanged || []).map(u => u.serviceId));
        const leftSet = new Set((diff.left || []).map(u => u.serviceId));

        return (
            <div className="space-y-2">
                {displayMembers.map((member, idx) => {
                    const isJoined = !isLeftList && joinedSet.has(member.serviceId);
                    const isRoleChanged = !isLeftList && roleChangedSet.has(member.serviceId);
                    const isLeft = isLeftList; // All in this list are left

                    let borderColor = 'border-transparent';
                    let cardBackground = 'var(--bg-page)';
                    let hoverBackground = 'var(--bg-hover)';

                    if (isJoined) {
                        borderColor = 'border-green-500/40';
                        cardBackground = 'color-mix(in srgb, var(--success) 10%, var(--bg-card))';
                        hoverBackground = 'color-mix(in srgb, var(--success) 14%, var(--bg-card))';
                    } else if (isLeft) {
                        borderColor = 'border-red-500/40';
                        cardBackground = 'color-mix(in srgb, var(--danger) 10%, var(--bg-card))';
                        hoverBackground = 'color-mix(in srgb, var(--danger) 14%, var(--bg-card))';
                    } else if (isRoleChanged) {
                        borderColor = 'border-amber-500/40';
                        cardBackground = 'color-mix(in srgb, var(--warning) 12%, var(--bg-card))';
                        hoverBackground = 'color-mix(in srgb, var(--warning) 16%, var(--bg-card))';
                    }

                    return (
                        <div
                            key={`${member.serviceId}-${idx}`}
                            className={`flex items-center justify-between p-2 rounded-lg cursor-pointer transition-colors border ${borderColor}`}
                            style={{ background: cardBackground }}
                            onClick={() => onDrillDown && onDrillDown('user', member.serviceId)}
                            onMouseEnter={(e) => { e.currentTarget.style.background = hoverBackground; }}
                            onMouseLeave={(e) => { e.currentTarget.style.background = cardBackground; }}
                        >
                            <div className="flex items-center space-x-3 overflow-hidden">
                                <div className={`h-8 w-8 rounded-full flex-shrink-0 flex items-center justify-center text-xs font-bold text-white border-2 ${isJoined ? 'border-green-500 bg-green-900' : isLeft ? 'border-red-500 bg-red-900' : isRoleChanged ? 'border-amber-500 bg-amber-900' : 'border-gray-700 bg-gray-800'}`}>
                                    {(member.name || member.profileName || member.profileFullName || member.profileFamilyName || "?")[0]?.toUpperCase()}
                                </div>
                                <div className="min-w-0">
                                    <div className="text-sm font-medium truncate flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
                                        {member.name || member.profileName || member.profileFullName || member.profileFamilyName || (member.serviceId ? `User (${member.serviceId.substring(0, 8)}...)` : <span className="opacity-50">Unknown</span>)}
                                        {isJoined && <span className="text-[9px] bg-green-500 text-white px-1 rounded uppercase font-bold">New</span>}
                                        {isLeft && <span className="text-[9px] bg-red-500 text-white px-1 rounded uppercase font-bold">Left</span>}
                                    </div>
                                    <div className="text-xs font-mono truncate" style={{ color: 'var(--text-secondary)' }}>
                                        {member.role}
                                        {isRoleChanged && <span className="text-amber-400 ml-1">(Role Changed)</span>}
                                    </div>
                                </div>
                            </div>
                            <div className="text-xs ml-2 whitespace-nowrap" style={{ color: 'var(--accent)' }}>View</div>
                        </div>
                    );
                })}
            </div>
        );
    };

    const formatDate = (val) => {
        if (!val) return 'N/A';
        if (typeof val === 'number') {
            // Heuristic: If > 100 billion, assume milliseconds (valid for years 1973-5138)
            // Otherwise assume seconds
            const multiplier = val > 100000000000 ? 1 : 1000;
            return new Date(val * multiplier).toLocaleString();
        }
        return new Date(val).toLocaleString();
    };

    const isDateField = (key) => {
        const lower = key.toLowerCase();
        // Explicitly exclude IDs that might contain "date" or "time" text
        if (lower.includes('jobid') || (lower.endsWith('id') && !lower.includes('storage'))) return false;

        return lower.includes('time') ||
            lower.includes('date') ||
            lower.includes('expiration') ||
            lower === 'activeat' ||
            boxProfileLastFetched(lower);
    };

    const boxProfileLastFetched = (k) => k.includes('profilelastfetched');

    // Fields to ignore in the UI mostly internal ids
    const IGNORED_FIELDS = ['historyId', 'historyDate', 'operation', 'previousData', 'currentData', 'id', '_isHistorical', '_historyDate'];

    // Friendly names for fields
    const FIELD_LABELS = {
        'name': 'Name',
        'profileName': 'Profile Name',
        'about': 'About',
        'e164': 'Phone Number',
        'groupMemberships': 'Group Memberships',
        'isAdmin': 'Admin Status',
        'remoteAvatarUrl': 'Profile Picture',
        'group_name': 'Group Name',
        'description': 'Description',
        'group_link': 'Group Link',
        'number_of_members': 'Member Count',
        'active_at': 'Last Active At',
        // CamelCase DTO mappings
        'groupId': 'Group ID',
        'groupName': 'Group Name',
        'numberOfMembers': 'Member Count',
        'groupLink': 'Join Link',
        'reconstructedLink': 'Reconstructed Link',
        'adminApprovalRequired': 'Access Type',
        'retentionPeriod': 'Retention Period',
        'publicParams': 'Public Params',
        // Extra Details
        'profileLastFetchedAt': 'Profile Last Fetched',
        'lastUpdatedJobId': 'Last Job ID',
        'snapshotHash': 'Snapshot Hash',
        'serviceId': 'Service ID',
    };

    const calculateFriendlyDiff = (prev, curr) => {
        if (!prev) prev = {};
        if (!curr) curr = {};
        const changes = [];
        const allKeys = new Set([...Object.keys(prev), ...Object.keys(curr)]);

        // Special handling for Group Memberships
        if (allKeys.has('groupMemberships') || allKeys.has('group_memberships')) {
            const key = allKeys.has('groupMemberships') ? 'groupMemberships' : 'group_memberships';
            const prevGroups = parseGroups(prev[key]);
            const currGroups = parseGroups(curr[key]);

            const prevIds = new Set(prevGroups.map(g => g.id));
            const currIds = new Set(currGroups.map(g => g.id));

            currGroups.forEach(g => {
                if (!prevIds.has(g.id)) {
                    changes.push({ type: 'GROUP_ADDED', label: 'Joined Group', value: g.groupName || g.title || "Unknown Group", icon: 'users-plus' });
                }
            });
            prevGroups.forEach(g => {
                if (!currIds.has(g.id)) {
                    changes.push({ type: 'GROUP_REMOVED', label: 'Left Group', value: g.groupName || g.title || "Unknown Group", icon: 'users-minus' });
                }
            });
            allKeys.delete(key);
        }

        // Processing other fields
        allKeys.forEach(key => {
            if (IGNORED_FIELDS.includes(key)) return;

            const oldVal = prev[key];
            const newVal = curr[key];

            if (JSON.stringify(oldVal) !== JSON.stringify(newVal)) {
                let formattedOld = formatValue(key, oldVal);
                let formattedNew = formatValue(key, newVal);
                const label = FIELD_LABELS[key] || key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());

                if (key === 'remoteAvatarUrl' || key === 'remote_avatar_url' || key === 'avatarId' || key === 'avatar_id') {
                    // Dedup avatar changes if both ID and URL change
                    if (!changes.some(c => c.type === 'AVATAR_CHANGED')) {
                        changes.push({ type: 'AVATAR_CHANGED', label: 'Profile Picture', icon: 'photo' });
                    }
                } else if ((oldVal === null || oldVal === undefined || oldVal === '') && newVal) {
                    changes.push({ type: 'ADDED', label: label, value: formattedNew, icon: 'plus' });
                } else if (oldVal && (newVal === null || newVal === undefined || newVal === '')) {
                    changes.push({ type: 'REMOVED', label: label, value: formattedOld, icon: 'minus' });
                } else {
                    changes.push({ type: 'MODIFIED', label: label, oldValue: formattedOld, newValue: formattedNew, icon: 'pencil' });
                }
            }
        });

        return changes;
    };

    const parseGroups = (val) => {
        if (!val) return [];
        if (Array.isArray(val)) return val;
        try { return JSON.parse(val); } catch (e) { return []; }
    };

    const formatValue = (key, val) => {
        if (val === null || val === undefined) return 'Empty';
        if (key === 'adminApprovalRequired') return val ? 'Approval Required' : 'Open';
        if (typeof val === 'boolean') return val ? 'True' : 'False';
        if (isDateField(key)) return formatDate(val);
        return String(val);
    };

    // Helper to render the main profile view (used for both current and historical)
    const renderProfileView = (profileData, changedFields = [], addedGroupIds = [], leftGroups = [], prevProfileData = null) => {

        const toggleSection = (sec) => {
            setExpandedSections(prev => ({ ...prev, [sec]: !prev[sec] }));
        };

        const TECHNICAL_FIELDS = type === 'group'
            ? ['groupId', 'retentionPeriod', 'publicParams', 'adminApprovalRequired', 'groupLink']
            : [
                'lastUpdatedJobId', 'snapshotHash', 'profileLastFetchedAt', 'serviceId'
            ];

        const FULL_WIDTH_FIELDS = ['description', 'reconstructedLink', 'reconstructed_link', 'about', 'secretParams', 'secret_params', 'publicParams', 'public_params'];
        const SECRET_FIELDS = ['secretParams', 'secret_params'];
        const LINK_FIELDS = ['reconstructedLink', 'reconstructed_link'];
        const MONO_COPY_FIELDS = ['masterKey', 'master_key', 'inviteLinkPassword', 'invite_link_password'];

        return (
            <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                {profileData._isHistorical && (
                    <div className="flex items-center gap-2">
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full" style={{ fontSize: '11px', fontWeight: 500, background: 'rgba(245,166,35,0.15)', color: 'var(--warning)', border: '1px solid rgba(245,166,35,0.3)' }}>
                            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                            Snapshot: {new Date(profileData._historyDate * 1000).toLocaleString()}
                        </span>
                    </div>
                )}

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '16px' }}>
                    {Object.entries(profileData).map(([key, value]) => {
                        if (key === 'members' || key === 'avatarId' || key === 'remoteAvatarUrl') return null;
                        if (value === null || value === undefined || value === "") return null;
                        if (key.startsWith('_') || TECHNICAL_FIELDS.includes(key)) return null;
                        if (key === 'groupMemberships' || key === 'membershipDiff') return null;

                        // Capabilities object → readable flag pills
                        if (key === 'capabilities' && value && typeof value === 'object' && !Array.isArray(value)) {
                            const flags = Object.entries(value).filter(([, v]) => v === true || v === 1);
                            if (flags.length === 0) return null;
                            return (
                                <div key={key} style={{ gridColumn: '1 / -1' }}>
                                    <label className="block" style={{ fontSize: '9px', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.8px', color: 'var(--text-secondary)', marginBottom: '8px' }}>Capabilities</label>
                                    <div className="flex flex-wrap gap-1.5">
                                        {flags.map(([flag]) => (
                                            <span key={flag} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium" style={{ background: 'var(--success-bg)', color: 'var(--success)', border: '1px solid color-mix(in srgb, var(--success) 30%, transparent)' }}>
                                                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" /></svg>
                                                {flag.replace(/([A-Z])/g, ' $1').trim()}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            );
                        }

                        // Skip other unhandled objects to avoid [object Object]
                        if (typeof value === 'object' && !Array.isArray(value)) return null;

                        const isChanged = changedFields.includes(key);
                        const label = FIELD_LABELS[key] || key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                        const isFullWidth = FULL_WIDTH_FIELDS.includes(key) || typeof value === 'object' || String(value).length > 50;
                        const isSecret = SECRET_FIELDS.includes(key);
                        const isLink = LINK_FIELDS.includes(key);
                        const isMonoCopy = MONO_COPY_FIELDS.includes(key);

                        if (isSecret) {
                            return (
                                <div key={key} style={{ gridColumn: '1 / -1' }}>
                                    <div className="flex items-center justify-between" style={{ marginBottom: expandedSections.secretParams ? '8px' : '0' }}>
                                        <label style={{ fontSize: '9px', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.8px', color: 'var(--text-secondary)' }}>{label}</label>
                                        <button onClick={() => setExpandedSections(prev => ({ ...prev, secretParams: !prev.secretParams }))} style={{ fontSize: '10px', fontWeight: 500, color: 'var(--accent)', background: 'none', border: 'none', cursor: 'pointer', padding: '2px 6px' }}>
                                            {expandedSections.secretParams ? 'Hide' : 'Show'}
                                        </button>
                                    </div>
                                    {expandedSections.secretParams && (
                                        <div className="custom-scrollbar" style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '10px', color: 'var(--text-tertiary)', background: 'var(--bg-page)', padding: '12px', borderRadius: '6px', maxHeight: '80px', overflowY: 'auto', wordBreak: 'break-all' }}>
                                            {String(value)}
                                        </div>
                                    )}
                                </div>
                            );
                        }

                        return (
                            <div key={key} style={isFullWidth ? { gridColumn: '1 / -1' } : undefined}>
                                <label className="block" style={{ fontSize: '9px', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.8px', color: isChanged ? 'var(--warning)' : 'var(--text-secondary)', marginBottom: '4px' }}>
                                    {label}
                                    {isChanged && <span style={{ marginLeft: '8px', fontSize: '9px', background: 'rgba(245,166,35,0.15)', color: 'var(--warning)', padding: '1px 6px', borderRadius: '4px' }}>CHANGED</span>}
                                </label>
                                <div className="break-words" style={{ fontSize: '14px', fontWeight: 400, color: 'var(--text-primary)' }}>
                                    {isLink ? (
                                        <a href={String(value)} target="_blank" rel="noopener noreferrer" className="hover:underline" style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '12px', color: 'var(--accent)', textDecoration: 'none' }}>{String(value)}</a>
                                    ) : isMonoCopy ? (
                                        <span className="inline-flex items-center gap-2 cursor-pointer" onClick={() => navigator.clipboard.writeText(String(value))}>
                                            <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '12px' }}>{String(value)}</span>
                                            <svg className="w-3.5 h-3.5" style={{ color: 'var(--text-tertiary)' }} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
                                        </span>
                                    ) : typeof value === 'boolean' ? (value ? 'Yes' : 'No') :
                                        isDateField(key) ? formatDate(value) : String(value)}

                                    {isChanged && prevProfileData && prevProfileData[key] !== undefined && (
                                        <div className="mt-1 flex items-center gap-2" style={{ fontSize: '12px', opacity: 0.7 }}>
                                            <span className="line-through" style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--danger)' }}>
                                                {typeof prevProfileData[key] === 'boolean' ? (prevProfileData[key] ? 'Yes' : 'No') :
                                                    isDateField(key) ? formatDate(prevProfileData[key]) : String(prevProfileData[key] || 'Empty')}
                                            </span>
                                            <svg className="w-3 h-3" style={{ color: 'var(--text-tertiary)' }} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" /></svg>
                                        </div>
                                    )}
                                </div>
                            </div>
                        );
                    })}
                </div>

                {/* Extra Details Accordion */}
                {TECHNICAL_FIELDS.some(k => profileData[k] != null && profileData[k] !== '') && (
                    <div className="rounded-lg overflow-hidden" style={{ marginTop: '16px', background: 'var(--bg-card)', border: '0.5px solid var(--border)' }}>
                        <div
                            className="flex justify-between items-center cursor-pointer transition-colors"
                            style={{ padding: '10px 16px' }}
                            onClick={() => toggleSection('extra')}
                            onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-hover)'}
                            onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                        >
                            <div className="flex items-center gap-2">
                                <span style={{ fontSize: '11px', fontWeight: 500, textTransform: 'uppercase', color: 'var(--text-secondary)' }}>Extra Details</span>
                                <span style={{ fontSize: '9px', padding: '2px 6px', borderRadius: '4px', background: 'var(--bg-accent-muted)', color: 'var(--accent)' }}>
                                    {TECHNICAL_FIELDS.filter(k => profileData[k] != null && profileData[k] !== '').length} items
                                </span>
                            </div>
                            <svg className={`transition-transform ${expandedSections.extra ? 'rotate-180' : ''}`} style={{ width: '14px', height: '14px', color: 'var(--text-secondary)' }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                            </svg>
                        </div>
                        {expandedSections.extra && (
                            <div style={{ padding: '16px', borderTop: '0.5px solid var(--border)' }}>
                                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                                    {TECHNICAL_FIELDS.map(key => {
                                        const val = profileData[key];
                                        if (val === null || val === undefined || val === '') return null;

                                        const isChanged = changedFields.includes(key);
                                        const label = FIELD_LABELS[key] || key;
                                        const formattedValue = isDateField(key) ? formatDate(val) : String(val);

                                        return (
                                            <div key={key} className="rounded" style={{ background: 'var(--bg-page)', padding: '12px', border: isChanged ? '0.5px solid var(--warning)' : '0.5px solid var(--border)', borderRadius: '6px' }}>
                                                <div className="flex justify-between" style={{ fontSize: '9px', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.8px', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                                                    {label}
                                                    {isChanged && <span style={{ color: 'var(--warning)', fontSize: '9px' }}>CHANGED</span>}
                                                </div>
                                                <div className="break-all" style={{ fontSize: '12px', fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-primary)' }}>{formattedValue}</div>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        )}
                    </div>
                )}

                {/* Photo Changed Banner */}
                {type === 'user' && (changedFields.includes('avatarId') || changedFields.includes('remoteAvatarUrl')) && (
                    <div className="flex items-center gap-2.5 px-3 py-2 rounded-lg" style={{ background: 'rgba(168,85,247,0.1)', border: '1px solid rgba(168,85,247,0.25)' }}>
                        <svg className="w-4 h-4 flex-shrink-0" style={{ color: 'rgb(216,180,254)' }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                        </svg>
                        <span style={{ fontSize: '12px', fontWeight: 500, color: 'rgb(216,180,254)' }}>Profile picture changed at this snapshot</span>
                    </div>
                )}

                {/* Group Memberships for User History */}
                {type === 'user' && profileData._isHistorical && (
                    <div className="mt-2">
                        {profileData.groupMemberships && profileData.groupMemberships.length > 0 ? (
                            <GroupMembershipTable
                                profileData={profileData}
                                leftGroups={leftGroups}
                                addedGroupIds={addedGroupIds}
                                onDrillDown={onDrillDown}
                            />
                        ) : (
                            <div className="rounded-lg px-4 py-3 flex items-center gap-2" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                                <svg className="w-4 h-4 flex-shrink-0" style={{ color: 'var(--text-tertiary)' }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                                </svg>
                                <span style={{ fontSize: '12px', color: 'var(--text-tertiary)' }}>No group memberships recorded at this snapshot</span>
                            </div>
                        )}
                    </div>
                )}
                {type === 'user' && !profileData._isHistorical && profileData.groupMemberships && profileData.groupMemberships.length > 0 && (
                    <div className="mt-6">
                        <GroupMembershipTable
                            profileData={profileData}
                            leftGroups={leftGroups}
                            addedGroupIds={addedGroupIds}
                            onDrillDown={onDrillDown}
                        />
                    </div>
                )}

                {/* Custom Content for Groups (Members List) */}
                {type === 'group' && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '16px' }}>
                        {/* Member Search Bar */}
                        <div>
                            <label className="block" style={{ fontSize: '9px', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.8px', color: 'var(--text-secondary)', marginBottom: '8px' }}>Search Group Members</label>
                            <div className="relative">
                                <input
                                    type="text"
                                    placeholder="Search by name, Signal ID, or phone number..."
                                    value={memberSearchQuery}
                                    onChange={(e) => setMemberSearchQuery(e.target.value)}
                                    className="w-full outline-none transition-all"
                                    style={{ background: 'var(--bg-page)', border: '0.5px solid var(--border)', borderRadius: '6px', height: '36px', paddingLeft: '12px', paddingRight: '36px', fontSize: '13px', fontFamily: "'Inter', sans-serif", color: 'var(--text-primary)' }}
                                    onFocus={(e) => e.currentTarget.style.border = '1px solid var(--accent)'}
                                    onBlur={(e) => e.currentTarget.style.border = '0.5px solid var(--border)'}
                                />
                                {memberSearchQuery ? (
                                    <button
                                        onClick={() => setMemberSearchQuery('')}
                                        className="absolute right-3 top-1/2 -translate-y-1/2 p-1 rounded-md transition-colors"
                                        style={{ color: 'var(--text-tertiary)' }}
                                    >
                                        <svg style={{ width: '14px', height: '14px' }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                        </svg>
                                    </button>
                                ) : (
                                    <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" style={{ color: 'var(--text-tertiary)' }}>
                                        <svg style={{ width: '14px', height: '14px' }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                                        </svg>
                                    </div>
                                )}
                            </div>
                            <div className="flex justify-between items-center" style={{ marginTop: '6px', fontSize: '11px', fontStyle: 'italic', color: 'var(--text-tertiary)' }}>
                                <span>Filtering through admins{profileData._isHistorical ? ', members, and former members' : ' and members'}</span>
                                {memberSearchQuery && <span style={{ color: 'var(--accent)', fontStyle: 'normal', fontWeight: 500 }}>Search Active</span>}
                            </div>
                        </div>

                        {(() => {
                            const diff = profileData.membershipDiff || {};
                            const membersList = profileData.members || [];

                            // Enhanced Filter Logic including e164
                            const filterFn = (m) => {
                                if (!memberSearchQuery) return true;
                                const q = memberSearchQuery.toLowerCase();
                                return (m.name || "").toLowerCase().includes(q) ||
                                    (m.profileName || "").toLowerCase().includes(q) ||
                                    (m.serviceId || "").toLowerCase().includes(q) ||
                                    (m.e164 || "").toLowerCase().includes(q);
                            };

                            const admins = membersList.filter(m => m.role?.toLowerCase() === 'admin').filter(filterFn);
                            const members = membersList.filter(m => m.role?.toLowerCase() !== 'admin').filter(filterFn);
                            const leftMembers = (diff.left || []).filter(filterFn);

                            const totalVisible = admins.length + members.length + leftMembers.length;

                            return (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                                    {/* Group Admins */}
                                    {admins.length > 0 && (
                                        <div>
                                            <h3 className="flex items-center" style={{ height: '32px', borderLeft: '2px solid var(--accent)', paddingLeft: '12px', fontSize: '12px', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.6px', color: 'var(--text-primary)', marginBottom: '12px' }}>
                                                Group Admins <span style={{ color: 'var(--text-secondary)', marginLeft: '4px' }}>({admins.length})</span>
                                            </h3>
                                            {renderGroupMembers(admins, { diff })}
                                        </div>
                                    )}

                                    {/* Group Members */}
                                    {members.length > 0 && (
                                        <div>
                                            <h3 className="flex items-center" style={{ height: '32px', borderLeft: '2px solid var(--accent)', paddingLeft: '12px', fontSize: '12px', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.6px', color: 'var(--text-primary)', marginBottom: '12px' }}>
                                                Group Members <span style={{ color: 'var(--text-secondary)', marginLeft: '4px' }}>({members.length})</span>
                                            </h3>
                                            {renderGroupMembers(members, { diff })}
                                        </div>
                                    )}

                                    {/* Recently Left Members */}
                                    {profileData._isHistorical && leftMembers.length > 0 && (
                                        <div>
                                            <h3 className="flex items-center" style={{ height: '32px', borderLeft: '2px solid var(--danger)', paddingLeft: '12px', fontSize: '12px', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.6px', color: 'var(--danger)', marginBottom: '12px' }}>
                                                Recently Left <span style={{ color: 'var(--text-secondary)', marginLeft: '4px' }}>({leftMembers.length})</span>
                                            </h3>
                                            {renderGroupMembers(leftMembers, { diff, isLeftList: true })}
                                        </div>
                                    )}

                                    {/* Fallback */}
                                    {totalVisible === 0 && (
                                        <div className="flex flex-col items-center justify-center py-12 rounded-xl border border-dashed" style={{ background: 'var(--bg-page)', borderColor: 'var(--border)' }}>
                                            <div className="p-3 rounded-full mb-3" style={{ background: 'var(--bg-hover)' }}>
                                                <svg className="w-8 h-8" style={{ color: 'var(--text-tertiary)' }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                                                </svg>
                                            </div>
                                            <p className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>No members match your search</p>
                                            <button
                                                onClick={() => setMemberSearchQuery('')}
                                                className="mt-2 text-xs hover:underline"
                                                style={{ color: 'var(--accent)' }}
                                            >
                                                Clear search query
                                            </button>
                                        </div>
                                    )}
                                </div>
                            );
                        })()}
                    </div>
                )}
            </div >
        );
    };

    const renderGroupMembersList = (profileData) => {
        const diff = profileData.membershipDiff || {};
        const membersList = profileData.members || [];

        const filterFn = (m) => {
            if (!memberSearchQuery) return true;
            const q = memberSearchQuery.toLowerCase();
            return (m.name || "").toLowerCase().includes(q) ||
                (m.profileName || "").toLowerCase().includes(q) ||
                (m.serviceId || "").toLowerCase().includes(q) ||
                (m.e164 || "").toLowerCase().includes(q);
        };

        const admins = membersList.filter(m => m.role?.toLowerCase() === 'admin').filter(filterFn);
        const members = membersList.filter(m => m.role?.toLowerCase() !== 'admin').filter(filterFn);
        const leftMembers = (diff.left || []).filter(filterFn);
        const totalVisible = admins.length + members.length + leftMembers.length;

        return (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {/* Member Search Bar */}
                <div>
                    <label className="block" style={{ fontSize: '9px', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.8px', color: 'var(--text-secondary)', marginBottom: '8px' }}>Search Group Members</label>
                    <div className="relative">
                        <input
                            type="text"
                            placeholder="Search by name, Signal ID, or phone number..."
                            value={memberSearchQuery}
                            onChange={(e) => setMemberSearchQuery(e.target.value)}
                            className="w-full outline-none transition-all"
                            style={{ background: 'var(--bg-page)', border: '0.5px solid var(--border)', borderRadius: '6px', height: '36px', paddingLeft: '12px', paddingRight: '36px', fontSize: '13px', fontFamily: "'Inter', sans-serif", color: 'var(--text-primary)' }}
                            onFocus={(e) => e.currentTarget.style.border = '1px solid var(--accent)'}
                            onBlur={(e) => e.currentTarget.style.border = '0.5px solid var(--border)'}
                        />
                        {memberSearchQuery ? (
                            <button onClick={() => setMemberSearchQuery('')} className="absolute right-3 top-1/2 -translate-y-1/2 p-1 rounded-md transition-colors" style={{ color: 'var(--text-tertiary)' }}>
                                <svg style={{ width: '14px', height: '14px' }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                            </button>
                        ) : (
                            <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" style={{ color: 'var(--text-tertiary)' }}>
                                <svg style={{ width: '14px', height: '14px' }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                                </svg>
                            </div>
                        )}
                    </div>
                    <div className="flex justify-between items-center" style={{ marginTop: '6px', fontSize: '11px', fontStyle: 'italic', color: 'var(--text-tertiary)' }}>
                        <span>Filtering through admins and members ({membersList.length} total)</span>
                        {memberSearchQuery && <span style={{ color: 'var(--accent)', fontStyle: 'normal', fontWeight: 500 }}>Search Active</span>}
                    </div>
                </div>

                {/* Group Admins */}
                {admins.length > 0 && (
                    <div>
                        <h3 className="flex items-center" style={{ height: '32px', borderLeft: '2px solid var(--accent)', paddingLeft: '12px', fontSize: '12px', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.6px', color: 'var(--text-primary)', marginBottom: '12px' }}>
                            Group Admins <span style={{ color: 'var(--text-secondary)', marginLeft: '4px' }}>({admins.length})</span>
                        </h3>
                        {renderGroupMembers(admins, { diff })}
                    </div>
                )}

                {/* Group Members */}
                {members.length > 0 && (
                    <div>
                        <h3 className="flex items-center" style={{ height: '32px', borderLeft: '2px solid var(--accent)', paddingLeft: '12px', fontSize: '12px', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.6px', color: 'var(--text-primary)', marginBottom: '12px' }}>
                            Group Members <span style={{ color: 'var(--text-secondary)', marginLeft: '4px' }}>({members.length})</span>
                        </h3>
                        {renderGroupMembers(members, { diff })}
                    </div>
                )}

                {/* Recently Left Members */}
                {leftMembers.length > 0 && (
                    <div>
                        <h3 className="flex items-center" style={{ height: '32px', borderLeft: '2px solid var(--danger)', paddingLeft: '12px', fontSize: '12px', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.6px', color: 'var(--danger)', marginBottom: '12px' }}>
                            Recently Left <span style={{ color: 'var(--text-secondary)', marginLeft: '4px' }}>({leftMembers.length})</span>
                        </h3>
                        {renderGroupMembers(leftMembers, { diff, isLeftList: true })}
                    </div>
                )}

                {/* Fallback */}
                {totalVisible === 0 && (
                    <div className="flex flex-col items-center justify-center py-12 rounded-xl border border-dashed" style={{ background: 'var(--bg-page)', borderColor: 'var(--border)' }}>
                        <div className="p-3 rounded-full mb-3" style={{ background: 'var(--bg-hover)' }}>
                            <svg className="w-8 h-8" style={{ color: 'var(--text-tertiary)' }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                            </svg>
                        </div>
                        <p className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>
                            {memberSearchQuery ? 'No members match your search' : 'No members found in this group'}
                        </p>
                        {memberSearchQuery && (
                            <button onClick={() => setMemberSearchQuery('')} className="mt-2 text-xs hover:underline" style={{ color: 'var(--accent)' }}>
                                Clear search query
                            </button>
                        )}
                    </div>
                )}
            </div>
        );
    };

    return (
        <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/80 backdrop-blur-sm p-0 md:p-4 animate-fade-in">
            <div className="rounded-none md:rounded-xl shadow-2xl w-full max-w-7xl h-full md:h-[95vh] flex flex-col md:flex-row overflow-hidden" style={{ border: '0.5px solid var(--border)' }}>

                {/* Mobile: sticky identity header + segmented tab control */}
                <div className="md:hidden flex-shrink-0" style={{ background: 'var(--bg-sidebar)', borderBottom: '1px solid var(--border)' }}>
                    {/* Identity row */}
                    <div className="flex items-center justify-between px-3 pt-3 pb-2">
                        <div className="flex items-center gap-2 min-w-0">
                            {navStack.length > 0 && (
                                <button onClick={handleBack} className="p-1.5 rounded-lg flex-shrink-0" style={{ color: 'var(--text-secondary)', background: 'var(--bg-hover)' }}>
                                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" /></svg>
                                </button>
                            )}
                            <AuthenticatedMediaImage
                                mediaId={(data || {}).avatarId}
                                initialUrl={(data || {}).remoteAvatarUrl}
                                alt="Profile"
                                className="h-9 w-9 rounded-full object-cover flex-shrink-0"
                                fallbackIcon={
                                    <div className="w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0" style={{ background: 'var(--bg-accent-muted)', color: 'var(--accent)', fontSize: '15px', fontWeight: 600 }}>
                                        {((data || {}).name || (data || {}).profileName || (data || {}).groupName || "?")[0]?.toUpperCase()}
                                    </div>
                                }
                            />
                            <div className="min-w-0">
                                <div className="text-sm font-semibold truncate" style={{ color: 'var(--text-primary)' }}>
                                    {(data || {}).name || (data || {}).profileName || (data || {}).groupName || "Unknown"}
                                </div>
                                {type === 'user' && (data || {}).isAdmin && (
                                    <div className="text-[10px] font-bold" style={{ color: 'var(--warning)' }}>ADMIN</div>
                                )}
                            </div>
                        </div>
                        <button onClick={onClose} className="p-1.5 rounded-lg flex-shrink-0" style={{ color: 'var(--text-secondary)', background: 'var(--bg-hover)' }}>
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                        </button>
                    </div>
                    {/* Segmented tab control — always visible, no dropdown */}
                    <div className="flex gap-1.5 px-3 pb-3 overflow-x-auto" style={{ scrollbarWidth: 'none' }}>
                        {[
                            { key: 'overview', label: 'Overview' },
                            { key: 'connections', label: type === 'group' ? 'Members' : 'Groups' },
                            { key: 'timeline', label: 'Timeline' },
                            { key: 'raw', label: 'Raw' },
                        ].map(tab => (
                            <button
                                key={tab.key}
                                onClick={() => setActiveTab(tab.key)}
                                className="flex-shrink-0 px-3 py-1 rounded-full text-xs font-medium transition-colors"
                                style={{
                                    background: activeTab === tab.key ? 'var(--accent)' : 'var(--bg-hover)',
                                    color: activeTab === tab.key ? 'white' : 'var(--text-secondary)',
                                    border: activeTab === tab.key ? '1px solid var(--accent)' : '1px solid var(--border)',
                                    whiteSpace: 'nowrap',
                                }}
                            >
                                {tab.label}
                            </button>
                        ))}
                    </div>
                </div>

                {/* Fixed Left Sidebar (Identity Pane) — Desktop only */}
                <div className="hidden md:flex w-[220px] flex-col z-10 flex-shrink-0" style={{ background: 'var(--bg-sidebar)', borderRight: '1px solid var(--border)' }}>
                    <div className="p-4 pt-5 flex flex-col items-center relative" style={{ borderBottom: '0.5px solid var(--border)' }}>
                                {(() => {
                                    const isTimelineView = activeTab === 'timeline' && viewingHistoryItem;
                                    const activeProfile = isTimelineView ? mapHistoryToProfile(viewingHistoryItem) : (data || {});
                                    const isGroup = type === 'group';

                                    return (
                                        <>
                                            {isTimelineView && (
                                                <div className="absolute top-0 inset-x-0 p-1 text-center" style={{ background: 'rgba(245, 166, 35, 0.15)', borderBottom: '1px solid rgba(245, 166, 35, 0.3)', fontSize: '9px', fontWeight: 500, letterSpacing: '0.8px', color: 'var(--warning)' }}>
                                                    HISTORICAL SNAPSHOT
                                                </div>
                                            )}
                                            <div className={`relative group mb-3 ${isTimelineView ? 'mt-3' : ''}`}>
                                                <AuthenticatedMediaImage
                                                    mediaId={activeProfile.avatarId}
                                                    initialUrl={activeProfile.remoteAvatarUrl}
                                                    alt="Profile Logo"
                                                    className="h-16 w-16 rounded-full object-cover"
                                                    style={{ border: '2px solid var(--border)' }}
                                                    fallbackIcon={
                                                        <div className="w-16 h-16 rounded-full flex items-center justify-center" style={{ background: 'var(--bg-accent-muted)', color: 'var(--accent)', fontSize: '22px', fontWeight: 500, fontFamily: "'Geist', sans-serif" }}>
                                                            {(activeProfile.name || activeProfile.profileName || activeProfile.groupName || "?")[0]?.toUpperCase()}
                                                        </div>
                                                    }
                                                />
                                                {isGroup ? (
                                                    <div className="absolute bottom-0 right-0 p-1 rounded-full text-white" style={{ background: 'var(--accent)', border: '2px solid var(--bg-sidebar)' }} title="Group">
                                                        <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" /></svg>
                                                    </div>
                                                ) : (
                                                    <div className="absolute bottom-0 right-0 p-1 rounded-full text-white" style={{ background: 'var(--accent)', border: '2px solid var(--bg-sidebar)' }} title="User">
                                                        <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg>
                                                    </div>
                                                )}
                                                <UserImageDownloadButton mediaId={activeProfile.avatarId} name={activeProfile.name} />
                                            </div>

                                            <h2 className="text-center break-words w-full px-1 leading-tight" style={{ fontSize: '15px', fontWeight: 500, color: 'var(--text-primary)', marginTop: '12px' }}>
                                                {activeProfile.name || activeProfile.profileName || activeProfile.groupName || (activeProfile.serviceId ? `User (${activeProfile.serviceId.substring(0, 8)})` : "Unknown")}
                                            </h2>

                                            <div className="mt-3 w-full space-y-1.5">
                                                {activeProfile.serviceId && (
                                                    <div className="flex justify-between items-center cursor-pointer group/id transition-colors" style={{ background: 'var(--bg-page)', padding: '8px', borderRadius: '6px' }} onClick={() => navigator.clipboard.writeText(activeProfile.serviceId)}>
                                                        <div className="min-w-0">
                                                            <div style={{ fontSize: '9px', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.8px', color: 'var(--text-secondary)' }}>Service ID</div>
                                                            <div className="truncate" style={{ fontSize: '11px', fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-tertiary)' }}>{activeProfile.serviceId}</div>
                                                        </div>
                                                        <svg className="w-3.5 h-3.5 flex-shrink-0 ml-1" style={{ color: 'var(--text-tertiary)' }} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
                                                    </div>
                                                )}
                                                {activeProfile.groupId && (
                                                    <div className="flex justify-between items-center cursor-pointer group/id transition-colors" style={{ background: 'var(--bg-page)', padding: '8px', borderRadius: '6px' }} onClick={() => navigator.clipboard.writeText(activeProfile.groupId)}>
                                                        <div className="min-w-0">
                                                            <div style={{ fontSize: '9px', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.8px', color: 'var(--text-secondary)' }}>Group ID</div>
                                                            <div className="truncate" style={{ fontSize: '11px', fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-tertiary)' }}>{activeProfile.groupId}</div>
                                                        </div>
                                                        <svg className="w-3.5 h-3.5 flex-shrink-0 ml-1" style={{ color: 'var(--text-tertiary)' }} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
                                                    </div>
                                                )}
                                                {activeProfile.e164 && (
                                                    <div className="flex justify-between items-center cursor-pointer group/id transition-colors" style={{ background: 'var(--bg-page)', padding: '8px', borderRadius: '6px' }} onClick={() => navigator.clipboard.writeText(activeProfile.e164)}>
                                                        <div className="min-w-0">
                                                            <div style={{ fontSize: '9px', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.8px', color: 'var(--text-secondary)' }}>Phone (E164)</div>
                                                            <div style={{ fontSize: '12px', fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-tertiary)' }}>{activeProfile.e164}</div>
                                                        </div>
                                                        <svg className="w-3.5 h-3.5 flex-shrink-0 ml-1" style={{ color: 'var(--text-tertiary)' }} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
                                                    </div>
                                                )}
                                            </div>
                                        </>
                                    );
                                })()}
                            </div>

                    <div className="flex-1 overflow-y-auto px-4 py-4 flex flex-col" style={{ gap: '2px' }}>
                        <div style={{ fontSize: '9px', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '1.2px', color: 'var(--text-secondary)', marginBottom: '8px', paddingLeft: '10px' }}>Analysis Views</div>
                        {[
                            { key: 'overview', label: 'Profile Overview', icon: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /> },
                            { key: 'connections', label: 'Connections & Groups', icon: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" /> },
                            { key: 'timeline', label: 'History Timeline', icon: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /> },
                            { key: 'raw', label: 'Raw Data', icon: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" /> },
                        ].map(tab => (
                            <button
                                key={tab.key}
                                onClick={() => setActiveTab(tab.key)}
                                className="w-full flex items-center transition-all"
                                style={{
                                    height: '36px',
                                    padding: '0 10px',
                                    borderRadius: '6px',
                                    gap: '8px',
                                    fontSize: '13px',
                                    fontWeight: 400,
                                    background: activeTab === tab.key ? 'var(--bg-accent-muted)' : 'transparent',
                                    color: activeTab === tab.key ? 'var(--accent)' : 'var(--text-secondary)',
                                }}
                                onMouseEnter={(e) => { if (activeTab !== tab.key) e.currentTarget.style.background = 'var(--bg-card)'; }}
                                onMouseLeave={(e) => { if (activeTab !== tab.key) e.currentTarget.style.background = 'transparent'; }}
                            >
                                <svg className="flex-shrink-0" style={{ width: '14px', height: '14px' }} fill="none" viewBox="0 0 24 24" stroke="currentColor">{tab.icon}</svg>
                                {tab.label}
                            </button>
                        ))}
                    </div>

                    <div className="space-y-1.5" style={{ padding: '16px', borderTop: '0.5px solid var(--border)' }}>
                        {navStack.length > 0 && (
                            <button
                                onClick={handleBack}
                                className="w-full flex items-center justify-center gap-2 transition-colors"
                                style={{ height: '36px', borderRadius: '6px', fontSize: '13px', fontWeight: 400, color: 'var(--text-secondary)', background: 'transparent', border: '0.5px solid var(--border)' }}
                                onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-hover)'}
                                onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                            >
                                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                                </svg>
                                Back
                            </button>
                        )}
                        <button
                            onClick={onClose}
                            className="w-full transition-colors"
                            style={{ height: '36px', borderRadius: '6px', fontSize: '13px', fontWeight: 400, color: 'var(--text-secondary)', background: 'transparent', border: '0.5px solid var(--border)' }}
                            onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-hover)'}
                            onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                        >
                            Close Dashboard
                        </button>
                    </div>
                </div>

                {/* Main Right Pane */}
                <div className="flex-1 flex flex-col min-h-0 relative" style={{ background: 'var(--bg-page)' }}>
                    <div className={`flex-1 min-h-0 overflow-y-auto custom-scrollbar ${activeTab === 'timeline' ? 'md:overflow-hidden' : 'p-3 md:p-6'}`}>
                        {loading ? (
                            <div className="flex flex-col justify-center items-center h-full space-y-4" style={{ color: 'var(--accent)' }}>
                                <div className="animate-spin rounded-full h-12 w-12" style={{ borderBottom: '2px solid var(--accent)' }}></div>
                                <div style={{ fontSize: '13px', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.8px' }}>Assembling Intel...</div>
                            </div>
                        ) : error ? (
                            <div className="text-center p-6 rounded-lg flex flex-col items-center max-w-lg mx-auto mt-20" style={{ color: 'var(--danger)', background: 'var(--danger-bg)', border: '0.5px solid var(--danger)' }}>
                                <svg className="w-12 h-12 mb-4 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
                                {error}
                            </div>
                        ) : data ? (
                            <>
                                {activeTab === 'overview' && (
                                    <div style={{ background: 'var(--bg-card)', border: '0.5px solid var(--border)', borderRadius: '8px', padding: '24px' }}>
                                        {renderProfileView(data, [], [], [], null, true)}
                                    </div>
                                )}
                                {activeTab === 'connections' && (
                                    <div style={{ background: 'var(--bg-card)', border: '0.5px solid var(--border)', borderRadius: '8px', padding: '24px' }}>
                                        {type === 'group' ? (
                                            renderGroupMembersList(data)
                                        ) : (
                                            <GroupMembershipTable
                                                profileData={data}
                                                leftGroups={[]}
                                                addedGroupIds={[]}
                                                onDrillDown={onDrillDown}
                                            />
                                        )}
                                    </div>
                                )}
                                {activeTab === 'timeline' && renderHistory()}
                                {activeTab === 'raw' && (
                                    <div style={{ background: 'var(--bg-card)', border: '0.5px solid var(--border)', borderRadius: '8px', padding: '24px', overflow: 'hidden' }}>
                                        <div className="flex items-center justify-between" style={{ marginBottom: '16px' }}>
                                            <h3 className="flex items-center gap-2" style={{ fontSize: '14px', fontWeight: 500, color: 'var(--text-primary)' }}>
                                                <svg className="w-5 h-5" style={{ color: 'var(--success)' }} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" /></svg>
                                                Raw JSON Output
                                            </h3>
                                            <div className="flex items-center gap-2">
                                                <button
                                                    onClick={() => {
                                                        navigator.clipboard.writeText(JSON.stringify(data, null, 2));
                                                    }}
                                                    className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium transition-colors"
                                                    style={{ background: 'var(--bg-hover)', color: 'var(--text-secondary)', border: '1px solid var(--border)' }}
                                                    title="Copy JSON"
                                                >
                                                    <PiCopyBold /> Copy
                                                </button>
                                                <button
                                                    onClick={() => {
                                                        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
                                                        const url = URL.createObjectURL(blob);
                                                        const a = document.createElement('a');
                                                        a.href = url;
                                                        a.download = `${type}_${id}.json`;
                                                        a.click();
                                                        URL.revokeObjectURL(url);
                                                    }}
                                                    className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium transition-colors"
                                                    style={{ background: 'var(--bg-hover)', color: 'var(--text-secondary)', border: '1px solid var(--border)' }}
                                                    title="Export JSON"
                                                >
                                                    <PiDownloadBold /> Export
                                                </button>
                                            </div>
                                        </div>
                                        <pre className="custom-scrollbar" style={{ fontSize: '12px', fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-primary)', background: 'var(--bg-page)', padding: '16px', borderRadius: '6px', overflow: 'auto', border: '0.5px solid var(--border)', maxHeight: '600px', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                                            {JSON.stringify(data, null, 2)}
                                        </pre>
                                    </div>
                                )}
                            </>
                        ) : null}
                    </div>
                </div>
            </div>
        </div>
    );
};

// Internal component for download button logic reusing useMediaUrl
const UserImageDownloadButton = ({ mediaId, name }) => {
    const [isDownloading, setIsDownloading] = useState(false);

    if (!mediaId) return null;

    const handleDownload = async (e) => {
        e.stopPropagation();
        setIsDownloading(true);
        try {
            // 1. Fetch current download URL from backend
            const response = await apiClient.get(`/media/${mediaId}/download`);
            const imageUrl = response.data?.url;

            if (!imageUrl) {
                console.error("No image URL found for download");
                return;
            }

            // 2. Trigger browser-native download via backend proxy for true streaming
            const filename = `${name || 'user'}_avatar.jpg`;
            const proxyUrl = `${apiClient.defaults.baseURL}/media/proxy?url=${encodeURIComponent(imageUrl)}&filename=${encodeURIComponent(filename)}`;

            const link = document.createElement('a');
            link.href = proxyUrl;
            link.setAttribute('download', filename);
            document.body.appendChild(link);
            link.click();
            link.remove();
        } catch (err) {
            console.error("Download failed", err);
        } finally {
            setIsDownloading(false);
        }
    };

    return (
        <button
            onClick={handleDownload}
            disabled={isDownloading}
            className="absolute bottom-0 right-0 bg-blue-600 text-white p-1.5 rounded-full border border-gray-700 shadow-lg hover:bg-blue-500 transition-colors z-10 disabled:opacity-50"
            title="Download Image"
        >
            {isDownloading ? (
                <svg className="animate-spin h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
            ) : (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
            )}
        </button>
    );
};



export default ResultDetailModal;
