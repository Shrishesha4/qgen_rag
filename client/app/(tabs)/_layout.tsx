import React from 'react';
import { Platform, StyleSheet } from 'react-native';
import { Tabs } from 'expo-router';
import { NativeTabs, Icon, Label } from 'expo-router/unstable-native-tabs';
import { BlurView } from 'expo-blur';

import { HapticTab } from '@/components/haptic-tab';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { Colors } from '@/constants/theme';
import { useColorScheme } from '@/hooks/use-color-scheme';

export default function TabLayout() {
  const colorScheme = useColorScheme();
  const colors = Colors[colorScheme ?? 'light'];
  const isDark = colorScheme === 'dark';

  // Use native iOS 26 tabs on iOS - provides Liquid Glass automatically
  // Each tab now uses nested Stack navigators for sub-screens
  // This solves the issue where hidden NativeTabs triggers cannot be navigated to
  if (Platform.OS === 'ios') {
    return (
      <NativeTabs
        disableTransparentOnScrollEdge={false}
        labelStyle={{
          fontSize: 10,
          fontWeight: '600',
        }}
      >
        <NativeTabs.Trigger name="home">
          <Label>Home</Label>
          <Icon sf="house.fill" />
        </NativeTabs.Trigger>

        <NativeTabs.Trigger name="quick-generate">
          <Label>Generate</Label>
          <Icon sf="sparkles" />
        </NativeTabs.Trigger>

        <NativeTabs.Trigger name="learn">
          <Label>Learn</Label>
          <Icon sf="book.fill" />
        </NativeTabs.Trigger>

        <NativeTabs.Trigger name="history">
          <Label>History</Label>
          <Icon sf="clock.arrow.circlepath" />
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
        headerShown: false, // Each nested stack handles its own headers
        tabBarStyle: {
          backgroundColor: colors.card,
          borderTopColor: colors.border,
          height: 60,
        },
        tabBarBackground: TabBarBackground,
        tabBarLabelStyle: {
          fontSize: 10,
          fontWeight: '600',
          marginBottom: 4,
        },
        tabBarButton: HapticTab,
      }}
      screenListeners={{
        tabPress: (e) => {
          // Prevent index tab from being tapped
          if (e.target?.split('-')[0] === 'index') {
            e.preventDefault();
          }
        },
      }}>
      <Tabs.Screen
        name="index"
        options={{
          href: null, // Hide from tab bar
        }}
      />
      <Tabs.Screen
        name="home"
        options={{
          title: 'Home',
          tabBarIcon: ({ color }) => (
            <IconSymbol size={26} name="house.fill" color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="quick-generate"
        options={{
          title: 'Generate',
          tabBarIcon: ({ color }) => (
            <IconSymbol size={28} name="sparkles" color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="learn"
        options={{
          title: 'Learn',
          tabBarIcon: ({ color }) => (
            <IconSymbol size={26} name="book.fill" color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="history"
        options={{
          title: 'History',
          tabBarIcon: ({ color }) => (
            <IconSymbol size={26} name="clock.arrow.circlepath" color={color} />
          ),
        }}
      />
    </Tabs>
  );
}