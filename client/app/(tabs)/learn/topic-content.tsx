/**
 * Topic Content Screen - Shows teacher's learning content/notes for a topic
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
import { useLocalSearchParams, useRouter, Stack } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { Colors, Spacing, FontSizes, BorderRadius } from '@/constants/theme';
import { IconSymbol } from '@/components/ui/icon-symbol';
import learnService from '@/services/learn';

export default function TopicContentScreen() {
  const colorScheme = useColorScheme() ?? 'light';
  const colors = Colors[colorScheme];
  const router = useRouter();
  const params = useLocalSearchParams<{ subjectId: string; topicId: string; topicName: string }>();

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [content, setContent] = useState<string>('');
  const [topicName, setTopicName] = useState(params.topicName || 'Topic');

  const loadContent = useCallback(async () => {
    try {
      const topicsData = await learnService.getTopics(params.subjectId);
      const topic = topicsData.topics.find((t: any) => t.id === params.topicId);
      if (topic) {
        setContent(topic.syllabus_content || '');
        setTopicName(topic.name);
      }
    } catch (err) {
      console.warn('Failed to load topic content:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [params.subjectId, params.topicId]);

  useEffect(() => {
    loadContent();
  }, [loadContent]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadContent();
  }, [loadContent]);

  return (
    <>
      <Stack.Screen
        options={{
          title: topicName,
          headerBackTitle: 'Back',
        }}
      />
      <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]} edges={['bottom']}>
        <ScrollView
          contentContainerStyle={styles.content}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        >
          {loading ? (
            <View style={styles.loadingContainer}>
              <ActivityIndicator size="large" color={colors.primary} />
            </View>
          ) : !content ? (
            <View style={styles.emptyContainer}>
              <IconSymbol name="doc.text" size={48} color={colors.textTertiary} />
              <Text style={[styles.emptyTitle, { color: colors.text }]}>No Content Available</Text>
              <Text style={[styles.emptyText, { color: colors.textSecondary }]}>
                The teacher hasn't added any learning content for this topic yet.
              </Text>
            </View>
          ) : (
            <View style={[styles.contentCard, { backgroundColor: colors.card }]}>
              <View style={styles.headerRow}>
                <Text style={styles.headerEmoji}>📖</Text>
                <Text style={[styles.headerTitle, { color: colors.text }]}>{topicName}</Text>
              </View>
              <View style={styles.divider} />
              <Text style={[styles.contentText, { color: colors.text }]}>{content}</Text>
            </View>
          )}
        </ScrollView>
      </SafeAreaView>
    </>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  content: { padding: Spacing.lg, paddingBottom: 100 },
  loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center', paddingTop: 80 },
  emptyContainer: { alignItems: 'center', paddingTop: 80 },
  emptyTitle: { fontSize: FontSizes.lg, fontWeight: '700', marginTop: Spacing.md },
  emptyText: { fontSize: FontSizes.md, marginTop: Spacing.sm, textAlign: 'center', paddingHorizontal: 40 },
  contentCard: {
    borderRadius: BorderRadius.lg,
    padding: Spacing.lg,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
    elevation: 3,
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    marginBottom: Spacing.md,
  },
  headerEmoji: { fontSize: 28 },
  headerTitle: { fontSize: FontSizes.xl, fontWeight: '700', flex: 1 },
  divider: {
    height: 1,
    backgroundColor: 'rgba(0,0,0,0.08)',
    marginBottom: Spacing.md,
  },
  contentText: {
    fontSize: FontSizes.md,
    lineHeight: 26,
  },
});
