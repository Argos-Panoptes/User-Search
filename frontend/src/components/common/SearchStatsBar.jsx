import React from 'react';
import useIsMobile from '../../hooks/useIsMobile';

export const USER_SORT_OPTIONS = [
    { value: '', label: 'Default' },
    { value: 'name_asc', label: 'A → Z' },
    { value: 'name_desc', label: 'Z → A' },
    { value: 'newest', label: 'Newest first' },
    { value: 'oldest', label: 'Oldest first' },
    { value: 'most_groups', label: 'Most groups' },
];

export const GROUP_SORT_OPTIONS = [
    { value: 'members-desc', label: 'Most members' },
    { value: 'members-asc', label: 'Fewest members' },
    { value: 'name-asc', label: 'A → Z' },
    { value: 'name-desc', label: 'Z → A' },
];

export default function SearchStatsBar({
    stats = [],
    activeFilters = [],
    onClearFilter,
    onReset,
    onExport,
    loading = false,
    viewMode = 'card',
    onViewModeChange,
    sortBy,
    onSortChange,
    mode = 'user',
}) {
    const isMobile = useIsMobile();

    if (!stats.length) {
        return null;
    }

    const [primaryStat] = stats;

    return (
        <div className={`si-stats-bar ${isMobile ? 'is-mobile' : ''}`}>
            <div className="si-stats-bar-main">
                {isMobile ? (
                    <div className="si-stats-compact-line">
                        {stats.map((stat, i) => (
                            <React.Fragment key={stat.label}>
                                {i > 0 && <span className="si-stats-compact-dot">•</span>}
                                <span>
                                    <span className="si-stats-compact-val">{stat.value}</span>
                                    <span className="si-stats-compact-label"> {stat.label.toLowerCase()}</span>
                                </span>
                            </React.Fragment>
                        ))}
                    </div>
                ) : (
                    <>
                        <div className="si-stat-inline">
                            <span className="si-stat-inline-label">{primaryStat.label}</span>
                            <span className="si-stat-inline-dot">·</span>
                            <span className="si-stat-inline-value">{primaryStat.value}</span>
                        </div>

                        {activeFilters.length > 0 && (
                            <div className="si-inline-filter-list">
                                {activeFilters.map((filter) => (
                                    <button
                                        key={filter.key}
                                        type="button"
                                        onClick={() => onClearFilter?.(filter.key)}
                                        className="si-inline-filter-chip"
                                        title={`Clear ${filter.label}`}
                                    >
                                        <span>{filter.label}: {filter.value}</span>
                                        <span aria-hidden="true">×</span>
                                    </button>
                                ))}
                            </div>
                        )}

                        <div className="si-stat-inline-group">
                            {stats.slice(1).map((secondaryStat) => (
                                <div key={secondaryStat.label} className="si-stat-inline si-stat-inline-divider">
                                    <span className="si-stat-inline-label">{secondaryStat.label}</span>
                                    <span className="si-stat-inline-dot">·</span>
                                    <span className="si-stat-inline-value">{secondaryStat.value}</span>
                                </div>
                            ))}
                        </div>
                    </>
                )}
            </div>

            {!isMobile && (
                <div className="si-stats-actions">
                    {onSortChange && (
                        <select
                            value={sortBy ?? ''}
                            onChange={(e) => onSortChange(e.target.value)}
                            className="si-button-secondary"
                            style={{ cursor: 'pointer', paddingRight: '1.5rem' }}
                            title="Sort results"
                        >
                            {(mode === 'group' ? GROUP_SORT_OPTIONS : USER_SORT_OPTIONS).map((opt) => (
                                <option key={opt.value} value={opt.value}>{opt.label}</option>
                            ))}
                        </select>
                    )}
                    <button type="button" onClick={onReset} className="si-button-secondary">
                        Reset
                    </button>
                    <button type="button" onClick={onExport} disabled={loading} className="si-button-secondary">
                        Export
                    </button>
                    {onViewModeChange && (
                        <div className="flex items-center gap-2">
                            <button
                                type="button"
                                onClick={() => onViewModeChange('table')}
                                className={`si-icon-button ${viewMode === 'table' ? 'is-active' : ''}`}
                                title="Table View"
                            >
                                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
                                </svg>
                            </button>
                            <button
                                type="button"
                                onClick={() => onViewModeChange('card')}
                                className={`si-icon-button ${viewMode === 'card' ? 'is-active' : ''}`}
                                title="Card View"
                            >
                                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 5a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM14 5a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1V5zM4 15a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H5a1 1 0 01-1-1v-4zM14 15a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z" />
                                </svg>
                            </button>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
