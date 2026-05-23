import React, { useState, useCallback } from 'react';
import AuthenticatedMediaImage from './AuthenticatedMediaImage';

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

export default function UserCardView({
    results,
    loading,
    lastResultElementRef,
    onCardClick,
    onDrillDown,
    onDownload,
    downloadingId,
}) {
    const [copiedId, setCopiedId] = useState(null);

    const handleCopy = useCallback((text, id) => {
        navigator.clipboard.writeText(text).catch(() => {});
        setCopiedId(id);
        setTimeout(() => setCopiedId(null), 1500);
    }, []);

    return (
        <div className="si-results-area custom-scrollbar">
            <div className="si-card-grid">
                {results.map((user, index) => {
                    const isLast = index === results.length - 1;
                    const userId = user.id || user.serviceId;
                    const displayName = user.name || user.profileName || user.profileFullName || user.profileFamilyName;
                    const groupCount = user.groupCount || user.groupMemberships?.length || 0;
                    const groups = user.groupMemberships || [];

                    return (
                        <div
                            key={`${userId}-${index}`}
                            ref={isLast ? lastResultElementRef : null}
                            onClick={() => onCardClick(userId)}
                            className="si-entity-card cursor-pointer"
                        >
                            <div className="si-entity-card-top">
                                <div className="si-avatar">
                                    <AuthenticatedMediaImage
                                        mediaId={user.avatarId}
                                        initialUrl={user.remoteAvatarUrl}
                                        alt={displayName || 'Avatar'}
                                        className="h-10 w-10 rounded-full object-cover"
                                        fallbackIcon={
                                            <div className="si-avatar-fallback">
                                                {(displayName || '?')[0]?.toUpperCase()}
                                            </div>
                                        }
                                    />
                                </div>
                                <div className="min-w-0 flex-1">
                                    <div className="flex items-start justify-between gap-2">
                                        <div className="min-w-0">
                                            <div className="si-card-name truncate">
                                                {displayName || 'Unknown'}
                                            </div>
                                            <button
                                                type="button"
                                                className="si-card-copy"
                                                onClick={(event) => {
                                                    event.stopPropagation();
                                                    handleCopy(user.serviceId || '', userId);
                                                }}
                                                title="Copy Service ID"
                                            >
                                                <span className="si-identifier block truncate">
                                                    {copiedId === userId ? 'Copied' : (user.serviceId || 'No service ID')}
                                                </span>
                                            </button>
                                        </div>
                                        {user.isAdmin && <span className="si-badge si-badge-danger">Admin</span>}
                                    </div>
                                </div>
                            </div>

                            <div className="si-entity-card-bottom">
                                <div className="si-kv-row">
                                    <span className="si-kv-label">Phone</span>
                                    <span className={`si-kv-value is-code ${user.e164 ? 'is-success' : 'is-muted'}`}>
                                        {user.e164 || 'Missing'}
                                    </span>
                                </div>
                                <div className="si-kv-row">
                                    <span className="si-kv-label">Groups</span>
                                    <span className="si-kv-value">{groupCount}</span>
                                </div>
                                <div className="si-kv-row si-desktop-kv">
                                    <span className="si-kv-label">Observed</span>
                                    <span className="si-kv-value is-muted is-code" style={{ fontSize: '10px' }}>
                                        {formatObservedRange(user.firstObserved, user.lastObserved)}
                                    </span>
                                </div>
                                <div className="si-kv-row si-desktop-kv">
                                    <span className="si-kv-label">About</span>
                                    <span className="si-kv-value is-muted truncate max-w-[136px]" title={user.about || 'No profile text'}>
                                        {user.about || 'No profile text'}
                                    </span>
                                </div>
                            </div>
                            <div className="si-tags si-card-tags">
                                {groups.slice(0, 2).map((group, groupIndex) => (
                                    <button
                                        key={groupIndex}
                                        type="button"
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            const gid = group.id || group.groupId;
                                            if (gid) onDrillDown('group', gid);
                                        }}
                                        className="si-tag"
                                    >
                                        <span className="truncate">{group.groupName || group.title || group.name || 'Group'}</span>
                                    </button>
                                ))}
                                {groups.length > 2 && (
                                    <span className="si-tag-overflow">+{groups.length - 2}</span>
                                )}
                            </div>
                        </div>
                    );
                })}
            </div>

            {/* Loading */}
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
