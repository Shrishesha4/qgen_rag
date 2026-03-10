/**
 * Toast Notification Component
 * 
 * A reusable toast notification system for displaying errors,
 * success messages, and other notifications throughout the app.
 */

import React, { createContext, useContext, useState, useCallback, useRef, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Animated,
  TouchableOpacity,
  Dimensions,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { Colors, Spacing, BorderRadius, FontSizes } from '@/constants/theme';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { extractErrorDetails } from '@/utils/errors';
import { successNotification, errorNotification, warningNotification } from '@/utils/haptics';

export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface ToastMessage {
  id: string;
  type: ToastType;
  title?: string;
  message: string;
  duration?: number;
  action?: {
    label: string;
    onPress: () => void;
  };
}

interface ToastContextValue {
  showToast: (toast: Omit<ToastMessage, 'id'>) => void;
  showError: (error: unknown, title?: string) => void;
  showSuccess: (message: string, title?: string) => void;
  showWarning: (message: string, title?: string) => void;
  showInfo: (message: string, title?: string) => void;
  hideToast: (id: string) => void;
  hideAll: () => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const TOAST_CONFIGS: Record<ToastType, {
  icon: string;
  backgroundColor: string;
  iconColor: string;
}> = {
  success: {
    icon: 'checkmark.circle.fill',
    backgroundColor: '#10B981',
    iconColor: '#FFFFFF',
  },
  error: {
    icon: 'exclamationmark.triangle.fill',
    backgroundColor: '#EF4444',
    iconColor: '#FFFFFF',
  },
  warning: {
    icon: 'exclamationmark.circle.fill',
    backgroundColor: '#F59E0B',
    iconColor: '#FFFFFF',
  },
  info: {
    icon: 'info.circle.fill',
    backgroundColor: '#3B82F6',
    iconColor: '#FFFFFF',
  },
};

const DEFAULT_DURATION = 4000;
const { width: SCREEN_WIDTH } = Dimensions.get('window');

/**
 * Individual Toast Item Component
 */
function ToastItem({
  toast,
  onHide,
}: {
  toast: ToastMessage;
  onHide: () => void;
}) {
  const colorScheme = useColorScheme();
  const colors = Colors[colorScheme ?? 'light'];
  const translateY = useRef(new Animated.Value(-100)).current;
  const opacity = useRef(new Animated.Value(0)).current;
  const config = TOAST_CONFIGS[toast.type];

  useEffect(() => {
    // Animate in
    Animated.parallel([
      Animated.spring(translateY, {
        toValue: 0,
        useNativeDriver: true,
        tension: 80,
        friction: 10,
      }),
      Animated.timing(opacity, {
        toValue: 1,
        duration: 200,
        useNativeDriver: true,
      }),
    ]).start();

    // Auto hide
    const duration = toast.duration ?? DEFAULT_DURATION;
    if (duration > 0) {
      const timer = setTimeout(() => {
        hideWithAnimation();
      }, duration);
      return () => clearTimeout(timer);
    }
  }, []);

  const hideWithAnimation = useCallback(() => {
    Animated.parallel([
      Animated.timing(translateY, {
        toValue: -100,
        duration: 200,
        useNativeDriver: true,
      }),
      Animated.timing(opacity, {
        toValue: 0,
        duration: 200,
        useNativeDriver: true,
      }),
    ]).start(() => onHide());
  }, [onHide]);

  return (
    <Animated.View
      style={[
        styles.toastContainer,
        {
          backgroundColor: colors.card,
          borderLeftColor: config.backgroundColor,
          transform: [{ translateY }],
          opacity,
        },
      ]}
    >
      <View style={[styles.iconContainer, { backgroundColor: config.backgroundColor }]}>
        <IconSymbol name={config.icon as any} size={20} color={config.iconColor} />
      </View>
      <View style={styles.contentContainer}>
        {toast.title && (
          <Text style={[styles.title, { color: colors.text }]}>{toast.title}</Text>
        )}
        <Text
          style={[styles.message, { color: toast.title ? colors.textSecondary : colors.text }]}
          numberOfLines={3}
        >
          {toast.message}
        </Text>
        {toast.action && (
          <TouchableOpacity
            style={[styles.actionButton, { backgroundColor: config.backgroundColor + '20' }]}
            onPress={() => {
              toast.action?.onPress();
              hideWithAnimation();
            }}
          >
            <Text style={[styles.actionText, { color: config.backgroundColor }]}>
              {toast.action.label}
            </Text>
          </TouchableOpacity>
        )}
      </View>
      <TouchableOpacity style={styles.closeButton} onPress={hideWithAnimation}>
        <IconSymbol name="xmark" size={16} color={colors.textSecondary} />
      </TouchableOpacity>
    </Animated.View>
  );
}

/**
 * Toast Provider Component
 */
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const insets = useSafeAreaInsets();
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const generateId = useCallback(() => {
    return `toast-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }, []);

  const showToast = useCallback((toast: Omit<ToastMessage, 'id'>) => {
    const id = generateId();
    setToasts((prev) => [...prev.slice(-2), { ...toast, id }]); // Keep max 3 toasts
  }, []);

  const showError = useCallback((error: unknown, title?: string) => {
    errorNotification();
    const details = extractErrorDetails(error);
    showToast({
      type: 'error',
      title: title || (details.isNetworkError ? 'Connection Error' : 'Error'),
      message: details.message,
      duration: details.isNetworkError ? 6000 : DEFAULT_DURATION,
    });
  }, [showToast]);

  const showSuccess = useCallback((message: string, title?: string) => {
    successNotification();
    showToast({
      type: 'success',
      title,
      message,
    });
  }, [showToast]);

  const showWarning = useCallback((message: string, title?: string) => {
    warningNotification();
    showToast({
      type: 'warning',
      title,
      message,
    });
  }, [showToast]);

  const showInfo = useCallback((message: string, title?: string) => {
    showToast({
      type: 'info',
      title,
      message,
    });
  }, [showToast]);

  const hideToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const hideAll = useCallback(() => {
    setToasts([]);
  }, []);

  return (
    <ToastContext.Provider
      value={{ showToast, showError, showSuccess, showWarning, showInfo, hideToast, hideAll }}
    >
      {children}
      <View style={[styles.toastsWrapper, { top: insets.top + 10, pointerEvents: 'box-none' }]}>
        {toasts.map((toast) => (
          <ToastItem key={toast.id} toast={toast} onHide={() => hideToast(toast.id)} />
        ))}
      </View>
    </ToastContext.Provider>
  );
}

/**
 * Hook to access toast functions
 */
export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
}

const styles = StyleSheet.create({
  toastsWrapper: {
    position: 'absolute',
    left: 0,
    right: 0,
    alignItems: 'center',
    zIndex: 9999,
    gap: Spacing.sm,
  },
  toastContainer: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    width: SCREEN_WIDTH - Spacing.lg * 2,
    maxWidth: 500,
    borderRadius: BorderRadius.md,
    borderLeftWidth: 4,
    padding: Spacing.md,
    boxShadow: '0px 4px 12px rgba(0,0,0,0.15)',
    elevation: 8,
  },
  iconContainer: {
    width: 32,
    height: 32,
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: Spacing.sm,
  },
  contentContainer: {
    flex: 1,
    marginRight: Spacing.sm,
  },
  title: {
    fontSize: FontSizes.md,
    fontWeight: '600',
    marginBottom: 2,
  },
  message: {
    fontSize: FontSizes.sm,
    lineHeight: 20,
  },
  actionButton: {
    alignSelf: 'flex-start',
    marginTop: Spacing.sm,
    paddingHorizontal: Spacing.sm,
    paddingVertical: Spacing.xs,
    borderRadius: BorderRadius.sm,
  },
  actionText: {
    fontSize: FontSizes.sm,
    fontWeight: '600',
  },
  closeButton: {
    padding: Spacing.xs,
    marginTop: -Spacing.xs,
    marginRight: -Spacing.xs,
  },
});
