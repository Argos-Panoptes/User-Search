import { configureStore } from '@reduxjs/toolkit';
import searchReducer from '../features/search/searchSlice';
import apiKeyReducer from './slices/apiKeySlice';
import monitoringReducer from './slices/monitoringSlice';

export const store = configureStore({
    reducer: {
        search: searchReducer,
        apiKeys: apiKeyReducer,
        monitoring: monitoringReducer,
    },
});
