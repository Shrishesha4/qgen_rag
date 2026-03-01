/**
 * Hearts Display component - Duolingo-style heart/lives system
 */
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { Colors, Spacing, FontSizes } from '@/constants/theme';

interface HeartsDisplayProps {
  hearts: number;
  maxHearts?: number;
  compact?: boolean;
}

export function HeartsDisplay({ hearts, maxHearts = 5, compact = false }: HeartsDisplayProps) {
  const colorScheme = useColorScheme() ?? 'light';
  const colors = Colors[colorScheme];

  if (compact) {
    return (
      <View style={styles.compactContainer}>
        <Text style={styles.heartEmoji}>❤️</Text>
        <Text style={[styles.compactCount, { color: hearts > 0 ? '#FF3B30' : colors.textSecondary }]}>
          {hearts}
        </Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.heartsRow}>
        {Array.from({ length: maxHearts }).map((_, i) => (
          <Text key={i} style={styles.heartIcon}>
            {i < hearts ? '❤️' : '🤍'}
          </Text>
        ))}
      </View>
      {hearts === 0 && (
        <Text style={[styles.noHeartsText, { color: '#FF3B30' }]}>
          No hearts! Practice to earn more.
        </Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
  },
  compactContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  heartEmoji: {
    fontSize: 16,
  },
  compactCount: {
    fontSize: FontSizes.lg,
    fontWeight: '700',
  },
  heartsRow: {
    flexDirection: 'row',
    gap: 4,
  },
  heartIcon: {
    fontSize: 22,
  },
  noHeartsText: {
    fontSize: FontSizes.xs,
    marginTop: Spacing.xs,
  },
});
