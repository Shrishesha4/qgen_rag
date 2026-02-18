/**
 * Authentication API Service
 */

import apiClient, { tokenStorage } from './api';

export interface User {
  id: string;
  email: string;
  username: string;
  full_name: string | null;
  avatar_url: string | null;
  timezone: string;
  language: string;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
  preferences: Record<string, unknown> | null;
  // Novelty settings
  novelty_threshold: number;
  max_regeneration_attempts: number;
  subject_reference_materials: Record<string, string[]> | null;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterData {
  email: string;
  username: string;
  password: string;
  full_name?: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface UpdateProfileData {
  full_name?: string;
  timezone?: string;
  language?: string;
  preferences?: Record<string, unknown>;
  novelty_threshold?: number;
  max_regeneration_attempts?: number;
}

export interface PasswordChangeData {
  current_password: string;
  new_password: string;
}

export const authService = {
  /**
   * Register a new user
   */
  async register(data: RegisterData): Promise<TokenResponse> {
    const response = await apiClient.post<TokenResponse>('/auth/register', data);
    await tokenStorage.setTokens(response.data.access_token, response.data.refresh_token);
    return response.data;
  },

  /**
   * Login with email and password
   */
  async login(credentials: LoginCredentials): Promise<TokenResponse> {
    const response = await apiClient.post<TokenResponse>('/auth/login', credentials);
    await tokenStorage.setTokens(response.data.access_token, response.data.refresh_token);
    return response.data;
  },

  /**
   * Logout from current session
   */
  async logout(): Promise<void> {
    try {
      const refreshToken = await tokenStorage.getRefreshToken();
      if (refreshToken) {
        await apiClient.post('/auth/logout', { refresh_token: refreshToken });
      }
    } finally {
      await tokenStorage.clearTokens();
    }
  },

  /**
   * Logout from all devices
   */
  async logoutAll(): Promise<{ sessions_revoked: number }> {
    const response = await apiClient.post<{ message: string; sessions_revoked: number }>(
      '/auth/logout-all'
    );
    await tokenStorage.clearTokens();
    return response.data;
  },

  /**
   * Get current user profile
   */
  async getCurrentUser(): Promise<User> {
    const response = await apiClient.get<User>('/auth/me');
    return response.data;
  },

  /**
   * Update user profile
   */
  async updateProfile(data: UpdateProfileData): Promise<User> {
    const response = await apiClient.put<User>('/auth/update-profile', data);
    return response.data;
  },

  /**
   * Change password
   */
  async changePassword(data: PasswordChangeData): Promise<void> {
    await apiClient.post('/auth/change-password', data);
  },

  /**
   * Get active sessions
   */
  async getSessions(): Promise<Array<{
    id: string;
    device_name: string | null;
    device_type: string | null;
    ip_address: string | null;
    last_activity: string;
    is_current: boolean;
  }>> {
    const response = await apiClient.get('/auth/sessions');
    return response.data.sessions;
  },

  /**
   * Check if user is authenticated
   */
  async isAuthenticated(): Promise<boolean> {
    const token = await tokenStorage.getAccessToken();
    return !!token;
  },
};

export default authService;
