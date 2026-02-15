/**
 * API Configuration and Axios Client
 */

import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

// Your machine's local IP address - update this if it changes
const DEV_MACHINE_IP = '10.0.0.5';

// Use environment variable to override for simulator testing
// Set EXPO_PUBLIC_SIMULATOR=true to test with iOS Simulator (uses localhost)
const USE_SIMULATOR = process.env.EXPO_PUBLIC_SIMULATOR === 'true';

// Determine API base URL based on environment and platform
const getApiBaseUrl = (): string => {
  if (!__DEV__) {
    return 'https://your-production-api.com/api/v1';
  }

  if (Platform.OS === 'android') {
    // Android Emulator special host address
    return `http://${DEV_MACHINE_IP}:8000/api/v1`;
  }

  if (Platform.OS === 'ios') {
    // iOS: use localhost for simulator (if flag set), otherwise use machine IP for physical device
    if (USE_SIMULATOR) {
      return 'http://localhost:8000/api/v1';
    }
    return `http://${DEV_MACHINE_IP}:8000/api/v1`;
  }

  // Fallback for web/other platforms
  return `http://${DEV_MACHINE_IP}:8000/api/v1`;
};

const API_BASE_URL = getApiBaseUrl();

console.log('[API] Base URL:', API_BASE_URL);
console.log('[API] Platform:', Platform.OS);
console.log('[API] USE_SIMULATOR flag:', USE_SIMULATOR);

// Token storage keys
const ACCESS_TOKEN_KEY = 'qgen_access_token';
const REFRESH_TOKEN_KEY = 'qgen_refresh_token';

// Create axios instance
export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Token management functions
export const tokenStorage = {
  async getAccessToken(): Promise<string | null> {
    try {
      return await SecureStore.getItemAsync(ACCESS_TOKEN_KEY);
    } catch {
      return null;
    }
  },

  async getRefreshToken(): Promise<string | null> {
    try {
      return await SecureStore.getItemAsync(REFRESH_TOKEN_KEY);
    } catch {
      return null;
    }
  },

  async setTokens(accessToken: string, refreshToken: string): Promise<void> {
    await SecureStore.setItemAsync(ACCESS_TOKEN_KEY, accessToken);
    await SecureStore.setItemAsync(REFRESH_TOKEN_KEY, refreshToken);
  },

  async clearTokens(): Promise<void> {
    await SecureStore.deleteItemAsync(ACCESS_TOKEN_KEY);
    await SecureStore.deleteItemAsync(REFRESH_TOKEN_KEY);
  },
};

// Request interceptor - add auth token
apiClient.interceptors.request.use(
  async (config: InternalAxiosRequestConfig) => {
    const token = await tokenStorage.getAccessToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
      console.log('[API Request]', {
        url: config.url,
        method: config.method?.toUpperCase(),
        hasAuth: true,
        tokenPreview: `${token.substring(0, 20)}...`,
      });
    } else {
      console.log('[API Request]', {
        url: config.url,
        method: config.method?.toUpperCase(),
        hasAuth: false,
      });
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor - handle token refresh
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value: unknown) => void;
  reject: (reason?: unknown) => void;
}> = [];

const processQueue = (error: Error | null, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const status = error.response?.status;
    const url = error.config?.url;
    
    console.log('[API Error]', {
      url,
      status,
      message: error.message,
      data: error.response?.data,
    });

    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    // Handle both 401 (Unauthorized) and 403 (Forbidden) with token refresh
    if ((status === 401 || status === 403) && !originalRequest._retry) {
      // Skip refresh for auth endpoints
      if (url?.includes('/auth/login') || url?.includes('/auth/register') || url?.includes('/auth/refresh')) {
        return Promise.reject(error);
      }

      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`;
          return apiClient(originalRequest);
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const refreshToken = await tokenStorage.getRefreshToken();
        if (!refreshToken) {
          console.log('[API] No refresh token available, clearing auth');
          throw new Error('No refresh token');
        }

        console.log('[API] Attempting token refresh...');
        const response = await axios.post(`${API_BASE_URL}/auth/refresh`, {
          refresh_token: refreshToken,
        });

        const { access_token, refresh_token } = response.data;
        await tokenStorage.setTokens(access_token, refresh_token);
        console.log('[API] Token refreshed successfully');

        processQueue(null, access_token);

        originalRequest.headers.Authorization = `Bearer ${access_token}`;
        return apiClient(originalRequest);
      } catch (refreshError) {
        console.log('[API] Token refresh failed, logging out');
        processQueue(refreshError as Error, null);
        await tokenStorage.clearTokens();
        
        // Import router dynamically to avoid circular dependency
        const { router } = await import('expo-router');
        router.replace('/(auth)/login');
        
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

export default apiClient;
