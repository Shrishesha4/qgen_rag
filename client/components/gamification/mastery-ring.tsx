/**
 * Mastery Ring component - circular progress for topic mastery
 */
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { Colors, Spacing, FontSizes } from '@/constants/theme';

interface MasteryRingProps {
  mastery: number; // 0-100
  size?: number;
  label?: string;
}

export function MasteryRing({ mastery, size = 60, label }: MasteryRingProps) {
  const colorScheme = useColorScheme() ?? 'light';
  const colors = Colors[colorScheme];
  
  const getColor = () => {
    if (mastery >= 80) return '#34C759';
    if (mastery >= 50) return '#FF9500';
    return '#FF3B30';
  };

  const borderWidth = 4;
  
  return (
    <View style={styles.container}>
      <View
        style={[
          styles.ring,
          {
            width: size,
            height: size,
            borderRadius: size / 2,
            borderWidth,
            borderColor: colors.glassTertiary,
          },
        ]}
      >
        <View
          style={[
            styles.ringFill,
            {
              width: size,
              height: size,
              borderRadius: size / 2,
              borderWidth,
              borderColor: getColor(),
              borderTopColor: mastery < 25 ? colors.glassTertiary : getColor(),
              borderRightColor: mastery < 50 ? colors.glassTertiary : getColor(),
              borderBottomColor: mastery < 75 ? colors.glassTertiary : getColor(),
              position: 'absolute',
            },
          ]}
        />
        <Text style={[styles.masteryText, { color: getColor(), fontSize: size * 0.25 }]}>
          {Math.round(mastery)}%
        </Text>
      </View>
      {label && (
        <Text style={[styles.label, { color: colors.textSecondary }]} numberOfLines={1}>
          {label}
        </Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
    gap: Spacing.xs,
  },
  ring: {
    justifyContent: 'center',
    alignItems: 'center',
  },
  ringFill: {},
  masteryText: {
    fontWeight: '800',
  },
  label: {
    fontSize: FontSizes.xs,
    maxWidth: 70,
    textAlign: 'center',
  },
});
