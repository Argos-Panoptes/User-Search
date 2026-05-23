import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import { adminApi } from '../../services/adminApi';

export const fetchMonitoringStats = createAsyncThunk(
    'monitoring/fetchStats',
    async (_, { rejectWithValue }) => {
        try {
            const res = await adminApi.getMonitoringStats();
            return res.data;
        } catch (err) {
            return rejectWithValue(err.response?.data?.detail || 'Failed to fetch stats');
        }
    }
);

export const fetchKeyUsageStats = createAsyncThunk(
    'monitoring/fetchKeyUsage',
    async (limit = 20, { rejectWithValue }) => {
        try {
            const res = await adminApi.getKeyUsageStats(limit);
            return res.data;
        } catch (err) {
            return rejectWithValue(err.response?.data?.detail || 'Failed to fetch key usage');
        }
    }
);

export const fetchSystemHealth = createAsyncThunk(
    'monitoring/fetchHealth',
    async (_, { rejectWithValue }) => {
        try {
            const res = await adminApi.getSystemHealth();
            return res.data;
        } catch (err) {
            return rejectWithValue(err.response?.data?.detail || 'Failed to fetch health');
        }
    }
);

export const fetchEndpointUsage = createAsyncThunk(
    'monitoring/fetchEndpointUsage',
    async (params = {}, { rejectWithValue }) => {
        try {
            const res = await adminApi.getEndpointUsage(params);
            return res.data;
        } catch (err) {
            return rejectWithValue(err.response?.data?.detail || 'Failed to fetch endpoint usage');
        }
    }
);

export const fetchUsageTimeline = createAsyncThunk(
    'monitoring/fetchTimeline',
    async (params = {}, { rejectWithValue }) => {
        try {
            const res = await adminApi.getUsageTimeline(params);
            return res.data;
        } catch (err) {
            return rejectWithValue(err.response?.data?.detail || 'Failed to fetch timeline');
        }
    }
);

export const fetchKeyDetailUsage = createAsyncThunk(
    'monitoring/fetchKeyDetail',
    async ({ keyId, params = {} }, { rejectWithValue }) => {
        try {
            const res = await adminApi.getKeyDetailUsage(keyId, params);
            return res.data;
        } catch (err) {
            return rejectWithValue(err.response?.data?.detail || 'Failed to fetch key detail');
        }
    }
);

const monitoringSlice = createSlice({
    name: 'monitoring',
    initialState: {
        stats: null,
        keyUsage: [],
        health: null,
        endpointUsage: [],
        timeline: [],
        keyDetail: null,
        timeRange: '24h',
        selectedKeyId: null,
        loading: false,
        error: null,
    },
    reducers: {
        setTimeRange: (state, action) => {
            state.timeRange = action.payload;
        },
        setSelectedKeyId: (state, action) => {
            state.selectedKeyId = action.payload;
        },
        clearKeyDetail: (state) => {
            state.keyDetail = null;
        },
    },
    extraReducers: (builder) => {
        builder
            .addCase(fetchMonitoringStats.pending, (state) => { state.loading = true; })
            .addCase(fetchMonitoringStats.fulfilled, (state, action) => {
                state.loading = false;
                state.stats = action.payload.data || action.payload;
            })
            .addCase(fetchMonitoringStats.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload;
            })
            .addCase(fetchKeyUsageStats.fulfilled, (state, action) => {
                state.keyUsage = action.payload.data || [];
            })
            .addCase(fetchSystemHealth.fulfilled, (state, action) => {
                state.health = action.payload.data || action.payload;
            })
            .addCase(fetchEndpointUsage.fulfilled, (state, action) => {
                state.endpointUsage = action.payload.data || [];
            })
            .addCase(fetchUsageTimeline.fulfilled, (state, action) => {
                state.timeline = action.payload.data || [];
            })
            .addCase(fetchKeyDetailUsage.fulfilled, (state, action) => {
                state.keyDetail = action.payload.data || action.payload;
            })
            .addCase(fetchKeyDetailUsage.rejected, (state) => {
                state.keyDetail = null;
            });
    },
});

export const { setTimeRange, setSelectedKeyId, clearKeyDetail } = monitoringSlice.actions;
export default monitoringSlice.reducer;
