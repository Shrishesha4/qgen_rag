/**
 * Streak Counter component - shows current streak with fire emoji
 */
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { Colors, Spacing, FontSizes, BorderRadius } from '@/constants/theme';

interface StreakCounterProps {
  streak: number;
  compact?: boolean;
}

export function StreakCounter({ streak, compact = false }: StreakCounterProps) {
  const colorScheme = useColorScheme() ?? 'light';
  const colors = Colors[colorScheme];
  
  if (compact) {
    return (
      <View style={styles.compactContainer}>
        <Text style={styles.fireEmoji}>🔥</Text>
        <Text style={[styles.compactCount, { color: '#FF9500' }]}>{streak}</Text>
      </View>
    );
  }

  return (
    <View style={[styles.container, { backgroundColor: colors.backgroundSecondary }]}>
      <Text style={styles.fireEmojiLarge}>🔥</Text>
      <Text style={[styles.streakCount, { color: '#FF9500' }]}>{streak}</Text>
      <Text style={[styles.streakLabel, { color: colors.textSecondary }]}>
        {streak === 1 ? 'day streak' : 'days streak'}
      </Text>
      {streak >= 7 && (
        <Text style={styles.badge}>
          {streak >= 100 ? '🥇' : streak >= 30 ? '🥈' : '🥉'}
        </Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
    padding: Spacing.md,
    borderRadius: BorderRadius.lg,
    minWidth: 80,
  },
  compactContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  fireEmoji: {
    fontSize: 18,
  },
  fireEmojiLarge: {
    fontSize: 32,
  },
  compactCount: {
    fontSize: FontSizes.lg,
    fontWeight: '700',
  },
  streakCount: {
    fontSize: FontSizes.xxl,
    fontWeight: '800',
  },
  streakLabel: {
    fontSize: FontSizes.xs,
    marginTop: 2,
  },
  badge: {
    fontSize: 20,
    marginTop: Spacing.xs,
  },
});
