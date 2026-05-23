import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import { apiKeyApi } from '../../services/apiKeyApi';

export const fetchMyApiKeys = createAsyncThunk(
    'apiKeys/fetchMyApiKeys',
    async (params = {}, { rejectWithValue }) => {
        try {
            const res = await apiKeyApi.getMyApiKeys(params);
            return res.data;
        } catch (err) {
            return rejectWithValue(err.response?.data?.detail || 'Failed to fetch API keys');
        }
    }
);

export const createApiKey = createAsyncThunk(
    'apiKeys/createApiKey',
    async (data, { rejectWithValue }) => {
        try {
            const res = await apiKeyApi.createApiKey(data);
            return res.data;
        } catch (err) {
            return rejectWithValue(err.response?.data?.detail || 'Failed to create API key');
        }
    }
);

export const revokeApiKey = createAsyncThunk(
    'apiKeys/revokeApiKey',
    async (keyId, { rejectWithValue }) => {
        try {
            const res = await apiKeyApi.revokeApiKey(keyId);
            return { keyId, ...res.data };
        } catch (err) {
            return rejectWithValue(err.response?.data?.detail || 'Failed to revoke API key');
        }
    }
);

const apiKeySlice = createSlice({
    name: 'apiKeys',
    initialState: {
        keys: [],
        pagination: null,
        loading: false,
        error: null,
        createdKey: null,
    },
    reducers: {
        clearCreatedKey: (state) => {
            state.createdKey = null;
        },
        clearError: (state) => {
            state.error = null;
        },
    },
    extraReducers: (builder) => {
        builder
            .addCase(fetchMyApiKeys.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            .addCase(fetchMyApiKeys.fulfilled, (state, action) => {
                state.loading = false;
                state.keys = action.payload.data || [];
                state.pagination = action.payload.pagination || null;
            })
            .addCase(fetchMyApiKeys.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload;
            })
            .addCase(createApiKey.fulfilled, (state, action) => {
                state.createdKey = action.payload.data || action.payload;
            })
            .addCase(createApiKey.rejected, (state, action) => {
                state.error = action.payload;
            })
            .addCase(revokeApiKey.fulfilled, (state, action) => {
                state.keys = state.keys.filter(k => k.key_id !== action.payload.keyId);
            });
    },
});

export const { clearCreatedKey, clearError } = apiKeySlice.actions;
export default apiKeySlice.reducer;
