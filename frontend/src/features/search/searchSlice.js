import { createSlice } from '@reduxjs/toolkit';

const initialState = {
    filters: {
        serviceId: '',
        name: '', // Maps to 'q'
        about: '',
        e164: '', // Unified phone field
        groupId: '',
        groupName: '',
        minGroupCount: '',
        maxGroupCount: '',
        phoneStatus: 'all', // 'all', 'present', 'missing'
        isAdmin: false,
        hasAvatar: false,
    },
};

const searchSlice = createSlice({
    name: 'search',
    initialState,
    reducers: {
        setFilters: (state, action) => {
            // Merge new filters with existing ones
            state.filters = { ...state.filters, ...action.payload };
        },
        resetFilters: (state) => {
            state.filters = initialState.filters;
        },
        setFilterValue: (state, action) => {
            const { key, value } = action.payload;
            if (key in state.filters) {
                state.filters[key] = value;
            }
        }
    },
});

export const { setFilters, resetFilters, setFilterValue } = searchSlice.actions;

export const selectFilters = (state) => state.search.filters;

export default searchSlice.reducer;
