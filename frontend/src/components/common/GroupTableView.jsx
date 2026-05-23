import React, { useState, useCallback } from 'react';

const COLUMNS = [
    { key: 'groupName', label: 'Group Name', width: '28%' },
    { key: 'groupId', label: 'Group ID', width: '14%' },
    { key: 'numberOfMembers', label: 'Members', width: '7%' },
    { key: 'access', label: 'Access', width: '7%' },
    { key: 'retentionPeriod', label: 'Retention', width: '8%' },
    { key: 'link', label: 'Link', width: '9%' },
    { key: 'description', label: 'Description', width: '19%' },
    { key: 'lastObserved', label: 'Last Seen', width: '8%' },
    { key: 'actions', label: '', width: '5%' },
];

function copyToClipboard(text) {
    navigator.clipboard.writeText(text).catch(() => {});
}

function formatDate(dateStr) {
    if (!dateStr) return '—';
    try {
        const d = new Date(dateStr);
        const now = new Date();
        const diffDays = Math.floor((now - d) / (1000 * 60 * 60 * 24));
        if (diffDays === 0) return 'Today';
        if (diffDays === 1) return '1d ago';
        if (diffDays < 30) return `${diffDays}d ago`;
        if (diffDays < 365) return `${Math.floor(diffDays / 30)}mo ago`;
        return d.toLocaleDateString('en-US', { month: 'short', year: '2-digit' });
    } catch {
        return '—';
    }
}

export default function GroupTableView({
    results,
    loading,
    lastResultElementRef,
    onRowClick,
    onViewMembers,
}) {
    const [expandedRow, setExpandedRow] = useState(null);
    const [copiedId, setCopiedId] = useState(null);

    const handleRowExpand = useCallback((groupId) => {
        setExpandedRow((prev) => (prev === groupId ? null : groupId));
    }, []);

    const handleCopy = useCallback((text, id) => {
        copyToClipboard(text);
        setCopiedId(id);
        setTimeout(() => setCopiedId(null), 1500);
    }, []);

    return (
        <div className="si-results-area overflow-auto custom-scrollbar">
            <div
                className="overflow-hidden rounded-lg"
                style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
            >
            <table className="si-data-table si-group-table text-left">
                <colgroup>
                    <col style={{ width: '40px' }} />
                    {COLUMNS.map((column) => (
                        <col key={column.key} style={{ width: column.width }} />
                    ))}
                </colgroup>
                <thead className="sticky top-0 z-10">
                    <tr>
                        <th className="w-8 px-2 py-2" />
                        {COLUMNS.map((column) => (
                            <th
                                key={column.key}
                                className={`px-2 py-2 ${column.key === 'groupId' || column.key === 'numberOfMembers' || column.key === 'actions' ? 'text-center' : ''}`}
                            >
                                {column.label}
                            </th>
                        ))}
                    </tr>
                </thead>

                <tbody>
                    {results.map((group, index) => {
                        const groupId = group.id || group.groupId;
                        const isLast = index === results.length - 1;
                        const isExpanded = expandedRow === groupId;
                        const linkUrl = group.reconstructedLink || group.groupLink;

                        return (
                            <React.Fragment key={`${groupId}-${index}`}>
                                <tr
                                    ref={isLast ? lastResultElementRef : null}
                                    className={`transition-colors ${isExpanded ? 'bg-bg-hover' : ''}`}
                                    onClick={() => onRowClick(groupId)}
                                >
                                    <td className="px-3 py-3 text-center align-middle">
                                        <button
                                            type="button"
                                            onClick={(event) => {
                                                event.stopPropagation();
                                                handleRowExpand(groupId);
                                            }}
                                            className="text-text-tertiary hover:text-text-secondary"
                                        >
                                            <svg
                                                className={`w-3 h-3 transition-transform duration-150 ${isExpanded ? 'rotate-90 text-text-secondary' : ''}`}
                                                fill="none"
                                                viewBox="0 0 24 24"
                                                stroke="currentColor"
                                            >
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                            </svg>
                                        </button>
                                    </td>
                                    <td className="px-3 py-3 align-middle">
                                        <span className="block truncate font-medium text-text-primary" title={group.groupName}>
                                            {group.groupName || 'Unknown'}
                                        </span>
                                    </td>
                                    <td className="px-3 py-3 text-center align-middle">
                                        <button
                                            type="button"
                                            className="font-mono text-[11px] text-accent hover:text-accent-hover transition-colors truncate w-full inline-block"
                                            onClick={(event) => {
                                                event.stopPropagation();
                                                handleCopy(group.groupId, groupId);
                                            }}
                                            title={group.groupId}
                                        >
                                            {copiedId === groupId ? 'Copied' : (group.groupId?.slice(0, 20) || '—')}
                                        </button>
                                    </td>
                                    <td className="px-3 py-3 text-center align-middle">
                                        <button
                                            type="button"
                                            className="font-mono text-[11px] text-text-secondary hover:text-accent transition-colors"
                                            onClick={(event) => {
                                                event.stopPropagation();
                                                onViewMembers(group);
                                            }}
                                        >
                                            {(group.numberOfMembers || 0).toLocaleString()}
                                        </button>
                                    </td>
                                    <td className="px-3 py-3 align-middle">
                                        <span className={`si-badge ${group.adminApprovalRequired ? 'si-badge-warning' : 'si-badge-success'}`}>
                                            {group.adminApprovalRequired ? 'Approval' : 'Open'}
                                        </span>
                                    </td>
                                    <td className="px-3 py-3 align-middle">
                                        <span className="si-identifier">{group.retentionPeriod || '—'}</span>
                                    </td>
                                    <td className="px-3 py-3 align-middle">
                                        {linkUrl ? (
                                            <a
                                                href={linkUrl}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="text-[13px] font-medium text-accent hover:text-accent-hover"
                                                onClick={(event) => event.stopPropagation()}
                                            >
                                                Open Link
                                            </a>
                                        ) : (
                                            <span className="text-[12px] text-text-tertiary">No link</span>
                                        )}
                                    </td>
                                    <td className="px-3 py-3 align-middle">
                                        <span className="block truncate text-[12px] text-text-secondary" title={group.description || 'No description'}>
                                            {group.description || 'No description'}
                                        </span>
                                    </td>
                                    <td className="px-3 py-3 align-middle">
                                        <span className="si-identifier">{formatDate(group.lastObserved || group.exportTimestamp)}</span>
                                    </td>
                                    <td className="px-3 py-3 text-center align-middle">
                                        <button
                                            type="button"
                                            onClick={(event) => {
                                                event.stopPropagation();
                                                onRowClick(groupId);
                                            }}
                                            className="si-icon-button h-8 w-8"
                                            title="View Details"
                                        >
                                            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                                            </svg>
                                        </button>
                                    </td>
                                </tr>

                                {isExpanded && (
                                    <tr className="bg-bg-card">
                                        <td colSpan={COLUMNS.length + 1} className="px-4 py-4">
                                            <div className="grid gap-4 md:grid-cols-4">
                                                <div>
                                                    <div className="si-label">Full Group ID</div>
                                                    <div className="si-identifier break-all">{group.groupId || '—'}</div>
                                                </div>
                                                <div>
                                                    <div className="si-label">First Seen</div>
                                                    <div className="si-identifier">{formatDate(group.firstObserved)}</div>
                                                </div>
                                                <div>
                                                    <div className="si-label">Last Seen</div>
                                                    <div className="si-identifier">{formatDate(group.lastObserved || group.exportTimestamp)}</div>
                                                </div>
                                                <div>
                                                    <div className="si-label">Description</div>
                                                    <div className="text-[12px] text-text-secondary">{group.description || 'No description'}</div>
                                                </div>
                                            </div>
                                        </td>
                                    </tr>
                                )}
                            </React.Fragment>
                        );
                    })}
                </tbody>
            </table>
            </div>

            {loading && (
                <div className="si-loader">
                    <div className="si-spinner" />
                    <span className="si-meta">Loading results...</span>
                </div>
            )}

            {results.length === 0 && !loading && (
                <div className="si-empty-state">
                    <p className="si-section-title">No groups found</p>
                    <p className="si-meta">Adjust filters and try again.</p>
                </div>
            )}
        </div>
    );
}
