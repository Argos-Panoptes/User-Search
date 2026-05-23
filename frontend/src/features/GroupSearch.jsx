import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { useDispatch } from 'react-redux';
import { setFilters } from '../features/search/searchSlice';
import apiClient from '../services/api';
import ResultDetailModal from './ResultDetailModal';
import CommandBar from '../components/common/CommandBar';
import SearchStatsBar from '../components/common/SearchStatsBar';
import GroupTableView from '../components/common/GroupTableView';
import GroupCardView from '../components/common/GroupCardView';
import useIsMobile from '../hooks/useIsMobile';

const GroupSearch = () => {
    const [searchParams, setSearchParams] = useSearchParams();
    const navigate = useNavigate();
    const dispatch = useDispatch();
    const isMobile = useIsMobile();

    // Filters as local state (GroupSearch doesn't use Redux for its own filters)
    const [filters, setLocalFilters] = useState({
        groupName: searchParams.get('groupName') || '',
        groupId: searchParams.get('groupId') || '',
        description: searchParams.get('description') || '',
        minMembers: searchParams.get('minMembers') || '',
        maxMembers: searchParams.get('maxMembers') || '',
        hasLink: searchParams.get('hasLink') || 'any',
        sortBy: searchParams.get('sortBy') || 'members-desc',
        retentionPeriod: searchParams.get('retentionPeriod') || '',
        accessType: searchParams.get('accessType') || '',
    });

    const [page, setPage] = useState(0);
    const [hasMore, setHasMore] = useState(true);
    const [results, setResults] = useState([]);
    const [loading, setLoading] = useState(false);
    const [selectedId, setSelectedId] = useState(null);
    const [modalType, setModalType] = useState('group');
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [viewMode, setViewMode] = useState('card');
    const [retentionPeriods, setRetentionPeriods] = useState([]);
    const [searchCompletionSignal, setSearchCompletionSignal] = useState(0);

    const observer = React.useRef();
    const lastResultElementRef = React.useCallback(node => {
        if (loading) return;
        if (observer.current) observer.current.disconnect();
        observer.current = new IntersectionObserver(entries => {
            if (entries[0].isIntersecting && hasMore) {
                setPage(prevPage => prevPage + 1);
            }
        });
        if (node) observer.current.observe(node);
    }, [loading, hasMore]);

    useEffect(() => {
        const fetchRetentionPeriods = async () => {
            try {
                const response = await apiClient.get('/groups/retention-periods');
                setRetentionPeriods(response.data || []);
            } catch (error) {
                console.error("Failed to fetch retention periods", error);
            }
        };
        fetchRetentionPeriods();
    }, []);

    const handleFilterChange = (updates) => {
        setLocalFilters(prev => ({ ...prev, ...updates }));
    };

    const searchGroups = async (isLoadMore = false) => {
        setLoading(true);
        try {
            const limit = 50;
            const offset = (isLoadMore ? page : 0) * limit;

            const params = {
                group_name: filters.groupName || undefined,
                group_id: filters.groupId || undefined,
                description: filters.description || undefined,
                limit,
                offset,
                sort_by: filters.sortBy
            };
            if (filters.minMembers) params.min_members = parseInt(filters.minMembers);
            if (filters.maxMembers) params.max_members = parseInt(filters.maxMembers);
            if (filters.hasLink === 'yes') params.has_link = true;
            if (filters.hasLink === 'no') params.has_link = false;
            if (filters.retentionPeriod) params.retention_period = filters.retentionPeriod;
            if (filters.accessType === 'open') params.admin_approval_required = false;
            if (filters.accessType === 'approval') params.admin_approval_required = true;

            const response = await apiClient.post('/groups/search', params);
            const newResults = response.data?.data || [];

            setResults(prev => isLoadMore ? [...prev, ...newResults] : newResults);
            setHasMore(newResults.length === limit);
            if (!isLoadMore) {
                setSearchCompletionSignal((currentSignal) => currentSignal + 1);
            }
        } catch (error) {
            console.error("Search failed", error);
        } finally {
            setLoading(false);
        }
    };

    // Reset page and debounce search when filters change
    useEffect(() => {
        setPage(0);
        setHasMore(true);

        const timeoutId = setTimeout(() => {
            searchGroups(false);
        }, 500);

        // Update URL
        const params = {};
        if (filters.groupName) params.groupName = filters.groupName;
        if (filters.groupId) params.groupId = filters.groupId;
        if (filters.description) params.description = filters.description;
        if (filters.minMembers) params.minMembers = filters.minMembers;
        if (filters.maxMembers) params.maxMembers = filters.maxMembers;
        if (filters.hasLink !== 'any') params.hasLink = filters.hasLink;
        if (filters.sortBy !== 'members-desc') params.sortBy = filters.sortBy;
        if (filters.retentionPeriod) params.retentionPeriod = filters.retentionPeriod;
        if (filters.accessType) params.accessType = filters.accessType;
        setSearchParams(params, { replace: true });

        return () => clearTimeout(timeoutId);
    }, [filters.sortBy, filters.retentionPeriod, filters.accessType, filters.groupName, filters.groupId, filters.description, filters.minMembers, filters.maxMembers, filters.hasLink]);

    useEffect(() => {
        if (page > 0) searchGroups(true);
    }, [page]);

    const handleCardClick = (id) => {
        setSelectedId(id);
        setModalType('group');
        setIsModalOpen(true);
    };

    const handleDrillDown = (type, id) => {
        setSelectedId(id);
        setModalType(type);
        setIsModalOpen(true);
    };

    const handleExport = async () => {
        try {
            const params = {
                group_name: filters.groupName || undefined,
                group_id: filters.groupId || undefined,
                description: filters.description || undefined,
                sort_by: filters.sortBy
            };
            if (filters.minMembers) params.min_members = parseInt(filters.minMembers);
            if (filters.maxMembers) params.max_members = parseInt(filters.maxMembers);
            if (filters.hasLink === 'yes') params.has_link = true;
            if (filters.hasLink === 'no') params.has_link = false;
            if (filters.retentionPeriod) params.retention_period = filters.retentionPeriod;
            if (filters.accessType === 'open') params.admin_approval_required = false;
            if (filters.accessType === 'approval') params.admin_approval_required = true;

            const response = await apiClient.post('/groups/export', params, { responseType: 'blob' });

            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', `groups_export_${new Date().toISOString()}.csv`);
            document.body.appendChild(link);
            link.click();
            link.parentNode.removeChild(link);
        } catch (error) {
            console.error("Export failed", error);
        }
    };

    const handleSearch = () => {
        setPage(0);
        searchGroups(false);
    };

    const handleReset = () => {
        setLocalFilters({
            groupName: '',
            groupId: '',
            description: '',
            minMembers: '',
            maxMembers: '',
            hasLink: 'any',
            sortBy: 'members-desc',
            retentionPeriod: '',
            accessType: '',
        });
    };

    const handleViewMembers = (group) => {
        dispatch(setFilters({
            groupId: group.id || group.groupId,
            groupName: group.groupName,
            serviceId: '',
            name: '',
            phoneStatus: 'all',
            isAdmin: false,
            hasAvatar: false
        }));
        navigate(`/users?groupId=${group.id || group.groupId}&groupName=${encodeURIComponent(group.groupName)}`);
    };

    const activeFilters = [
        filters.groupName ? { key: 'groupName', label: 'Name', value: filters.groupName } : null,
        filters.groupId ? { key: 'groupId', label: 'Group ID', value: filters.groupId } : null,
        filters.description ? { key: 'description', label: 'Description', value: filters.description } : null,
        filters.minMembers ? { key: 'minMembers', label: 'Min Members', value: filters.minMembers } : null,
        filters.maxMembers ? { key: 'maxMembers', label: 'Max Members', value: filters.maxMembers } : null,
        filters.hasLink !== 'any' ? { key: 'hasLink', label: 'Has Link', value: filters.hasLink } : null,
        filters.retentionPeriod ? { key: 'retentionPeriod', label: 'Retention', value: filters.retentionPeriod } : null,
        filters.accessType ? { key: 'accessType', label: 'Access', value: filters.accessType } : null,
        filters.sortBy !== 'members-desc' ? { key: 'sortBy', label: 'Sort', value: filters.sortBy } : null,
    ].filter(Boolean);

    const clearFilter = (key) => {
        switch (key) {
            case 'hasLink':
                setLocalFilters((prev) => ({ ...prev, hasLink: 'any' }));
                break;
            case 'sortBy':
                setLocalFilters((prev) => ({ ...prev, sortBy: 'members-desc' }));
                break;
            default:
                setLocalFilters((prev) => ({ ...prev, [key]: '' }));
                break;
        }
    };

    const groupStats = [
        { label: 'Total Results', value: results.length.toLocaleString() },
        { label: 'Open Groups', value: results.filter((group) => !group.adminApprovalRequired).length.toLocaleString() },
        { label: 'With Link', value: results.filter((group) => group.reconstructedLink || group.groupLink).length.toLocaleString() },
        {
            label: 'Average Members',
            value: results.length
                ? Math.round(results.reduce((sum, group) => sum + (group.numberOfMembers || 0), 0) / results.length).toLocaleString()
                : '0',
        },
    ];
    const effectiveViewMode = isMobile ? 'card' : viewMode;

    return (
        <div className="flex flex-col min-h-full">
            {/* Command Bar */}
            <div className="sticky top-0 z-20 flex-shrink-0">
                <CommandBar
                    mode="group"
                    filters={filters}
                    onFilterChange={handleFilterChange}
                    onSearch={handleSearch}
                    onReset={handleReset}
                    onExport={handleExport}
                    loading={loading}
                    extraFilterOptions={{ retentionPeriods }}
                    activeFilterCount={activeFilters.length}
                    autoCollapseSignal={searchCompletionSignal}
                    activeFilters={activeFilters}
                    onClearFilter={clearFilter}
                    sortBy={filters.sortBy}
                    onSortChange={(val) => handleFilterChange({ sortBy: val })}
                />
            </div>

            <SearchStatsBar
                stats={groupStats}
                activeFilters={activeFilters}
                onClearFilter={clearFilter}
                onReset={handleReset}
                onExport={handleExport}
                loading={loading}
                viewMode={effectiveViewMode}
                onViewModeChange={setViewMode}
                mode="group"
                sortBy={filters.sortBy}
                onSortChange={(val) => handleFilterChange({ sortBy: val })}
            />

            {/* Results */}
            {effectiveViewMode === 'table' ? (
                <GroupTableView
                    results={results}
                    loading={loading}
                    lastResultElementRef={lastResultElementRef}
                    onRowClick={handleCardClick}
                    onDrillDown={handleDrillDown}
                    onViewMembers={handleViewMembers}
                />
            ) : (
                <GroupCardView
                    results={results}
                    loading={loading}
                    lastResultElementRef={lastResultElementRef}
                    onCardClick={handleCardClick}
                    onViewMembers={handleViewMembers}
                />
            )}

            <ResultDetailModal
                isOpen={isModalOpen}
                onClose={() => setIsModalOpen(false)}
                type={modalType}
                id={selectedId}
                onDrillDown={handleDrillDown}
            />
        </div>
    );
};

export default GroupSearch;
