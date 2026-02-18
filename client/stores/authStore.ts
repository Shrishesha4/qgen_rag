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
  
  // Novelty settings (cached from user)
  noveltyThreshold: number;
  maxRegenerationAttempts: number;
  
  // Actions
  login: (email: string, password: string) => Promise<boolean>;
  register: (email: string, username: string, password: string, fullName?: string) => Promise<boolean>;
  logout: () => Promise<void>;
  logoutAll: () => Promise<void>;
  checkAuth: () => Promise<boolean>;
  updateProfile: (data: UpdateProfileData) => Promise<void>;
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>;
  setNoveltyThreshold: (value: number) => Promise<void>;
  setMaxRegenerationAttempts: (value: number) => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  isAuthenticated: false,
  isLoading: true,
  error: null,
  noveltyThreshold: 0.3,
  maxRegenerationAttempts: 3,

  login: async (email: string, password: string): Promise<boolean> => {
    set({ isLoading: true, error: null });
    try {
      const response = await authService.login({ email, password });
      set({
        user: response.user,
        isAuthenticated: true,
        isLoading: false,
        noveltyThreshold: response.user.novelty_threshold ?? 0.3,
        maxRegenerationAttempts: response.user.max_regeneration_attempts ?? 3,
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
        noveltyThreshold: response.user.novelty_threshold ?? 0.3,
        maxRegenerationAttempts: response.user.max_regeneration_attempts ?? 3,
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
        noveltyThreshold: user.novelty_threshold ?? 0.3,
        maxRegenerationAttempts: user.max_regeneration_attempts ?? 3,
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
        noveltyThreshold: updatedUser.novelty_threshold ?? get().noveltyThreshold,
        maxRegenerationAttempts: updatedUser.max_regeneration_attempts ?? get().maxRegenerationAttempts,
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

  clearError: (): void => {
    set({ error: null });
  },

  setNoveltyThreshold: async (value: number): Promise<void> => {
    const previousValue = get().noveltyThreshold;
    // Optimistic update
    set({ noveltyThreshold: value });
    try {
      await authService.updateProfile({ novelty_threshold: value });
    } catch (error) {
      // Revert on failure
      set({ noveltyThreshold: previousValue });
      throw error;
    }
  },

  setMaxRegenerationAttempts: async (value: number): Promise<void> => {
    const previousValue = get().maxRegenerationAttempts;
    // Optimistic update
    set({ maxRegenerationAttempts: value });
    try {
      await authService.updateProfile({ max_regeneration_attempts: value });
    } catch (error) {
      // Revert on failure
      set({ maxRegenerationAttempts: previousValue });
      throw error;
    }
  },
}));

export default useAuthStore;
