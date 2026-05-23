import React, { useState, useEffect } from 'react';
import apiClient from '../../services/api';
import AuthenticatedMediaImage from './AuthenticatedMediaImage';

function formatTimestamp(ts) {
    if (!ts) return '—';
    try {
        return new Date(ts).toLocaleString('en-US', {
            month: 'short', day: 'numeric', year: 'numeric',
            hour: '2-digit', minute: '2-digit'
        });
    } catch { return '—'; }
}

function formatDate(ts) {
    if (!ts) return '—';
    try {
        return new Date(ts).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    } catch { return '—'; }
}

export default function InlineDetailPanel({ type, id, user, onDrillDown, onViewFull }) {
    const [details, setDetails] = useState(null);
    const [timeline, setTimeline] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [activeSection, setActiveSection] = useState('overview');

    useEffect(() => {
        if (!id) return;
        setLoading(true);
        setError(null);

        const fetchData = async () => {
            try {
                const idStr = String(id);
                const [detailsRes, timelineRes] = await Promise.all([
                    type === 'user'
                        ? apiClient.post('/users/details', { serviceId: idStr })
                        : apiClient.post('/groups/details', { groupId: idStr }),
                    type === 'user'
                        ? apiClient.post('/users/timeline', { serviceId: idStr, limit: 10, offset: 0 })
                        : apiClient.post('/groups/timeline', { groupId: idStr, limit: 10, offset: 0 }),
                ]);

                setDetails(detailsRes.data);
                setTimeline(timelineRes.data?.events || timelineRes.data || []);
            } catch (err) {
                setError('Failed to load details');
                console.error(err);
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, [id, type]);

    if (loading) {
        return (
            <div className="px-4 py-6 flex items-center justify-center gap-2" style={{ background: 'var(--bg-card)', borderTop: '1px solid var(--border)' }}>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2" style={{ borderColor: 'var(--accent)' }} />
                <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>Loading intel...</span>
            </div>
        );
    }

    if (error) {
        return (
            <div className="px-4 py-4 text-center" style={{ background: 'var(--bg-card)', borderTop: '1px solid var(--border)' }}>
                <span className="text-xs" style={{ color: 'var(--danger)' }}>{error}</span>
            </div>
        );
    }

    const data = details || user;
    const displayName = data?.name || data?.profileName || data?.profileFullName || data?.profileFamilyName;
    const groups = data?.groupMemberships || [];
    const adminGroups = groups.filter(g => g.role === 'ADMINISTRATOR' || g.role === 'admin');
    const memberGroups = groups.filter(g => g.role !== 'ADMINISTRATOR' && g.role !== 'admin');

    const sections = [
        { key: 'overview', label: 'Overview' },
        { key: 'groups', label: `Groups (${groups.length})` },
        { key: 'timeline', label: 'Timeline' },
    ];

    return (
        <div style={{ background: 'var(--bg-card)', borderTop: '1px solid var(--border)', borderBottom: '1px solid var(--border)' }}>
            {/* Section Tabs */}
            <div className="flex items-center gap-0 px-4" style={{ borderBottom: '1px solid var(--border)' }}>
                {sections.map(s => (
                    <button
                        key={s.key}
                        onClick={(e) => { e.stopPropagation(); setActiveSection(s.key); }}
                        className="px-3 py-2 text-[10px] font-bold uppercase tracking-wider transition-colors"
                        style={{
                            color: activeSection === s.key ? 'var(--accent)' : 'var(--text-tertiary)',
                            borderBottom: activeSection === s.key ? '2px solid var(--accent)' : '2px solid transparent'
                        }}
                    >
                        {s.label}
                    </button>
                ))}

                <div className="flex-1" />

                <button
                    onClick={(e) => { e.stopPropagation(); onViewFull(); }}
                    className="text-[10px] transition-colors font-medium flex items-center gap-1"
                    style={{ color: 'var(--text-tertiary)' }}
                    onMouseEnter={(e) => e.currentTarget.style.color = 'var(--accent)'}
                    onMouseLeave={(e) => e.currentTarget.style.color = 'var(--text-tertiary)'}
                >
                    Full View
                    <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                    </svg>
                </button>
            </div>

            <div className="px-4 py-3">
                {/* Overview Section */}
                {activeSection === 'overview' && (
                    <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-x-6 gap-y-3">
                        {/* Identity Block */}
                        <div className="col-span-2 flex items-center gap-3">
                            <AuthenticatedMediaImage
                                mediaId={data?.avatarId}
                                initialUrl={data?.remoteAvatarUrl}
                                alt={displayName || 'Avatar'}
                                className="h-12 w-12 rounded-full object-cover flex-shrink-0"
                                style={{ background: 'var(--bg-hover)' }}
                                fallbackIcon={
                                    <div className="w-full h-full rounded-full flex items-center justify-center text-lg font-bold" style={{ background: 'linear-gradient(to top right, rgba(79,110,247,0.6), rgba(139,91,168,0.6))', color: 'var(--text-on-accent)' }}>
                                        {(displayName || '?')[0]?.toUpperCase()}
                                    </div>
                                }
                            />
                            <div>
                                <div className="font-semibold text-sm" style={{ color: 'var(--text-primary)' }}>{displayName || 'Unknown'}</div>
                                <code className="text-[10px] font-mono" style={{ color: 'var(--text-tertiary)' }}>{data?.serviceId || id}</code>
                                {data?.isAdmin && (
                                    <span className="ml-2 inline-flex items-center px-1.5 py-0.5 rounded text-[8px] font-bold uppercase" style={{ background: 'var(--danger-bg)', color: 'var(--danger)', border: '1px solid color-mix(in srgb, var(--danger) 30%, transparent)' }}>
                                        Admin
                                    </span>
                                )}
                            </div>
                        </div>

                        {/* Data Fields */}
                        <DataField label="Phone" value={data?.e164} color="emerald" mono />
                        <DataField label="Groups" value={groups.length} color={groups.length >= 50 ? 'red' : groups.length >= 20 ? 'yellow' : 'blue'} />
                        <DataField label="First Seen" value={formatDate(data?.firstObserved)} />
                        <DataField label="Last Seen" value={formatDate(data?.lastObserved || data?.exportTimestamp)} />

                        {/* About */}
                        {data?.about && (
                            <div className="col-span-2 md:col-span-4 lg:col-span-6">
                                <span className="text-[9px] uppercase font-bold tracking-wider" style={{ color: 'var(--text-tertiary)' }}>About</span>
                                <p className="text-xs mt-0.5 leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{data.about}</p>
                            </div>
                        )}
                    </div>
                )}

                {/* Groups Section */}
                {activeSection === 'groups' && (
                    <div className="space-y-3 max-h-64 overflow-y-auto custom-scrollbar">
                        {adminGroups.length > 0 && (
                            <div>
                                <span className="text-[9px] uppercase font-bold tracking-wider" style={{ color: 'var(--danger)', opacity: 0.6 }}>Admin In ({adminGroups.length})</span>
                                <div className="flex flex-wrap gap-1 mt-1">
                                    {adminGroups.map((g, i) => (
                                        <GroupChip key={i} group={g} onDrillDown={onDrillDown} isAdmin />
                                    ))}
                                </div>
                            </div>
                        )}
                        <div>
                            <span className="text-[9px] uppercase font-bold tracking-wider" style={{ color: 'var(--text-tertiary)' }}>Member Of ({memberGroups.length})</span>
                            <div className="flex flex-wrap gap-1 mt-1">
                                {memberGroups.slice(0, 50).map((g, i) => (
                                    <GroupChip key={i} group={g} onDrillDown={onDrillDown} />
                                ))}
                                {memberGroups.length > 50 && (
                                    <span className="text-[10px] self-center" style={{ color: 'var(--text-tertiary)' }}>+{memberGroups.length - 50} more</span>
                                )}
                            </div>
                        </div>
                        {groups.length === 0 && (
                            <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>No group memberships</p>
                        )}
                    </div>
                )}

                {/* Timeline Section */}
                {activeSection === 'timeline' && (
                    <div className="space-y-1 max-h-64 overflow-y-auto custom-scrollbar">
                        {timeline.length > 0 ? timeline.map((event, i) => (
                            <TimelineEvent key={i} event={event} />
                        )) : (
                            <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>No timeline events</p>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}

function DataField({ label, value, color, mono }) {
    if (!value && value !== 0) return (
        <div>
            <span className="text-[9px] uppercase font-bold tracking-wider" style={{ color: 'var(--text-tertiary)' }}>{label}</span>
            <div className="text-xs mt-0.5" style={{ color: 'var(--text-tertiary)', opacity: 0.6 }}>—</div>
        </div>
    );

    const colorMap = {
        emerald: 'var(--success)',
        red: 'var(--danger)',
        yellow: 'var(--warning)',
        blue: 'var(--accent)',
    };

    return (
        <div>
            <span className="text-[9px] uppercase font-bold tracking-wider" style={{ color: 'var(--text-tertiary)' }}>{label}</span>
            <div className={`text-xs mt-0.5 ${mono ? 'font-mono' : ''}`} style={{ color: colorMap[color] || 'var(--text-primary)' }}>
                {value}
            </div>
        </div>
    );
}

function GroupChip({ group, onDrillDown, isAdmin }) {
    const gid = group.id || group.groupId;
    const name = group.groupName || group.title || group.name || 'Group';

    return (
        <button
            type="button"
            onClick={(e) => {
                e.stopPropagation();
                if (gid) onDrillDown('group', gid);
            }}
            className="inline-flex items-center px-2 py-0.5 rounded text-[10px] transition-colors cursor-pointer"
            style={isAdmin
                ? { background: 'var(--danger-bg)', color: 'var(--danger)', border: '1px solid color-mix(in srgb, var(--danger) 20%, transparent)' }
                : { background: 'var(--bg-hover)', color: 'var(--text-secondary)', border: '1px solid var(--border)' }
            }
            onMouseEnter={(e) => {
                if (!isAdmin) {
                    e.currentTarget.style.borderColor = 'var(--accent)';
                    e.currentTarget.style.color = 'var(--accent)';
                }
            }}
            onMouseLeave={(e) => {
                if (!isAdmin) {
                    e.currentTarget.style.borderColor = 'var(--border)';
                    e.currentTarget.style.color = 'var(--text-secondary)';
                }
            }}
        >
            {name}
        </button>
    );
}

function TimelineEvent({ event }) {
    const opLabel = event.operationLabel || event.operation || event.type || 'Event';
    const timestamp = event.timestamp || event.exportTimestamp || event.created_at;

    // Determine event type color
    let dotColor = 'var(--text-tertiary)';
    const op = opLabel.toLowerCase();
    if (op.includes('profile') || op.includes('name') || op.includes('avatar')) dotColor = 'var(--warning)';
    else if (op.includes('member') || op.includes('join') || op.includes('left')) dotColor = 'var(--accent)';
    else if (op.includes('admin')) dotColor = 'var(--danger)';
    else if (op.includes('snapshot') || op.includes('system')) dotColor = 'var(--accent)';

    return (
        <div
            className="flex items-start gap-2 py-1.5 group/event px-2 rounded transition-colors"
            onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-hover)'}
            onMouseLeave={(e) => e.currentTarget.style.background = ''}
        >
            <div className="w-2 h-2 rounded-full flex-shrink-0 mt-1" style={{ background: dotColor }} />
            <div className="flex-1 min-w-0">
                <span className="text-[11px] font-medium" style={{ color: 'var(--text-primary)' }}>{opLabel}</span>
                {event.summary && (
                    <span className="text-[10px] ml-2" style={{ color: 'var(--text-tertiary)' }}>{event.summary}</span>
                )}
            </div>
            <span className="text-[10px] font-mono flex-shrink-0 tabular-nums" style={{ color: 'var(--text-tertiary)' }}>
                {formatTimestamp(timestamp)}
            </span>
        </div>
    );
}
