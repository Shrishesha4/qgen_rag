import React from 'react';
import { Platform, StyleSheet } from 'react-native';
import { Tabs, useRouter } from 'expo-router';
import { NativeTabs, Icon, Label } from 'expo-router/unstable-native-tabs';
import { BlurView } from 'expo-blur';

import { HapticTab } from '@/components/haptic-tab';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { Colors } from '@/constants/theme';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { useAuthStore } from '@/stores/authStore';
import { useEffect } from 'react';

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

  // Use native iOS tabs on iOS
  if (Platform.OS === 'ios') {
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
