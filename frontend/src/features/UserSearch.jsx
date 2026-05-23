import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router';
import { useDispatch, useSelector } from 'react-redux';
import { setFilters, resetFilters, selectFilters } from '../features/search/searchSlice';
import apiClient from '../services/api';
import ResultDetailModal from './ResultDetailModal';
import CommandBar from '../components/common/CommandBar';
import SearchStatsBar from '../components/common/SearchStatsBar';
import UserTableView from '../components/common/UserTableView';
import UserCardView from '../components/common/UserCardView';
import useIsMobile from '../hooks/useIsMobile';

const UserSearch = () => {
    const [searchParams, setSearchParams] = useSearchParams();
    const dispatch = useDispatch();
    const filters = useSelector(selectFilters);
    const isMobile = useIsMobile();

    const [initialized, setInitialized] = useState(false);

    // Init filters from URL on mount
    useEffect(() => {
        const urlFilters = {
            serviceId: searchParams.get('serviceId') || '',
            name: searchParams.get('name') || '',
            about: searchParams.get('about') || '',
            e164: searchParams.get('phone') || '',
            groupId: searchParams.get('groupId') || '',
            groupName: searchParams.get('groupName') || '',
            minGroupCount: searchParams.get('minGroupCount') || '',
            maxGroupCount: searchParams.get('maxGroupCount') || '',
            phoneStatus: searchParams.get('phoneStatus') || 'all',
            isAdmin: searchParams.get('isAdmin') === 'true',
            hasAvatar: searchParams.get('hasAvatar') === 'true'
        };
        dispatch(setFilters(urlFilters));
        setInitialized(true);
    }, []);

    const [page, setPage] = useState(0);
    const [hasMore, setHasMore] = useState(true);
    const [loading, setLoading] = useState(false);
    const [results, setResults] = useState([]);
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [selectedId, setSelectedId] = useState(null);
    const [modalType, setModalType] = useState('user');
    const [downloadingId, setDownloadingId] = useState(null);
    const [viewMode, setViewMode] = useState('card');
    const [searchCompletionSignal, setSearchCompletionSignal] = useState(0);
    const [sortBy, setSortBy] = useState('');

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

    const handleFilterChange = (updates) => {
        dispatch(setFilters(updates));
    };

    // Reset page and search when filters or sort change (with debounce)
    useEffect(() => {
        if (!initialized) return;
        setPage(0);
        setHasMore(true);

        const handler = setTimeout(() => {
            searchUsers(false);
        }, 500);

        return () => clearTimeout(handler);
    }, [filters, sortBy, initialized]);

    // Fetch more when page changes
    useEffect(() => {
        if (page > 0) {
            searchUsers(true);
        }
    }, [page]);

    const updateURL = () => {
        const params = {};
        if (filters.serviceId) params.serviceId = filters.serviceId;
        if (filters.name) params.name = filters.name;
        if (filters.about) params.about = filters.about;
        if (filters.e164) params.phone = filters.e164;
        if (filters.groupId) params.groupId = filters.groupId;
        if (filters.groupName) params.groupName = filters.groupName;
        if (filters.minGroupCount) params.minGroupCount = filters.minGroupCount;
        if (filters.maxGroupCount) params.maxGroupCount = filters.maxGroupCount;
        if (filters.phoneStatus !== 'all') params.phoneStatus = filters.phoneStatus;
        if (filters.isAdmin) params.isAdmin = 'true';
        if (filters.hasAvatar) params.hasAvatar = 'true';
        setSearchParams(params, { replace: true });
    };

    useEffect(() => {
        if (!initialized) return;
        updateURL();
    }, [filters, initialized]);

    const searchUsers = async (isLoadMore = false) => {
        setLoading(true);
        try {
            const limit = 50;
            const offset = (isLoadMore ? page : 0) * limit;

            const params = {
                limit,
                offset,
                service_id: filters.serviceId || undefined,
                name: filters.name || undefined,
                about: filters.about || undefined,
                e164: filters.e164 || undefined,
                min_group_count: filters.minGroupCount ? parseInt(filters.minGroupCount) : undefined,
                max_group_count: filters.maxGroupCount ? parseInt(filters.maxGroupCount) : undefined,
                group_id: filters.groupId || undefined,
                group_name: (!filters.groupId && filters.groupName) ? filters.groupName : undefined,
                is_admin: filters.isAdmin ? true : undefined,
                has_phone: filters.phoneStatus === 'all' ? undefined : (filters.phoneStatus === 'present'),
                has_avatar: filters.hasAvatar ? true : undefined,
                sort_by: sortBy || undefined,
            };

            const response = await apiClient.post('/users/search', params);
            const rawData = response.data?.data;
            const newResults = Array.isArray(rawData) ? rawData : [];

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

    const handleRowClick = (id) => {
        setSelectedId(id);
        setModalType('user');
        setIsModalOpen(true);
    };

    const handleDrillDown = (type, id) => {
        setSelectedId(id);
        setModalType(type);
        setIsModalOpen(true);
    };

    const handleDownloadUser = async (e, user) => {
        e.stopPropagation();
        if (!user.avatarId) return;

        setDownloadingId(user.id || user.serviceId);
        try {
            const response = await apiClient.get(`/media/${user.avatarId}/download`);
            const imageUrl = response.data?.url;
            if (!imageUrl) return;

            const filename = `${user.profileName || user.name || 'user'}_avatar.jpg`;
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
            setDownloadingId(null);
        }
    };

    const handleSearch = () => {
        setPage(0);
        searchUsers(false);
    };

    const handleExport = async () => {
        if (loading) return;
        try {
            const params = {
                service_id: filters.serviceId || undefined,
                name: filters.name || undefined,
                about: filters.about || undefined,
                e164: filters.e164 || undefined,
                min_group_count: filters.minGroupCount ? parseInt(filters.minGroupCount) : undefined,
                max_group_count: filters.maxGroupCount ? parseInt(filters.maxGroupCount) : undefined,
                group_id: filters.groupId || undefined,
                is_admin: filters.isAdmin ? true : undefined,
                has_phone: filters.phoneStatus === 'all' ? undefined : (filters.phoneStatus === 'present'),
                has_avatar: filters.hasAvatar ? true : undefined
            };

            const response = await apiClient.post('/users/export', params, { responseType: 'blob' });

            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', 'users_export.csv');
            document.body.appendChild(link);
            link.click();
            link.remove();
        } catch (error) {
            console.error("Export failed", error);
        }
    };

    const handleReset = () => {
        dispatch(resetFilters());
    };

    const activeFilters = [
        filters.serviceId ? { key: 'serviceId', label: 'Service ID', value: filters.serviceId } : null,
        filters.name ? { key: 'name', label: 'Name', value: filters.name } : null,
        filters.about ? { key: 'about', label: 'About', value: filters.about } : null,
        filters.e164 ? { key: 'e164', label: 'Phone', value: filters.e164 } : null,
        (filters.groupId || filters.groupName) ? { key: 'group', label: 'Group', value: filters.groupName || filters.groupId } : null,
        filters.minGroupCount ? { key: 'minGroupCount', label: 'Min Groups', value: filters.minGroupCount } : null,
        filters.maxGroupCount ? { key: 'maxGroupCount', label: 'Max Groups', value: filters.maxGroupCount } : null,
        filters.phoneStatus !== 'all' ? { key: 'phoneStatus', label: 'Phone Status', value: filters.phoneStatus } : null,
        filters.isAdmin ? { key: 'isAdmin', label: 'Admin', value: 'On' } : null,
        filters.hasAvatar ? { key: 'hasAvatar', label: 'Has Avatar', value: 'On' } : null,
    ].filter(Boolean);

    const clearFilter = (key) => {
        switch (key) {
            case 'phoneStatus':
                dispatch(setFilters({ phoneStatus: 'all' }));
                break;
            case 'isAdmin':
                dispatch(setFilters({ isAdmin: false }));
                break;
            case 'hasAvatar':
                dispatch(setFilters({ hasAvatar: false }));
                break;
            case 'group':
                dispatch(setFilters({ groupId: '', groupName: '' }));
                break;
            default:
                dispatch(setFilters({ [key]: '' }));
                break;
        }
    };

    const userStats = [
        { label: 'Total Results', value: results.length.toLocaleString() },
        { label: 'Admins', value: results.filter((user) => user.isAdmin).length.toLocaleString() },
        { label: 'With Avatar', value: results.filter((user) => user.avatarId || user.remoteAvatarUrl).length.toLocaleString() },
        {
            label: 'Average Groups',
            value: results.length
                ? (results.reduce((sum, user) => sum + (user.groupCount || user.groupMemberships?.length || 0), 0) / results.length).toFixed(1)
                : '0.0',
        },
    ];
    const effectiveViewMode = isMobile ? 'card' : viewMode;

    return (
        <div className="flex flex-col min-h-full">
            {/* Command Bar - Sticky top */}
            <div className="sticky top-0 z-20 flex-shrink-0">
                <CommandBar
                    mode="user"
                    filters={filters}
                    onFilterChange={handleFilterChange}
                    onSearch={handleSearch}
                    onReset={handleReset}
                    onExport={handleExport}
                    loading={loading}
                    activeFilterCount={activeFilters.length}
                    autoCollapseSignal={searchCompletionSignal}
                    activeFilters={activeFilters}
                    onClearFilter={clearFilter}
                    sortBy={sortBy}
                    onSortChange={setSortBy}
                />
            </div>

            <SearchStatsBar
                stats={userStats}
                activeFilters={activeFilters}
                onClearFilter={clearFilter}
                onReset={handleReset}
                onExport={handleExport}
                loading={loading}
                viewMode={effectiveViewMode}
                onViewModeChange={setViewMode}
                sortBy={sortBy}
                onSortChange={setSortBy}
            />

            {/* Results Area */}
            {effectiveViewMode === 'table' ? (
                <UserTableView
                    results={results}
                    loading={loading}
                    lastResultElementRef={lastResultElementRef}
                    onRowClick={handleRowClick}
                    onDrillDown={handleDrillDown}
                    onDownload={handleDownloadUser}
                    downloadingId={downloadingId}
                />
            ) : (
                <UserCardView
                    results={results}
                    loading={loading}
                    lastResultElementRef={lastResultElementRef}
                    onCardClick={handleRowClick}
                    onDrillDown={handleDrillDown}
                    onDownload={handleDownloadUser}
                    downloadingId={downloadingId}
                />
            )}

            {/* Detail Modal (for Full View from inline panel) */}
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

export default UserSearch;
