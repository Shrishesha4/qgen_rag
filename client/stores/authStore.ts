/**
 * Authentication Store using Zustand
 */

import { create } from 'zustand';
import { authService, User, UpdateProfileData } from '../services/auth';
import { tokenStorage } from '../services/api';

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  // Actions
  login: (email: string, password: string) => Promise<boolean>;
  register: (email: string, username: string, password: string, fullName?: string) => Promise<boolean>;
  logout: () => Promise<void>;
  logoutAll: () => Promise<void>;
  checkAuth: () => Promise<boolean>;
  updateProfile: (data: UpdateProfileData) => Promise<void>;
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>;
  uploadAvatar: (uri: string) => Promise<void>;
  deleteAvatar: () => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  isAuthenticated: false,
  isLoading: true,
  error: null,

  login: async (email: string, password: string): Promise<boolean> => {
    set({ isLoading: true, error: null });
    try {
      const response = await authService.login({ email, password });
      set({
        user: response.user,
        isAuthenticated: true,
        isLoading: false,
      });
      return true;
    } catch (error: unknown) {
      const message = error instanceof Error
        ? error.message
        : (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Login failed';
      set({ error: message, isLoading: false });
      return false;
    }
  },

  register: async (email: string, username: string, password: string, fullName?: string): Promise<boolean> => {
    set({ isLoading: true, error: null });
    try {
      const response = await authService.register({
        email,
        username,
        password,
        full_name: fullName,
      });
      set({
        user: response.user,
        isAuthenticated: true,
        isLoading: false,
      });
      return true;
    } catch (error: unknown) {
      const message = error instanceof Error
        ? error.message
        : (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Registration failed';
      set({ error: message, isLoading: false });
      return false;
    }
  },

  logout: async (): Promise<void> => {
    set({ isLoading: true });
    try {
      await authService.logout();
    } finally {
      set({
        user: null,
        isAuthenticated: false,
        isLoading: false,
        error: null,
      });
    }
  },

  logoutAll: async (): Promise<void> => {
    set({ isLoading: true });
    try {
      await authService.logoutAll();
    } finally {
      set({
        user: null,
        isAuthenticated: false,
        isLoading: false,
        error: null,
      });
    }
  },

  checkAuth: async (): Promise<boolean> => {
    set({ isLoading: true });
    try {
      const hasToken = await authService.isAuthenticated();
      if (!hasToken) {
        set({ isAuthenticated: false, user: null, isLoading: false });
        return false;
      }

      const user = await authService.getCurrentUser();
      set({
        user,
        isAuthenticated: true,
        isLoading: false,
      });
      return true;
    } catch {
      await tokenStorage.clearTokens();
      set({
        user: null,
        isAuthenticated: false,
        isLoading: false,
      });
      return false;
    }
  },

  updateProfile: async (data: UpdateProfileData): Promise<void> => {
    set({ isLoading: true, error: null });
    try {
      const updatedUser = await authService.updateProfile(data);
      set({
        user: updatedUser,
        isLoading: false,
      });
    } catch (error: unknown) {
      const message = error instanceof Error
        ? error.message
        : 'Failed to update profile';
      set({ error: message, isLoading: false });
      throw error;
    }
  },

  changePassword: async (currentPassword: string, newPassword: string): Promise<void> => {
    set({ isLoading: true, error: null });
    try {
      await authService.changePassword({ current_password: currentPassword, new_password: newPassword });
      set({ isLoading: false });
    } catch (error: unknown) {
      const message = error instanceof Error
        ? error.message
        : 'Failed to change password';
      set({ error: message, isLoading: false });
      throw error;
    }
  },

  uploadAvatar: async (uri: string): Promise<void> => {
    set({ isLoading: true, error: null });
    try {
      const updatedUser = await authService.uploadAvatar(uri);
      set({
        user: updatedUser,
        isLoading: false,
      });
    } catch (error: unknown) {
      const message = error instanceof Error
        ? error.message
        : 'Failed to upload avatar';
      set({ error: message, isLoading: false });
      throw error;
    }
  },

  deleteAvatar: async (): Promise<void> => {
    set({ isLoading: true, error: null });
    try {
      const updatedUser = await authService.deleteAvatar();
      set({
        user: updatedUser,
        isLoading: false,
      });
    } catch (error: unknown) {
      const message = error instanceof Error
        ? error.message
        : 'Failed to delete avatar';
      set({ error: message, isLoading: false });
      throw error;
    }
  },

  clearError: (): void => {
    set({ error: null });
  },
}));

export default useAuthStore;
