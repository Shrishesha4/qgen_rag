import { DarkTheme, DefaultTheme, ThemeProvider } from '@react-navigation/native';
import { Stack, useRouter, useSegments, usePathname } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';
import 'react-native-reanimated';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { Platform } from 'react-native';

import { useColorScheme } from '@/hooks/use-color-scheme';
import { useAuthStore } from '@/stores/authStore';
import { View, ActivityIndicator } from 'react-native';
import { ToastProvider } from '@/components/toast';
import { ErrorBoundary } from '@/components/error-boundary';

/**
 * Blurs the focused DOM element whenever the route changes on web.
 *
 * React Navigation marks inactive Stack screens with aria-hidden="true" to hide
 * them from screen readers. If a button on the departing screen retains browser
 * focus at that moment, Chrome fires:
 *   "Blocked aria-hidden on an element because its descendant retained focus."
 * Pre-emptively blurring the active element before the new screen renders
 * prevents the conflict entirely.
 */
function BlurOnNavigate() {
  const pathname = usePathname();
  useEffect(() => {
    if (Platform.OS === 'web' && typeof document !== 'undefined') {
      (document.activeElement as HTMLElement | null)?.blur?.();
    }
  }, [pathname]);
  return null;
}

export const unstable_settings = {
  initialRouteName: '(tabs)',
};

function AuthGuard({ children }: { children: React.ReactNode }) {
  const segments = useSegments();
  const router = useRouter();
  const { isAuthenticated, isLoading, checkAuth, user } = useAuthStore();

  useEffect(() => {
    checkAuth();
  }, []);

  useEffect(() => {
    if (isLoading) return;

    const inAuthGroup = segments[0] === '(auth)';
    const inVetterGroup = segments[0] === '(vetter)';
    const inTabsGroup = segments[0] === '(tabs)';
    
    try {
      if (!isAuthenticated && !inAuthGroup) {
        // Redirect to login
        router.replace('/(auth)/login');
      } else if (isAuthenticated && inAuthGroup) {
        // Redirect based on role
        if (user?.role === 'vetter') {
          router.replace('/(vetter)/dashboard');
        } else {
          router.replace('/(tabs)/home');
        }
      } else if (isAuthenticated && user?.role === 'vetter' && inTabsGroup) {
        // Vetter trying to access teacher tabs, redirect to vetter portal
        router.replace('/(vetter)/dashboard');
      } else if (isAuthenticated && user?.role !== 'vetter' && inVetterGroup) {
        // Non-vetter trying to access vetter portal, redirect to tabs
        router.replace('/(tabs)/home');
      }
    } catch (error) {
      console.error('[AuthGuard] Navigation error:', error);
    }
  }, [isAuthenticated, isLoading, segments, user?.role]);

  if (isLoading) {
    return (
      <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
        <ActivityIndicator size="large" />
      </View>
    );
  }

  return <>{children}</>;
}

export default function RootLayout() {
  const colorScheme = useColorScheme();

  return (
    <ErrorBoundary>
      <SafeAreaProvider>
        <ThemeProvider value={colorScheme === 'dark' ? DarkTheme : DefaultTheme}>
          <ToastProvider>
            <AuthGuard>
              <BlurOnNavigate />
              <Stack
                screenOptions={{
                  headerTransparent: true,
                  headerStyle: { backgroundColor: 'transparent' },
                }}
              >
                <Stack.Screen name="(auth)" options={{ headerShown: false }} />
                <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
                <Stack.Screen name="(vetter)" options={{ headerShown: false }} />
                <Stack.Screen name="modal" options={{ presentation: 'modal', title: 'Modal' }} />
              </Stack>
            </AuthGuard>
          </ToastProvider>
          <StatusBar style="auto" />
        </ThemeProvider>
      </SafeAreaProvider>
    </ErrorBoundary>
  );
}

