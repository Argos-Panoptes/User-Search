import axios from 'axios';
import { API_BASE_URL } from '../config';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true, // Always send cookies (primary B2C auth)
  headers: {
    'Content-Type': 'application/json',
  },
});

// Module-level token — set by AuthContext after login
let _jwtToken = null;

export const setJwtToken = (token) => { _jwtToken = token; };
export const clearJwtToken = () => { _jwtToken = null; };

// Attach JWT Bearer header when available (header-based auth for programmatic use)
apiClient.interceptors.request.use((config) => {
  if (_jwtToken) {
    config.headers['Authorization'] = `Bearer ${_jwtToken}`;
  }
  return config;
});

// 401 → clear token and redirect to login
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      clearJwtToken();
      if (!window.location.pathname.endsWith('/login')) {
        window.location.href = '/app/login';
      }
    }
    return Promise.reject(error);
  }
);

export default apiClient;
