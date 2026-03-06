import { DarkTheme, DefaultTheme, ThemeProvider } from '@react-navigation/native';
import { Stack, useRouter, useSegments } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';
import 'react-native-reanimated';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { useColorScheme } from '@/hooks/use-color-scheme';
import { useAuthStore } from '@/stores/authStore';
import { View, ActivityIndicator } from 'react-native';
import { ToastProvider } from '@/components/toast';
import { ErrorBoundary } from '@/components/error-boundary';

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

