/**
 * Subject Detail Screen - shows topics with progress
 */
import React, { useEffect, useCallback, useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  RefreshControl,
  ActivityIndicator,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { Colors, Spacing, FontSizes, BorderRadius } from '@/constants/theme';
import { MasteryRing } from '@/components/gamification';
import learnService from '@/services/learn';
import { subjectsService } from '@/services/subjects';

interface TopicWithProgress {
  id: string;
  name: string;
  mastery: number;
  questionsAttempted: number;
  accuracy: number;
  difficulty: string;
}

export default function SubjectDetailScreen() {
  const colorScheme = useColorScheme() ?? 'light';
  const colors = Colors[colorScheme];
  const router = useRouter();
  const params = useLocalSearchParams<{ subjectId: string; subjectName: string }>();

  const [topics, setTopics] = useState<TopicWithProgress[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [topicsResponse, progressData] = await Promise.all([
        subjectsService.listTopics(params.subjectId),
        learnService.getSubjectProgress(params.subjectId),
      ]);

      const progressMap = new Map(
        progressData.map((p) => [p.topic_id, p])
      );

      const merged: TopicWithProgress[] = topicsResponse.topics.map((t) => {
        const p = progressMap.get(t.id);
        return {
          id: t.id,
          name: t.name,
          mastery: p?.topic_mastery ?? 0,
          questionsAttempted: p?.questions_attempted ?? 0,
          accuracy: p?.accuracy_percentage ?? 0,
          difficulty: p?.current_difficulty ?? 'easy',
        };
      });
      setTopics(merged);
    } catch {
      // Ignore errors, show empty
    } finally {
      setLoading(false);
    }
  }, [params.subjectId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  }, [loadData]);

  const handleStartTopic = (topicId: string) => {
    router.push({
      pathname: '/(tabs)/learn/lesson',
      params: { subjectId: params.subjectId, subjectName: params.subjectName, topicId },
    });
  };

  const handleStartAll = () => {
    router.push({
      pathname: '/(tabs)/learn/lesson',
      params: { subjectId: params.subjectId, subjectName: params.subjectName },
    });
  };

  return (
    <SafeAreaView style={[styles.safeArea, { backgroundColor: colors.background }]}>
      {/* Header */}
      <View style={styles.headerRow}>
        <TouchableOpacity onPress={() => router.back()}>
          <Text style={[styles.backButton, { color: colors.primary }]}>← Back</Text>
        </TouchableOpacity>
        <Text style={[styles.title, { color: colors.text }]} numberOfLines={1}>
          {params.subjectName}
        </Text>
        <View style={{ width: 60 }} />
      </View>

      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
      >
        {/* Start All Button */}
        <TouchableOpacity
          style={[styles.startAllButton, { backgroundColor: colors.primary }]}
          onPress={handleStartAll}
        >
          <Text style={styles.startAllText}>🎯 Start Mixed Lesson</Text>
        </TouchableOpacity>

        {loading ? (
          <ActivityIndicator size="large" color={colors.primary} style={{ marginTop: 40 }} />
        ) : topics.length === 0 ? (
          <View style={styles.empty}>
            <Text style={styles.emptyEmoji}>📝</Text>
            <Text style={[styles.emptyText, { color: colors.textSecondary }]}>
              No topics available yet.
            </Text>
          </View>
        ) : (
          topics.map((topic) => (
            <TouchableOpacity
              key={topic.id}
              style={[styles.topicCard, { backgroundColor: colors.backgroundSecondary }]}
              onPress={() => handleStartTopic(topic.id)}
              activeOpacity={0.7}
            >
              <View style={styles.topicLeft}>
                <MasteryRing mastery={topic.mastery} size={50} />
              </View>
              <View style={styles.topicInfo}>
                <Text style={[styles.topicName, { color: colors.text }]}>{topic.name}</Text>
                <Text style={[styles.topicMeta, { color: colors.textSecondary }]}>
                  {topic.questionsAttempted > 0
                    ? `${Math.round(topic.accuracy)}% accuracy · ${topic.questionsAttempted} attempted`
                    : 'Not started'}
                </Text>
                <View style={[styles.diffBadge, {
                  backgroundColor: topic.difficulty === 'hard' ? '#FF3B3020' : topic.difficulty === 'medium' ? '#FF950020' : '#34C75920',
                }]}>
                  <Text style={[styles.diffText, {
                    color: topic.difficulty === 'hard' ? '#FF3B30' : topic.difficulty === 'medium' ? '#FF9500' : '#34C759',
                  }]}>
                    {topic.difficulty}
                  </Text>
                </View>
              </View>
              <Text style={[styles.arrow, { color: colors.textSecondary }]}>›</Text>
            </TouchableOpacity>
          ))
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1 },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.sm,
  },
  backButton: { fontSize: FontSizes.md, fontWeight: '600' },
  title: { fontSize: FontSizes.lg, fontWeight: '700', flex: 1, textAlign: 'center' },
  content: { padding: Spacing.lg, paddingBottom: 100 },
  startAllButton: {
    paddingVertical: Spacing.md,
    borderRadius: BorderRadius.lg,
    alignItems: 'center',
    marginBottom: Spacing.lg,
  },
  startAllText: { color: '#fff', fontSize: FontSizes.md, fontWeight: '700' },
  topicCard: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: Spacing.md,
    borderRadius: BorderRadius.lg,
    marginBottom: Spacing.sm,
  },
  topicLeft: { marginRight: Spacing.md },
  topicInfo: { flex: 1 },
  topicName: { fontSize: FontSizes.md, fontWeight: '600' },
  topicMeta: { fontSize: FontSizes.xs, marginTop: 2 },
  diffBadge: {
    alignSelf: 'flex-start',
    paddingHorizontal: Spacing.sm,
    paddingVertical: 2,
    borderRadius: BorderRadius.sm,
    marginTop: 4,
  },
  diffText: { fontSize: FontSizes.xs, fontWeight: '600', textTransform: 'capitalize' },
  arrow: { fontSize: 24, fontWeight: '300' },
  empty: { alignItems: 'center', paddingTop: 60 },
  emptyEmoji: { fontSize: 48 },
  emptyText: { fontSize: FontSizes.md, marginTop: Spacing.md },
});
