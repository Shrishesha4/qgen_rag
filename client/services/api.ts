/**
 * API Configuration and Axios Client
 */

import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import { Platform } from 'react-native';
import { ENV_CONFIG, isSimulator } from '../config/env';

// Platform-aware token storage: SecureStore on native, localStorage on web
const ACCESS_TOKEN_KEY = 'qgen_access_token';
const REFRESH_TOKEN_KEY = 'qgen_refresh_token';

interface TokenStorage {
  getAccessToken(): Promise<string | null>;
  getRefreshToken(): Promise<string | null>;
  setTokens(accessToken: string, refreshToken: string): Promise<void>;
  clearTokens(): Promise<void>;
}

const createTokenStorage = (): TokenStorage => {
  if (Platform.OS === 'web') {
    return {
      async getAccessToken(): Promise<string | null> {
        try { return localStorage.getItem(ACCESS_TOKEN_KEY); } catch { return null; }
      },
      async getRefreshToken(): Promise<string | null> {
        try { return localStorage.getItem(REFRESH_TOKEN_KEY); } catch { return null; }
      },
      async setTokens(accessToken: string, refreshToken: string): Promise<void> {
        localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
        localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
      },
      async clearTokens(): Promise<void> {
        localStorage.removeItem(ACCESS_TOKEN_KEY);
        localStorage.removeItem(REFRESH_TOKEN_KEY);
      },
    };
  }

  // Native: use SecureStore
  // Lazy require to avoid crashing on web during module evaluation
  const SecureStore = require('expo-secure-store') as typeof import('expo-secure-store');
  return {
    async getAccessToken(): Promise<string | null> {
      try { return await SecureStore.getItemAsync(ACCESS_TOKEN_KEY); } catch { return null; }
    },
    async getRefreshToken(): Promise<string | null> {
      try { return await SecureStore.getItemAsync(REFRESH_TOKEN_KEY); } catch { return null; }
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
};

export const tokenStorage = createTokenStorage();

const getApiBaseUrl = (): string => {
  // Always use production URL for release builds
  if (!__DEV__) {
    return ENV_CONFIG.PRODUCTION_API_URL;
  }

  // In dev, allow override via env variable to use production URL
  if (ENV_CONFIG.USE_PRODUCTION_API === 'true') {
    return ENV_CONFIG.PRODUCTION_API_URL;
  }

  if (Platform.OS === 'android') {
    // Android Emulator special host address
    return `http://${ENV_CONFIG.DEV_MACHINE_IP}:8000/api/v1`;
  }

  if (Platform.OS === 'ios') {
    // iOS: use localhost for simulator (if flag set), otherwise use machine IP for physical device
    if (isSimulator()) {
      return 'http://localhost:8000/api/v1';
    }
    return `http://${ENV_CONFIG.DEV_MACHINE_IP}:8000/api/v1`;
  }

  // Fallback for web/other platforms — use localhost in dev
  if (Platform.OS === 'web') {
    return 'http://localhost:8000/api/v1';
  }

  return `http://${ENV_CONFIG.DEV_MACHINE_IP}:8000/api/v1`;
};

export const API_BASE_URL = getApiBaseUrl();

// Create axios instance
export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

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
          console.log('[API] No refresh token available — clearing auth and redirecting to login');

          // Clear any stored tokens and redirect to the login screen immediately
          await tokenStorage.clearTokens();
          try {
            const { router } = await import('expo-router');
            router.replace('/(auth)/login');
          } catch (routerError) {
            console.error('[API] Failed to redirect to login:', routerError);
          }

          // Build a normalized AxiosError with 401 response so UI helpers treat this as an auth error
          const authResponse = {
            data: { detail: 'No refresh token' },
            status: 401,
            statusText: 'Unauthorized',
            headers: {},
            config: originalRequest,
          } as any;

          const axiosAuthError = new AxiosError('No refresh token', 'AUTH_EXPIRED', originalRequest, undefined, authResponse);

          // Reject any queued requests and stop the refresh flow
          processQueue(axiosAuthError as unknown as Error, null);
          isRefreshing = false;
          return Promise.reject(axiosAuthError);
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
        try {
          const { router } = await import('expo-router');
          router.replace('/(auth)/login');
        } catch (routerError) {
          console.error('[API] Failed to redirect to login:', routerError);
        }

        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

export default apiClient;
