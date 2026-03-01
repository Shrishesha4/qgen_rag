/**
 * XP Progress Bar component - shows current XP and level progress
 */
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { Colors, Spacing, FontSizes, BorderRadius } from '@/constants/theme';

interface XPBarProps {
  xpTotal: number;
  level: number;
  xpPerLevel?: number;
}

const XP_PER_LEVEL = 100;

export function XPBar({ xpTotal, level, xpPerLevel = XP_PER_LEVEL }: XPBarProps) {
  const colorScheme = useColorScheme() ?? 'light';
  const colors = Colors[colorScheme];
  
  const xpInLevel = xpTotal % xpPerLevel;
  const progress = xpInLevel / xpPerLevel;
  
  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={[styles.levelText, { color: colors.primary }]}>
          Level {level}
        </Text>
        <Text style={[styles.xpText, { color: colors.textSecondary }]}>
          {xpInLevel}/{xpPerLevel} XP
        </Text>
      </View>
      <View style={[styles.barBackground, { backgroundColor: colors.glassTertiary }]}>
        <LinearGradient
          colors={['#007AFF', '#5856D6']}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 0 }}
          style={[styles.barFill, { width: `${Math.min(progress * 100, 100)}%` }]}
        />
      </View>
      <Text style={[styles.totalXP, { color: colors.textSecondary }]}>
        Total: {xpTotal} XP
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: Spacing.xs,
  },
  levelText: {
    fontSize: FontSizes.lg,
    fontWeight: '700',
  },
  xpText: {
    fontSize: FontSizes.sm,
  },
  barBackground: {
    height: 10,
    borderRadius: BorderRadius.full,
    overflow: 'hidden',
  },
  barFill: {
    height: '100%',
    borderRadius: BorderRadius.full,
  },
  totalXP: {
    fontSize: FontSizes.xs,
    marginTop: 2,
    textAlign: 'right',
  },
});
