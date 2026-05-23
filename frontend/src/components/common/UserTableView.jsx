import React, { useState, useCallback } from 'react';
import AuthenticatedMediaImage from './AuthenticatedMediaImage';
import InlineDetailPanel from './InlineDetailPanel';

const COLUMNS = [
    { key: 'name', label: 'Identity', sortable: true, width: '26%' },
    { key: 'serviceId', label: 'Service ID', sortable: false, width: '16%' },
    { key: 'e164', label: 'Phone', sortable: true, width: '14%' },
    { key: 'groupCount', label: 'Groups', sortable: true, width: '7%' },
    { key: 'isAdmin', label: 'Role', sortable: true, width: '7%' },
    { key: 'lastObserved', label: 'Observed', sortable: false, width: '14%' },
    { key: 'groups', label: 'Key Groups', sortable: false, width: '16%' },
];

function copyToClipboard(text) {
    navigator.clipboard.writeText(text).catch(() => {});
}

function formatObservedDate(dateStr) {
    if (!dateStr) return null;
    try {
        return new Date(dateStr).toLocaleDateString('en-US', { month: '2-digit', day: '2-digit', year: 'numeric' });
    } catch { return null; }
}

function formatObservedRange(first, last) {
    const f = formatObservedDate(first);
    const l = formatObservedDate(last);
    if (!f && !l) return '—';
    if (!f) return l;
    if (!l) return f;
    if (f === l) return f;
    return `${f} – ${l}`;
}

export default function UserTableView({
    results,
    loading,
    lastResultElementRef,
    onRowClick,
    onDrillDown,
    onDownload,
    downloadingId,
}) {
    const [expandedRow, setExpandedRow] = useState(null);
    const [sortConfig, setSortConfig] = useState({ key: null, direction: 'desc' });
    const [copiedId, setCopiedId] = useState(null);

    const handleSort = useCallback((key) => {
        setSortConfig(prev => ({
            key,
            direction: prev.key === key && prev.direction === 'desc' ? 'asc' : 'desc',
        }));
    }, []);

    const handleRowExpand = useCallback((userId) => {
        setExpandedRow(prev => prev === userId ? null : userId);
    }, []);

    const handleCopy = useCallback((text, id) => {
        copyToClipboard(text);
        setCopiedId(id);
        setTimeout(() => setCopiedId(null), 1500);
    }, []);

    // Sort results locally
    const sortedResults = React.useMemo(() => {
        if (!sortConfig.key) return results;
        return [...results].sort((a, b) => {
            let aVal = a[sortConfig.key];
            let bVal = b[sortConfig.key];

            // Handle group count
            if (sortConfig.key === 'groupCount') {
                aVal = a.groupCount || a.groupMemberships?.length || 0;
                bVal = b.groupCount || b.groupMemberships?.length || 0;
            }

            // Handle name
            if (sortConfig.key === 'name') {
                aVal = (a.name || a.profileName || a.profileFullName || '').toLowerCase();
                bVal = (b.name || b.profileName || b.profileFullName || '').toLowerCase();
            }

            if (aVal < bVal) return sortConfig.direction === 'asc' ? -1 : 1;
            if (aVal > bVal) return sortConfig.direction === 'asc' ? 1 : -1;
            return 0;
        });
    }, [results, sortConfig]);

    return (
        <div className="si-results-area overflow-auto custom-scrollbar">
            <div
                className="overflow-auto rounded-lg custom-scrollbar"
                style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
            >
            <table className="si-data-table si-user-table text-left">
                <colgroup>
                    <col style={{ width: '40px' }} />
                    {COLUMNS.map((column) => (
                        <col key={column.key} style={{ width: column.width }} />
                    ))}
                </colgroup>
                {/* Sticky Header */}
                <thead className="sticky top-0 z-10">
                    <tr>
                        {/* Expand column */}
                        <th className="w-8 px-2 py-2" />
                        {COLUMNS.map(col => (
                            <th
                                key={col.key}
                                className={`px-2 py-2 select-none whitespace-nowrap ${col.sortable ? 'cursor-pointer hover:text-text-primary transition-colors' : ''}`}
                                onClick={() => col.sortable && handleSort(col.key)}
                            >
                                <span className="inline-flex items-center gap-1">
                                    {col.label}
                                    {col.sortable && sortConfig.key === col.key && (
                                        <svg className={`w-3 h-3 transition-transform ${sortConfig.direction === 'asc' ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                        </svg>
                                    )}
                                </span>
                            </th>
                        ))}
                    </tr>
                </thead>

                <tbody>
                    {sortedResults.map((user, index) => {
                        const userId = user.id || user.serviceId;
                        const isLast = index === results.length - 1;
                        const isExpanded = expandedRow === userId;
                        const displayName = user.name || user.profileName || user.profileFullName || user.profileFamilyName;
                        const groupCount = user.groupCount || user.groupMemberships?.length || 0;

                        return (
                            <React.Fragment key={`${userId}-${index}`}>
                                <tr
                                    ref={isLast ? lastResultElementRef : null}
                                    className={`group cursor-pointer transition-colors text-sm ${isExpanded ? 'bg-bg-hover' : ''}`}
                                    onClick={() => handleRowExpand(userId)}
                                >
                                    {/* Expand arrow */}
                                    <td className="px-3 py-3 align-middle">
                                        <svg
                                            className={`w-3 h-3 transition-all duration-150 ${isExpanded ? 'rotate-90 text-accent' : 'text-text-tertiary group-hover:text-text-secondary'}`}
                                            fill="none" viewBox="0 0 24 24" stroke="currentColor"
                                        >
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                        </svg>
                                    </td>

                                    {/* Identity */}
                                    <td className="px-3 py-3 align-middle">
                                        <div className="flex items-center gap-2">
                                            <AuthenticatedMediaImage
                                                mediaId={user.avatarId}
                                                initialUrl={user.remoteAvatarUrl}
                                                alt={displayName || 'Avatar'}
                                                className="h-7 w-7 rounded-full object-cover flex-shrink-0 bg-bg-accent-muted"
                                                fallbackIcon={
                                                    <div className="si-avatar-fallback text-[10px]">
                                                        {(displayName || '?')[0]?.toUpperCase()}
                                                    </div>
                                                }
                                            />
                                            <div className="min-w-0">
                                                <div className="text-text-primary font-medium truncate text-sm leading-tight">
                                                    {displayName || <span className="text-text-tertiary italic">Unknown</span>}
                                                </div>
                                                {user.about && (
                                                    <div className="text-[10px] text-text-secondary truncate" title={user.about}>
                                                        {user.about}
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    </td>

                                    {/* Service ID */}
                                    <td className="px-3 py-3 align-middle">
                                        <button
                                            className="font-mono text-[11px] text-text-tertiary hover:text-text-secondary transition-colors truncate w-full block text-left"
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                handleCopy(user.serviceId, userId);
                                            }}
                                            title={`Click to copy: ${user.serviceId}`}
                                        >
                                            {copiedId === userId ? (
                                                <span className="text-success">Copied!</span>
                                            ) : (
                                                user.serviceId?.slice(0, 18) + '...'
                                            )}
                                        </button>
                                    </td>

                                    {/* Phone */}
                                    <td className="px-3 py-3 align-middle">
                                        {user.e164 ? (
                                            <span className="font-mono text-xs text-success block truncate">{user.e164}</span>
                                        ) : (
                                            <span className="text-text-tertiary text-xs">—</span>
                                        )}
                                    </td>

                                    {/* Groups */}
                                    <td className="px-3 py-3 align-middle">
                                        <span className={`font-mono text-xs font-semibold tabular-nums ${groupCount >= 50 ? 'text-accent' : groupCount >= 20 ? 'text-text-primary' : 'text-text-secondary'}`}>
                                            {groupCount}
                                        </span>
                                    </td>

                                    {/* Role */}
                                    <td className="px-3 py-3 align-middle">
                                        {user.isAdmin ? (
                                            <span className="si-badge si-badge-danger">
                                                ADM
                                            </span>
                                        ) : (
                                            <span className="text-text-tertiary text-[10px]">—</span>
                                        )}
                                    </td>

                                    {/* Observed */}
                                    <td className="px-3 py-3 align-middle">
                                        <span className="text-[10px] text-text-tertiary font-mono tabular-nums whitespace-nowrap">
                                            {formatObservedRange(user.firstObserved, user.lastObserved)}
                                        </span>
                                    </td>

                                    {/* Key Groups */}
                                    <td className="px-3 py-3 align-middle">
                                        {user.groupMemberships && user.groupMemberships.length > 0 ? (
                                            <div className="flex items-center gap-1 overflow-hidden">
                                                {user.groupMemberships.slice(0, 2).map((g, i) => (
                                                    <span
                                                        key={i}
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            const gid = g.id || g.groupId;
                                                            if (gid) onDrillDown('group', gid);
                                                        }}
                                                        className="si-tag cursor-pointer truncate max-w-[140px]"
                                                    >
                                                        {g.groupName || g.title || g.name || 'Group'}
                                                    </span>
                                                ))}
                                                {user.groupMemberships.length > 2 && (
                                                    <span className="text-[10px] text-accent flex-shrink-0">
                                                        +{user.groupMemberships.length - 2}
                                                    </span>
                                                )}
                                            </div>
                                        ) : (
                                            <span className="text-text-tertiary text-[10px]">—</span>
                                        )}
                                    </td>
                                </tr>

                                {/* Expandable Inline Detail Panel */}
                                {isExpanded && (
                                    <tr>
                                        <td colSpan={COLUMNS.length + 1} className="p-0">
                                            <InlineDetailPanel
                                                type="user"
                                                id={userId}
                                                user={user}
                                                onDrillDown={onDrillDown}
                                                onViewFull={() => onRowClick(userId)}
                                            />
                                        </td>
                                    </tr>
                                )}
                            </React.Fragment>
                        );
                    })}
                </tbody>
            </table>
            </div>

            {/* Loading indicator */}
            {loading && (
                <div className="si-loader">
                    <div className="si-spinner" />
                    <span className="si-meta">Loading results...</span>
                </div>
            )}

            {/* Empty State */}
            {results.length === 0 && !loading && (
                <div className="si-empty-state">
                    <svg className="w-12 h-12 text-text-tertiary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                    <p className="si-section-title">No users found</p>
                    <p className="si-meta">Adjust filters and try again.</p>
                </div>
            )}
        </div>
    );
}
