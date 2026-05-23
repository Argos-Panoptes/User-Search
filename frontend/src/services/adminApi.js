import apiClient from './api';

export const adminApi = {
    // Deletion endpoints
    previewUserDeletion: (serviceId) =>
        apiClient.get(`/admin/users/${encodeURIComponent(serviceId)}/deletion-preview`),

    deleteUser: (data) =>
        apiClient.post('/admin/users/delete', data),

    bulkDeleteUsers: (data) =>
        apiClient.post('/admin/users/bulk-delete', data),

    getAuditLog: (params) =>
        apiClient.get('/admin/deletions/audit-log', { params }),

    exportAuditLogCsv: () =>
        apiClient.get('/admin/deletions/audit-log/export', { responseType: 'blob' }),

    // Admin API key management
    getAllApiKeys: (params = {}) =>
        apiClient.get('/admin/api-keys', { params }),

    createApiKeyOnBehalf: (data) =>
        apiClient.post('/admin/api-keys', data),

    getAdminApiKeyDetail: (keyId) =>
        apiClient.get(`/admin/api-keys/${encodeURIComponent(keyId)}`),

    updateApiKey: (keyId, data) =>
        apiClient.patch(`/admin/api-keys/${encodeURIComponent(keyId)}`, data),

    revokeApiKey: (keyId) =>
        apiClient.delete(`/admin/api-keys/${encodeURIComponent(keyId)}`),

    // Monitoring
    getMonitoringStats: () =>
        apiClient.get('/admin/monitoring/usage/stats'),

    getKeyUsageStats: (limit = 20) =>
        apiClient.get('/admin/monitoring/usage/by-key', { params: { limit } }),

    getSystemHealth: () =>
        apiClient.get('/admin/monitoring/health'),

    getEndpointUsage: (params = {}) =>
        apiClient.get('/admin/monitoring/usage/endpoints', { params }),

    getUsageTimeline: (params = {}) =>
        apiClient.get('/admin/monitoring/usage/timeline', { params }),

    getKeyDetailUsage: (keyId, params = {}) =>
        apiClient.get(`/admin/monitoring/usage/by-key/${encodeURIComponent(keyId)}`, { params }),

    // User Limits management
    getUserLimits: (params = {}) =>
        apiClient.get('/admin/monitoring/users/limits', { params }),

    getUserLimitDetail: (userId) =>
        apiClient.get(`/admin/monitoring/users/${userId}/limits`),

    updateUserLimits: (userId, data, params = {}) =>
        apiClient.patch(`/admin/monitoring/users/${userId}/limits`, data, { params }),
};
