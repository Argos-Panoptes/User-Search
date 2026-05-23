import apiClient from './api';

export const apiKeyApi = {
    // User self-service endpoints
    getMyApiKeys: (params = {}) =>
        apiClient.get('/api-keys', { params }),

    createApiKey: (data) =>
        apiClient.post('/api-keys', data),

    getApiKeyDetail: (keyId) =>
        apiClient.get(`/api-keys/${encodeURIComponent(keyId)}`),

    updateApiKey: (keyId, data) =>
        apiClient.patch(`/api-keys/${encodeURIComponent(keyId)}`, data),

    revokeApiKey: (keyId) =>
        apiClient.delete(`/api-keys/${encodeURIComponent(keyId)}`),
};
