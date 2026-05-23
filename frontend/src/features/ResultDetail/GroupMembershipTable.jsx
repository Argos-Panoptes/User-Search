import React, { useMemo, useState } from 'react';

const PAGE_SIZE = 25;

const GroupMembershipTable = ({
    profileData,
    leftGroups,
    addedGroupIds,
    onDrillDown
}) => {
    const [searchQuery, setSearchQuery] = useState('');
    const [sortConfig, setSortConfig] = useState({ key: 'name', direction: 'asc' });
    const [expandedRowId, setExpandedRowId] = useState(null);
    const [currentPage, setCurrentPage] = useState(1);

    const { allGroups, mappedLeftGroups } = useMemo(() => {
        const value = profileData.groupMemberships || profileData.group_memberships;
        let parsed = [];
        if (Array.isArray(value)) {
            parsed = value;
        } else if (typeof value === 'string') {
            try { parsed = JSON.parse(value); } catch (e) { }
        }

        const active = parsed.map(g => ({
            ...g,
            id: g.groupId || g.id || g.group_id,
            name: g.groupName || g.group_name || g.title || g.name || "Unknown Group",
            memberCount: g.numberOfMembers || g.number_of_members || g.memberCount || 0,
            status: addedGroupIds.includes(g.groupId || g.id || g.group_id) ? 'new' : 'active'
        }));

        const left = leftGroups.map(g => ({
            ...g,
            id: g.groupId || g.id || g.group_id,
            name: g.groupName || g.group_name || g.title || g.name || "Unknown Group",
            memberCount: g.numberOfMembers || g.number_of_members || g.memberCount || 0,
            status: 'left'
        }));

        return { allGroups: active, mappedLeftGroups: left };
    }, [profileData, leftGroups, addedGroupIds]);

    const combinedGroups = useMemo(() => [...allGroups, ...mappedLeftGroups], [allGroups, mappedLeftGroups]);
    const hasMemberData = useMemo(() => combinedGroups.some(g => g.memberCount > 0), [combinedGroups]);

    const filteredAndSortedGroups = useMemo(() => {
        let result = combinedGroups;

        if (searchQuery) {
            const q = searchQuery.toLowerCase();
            result = result.filter(g =>
                (g.name || '').toLowerCase().includes(q) ||
                (g.id || '').toLowerCase().includes(q) ||
                (g.role || '').toLowerCase().includes(q)
            );
        }

        result = [...result].sort((a, b) => {
            const aVal = a[sortConfig.key] ?? '';
            const bVal = b[sortConfig.key] ?? '';
            if (aVal < bVal) return sortConfig.direction === 'asc' ? -1 : 1;
            if (aVal > bVal) return sortConfig.direction === 'asc' ? 1 : -1;
            return 0;
        });

        return result;
    }, [combinedGroups, searchQuery, sortConfig]);

    const totalPages = Math.max(1, Math.ceil(filteredAndSortedGroups.length / PAGE_SIZE));
    const safePage = Math.min(currentPage, totalPages);
    const pageStart = (safePage - 1) * PAGE_SIZE;
    const pageItems = filteredAndSortedGroups.slice(pageStart, pageStart + PAGE_SIZE);

    const handleSearch = (val) => {
        setSearchQuery(val);
        setCurrentPage(1);
    };

    const requestSort = (key) => {
        setSortConfig(prev => ({
            key,
            direction: prev.key === key && prev.direction === 'asc' ? 'desc' : 'asc'
        }));
        setCurrentPage(1);
    };

    const SortIndicator = ({ field }) => {
        if (sortConfig.key !== field) return null;
        return <span className="ml-1">{sortConfig.direction === 'asc' ? '↑' : '↓'}</span>;
    };

    if (combinedGroups.length === 0) return (
        <div className="flex flex-col items-center justify-center py-12">
            <svg className="w-12 h-12 mb-3" style={{ color: 'var(--text-tertiary)', opacity: 0.4 }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            <p className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>No group memberships found</p>
            <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>This profile has no associated groups.</p>
        </div>
    );

    const RoleBadge = ({ role }) => role?.toLowerCase() === 'admin' ? (
        <span className="px-2 py-0.5 rounded text-[10px] font-bold" style={{ background: 'var(--accent-muted)', color: 'var(--accent)', border: '1px solid var(--accent)' }}>ADMIN</span>
    ) : (
        <span className="px-2 py-0.5 rounded text-[10px] font-medium" style={{ background: 'var(--bg-hover)', color: 'var(--text-secondary)', border: '1px solid var(--border)' }}>MEMBER</span>
    );

    const StatusBadge = ({ status }) => {
        if (status === 'new') return <span className="px-1.5 py-0.5 rounded text-[9px] font-bold" style={{ background: 'var(--success-bg)', color: 'var(--success)', border: '1px solid var(--success)' }}>NEW</span>;
        if (status === 'left') return <span className="px-1.5 py-0.5 rounded text-[9px] font-bold" style={{ background: 'var(--danger-bg)', color: 'var(--danger)', border: '1px solid var(--danger)' }}>LEFT</span>;
        return null;
    };

    const Pagination = () => {
        if (totalPages <= 1) return null;
        return (
            <div className="flex items-center justify-between pt-2 pb-1 px-1">
                <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
                    {pageStart + 1}–{Math.min(pageStart + PAGE_SIZE, filteredAndSortedGroups.length)} of {filteredAndSortedGroups.length}
                </span>
                <div className="flex items-center gap-1">
                    <button
                        disabled={safePage <= 1}
                        onClick={() => setCurrentPage(p => p - 1)}
                        className="px-2 py-1 rounded text-xs transition-colors disabled:opacity-30"
                        style={{ background: 'var(--bg-hover)', color: 'var(--text-secondary)', border: '1px solid var(--border)' }}
                    >
                        ‹
                    </button>
                    <span className="text-xs px-1" style={{ color: 'var(--text-secondary)' }}>
                        {safePage} / {totalPages}
                    </span>
                    <button
                        disabled={safePage >= totalPages}
                        onClick={() => setCurrentPage(p => p + 1)}
                        className="px-2 py-1 rounded text-xs transition-colors disabled:opacity-30"
                        style={{ background: 'var(--bg-hover)', color: 'var(--text-secondary)', border: '1px solid var(--border)' }}
                    >
                        ›
                    </button>
                </div>
            </div>
        );
    };

    return (
        <div className="flex flex-col space-y-3">
            {/* Header */}
            <div className="flex justify-between items-end">
                <div>
                    <h3 className="text-lg font-bold mb-0.5" style={{ color: 'var(--text-primary)' }}>Group Memberships</h3>
                    <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Total groups: {combinedGroups.length}</p>
                </div>
                <div className="w-48 relative">
                    <input
                        type="text"
                        placeholder="Search groups..."
                        value={searchQuery}
                        onChange={(e) => handleSearch(e.target.value)}
                        className="si-input w-full pl-4 pr-9 py-1.5 text-sm"
                    />
                    <svg className="absolute right-3 top-2 h-4 w-4" style={{ color: 'var(--text-tertiary)' }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                    </svg>
                </div>
            </div>

            {/* Mobile card list */}
            <div className="block md:hidden rounded-lg overflow-hidden" style={{ background: 'var(--bg-page)', border: '1px solid var(--border)' }}>
                {pageItems.length === 0 ? (
                    <p className="px-4 py-6 text-center text-sm" style={{ color: 'var(--text-tertiary)' }}>No groups found.</p>
                ) : pageItems.map((g, i) => (
                    <button
                        key={g.id + i}
                        type="button"
                        className="w-full text-left px-3 py-2.5 flex items-center justify-between transition-colors"
                        style={{ borderBottom: '1px solid var(--border)' }}
                        onClick={() => onDrillDown && onDrillDown('group', g.id)}
                        onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-hover)'}
                        onMouseLeave={(e) => e.currentTarget.style.background = ''}
                    >
                        <div className="flex items-center gap-2 min-w-0">
                            <span
                                className="text-sm font-medium truncate"
                                style={{ color: g.status === 'left' ? 'var(--text-tertiary)' : 'var(--text-primary)', textDecoration: g.status === 'left' ? 'line-through' : 'none' }}
                            >
                                {g.name}
                            </span>
                            <StatusBadge status={g.status} />
                        </div>
                        <div className="flex-shrink-0 ml-2">
                            <RoleBadge role={g.role} />
                        </div>
                    </button>
                ))}
                <div className="px-3">
                    <Pagination />
                </div>
            </div>

            {/* Desktop table */}
            <div className="hidden md:block rounded-lg overflow-hidden" style={{ background: 'var(--bg-page)', border: '1px solid var(--border)' }}>
                <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                        <thead className="sticky top-0 z-10" style={{ background: 'var(--bg-hover)' }}>
                            <tr>
                                <th className="px-4 py-2.5 text-xs font-bold uppercase tracking-wider cursor-pointer w-[55%]"
                                    style={{ color: 'var(--text-tertiary)' }}
                                    onClick={() => requestSort('name')}>
                                    Group Name <SortIndicator field="name" />
                                </th>
                                <th className="px-4 py-2.5 text-xs font-bold uppercase tracking-wider cursor-pointer"
                                    style={{ color: 'var(--text-tertiary)' }}
                                    onClick={() => requestSort('role')}>
                                    Role <SortIndicator field="role" />
                                </th>
                                {hasMemberData && (
                                    <th className="px-4 py-2.5 text-xs font-bold uppercase tracking-wider cursor-pointer text-right"
                                        style={{ color: 'var(--text-tertiary)' }}
                                        onClick={() => requestSort('memberCount')}>
                                        Members <SortIndicator field="memberCount" />
                                    </th>
                                )}
                                <th className="px-2 py-2.5 w-8"></th>
                            </tr>
                        </thead>
                        <tbody>
                            {pageItems.map((g, i) => {
                                const rowKey = g.id + i;
                                const isExpanded = expandedRowId === rowKey;
                                return (
                                    <React.Fragment key={rowKey}>
                                        <tr
                                            className="transition-colors cursor-pointer"
                                            style={{ borderBottom: '1px solid var(--border)' }}
                                            onClick={() => onDrillDown && onDrillDown('group', g.id)}
                                            onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-hover)'}
                                            onMouseLeave={(e) => e.currentTarget.style.background = ''}
                                        >
                                            <td className="px-4 py-2.5">
                                                <div className="flex items-center gap-2">
                                                    <span className="font-medium text-sm"
                                                        style={{ color: g.status === 'left' ? 'var(--text-tertiary)' : 'var(--text-primary)', textDecoration: g.status === 'left' ? 'line-through' : 'none' }}>
                                                        {g.name}
                                                    </span>
                                                    <StatusBadge status={g.status} />
                                                </div>
                                            </td>
                                            <td className="px-4 py-2.5">
                                                <RoleBadge role={g.role} />
                                            </td>
                                            {hasMemberData && (
                                                <td className="px-4 py-2.5 text-right">
                                                    <span className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
                                                        {g.memberCount > 0 ? g.memberCount.toLocaleString() : '-'}
                                                    </span>
                                                </td>
                                            )}
                                            <td className="px-2 py-2.5">
                                                <button
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        setExpandedRowId(isExpanded ? null : rowKey);
                                                    }}
                                                    className="p-1 rounded transition-colors"
                                                    style={{ color: 'var(--text-tertiary)' }}
                                                    title="Show ID"
                                                >
                                                    <svg className={`w-3.5 h-3.5 transition-transform ${isExpanded ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                                    </svg>
                                                </button>
                                            </td>
                                        </tr>
                                        {isExpanded && (
                                            <tr>
                                                <td colSpan={hasMemberData ? 4 : 3} className="px-4 py-2" style={{ background: 'var(--bg-hover)', borderBottom: '1px solid var(--border)' }}>
                                                    <div className="flex items-center gap-2">
                                                        <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-tertiary)' }}>Group ID:</span>
                                                        <code className="text-[11px] font-mono px-2 py-0.5 rounded select-all" style={{ color: 'var(--text-primary)', background: 'var(--bg-page)', border: '1px solid var(--border)' }}>{g.id}</code>
                                                        <button
                                                            onClick={(e) => {
                                                                e.stopPropagation();
                                                                navigator.clipboard.writeText(g.id);
                                                            }}
                                                            className="p-1 rounded transition-colors"
                                                            style={{ color: 'var(--text-tertiary)' }}
                                                            title="Copy ID"
                                                        >
                                                            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
                                                        </button>
                                                    </div>
                                                </td>
                                            </tr>
                                        )}
                                    </React.Fragment>
                                );
                            })}
                            {pageItems.length === 0 && (
                                <tr>
                                    <td colSpan={hasMemberData ? 4 : 3} className="px-4 py-8 text-center text-sm" style={{ color: 'var(--text-tertiary)' }}>
                                        No groups found matching your search.
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
                <div className="px-3 border-t" style={{ borderColor: 'var(--border)' }}>
                    <Pagination />
                </div>
            </div>
        </div>
    );
};

export default GroupMembershipTable;
