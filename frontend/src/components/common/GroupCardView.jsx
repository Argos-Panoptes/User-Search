import React, { useState, useCallback } from 'react';
import useIsMobile from '../../hooks/useIsMobile';

function copyToClipboard(text) {
    navigator.clipboard.writeText(text).catch(() => { });
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

export default function GroupCardView({
    results,
    loading,
    lastResultElementRef,
    onCardClick,
    onViewMembers,
}) {
    const [copiedId, setCopiedId] = useState(null);
    const isMobile = useIsMobile();

    const handleCopy = useCallback((text, id) => {
        copyToClipboard(text);
        setCopiedId(id);
        setTimeout(() => setCopiedId(null), 1500);
    }, []);

    return (
        <div className="si-results-area custom-scrollbar">
            <div className="si-card-grid">
                {results.map((group, index) => {
                    const isLast = index === results.length - 1;
                    const groupId = group.id || group.groupId;
                    const linkUrl = group.reconstructedLink || group.groupLink;
                    const accessLabel = group.adminApprovalRequired ? 'Approval' : 'Open';

                    if (isMobile) {
                        return (
                            <div
                                key={`${groupId}-${index}`}
                                ref={isLast ? lastResultElementRef : null}
                                onClick={() => onCardClick(groupId)}
                                className="si-entity-card si-group-mobile-card cursor-pointer"
                            >
                                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                                    <div className="si-avatar" style={{ width: 32, height: 32, flexShrink: 0 }}>
                                        <div className="si-avatar-fallback" style={{ fontSize: 12 }}>
                                            {(group.groupName || '?')[0]?.toUpperCase()}
                                        </div>
                                    </div>
                                    <div style={{ flex: 1, minWidth: 0 }}>
                                        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 4 }}>
                                            <h3 className="si-card-name" style={{ fontSize: 13, margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }} title={group.groupName}>
                                                {group.groupName || 'Unknown Group'}
                                            </h3>
                                            <span className={`si-badge flex-shrink-0 ${group.adminApprovalRequired ? 'si-badge-warning' : 'si-badge-success'}`}>
                                                {accessLabel}
                                            </span>
                                        </div>
                                        <button
                                            type="button"
                                            className="si-card-copy"
                                            style={{ width: '100%' }}
                                            onClick={(e) => { e.stopPropagation(); handleCopy(group.groupId, groupId); }}
                                            title={group.groupId}
                                        >
                                            <span className="si-identifier" style={{ display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '100%' }}>
                                                {copiedId === groupId ? 'Copied!' : group.groupId}
                                            </span>
                                        </button>
                                    </div>
                                </div>

                                <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 6 }}>
                                    <div>
                                        <span style={{ color: 'var(--text-tertiary)' }}>Members </span>
                                        <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{group.numberOfMembers?.toLocaleString() || 0}</span>
                                        <span style={{ margin: '0 5px', color: 'var(--text-tertiary)' }}>•</span>
                                        <span style={{ color: 'var(--text-tertiary)' }}>Observed </span>
                                        <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10 }}>{formatObservedRange(group.firstObserved, group.lastObserved)}</span>
                                    </div>
                                    <div style={{ marginTop: 2 }}>
                                        <span style={{ color: 'var(--text-tertiary)' }}>Retention </span>
                                        <span>{group.retentionPeriod || 'Unknown'}</span>
                                        <span style={{ margin: '0 5px', color: 'var(--text-tertiary)' }}>•</span>
                                        <span style={{ color: 'var(--text-tertiary)' }}>Link </span>
                                        {linkUrl ? (
                                            <a href={linkUrl} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()} style={{ color: 'var(--accent)' }}>Open</a>
                                        ) : (
                                            <span style={{ color: 'var(--text-tertiary)' }}>Missing</span>
                                        )}
                                    </div>
                                </div>

                                <div style={{ display: 'flex', gap: 6, marginTop: 8, paddingTop: 6, borderTop: '0.5px solid var(--border)' }}>
                                    <button
                                        type="button"
                                        onClick={(e) => { e.stopPropagation(); onViewMembers(group); }}
                                        className="si-tag"
                                        style={{ flex: '1 1 0', maxWidth: 'none', justifyContent: 'center' }}
                                    >
                                        View Members
                                    </button>
                                    {linkUrl && (
                                        <a
                                            href={linkUrl}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="si-tag is-link"
                                            onClick={(e) => e.stopPropagation()}
                                            style={{ maxWidth: 'none', justifyContent: 'center' }}
                                        >
                                            Open Link
                                        </a>
                                    )}
                                </div>
                            </div>
                        );
                    }

                    return (
                        <div
                            key={`${groupId}-${index}`}
                            ref={isLast ? lastResultElementRef : null}
                            onClick={() => onCardClick(groupId)}
                            className="si-entity-card cursor-pointer"
                        >
                            <div className="si-entity-card-top">
                                <div className="si-avatar">
                                    <div className="si-avatar-fallback">
                                        {(group.groupName || '?')[0]?.toUpperCase()}
                                    </div>
                                </div>
                                <div className="min-w-0 flex-1">
                                    <div className="flex items-start justify-between gap-2">
                                        <div className="min-w-0 overflow-hidden">
                                            <h3 className="si-card-name truncate" title={group.groupName}>
                                                {group.groupName || 'Unknown Group'}
                                            </h3>
                                            <button
                                                type="button"
                                                className="si-card-copy w-full"
                                                onClick={(event) => {
                                                    event.stopPropagation();
                                                    handleCopy(group.groupId, groupId);
                                                }}
                                                title={group.groupId}
                                            >
                                                <span className="si-identifier block truncate">
                                                    {copiedId === groupId ? 'Copied!' : (group.groupId?.slice(0, 28) + '...' || 'No group ID')}
                                                </span>
                                            </button>
                                        </div>
                                        <span className={`si-badge ${group.adminApprovalRequired ? 'si-badge-warning' : 'si-badge-success'}`}>
                                            {accessLabel}
                                        </span>
                                    </div>
                                </div>
                            </div>

                            <div className="si-entity-card-bottom">
                                <div className="si-kv-row">
                                    <span className="si-kv-label">Members</span>
                                    <span className="si-kv-value">{group.numberOfMembers?.toLocaleString() || 0}</span>
                                </div>
                                <div className="si-kv-row">
                                    <span className="si-kv-label">Observed</span>
                                    <span className="si-kv-value is-muted is-code" style={{ fontSize: '10px' }}>
                                        {formatObservedRange(group.firstObserved, group.lastObserved)}
                                    </span>
                                </div>
                                <div className="si-kv-row">
                                    <span className="si-kv-label">Retention</span>
                                    <span className="si-kv-value is-muted is-code">
                                        {group.retentionPeriod || 'Unknown'}
                                    </span>
                                </div>
                                <div className="si-kv-row">
                                    <span className="si-kv-label">Link</span>
                                    {linkUrl ? (
                                        <a
                                            href={linkUrl}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="si-kv-value truncate max-w-[136px]"
                                            onClick={(event) => event.stopPropagation()}
                                            title={linkUrl}
                                        >
                                            Open Invite
                                        </a>
                                    ) : (
                                        <span className="si-kv-value is-muted">Missing</span>
                                    )}
                                </div>
                                <div className="si-kv-row">
                                    <span className="si-kv-label">About</span>
                                    <span className="si-kv-value is-muted truncate max-w-[136px]" title={group.description || 'No description available'}>
                                        {group.description || 'No description available'}
                                    </span>
                                </div>
                            </div>
                            <div className="si-tags si-card-tags">
                                <button
                                    type="button"
                                    onClick={(event) => {
                                        event.stopPropagation();
                                        onViewMembers(group);
                                    }}
                                    className="si-tag"
                                >
                                    <span className="truncate">View Members</span>
                                </button>
                                {linkUrl && (
                                    <a
                                        href={linkUrl}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="si-tag is-link"
                                        onClick={(event) => event.stopPropagation()}
                                    >
                                        <span className="truncate">Open Link</span>
                                    </a>
                                )}
                            </div>
                        </div>
                    );
                })}
            </div>

            {loading && (
                <div className="si-loader">
                    <div className="si-spinner" />
                    <span className="si-meta">Loading results...</span>
                </div>
            )}

            {results.length === 0 && !loading && (
                <div className="si-empty-state">
                    <svg className="w-12 h-12 text-text-tertiary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                    <p className="si-section-title">No groups found</p>
                    <p className="si-meta">Adjust filters and try again.</p>
                </div>
            )}
        </div>
    );
}
