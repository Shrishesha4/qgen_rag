/**
 * WebSidebar — Desktop sidebar navigation for web
 * Replaces the bottom tab bar on desktop/web with a persistent left-rail nav.
 */

import React from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { usePathname, useRouter } from 'expo-router';

import { IconSymbol } from './icon-symbol';
import { Colors, BorderRadius, FontSizes, AquaTokens as A } from '@/constants/theme';
import { useColorScheme } from '@/hooks/use-color-scheme';

export interface SidebarItem {
  name: string;
  href: string;
  title: string;
  icon: string;
}

interface WebSidebarProps {
  items: SidebarItem[];
  appTitle?: string;
  appSubtitle?: string;
}

export function WebSidebar({
  items,
  appTitle = 'QGen',
  appSubtitle,
}: WebSidebarProps) {
  const colorScheme = useColorScheme();
  const colors = Colors[colorScheme ?? 'light'];
  const isDark = colorScheme === 'dark';
  const pathname = usePathname();
  const router = useRouter();

  const isActive = (href: string) => {
    // Normalize: strip leading slash from href for comparison
    const normalized = href.replace(/^\//, '');
    const current = pathname.replace(/^\//, '');
    return current === normalized || current.startsWith(normalized + '/');
  };

  return (
    <View
      style={[
        styles.sidebar,
        {
          backgroundColor: isDark ? A.bgDark : A.bgLight,
          borderRightColor: colors.border,
        },
      ]}
    >
      {/* Brand header */}
      <LinearGradient
        colors={[A.deepBlue, A.aquaBlue]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={styles.brand}
      >
        <View style={styles.logoCircle}>
          <Text style={styles.logoLetter}>Q</Text>
        </View>
        <View style={styles.brandText}>
          <Text style={styles.brandTitle}>{appTitle}</Text>
          {appSubtitle && (
            <Text style={styles.brandSubtitle}>{appSubtitle}</Text>
          )}
        </View>
      </LinearGradient>

      {/* Divider */}
      <View style={[styles.divider, { backgroundColor: colors.border }]} />

      {/* Navigation */}
      <View style={styles.nav}>
        {items.map((item) => {
          const active = isActive(item.href);
          return (
            <TouchableOpacity
              key={item.name}
              onPress={() => router.navigate(item.href as any)}
              activeOpacity={0.7}
              style={[
                styles.navItem,
                active && {
                  backgroundColor: isDark
                    ? 'rgba(10,132,255,0.18)'
                    : 'rgba(0,122,255,0.10)',
                },
              ]}
            >
              <IconSymbol
                name={item.icon as any}
                size={20}
                color={active ? colors.primary : colors.textTertiary}
              />
              <Text
                style={[
                  styles.navLabel,
                  {
                    color: active ? colors.primary : colors.textSecondary,
                    fontWeight: active ? '600' : '500',
                  },
                ]}
              >
                {item.title}
              </Text>
              {active && (
                <View
                  style={[
                    styles.activeIndicator,
                    { backgroundColor: colors.primary },
                  ]}
                />
              )}
            </TouchableOpacity>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  sidebar: {
    width: 248,
    borderRightWidth: StyleSheet.hairlineWidth,
  },
  brand: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingHorizontal: 20,
    paddingVertical: 18,
  },
  logoCircle: {
    width: 38,
    height: 38,
    borderRadius: 12,
    backgroundColor: 'rgba(255,255,255,0.22)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  logoLetter: {
    color: '#FFFFFF',
    fontSize: 20,
    fontWeight: '800',
  },
  brandText: {
    flex: 1,
  },
  brandTitle: {
    color: '#FFFFFF',
    fontSize: FontSizes.lg,
    fontWeight: '700',
    letterSpacing: -0.3,
  },
  brandSubtitle: {
    color: 'rgba(255,255,255,0.72)',
    fontSize: FontSizes.xs,
    fontWeight: '500',
    marginTop: 2,
    letterSpacing: 0.2,
  },
  divider: {
    height: StyleSheet.hairlineWidth,
  },
  nav: {
    paddingTop: 12,
    paddingHorizontal: 12,
    gap: 2,
  },
  navItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 11,
    paddingHorizontal: 12,
    borderRadius: BorderRadius.md,
    gap: 12,
  },
  navLabel: {
    fontSize: FontSizes.md,
    flex: 1,
  },
  activeIndicator: {
    width: 4,
    height: 20,
    borderRadius: 2,
  },
});
