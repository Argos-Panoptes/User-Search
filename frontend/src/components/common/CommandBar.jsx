import React, { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { PiArrowsClockwiseBold, PiExportBold, PiFunnelBold } from "react-icons/pi";
import useIsMobile from '../../hooks/useIsMobile';
import apiClient from '../../services/api';
import { GROUP_SORT_OPTIONS, USER_SORT_OPTIONS } from './SearchStatsBar';

const FILTER_STORAGE_KEY = 'si_filters_open';

const FILTER_DEFINITIONS = {
    user: {
        primary: [
            { key: 'serviceId', label: 'Service ID', type: 'text', placeholder: 'Service ID' },
            { key: 'name', label: 'Name', type: 'text', placeholder: 'Name' },
            { key: 'about', label: 'About', type: 'text', placeholder: 'About' },
        ],
        secondary: [
            { key: 'e164', label: 'Phone', type: 'text', placeholder: 'Phone', width: 'w-[160px]' },
            { key: 'groupName', label: 'Group', type: 'text', placeholder: 'Group', width: 'w-[160px]' },
            { key: 'minGroupCount', label: 'Min Groups', type: 'number', placeholder: 'Min groups', width: 'w-[100px]' },
            { key: 'maxGroupCount', label: 'Max Groups', type: 'number', placeholder: 'Max groups', width: 'w-[100px]' },
            { key: 'phoneStatus', label: 'Phone Status', type: 'select', options: ['all', 'present', 'missing'], width: 'w-[140px]' },
            { key: 'isAdmin', label: 'Admin', type: 'toggle' },
            { key: 'hasAvatar', label: 'Has Avatar', type: 'toggle' },
        ],
    },
    group: {
        primary: [
            { key: 'groupName', label: 'Name', type: 'text', placeholder: 'Name' },
            { key: 'groupId', label: 'Group ID', type: 'text', placeholder: 'Group ID' },
            { key: 'description', label: 'Description', type: 'text', placeholder: 'Description' },
        ],
        secondary: [
            { key: 'minMembers', label: 'Min Members', type: 'number', placeholder: 'Min Members', width: 'w-[160px]' },
            { key: 'maxMembers', label: 'Max Members', type: 'number', placeholder: 'Max Members', width: 'w-[160px]' },
            { key: 'hasLink', label: 'Has Link', type: 'select', options: ['any', 'yes', 'no'], width: 'w-[140px]' },
            { key: 'accessType', label: 'Access', type: 'select', options: ['', 'open', 'approval'], width: 'w-[140px]' },
        ],
    },
};

function getInitialExpandedState() {
    if (typeof window === 'undefined') {
        return false;
    }
    return window.localStorage.getItem(FILTER_STORAGE_KEY) === 'true';
}

export default function CommandBar({
    mode = 'user',
    filters,
    onFilterChange,
    onSearch,
    onReset,
    onExport,
    loading = false,
    extraFilterOptions = {},
    activeFilterCount = 0,
    autoCollapseSignal = 0,
    activeFilters = [],
    onClearFilter,
    sortBy,
    onSortChange,
}) {
    const [isExpanded, setIsExpanded] = useState(getInitialExpandedState);
    const [suggestions, setSuggestions] = useState([]);
    const [showSuggestions, setShowSuggestions] = useState(false);
    const [suggestionsLoading, setSuggestionsLoading] = useState(false);
    const suggestionsRef = useRef(null);
    const suggestionsTimerRef = useRef(null);
    const firstInputRef = useRef(null);
    const isMobile = useIsMobile();

    const fetchSuggestions = useCallback(async (query) => {
        if (!query || query.length < 2) {
            setSuggestions([]);
            setShowSuggestions(false);
            return;
        }
        setSuggestionsLoading(true);
        try {
            const endpoint = mode === 'group' ? '/groups/search' : '/users/search';
            const payload = mode === 'group'
                ? { group_name: query, limit: 8, offset: 0 }
                : { name: query, limit: 8, offset: 0 };
            const { data } = await apiClient.post(endpoint, payload);
            const items = Array.isArray(data) ? data : (data.items || data.results || []);
            setSuggestions(items);
            setShowSuggestions(items.length > 0);
        } catch {
            setSuggestions([]);
        } finally {
            setSuggestionsLoading(false);
        }
    }, [mode]);

    const handleNameChange = useCallback((key, value) => {
        onFilterChange({ [key]: value });
        if (suggestionsTimerRef.current) clearTimeout(suggestionsTimerRef.current);
        suggestionsTimerRef.current = setTimeout(() => fetchSuggestions(value), 300);
    }, [onFilterChange, fetchSuggestions]);

    const handleSuggestionClick = useCallback((item) => {
        if (mode === 'group') {
            onFilterChange({ groupName: item.groupName || item.name || '' });
        } else {
            onFilterChange({ name: item.name || item.profileName || item.profileFullName || '' });
        }
        setShowSuggestions(false);
        setSuggestions([]);
    }, [mode, onFilterChange]);

    // Close suggestions on outside click
    useEffect(() => {
        const handleClickOutside = (e) => {
            if (suggestionsRef.current && !suggestionsRef.current.contains(e.target)) {
                setShowSuggestions(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const config = FILTER_DEFINITIONS[mode] || FILTER_DEFINITIONS.user;
    const primaryFields = config.primary;
    const secondaryFields = config.secondary;

    // On mobile, all filters (primary + secondary minus the first) go into the collapsible panel
    const mobileMainField = primaryFields[0];
    const mobileFilterFields = useMemo(() => {
        if (!isMobile) return [];
        return [...primaryFields.slice(1), ...secondaryFields];
    }, [isMobile, primaryFields, secondaryFields]);

    useEffect(() => {
        window.localStorage.setItem(FILTER_STORAGE_KEY, String(isExpanded));
    }, [isExpanded]);

    // Filter panel stays open until user explicitly closes it

    useEffect(() => {
        const handleKeyDown = (event) => {
            const target = event.target;
            const isTypingTarget = target instanceof HTMLElement && (
                target.tagName === 'INPUT' ||
                target.tagName === 'TEXTAREA' ||
                target.tagName === 'SELECT' ||
                target.isContentEditable
            );

            if (event.key === '/' && !isTypingTarget) {
                event.preventDefault();
                firstInputRef.current?.focus();
            }

            if (event.key === 'Escape' && !isMobile) {
                setIsExpanded(false);
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [isMobile]);

    useEffect(() => {
        if (isMobile && isExpanded) {
            document.body.style.overflow = 'hidden';
        } else {
            document.body.style.overflow = '';
        }
        return () => { document.body.style.overflow = ''; };
    }, [isMobile, isExpanded]);

    const getSelectOptions = useMemo(() => (field) => {
        if (field.key === 'retentionPeriod' && extraFilterOptions.retentionPeriods?.length) {
            return ['', ...extraFilterOptions.retentionPeriods];
        }
        return field.options || [];
    }, [extraFilterOptions.retentionPeriods]);

    const nameFieldKey = mode === 'group' ? 'groupName' : 'name';
    const isNameField = (key) => key === nameFieldKey;

    const handleInputChange = (key, value) => {
        onFilterChange({ [key]: value });
    };

    const getSuggestionLabel = (item) => {
        if (mode === 'group') return item.groupName || item.name || '';
        return item.name || item.profileName || item.profileFullName || 'Unknown';
    };

    const getSuggestionSub = (item) => {
        if (mode === 'group') return `${item.numberOfMembers || 0} members`;
        return item.e164 || item.serviceId?.slice(0, 12) + '...' || '';
    };

    const renderSuggestionsDropdown = () => {
        if (!showSuggestions || suggestions.length === 0) return null;
        return (
            <ul
                ref={suggestionsRef}
                className="absolute z-[200] w-full mt-1 rounded-lg shadow-xl max-h-60 overflow-auto custom-scrollbar"
                style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}
            >
                {suggestions.map((item, i) => (
                    <li
                        key={item.serviceId || item.groupId || i}
                        onClick={() => handleSuggestionClick(item)}
                        className="px-3 py-2 cursor-pointer flex justify-between items-center"
                        onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-hover)'}
                        onMouseLeave={(e) => e.currentTarget.style.background = ''}
                    >
                        <span className="text-sm font-medium truncate" style={{ color: 'var(--text-primary)' }}>
                            {getSuggestionLabel(item)}
                        </span>
                        <span className="text-[10px] font-mono ml-2 flex-shrink-0" style={{ color: 'var(--text-tertiary)' }}>
                            {getSuggestionSub(item)}
                        </span>
                    </li>
                ))}
            </ul>
        );
    };

    const renderFilterField = (field) => {
        if (field.type === 'toggle') {
            const isActive = Boolean(filters[field.key]);
            return (
                <label key={field.key} className="si-inline-toggle">
                    <span className="si-label">{field.label}</span>
                    <button
                        type="button"
                        onClick={() => handleInputChange(field.key, !isActive)}
                        className={`si-toggle ${isActive ? 'is-active' : ''}`}
                        aria-pressed={isActive}
                        aria-label={field.label}
                    />
                </label>
            );
        }

        if (field.type === 'select') {
            const options = getSelectOptions(field);
            return (
                <select
                    key={field.key}
                    value={filters[field.key] ?? options[0] ?? ''}
                    onChange={(event) => handleInputChange(field.key, event.target.value)}
                    className={`si-select ${isMobile ? 'w-full' : (field.width || '')}`}
                    aria-label={field.label}
                >
                    {options.map((option) => (
                        <option key={option || 'empty'} value={option}>
                            {option || field.label}
                        </option>
                    ))}
                </select>
            );
        }

        if (isNameField(field.key)) {
            return (
                <div key={field.key} className={`relative ${isMobile ? 'w-full' : (field.width || 'w-[160px]')}`}>
                    <input
                        type={field.type}
                        value={filters[field.key] ?? ''}
                        onChange={(event) => handleNameChange(field.key, event.target.value)}
                        onFocus={() => { if (suggestions.length > 0) setShowSuggestions(true); }}
                        className="si-input w-full"
                        placeholder={field.placeholder}
                        aria-label={field.label}
                        autoComplete="off"
                    />
                    {renderSuggestionsDropdown()}
                </div>
            );
        }

        return (
            <input
                key={field.key}
                type={field.type}
                value={filters[field.key] ?? ''}
                onChange={(event) => handleInputChange(field.key, event.target.value)}
                className={`si-input ${isMobile ? 'w-full' : (field.width || 'w-[160px]')}`}
                placeholder={field.placeholder}
                aria-label={field.label}
            />
        );
    };

    // --- Mobile Layout ---
    if (isMobile) {
        const sheet = (
            <>
                {isExpanded && (
                    <div
                        onClick={() => setIsExpanded(false)}
                        style={{ position: 'fixed', inset: 0, zIndex: 990, background: 'rgba(0,0,0,0.55)' }}
                    />
                )}
                <div
                    style={{
                        position: 'fixed',
                        bottom: 0, left: 0, right: 0,
                        zIndex: 1000,
                        background: 'var(--bg-card)',
                        borderTop: '1px solid var(--border)',
                        borderRadius: '16px 16px 0 0',
                        maxHeight: '80vh',
                        display: 'flex',
                        flexDirection: 'column',
                        transform: isExpanded ? 'translateY(0)' : 'translateY(100%)',
                        transition: 'transform 0.25s cubic-bezier(0.32, 0.72, 0, 1)',
                    }}
                    onClick={(e) => e.stopPropagation()}
                >
                    {/* Handle + header — never scrolls */}
                    <div style={{ flexShrink: 0, padding: '0 16px' }}>
                        <div style={{ display: 'flex', justifyContent: 'center', padding: '10px 0 4px' }}>
                            <div style={{ width: 36, height: 4, borderRadius: 2, background: 'var(--border)' }} />
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                            <span style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)', fontFamily: "'Geist', sans-serif" }}>Filters</span>
                            <button
                                type="button"
                                onClick={() => setIsExpanded(false)}
                                style={{ color: 'var(--text-tertiary)', fontSize: 22, lineHeight: 1, padding: '4px 8px', background: 'transparent', border: 'none' }}
                            >×</button>
                        </div>
                    </div>

                    {/* Scrollable filter fields */}
                    <div style={{ flex: 1, overflowY: 'auto', WebkitOverflowScrolling: 'touch', padding: '0 16px' }}>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, paddingBottom: 8 }}>
                            {mobileFilterFields.map((field) => (
                                <div key={field.key}>
                                    {field.type !== 'toggle' && (
                                        <label style={{ display: 'block', fontSize: 10, fontWeight: 500, letterSpacing: '0.6px', textTransform: 'uppercase', color: 'var(--text-tertiary)', marginBottom: 4 }}>
                                            {field.label}
                                        </label>
                                    )}
                                    {renderFilterField(field)}
                                </div>
                            ))}
                            {onSortChange && (
                                <div>
                                    <label style={{ display: 'block', fontSize: 10, fontWeight: 500, letterSpacing: '0.6px', textTransform: 'uppercase', color: 'var(--text-tertiary)', marginBottom: 4 }}>
                                        Sort By
                                    </label>
                                    <select
                                        value={sortBy ?? ''}
                                        onChange={(e) => onSortChange(e.target.value)}
                                        className="si-select w-full"
                                        aria-label="Sort By"
                                    >
                                        {(mode === 'group' ? GROUP_SORT_OPTIONS : USER_SORT_OPTIONS).map((opt) => (
                                            <option key={opt.value} value={opt.value}>{opt.label}</option>
                                        ))}
                                    </select>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Action buttons — always visible at the bottom */}
                    <div style={{
                        flexShrink: 0,
                        display: 'flex',
                        gap: 8,
                        padding: '12px 16px',
                        paddingBottom: 'max(16px, env(safe-area-inset-bottom))',
                        borderTop: '1px solid var(--border)',
                        background: 'var(--bg-card)',
                    }}>
                        <button
                            type="button"
                            onClick={() => { onReset(); setIsExpanded(false); }}
                            className="si-button-secondary"
                            style={{ flex: 1, height: 44 }}
                        >
                            Reset
                        </button>
                        <button
                            type="button"
                            onClick={() => { onExport(); setIsExpanded(false); }}
                            className="si-button-secondary"
                            style={{ height: 44, width: 44 }}
                            title="Export"
                        >
                            <PiExportBold />
                        </button>
                        <button
                            type="button"
                            onClick={() => { onSearch(); setIsExpanded(false); }}
                            disabled={loading}
                            className="si-button-primary"
                            style={{ flex: 1, height: 44 }}
                        >
                            Apply
                        </button>
                    </div>
                </div>
            </>
        );

        return (
            <>
                <form
                    className="si-search-panel"
                    onSubmit={(event) => {
                        event.preventDefault();
                        onSearch();
                    }}
                >
                    <div className="flex gap-2 items-center">
                        <div className="relative flex-1 min-w-0">
                            <input
                                ref={firstInputRef}
                                type={mobileMainField.type}
                                value={filters[mobileMainField.key] ?? ''}
                                onChange={(event) => isNameField(mobileMainField.key)
                                    ? handleNameChange(mobileMainField.key, event.target.value)
                                    : handleInputChange(mobileMainField.key, event.target.value)}
                                onFocus={() => { if (suggestions.length > 0) setShowSuggestions(true); }}
                                className="si-input w-full"
                                placeholder={`Search by ${mobileMainField.label.toLowerCase()}...`}
                                aria-label={mobileMainField.label}
                                autoComplete="off"
                            />
                            {renderSuggestionsDropdown()}
                        </div>
                        <button
                            type="button"
                            onClick={() => setIsExpanded(prev => !prev)}
                            className="si-icon-button flex-shrink-0"
                            style={{
                                width: 44, height: 44,
                                position: 'relative',
                                background: isExpanded ? 'var(--accent)' : 'var(--bg-accent-muted)',
                                color: isExpanded ? '#fff' : 'var(--accent)',
                                borderRadius: 8,
                            }}
                            aria-label="Filters"
                        >
                            <PiFunnelBold className="text-base" />
                            {activeFilterCount > 0 && (
                                <span style={{
                                    position: 'absolute', top: -4, right: -4,
                                    background: 'var(--danger)', color: '#fff',
                                    fontSize: 10, fontWeight: 700,
                                    width: 18, height: 18, borderRadius: '50%',
                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                }}>
                                    {activeFilterCount}
                                </span>
                            )}
                        </button>
                        <button type="submit" disabled={loading} className="si-button-primary flex-shrink-0" style={{ height: 44, borderRadius: 8, padding: '0 16px' }}>
                            {loading ? '...' : 'Search'}
                        </button>
                    </div>

                    {activeFilters.length > 0 && (
                        <div className="flex flex-wrap gap-1.5 mt-2">
                            {activeFilters.map((filter) => (
                                <button
                                    key={filter.key}
                                    type="button"
                                    onClick={() => onClearFilter?.(filter.key)}
                                    className="si-inline-filter-chip"
                                >
                                    <span>{filter.label}: {filter.value}</span>
                                    <span aria-hidden="true">×</span>
                                </button>
                            ))}
                        </div>
                    )}
                </form>
                {createPortal(sheet, document.body)}
            </>
        );
    }

    // --- Desktop Layout ---
    return (
        <form
            className="si-search-panel"
            onSubmit={(event) => {
                event.preventDefault();
                onSearch();
            }}
        >
            <div className="si-search-row">
                {primaryFields.map((field, index) => {
                    if (isNameField(field.key)) {
                        return (
                            <div key={field.key} className="relative flex-1 min-w-[160px]">
                                <input
                                    type={field.type}
                                    value={filters[field.key] ?? ''}
                                    onChange={(event) => handleNameChange(field.key, event.target.value)}
                                    onFocus={() => { if (suggestions.length > 0) setShowSuggestions(true); }}
                                    className="si-input w-full"
                                    placeholder={field.placeholder}
                                    aria-label={field.label}
                                    autoComplete="off"
                                />
                                {renderSuggestionsDropdown()}
                            </div>
                        );
                    }
                    return (
                        <input
                            key={field.key}
                            ref={index === 0 ? firstInputRef : undefined}
                            type={field.type}
                            value={filters[field.key] ?? ''}
                            onChange={(event) => handleInputChange(field.key, event.target.value)}
                            className="si-input flex-1 min-w-[160px]"
                            placeholder={field.placeholder}
                            aria-label={field.label}
                        />
                    );
                })}

                <button type="button" onClick={onReset} className="si-button-secondary" title="Reset all filters">
                    <PiArrowsClockwiseBold />
                </button>

                <button
                    type="button"
                    onClick={() => setIsExpanded((currentState) => !currentState)}
                    className="si-button-secondary si-search-toggle"
                    aria-expanded={isExpanded}
                    aria-controls={`si-filters-${mode}`}
                >
                    Filters{activeFilterCount > 0 ? ` · ${activeFilterCount}` : ''}
                </button>

                <button type="submit" disabled={loading} className="si-button-primary si-search-submit">
                    Search
                </button>
            </div>

            <div
                id={`si-filters-${mode}`}
                className={`si-search-filters ${isExpanded ? 'is-open' : ''}`}
            >
                <div className="si-search-filters-row">
                    {secondaryFields.map((field) => renderFilterField(field))}
                </div>
            </div>
        </form>
    );
}
