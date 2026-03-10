import React, { useEffect } from 'react';
import { Platform, StyleSheet, View } from 'react-native';
import { Tabs, useRouter } from 'expo-router';
import { BlurView } from 'expo-blur';

import { HapticTab } from '@/components/haptic-tab';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { WebSidebar } from '@/components/ui/web-sidebar';
import { Colors } from '@/constants/theme';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { useAuthStore } from '@/stores/authStore';

const VETTER_TABS = [
  { name: 'dashboard', href: '/(vetter)/dashboard', title: 'Dashboard', icon: 'chart.bar.fill' },
  { name: 'teachers', href: '/(vetter)/teachers', title: 'Teachers', icon: 'person.2.fill' },
  { name: 'questions', href: '/(vetter)/questions', title: 'Questions', icon: 'list.bullet.clipboard.fill' },
  { name: 'settings', href: '/(vetter)/settings', title: 'Settings', icon: 'gearshape.fill' },
];

export default function VetterTabLayout() {
  const colorScheme = useColorScheme();
  const colors = Colors[colorScheme ?? 'light'];
  const isDark = colorScheme === 'dark';
  const router = useRouter();
  const { user, isVetter } = useAuthStore();

  // Redirect non-vetters away from this portal
  useEffect(() => {
    if (user && !isVetter()) {
      router.replace('/(tabs)/home');
    }
  }, [user]);

  // Web: sidebar + hidden tab bar
  if (Platform.OS === 'web') {
    return (
      <View style={{ flex: 1, flexDirection: 'row', backgroundColor: colors.background }}>
        <WebSidebar items={VETTER_TABS} appTitle="QGen" appSubtitle="Vetter Portal" />
        <View style={{ flex: 1 }}>
          <Tabs
            screenOptions={{
              headerShown: false,
              tabBarStyle: { display: 'none' },
            }}
          >
            <Tabs.Screen name="dashboard" options={{ title: 'Dashboard' }} />
            <Tabs.Screen name="teachers" options={{ title: 'Teachers' }} />
            <Tabs.Screen name="questions" options={{ title: 'Questions' }} />
            <Tabs.Screen name="settings" options={{ title: 'Settings' }} />
          </Tabs>
        </View>
      </View>
    );
  }

  // Use native iOS tabs on iOS
  if (Platform.OS === 'ios') {
    // Lazy require to avoid bundling iOS-only module on web
    const { NativeTabs, Icon, Label } = require('expo-router/unstable-native-tabs');
    return (
      <NativeTabs
        disableTransparentOnScrollEdge={false}
        labelStyle={{
          fontSize: 10,
          fontWeight: '600',
        }}
      >
        <NativeTabs.Trigger name="dashboard">
          <Label>Dashboard</Label>
          <Icon sf="chart.bar.fill" />
        </NativeTabs.Trigger>

        <NativeTabs.Trigger name="teachers">
          <Label>Teachers</Label>
          <Icon sf="person.2.fill" />
        </NativeTabs.Trigger>

        <NativeTabs.Trigger name="questions">
          <Label>Questions</Label>
          <Icon sf="list.bullet.clipboard.fill" />
        </NativeTabs.Trigger>

        <NativeTabs.Trigger name="settings">
          <Label>Settings</Label>
          <Icon sf="gearshape.fill" />
        </NativeTabs.Trigger>
      </NativeTabs>
    );
  }

  // Android fallback with custom styled tabs
  const TabBarBackground = () => (
    <BlurView
      intensity={isDark ? 50 : 70}
      tint={isDark ? 'systemChromeMaterialDark' : 'systemChromeMaterial'}
      style={StyleSheet.absoluteFill}
    />
  );

  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.textTertiary,
        headerShown: false,
        tabBarStyle: {
          backgroundColor: colors.card,
          borderTopColor: colors.border,
          height: 76,
          paddingBottom: 12,
          paddingTop: 8,
        },
        tabBarBackground: TabBarBackground,
        tabBarLabelStyle: {
          fontSize: 11,
          fontWeight: '600',
          marginBottom: 2,
        },
        tabBarButton: HapticTab,
      }}
    >
      <Tabs.Screen
        name="dashboard"
        options={{
          title: 'Dashboard',
          tabBarIcon: ({ color }) => (
            <IconSymbol size={26} name="chart.bar.fill" color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="teachers"
        options={{
          title: 'Teachers',
          tabBarIcon: ({ color }) => (
            <IconSymbol size={26} name="person.2.fill" color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="questions"
        options={{
          title: 'Questions',
          tabBarIcon: ({ color }) => (
            <IconSymbol size={26} name="list.bullet.clipboard.fill" color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="settings"
        options={{
          title: 'Settings',
          tabBarIcon: ({ color }) => (
            <IconSymbol size={26} name="gearshape.fill" color={color} />
          ),
        }}
      />
    </Tabs>
  );
}
