/**
 * Leaderboard Screen - XP rankings
 */
import React, { useEffect, useCallback, useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  RefreshControl,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { Colors, Spacing, FontSizes, BorderRadius } from '@/constants/theme';
import { useLearningStore } from '@/stores/learningStore';
import { useAuthStore } from '@/stores/authStore';

export default function LeaderboardScreen() {
  const colorScheme = useColorScheme() ?? 'light';
  const colors = Colors[colorScheme];
  const [refreshing, setRefreshing] = useState(false);

  const { user } = useAuthStore();
  const { leaderboard, isLoading, loadLeaderboard } = useLearningStore();

  useEffect(() => {
    loadLeaderboard();
  }, [loadLeaderboard]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadLeaderboard();
    setRefreshing(false);
  }, [loadLeaderboard]);

  const getMedalEmoji = (rank: number) => {
    if (rank === 1) return '🥇';
    if (rank === 2) return '🥈';
    if (rank === 3) return '🥉';
    return `${rank}`;
  };

  return (
    <SafeAreaView style={[styles.safeArea, { backgroundColor: colors.background }]}>
      <Text style={[styles.title, { color: colors.text }]}>Leaderboard 🏆</Text>

      {isLoading && !refreshing && !leaderboard ? (
        <ActivityIndicator size="large" color={colors.primary} style={{ marginTop: 40 }} />
      ) : (
        <ScrollView
          contentContainerStyle={styles.content}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        >
          {/* Current rank banner */}
          {leaderboard?.current_user_rank && (
            <View style={[styles.rankBanner, { backgroundColor: `${colors.primary}15` }]}>
              <Text style={[styles.rankBannerText, { color: colors.primary }]}>
                Your Rank: #{leaderboard.current_user_rank} of {leaderboard.total_students}
              </Text>
            </View>
          )}

          {/* Top 3 Podium */}
          {leaderboard && leaderboard.entries.length >= 3 && (
            <View style={styles.podium}>
              {[1, 0, 2].map((idx) => {
                const entry = leaderboard.entries[idx];
                if (!entry) return null;
                const isFirst = idx === 0;
                return (
                  <View
                    key={entry.user_id}
                    style={[
                      styles.podiumItem,
                      isFirst && styles.podiumFirst,
                    ]}
                  >
                    <Text style={styles.podiumMedal}>{getMedalEmoji(entry.rank)}</Text>
                    <View
                      style={[
                        styles.podiumAvatar,
                        {
                          backgroundColor: colors.primary,
                          width: isFirst ? 60 : 48,
                          height: isFirst ? 60 : 48,
                          borderRadius: isFirst ? 30 : 24,
                        },
                      ]}
                    >
                      <Text style={[styles.podiumAvatarText, { fontSize: isFirst ? 24 : 18 }]}>
                        {(entry.full_name || entry.username)?.[0]?.toUpperCase() ?? '?'}
                      </Text>
                    </View>
                    <Text
                      style={[
                        styles.podiumName,
                        { color: entry.user_id === user?.id ? colors.primary : colors.text },
                      ]}
                      numberOfLines={1}
                    >
                      {entry.username}
                    </Text>
                    <Text style={[styles.podiumXP, { color: colors.secondaryText }]}>
                      {entry.xp_total} XP
                    </Text>
                  </View>
                );
              })}
            </View>
          )}

          {/* Full list */}
          {leaderboard?.entries.map((entry) => (
            <View
              key={entry.user_id}
              style={[
                styles.listItem,
                {
                  backgroundColor:
                    entry.user_id === user?.id
                      ? `${colors.primary}10`
                      : colors.secondaryBackground,
                },
              ]}
            >
              <Text style={[styles.rankNumber, { color: entry.rank <= 3 ? '#FF9500' : colors.secondaryText }]}>
                {getMedalEmoji(entry.rank)}
              </Text>
              <View
                style={[
                  styles.listAvatar,
                  { backgroundColor: colors.primary },
                ]}
              >
                <Text style={styles.listAvatarText}>
                  {(entry.full_name || entry.username)?.[0]?.toUpperCase() ?? '?'}
                </Text>
              </View>
              <View style={styles.listInfo}>
                <Text
                  style={[
                    styles.listName,
                    { color: entry.user_id === user?.id ? colors.primary : colors.text },
                  ]}
                >
                  {entry.username}
                  {entry.user_id === user?.id ? ' (You)' : ''}
                </Text>
                <Text style={[styles.listMeta, { color: colors.secondaryText }]}>
                  Level {entry.level} · 🔥 {entry.streak_count}
                </Text>
              </View>
              <Text style={[styles.listXP, { color: colors.text }]}>
                {entry.xp_total} XP
              </Text>
            </View>
          ))}

          {(!leaderboard || leaderboard.entries.length === 0) && (
            <View style={styles.empty}>
              <Text style={styles.emptyEmoji}>🏅</Text>
              <Text style={[styles.emptyText, { color: colors.secondaryText }]}>
                No students on the leaderboard yet. Be the first!
              </Text>
            </View>
          )}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1 },
  title: {
    fontSize: FontSizes.title,
    fontWeight: '800',
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.lg,
    paddingBottom: Spacing.sm,
  },
  content: { paddingHorizontal: Spacing.lg, paddingBottom: 100 },
  rankBanner: {
    padding: Spacing.md,
    borderRadius: BorderRadius.md,
    alignItems: 'center',
    marginBottom: Spacing.lg,
  },
  rankBannerText: { fontSize: FontSizes.md, fontWeight: '700' },
  podium: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'flex-end',
    marginBottom: Spacing.xl,
    paddingTop: Spacing.lg,
  },
  podiumItem: {
    alignItems: 'center',
    flex: 1,
    paddingVertical: Spacing.sm,
  },
  podiumFirst: {
    marginBottom: Spacing.md,
  },
  podiumMedal: { fontSize: 28, marginBottom: Spacing.xs },
  podiumAvatar: {
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: Spacing.xs,
  },
  podiumAvatarText: { color: '#fff', fontWeight: '700' },
  podiumName: { fontSize: FontSizes.sm, fontWeight: '600', maxWidth: 80, textAlign: 'center' },
  podiumXP: { fontSize: FontSizes.xs, marginTop: 2 },
  listItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: Spacing.md,
    borderRadius: BorderRadius.lg,
    marginBottom: Spacing.xs,
  },
  rankNumber: { fontSize: FontSizes.md, fontWeight: '700', width: 36, textAlign: 'center' },
  listAvatar: {
    width: 36,
    height: 36,
    borderRadius: 18,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: Spacing.sm,
  },
  listAvatarText: { color: '#fff', fontWeight: '700', fontSize: FontSizes.sm },
  listInfo: { flex: 1 },
  listName: { fontSize: FontSizes.md, fontWeight: '600' },
  listMeta: { fontSize: FontSizes.xs, marginTop: 2 },
  listXP: { fontSize: FontSizes.md, fontWeight: '700' },
  empty: { alignItems: 'center', paddingTop: 60 },
  emptyEmoji: { fontSize: 48 },
  emptyText: { fontSize: FontSizes.md, marginTop: Spacing.md, textAlign: 'center' },
});
