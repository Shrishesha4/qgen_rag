/**
 * Lesson Result Screen - shows score, XP earned, streak
 */
import React, { useEffect } from 'react';
import { View, Text, ScrollView, StyleSheet, TouchableOpacity } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { Colors, Spacing, FontSizes, BorderRadius } from '@/constants/theme';
import { useLearningStore } from '@/stores/learningStore';

export default function ResultScreen() {
  const colorScheme = useColorScheme() ?? 'light';
  const colors = Colors[colorScheme];
  const router = useRouter();
  const params = useLocalSearchParams<{ subjectId: string; subjectName: string }>();

  const { lessonResult, clearLesson, loadProfile } = useLearningStore();

  useEffect(() => {
    return () => {
      clearLesson();
    };
  }, [clearLesson]);

  const handleContinue = () => {
    loadProfile();
    router.replace('/(tabs)/learn');
  };

  const handleRetry = () => {
    clearLesson();
    router.replace({
      pathname: '/(tabs)/learn/lesson',
      params: { subjectId: params.subjectId, subjectName: params.subjectName },
    });
  };

  if (!lessonResult) {
    return (
      <SafeAreaView style={[styles.safeArea, { backgroundColor: colors.background }]}>
        <View style={styles.center}>
          <Text style={[{ color: colors.text }]}>No results available.</Text>
          <TouchableOpacity onPress={handleContinue}>
            <Text style={[{ color: colors.primary, marginTop: 20 }]}>Go Back</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  const accuracy = lessonResult.accuracy;
  const isPerfect = lessonResult.correct_answers === lessonResult.total_questions;

  return (
    <SafeAreaView style={[styles.safeArea, { backgroundColor: colors.background }]}>
      <ScrollView contentContainerStyle={styles.content}>
        {/* Hero */}
        <View style={styles.hero}>
          <Text style={styles.heroEmoji}>
            {isPerfect ? '🏆' : accuracy >= 80 ? '🌟' : accuracy >= 50 ? '👍' : '💪'}
          </Text>
          <Text style={[styles.heroTitle, { color: colors.text }]}>
            {isPerfect ? 'Perfect!' : accuracy >= 80 ? 'Great Job!' : accuracy >= 50 ? 'Good Try!' : 'Keep Going!'}
          </Text>
          <Text style={[styles.heroSubtitle, { color: colors.textSecondary }]}>
            {params.subjectName}
          </Text>
        </View>

        {/* Score */}
        <View style={[styles.scoreCard, { backgroundColor: colors.backgroundSecondary }]}>
          <View style={styles.scoreRow}>
            <Text style={[styles.scoreLabel, { color: colors.textSecondary }]}>Score</Text>
            <Text style={[styles.scoreValue, { color: colors.text }]}>
              {lessonResult.correct_answers}/{lessonResult.total_questions}
            </Text>
          </View>
          <View style={styles.scoreRow}>
            <Text style={[styles.scoreLabel, { color: colors.textSecondary }]}>Accuracy</Text>
            <Text style={[styles.scoreValue, { color: colors.text }]}>
              {Math.round(accuracy)}%
            </Text>
          </View>
        </View>

        {/* XP Earned */}
        <LinearGradient
          colors={['#007AFF', '#5856D6']}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 0 }}
          style={styles.xpCard}
        >
          <Text style={styles.xpEmoji}>⚡</Text>
          <Text style={styles.xpText}>+{lessonResult.xp_earned} XP</Text>
          {lessonResult.level_up && (
            <Text style={styles.levelUpText}>🎉 Level Up! → Level {lessonResult.new_level}</Text>
          )}
        </LinearGradient>

        {/* Streak & Stats */}
        <View style={styles.statsGrid}>
          <View style={[styles.miniStat, { backgroundColor: colors.backgroundSecondary }]}>
            <Text style={styles.miniStatEmoji}>🔥</Text>
            <Text style={[styles.miniStatValue, { color: '#FF9500' }]}>
              {lessonResult.new_streak_count}
            </Text>
            <Text style={[styles.miniStatLabel, { color: colors.textSecondary }]}>Streak</Text>
          </View>
          <View style={[styles.miniStat, { backgroundColor: colors.backgroundSecondary }]}>
            <Text style={styles.miniStatEmoji}>❤️</Text>
            <Text style={[styles.miniStatValue, { color: '#FF3B30' }]}>
              {lessonResult.hearts_remaining}
            </Text>
            <Text style={[styles.miniStatLabel, { color: colors.textSecondary }]}>Hearts</Text>
          </View>
          <View style={[styles.miniStat, { backgroundColor: colors.backgroundSecondary }]}>
            <Text style={styles.miniStatEmoji}>📈</Text>
            <Text style={[styles.miniStatValue, { color: '#34C759' }]}>
              {Math.round(lessonResult.new_mastery)}%
            </Text>
            <Text style={[styles.miniStatLabel, { color: colors.textSecondary }]}>Mastery</Text>
          </View>
        </View>

        {/* Actions */}
        <View style={styles.actions}>
          <TouchableOpacity
            style={[styles.primaryAction, { backgroundColor: colors.primary }]}
            onPress={handleContinue}
          >
            <Text style={styles.primaryActionText}>Continue</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.secondaryAction, { borderColor: colors.primary }]}
            onPress={handleRetry}
          >
            <Text style={[styles.secondaryActionText, { color: colors.primary }]}>
              Try Again
            </Text>
          </TouchableOpacity>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  content: { padding: Spacing.lg, paddingBottom: 100 },
  hero: { alignItems: 'center', paddingVertical: Spacing.xl },
  heroEmoji: { fontSize: 64 },
  heroTitle: { fontSize: FontSizes.xxxl, fontWeight: '800', marginTop: Spacing.md },
  heroSubtitle: { fontSize: FontSizes.md, marginTop: Spacing.xs },
  scoreCard: {
    padding: Spacing.lg,
    borderRadius: BorderRadius.lg,
    marginTop: Spacing.lg,
    gap: Spacing.md,
  },
  scoreRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  scoreLabel: { fontSize: FontSizes.md },
  scoreValue: { fontSize: FontSizes.xl, fontWeight: '700' },
  xpCard: {
    padding: Spacing.lg,
    borderRadius: BorderRadius.lg,
    marginTop: Spacing.md,
    alignItems: 'center',
  },
  xpEmoji: { fontSize: 32 },
  xpText: { fontSize: FontSizes.xxl, fontWeight: '800', color: '#fff', marginTop: Spacing.xs },
  levelUpText: { fontSize: FontSizes.md, color: '#fff', marginTop: Spacing.xs },
  statsGrid: {
    flexDirection: 'row',
    gap: Spacing.sm,
    marginTop: Spacing.md,
  },
  miniStat: {
    flex: 1,
    alignItems: 'center',
    padding: Spacing.md,
    borderRadius: BorderRadius.md,
  },
  miniStatEmoji: { fontSize: 24 },
  miniStatValue: { fontSize: FontSizes.xl, fontWeight: '700', marginTop: 4 },
  miniStatLabel: { fontSize: FontSizes.xs, marginTop: 2 },
  actions: { marginTop: Spacing.xl, gap: Spacing.sm },
  primaryAction: {
    paddingVertical: Spacing.md,
    borderRadius: BorderRadius.lg,
    alignItems: 'center',
  },
  primaryActionText: { color: '#fff', fontSize: FontSizes.lg, fontWeight: '700' },
  secondaryAction: {
    paddingVertical: Spacing.md,
    borderRadius: BorderRadius.lg,
    alignItems: 'center',
    borderWidth: 2,
  },
  secondaryActionText: { fontSize: FontSizes.lg, fontWeight: '700' },
});
