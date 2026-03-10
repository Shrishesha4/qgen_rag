import React from 'react';
import { Platform, StyleSheet, View, useWindowDimensions } from 'react-native';
import { Tabs } from 'expo-router';
import { BlurView } from 'expo-blur';

import { HapticTab } from '@/components/haptic-tab';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { WebSidebar } from '@/components/ui/web-sidebar';
import { Colors } from '@/constants/theme';
import { useColorScheme } from '@/hooks/use-color-scheme';

const TEACHER_TABS = [
  { name: 'home', href: '/(tabs)/home', title: 'Home', icon: 'house.fill' },
  { name: 'quick-generate', href: '/(tabs)/quick-generate', title: 'Generate', icon: 'sparkles' },
  { name: 'history', href: '/(tabs)/history', title: 'History', icon: 'clock.arrow.circlepath' },
];

const DESKTOP_BREAKPOINT = 768;

export default function TabLayout() {
  const colorScheme = useColorScheme();
  const colors = Colors[colorScheme ?? 'light'];
  const isDark = colorScheme === 'dark';
  const { width } = useWindowDimensions();
  const isDesktopWeb = Platform.OS === 'web' && width >= DESKTOP_BREAKPOINT;

  // Desktop web: sidebar + hidden tab bar
  if (isDesktopWeb) {
    return (
      <View style={{ flex: 1, flexDirection: 'row', backgroundColor: colors.background }}>
        <WebSidebar items={TEACHER_TABS} appTitle="QGen" appSubtitle="Teacher Portal" />
        <View style={{ flex: 1 }}>
          <Tabs
            screenOptions={{
              headerShown: false,
              tabBarStyle: { display: 'none' },
            }}
          >
            <Tabs.Screen name="index" options={{ href: null }} />
            <Tabs.Screen name="home" options={{ title: 'Home' }} />
            <Tabs.Screen name="quick-generate" options={{ title: 'Generate' }} />
            <Tabs.Screen name="history" options={{ title: 'History' }} />
          </Tabs>
        </View>
      </View>
    );
  }

  // Use native iOS 26 tabs on iOS
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
        <NativeTabs.Trigger name="home">
          <Label>Home</Label>
          <Icon sf="house.fill" />
        </NativeTabs.Trigger>

        <NativeTabs.Trigger name="quick-generate">
          <Label>Generate</Label>
          <Icon sf="sparkles" />
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
          height: 66,
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