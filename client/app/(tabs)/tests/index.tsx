/**
 * Teacher Tests Dashboard - List all tests with status filtering
 */
import React, { useEffect, useCallback, useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  RefreshControl,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { Colors, Spacing, FontSizes, BorderRadius } from '@/constants/theme';
import { useAuthStore } from '@/stores/authStore';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { GlassCard } from '@/components/ui/glass-card';
import { NativeButton } from '@/components/ui/native-button';
import { testsService, TestResponse } from '@/services/tests';

type StatusFilter = 'all' | 'draft' | 'published' | 'unpublished';

export default function TestsDashboard() {
  const colorScheme = useColorScheme() ?? 'light';
  const colors = Colors[colorScheme];
  const router = useRouter();
  const { user } = useAuthStore();

  const [tests, setTests] = useState<TestResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState<StatusFilter>('all');

  const loadTests = useCallback(async () => {
    try {
      const status = filter === 'all' ? undefined : filter;
      const data = await testsService.listTests(status);
      setTests(data);
    } catch (error: any) {
      console.error('Failed to load tests:', error);
    } finally {
      setIsLoading(false);
      setRefreshing(false);
    }
  }, [filter]);

  useEffect(() => {
    loadTests();
  }, [loadTests]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadTests();
  }, [loadTests]);

  const handleDelete = async (testId: string) => {
    Alert.alert('Delete Test', 'Are you sure you want to delete this test?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          try {
            await testsService.deleteTest(testId);
            setTests((prev) => prev.filter((t) => t.id !== testId));
          } catch (error: any) {
            Alert.alert('Error', error?.message || 'Failed to delete test');
          }
        },
      },
    ]);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'draft':
        return colors.warning;
      case 'published':
        return colors.success;
      case 'unpublished':
        return colors.textTertiary;
      default:
        return colors.textSecondary;
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'draft':
        return 'pencil.circle.fill';
      case 'published':
        return 'checkmark.circle.fill';
      case 'unpublished':
        return 'xmark.circle.fill';
      default:
        return 'questionmark.circle.fill';
    }
  };

  const filters: { key: StatusFilter; label: string }[] = [
    { key: 'all', label: 'All' },
    { key: 'draft', label: 'Drafts' },
    { key: 'published', label: 'Published' },
    { key: 'unpublished', label: 'Unpublished' },
  ];

  if (isLoading) {
    return (
      <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]}>
        <View style={styles.centered}>
          <ActivityIndicator size="large" color={colors.primary} />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]}>
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
      >
        {/* Header */}
        <View style={styles.header}>
          <View>
            <Text style={[styles.title, { color: colors.text }]}>Tests</Text>
            <Text style={[styles.subtitle, { color: colors.textSecondary }]}>
              Create and manage assessments
            </Text>
          </View>
          <TouchableOpacity
            style={[styles.createButton, { backgroundColor: colors.primary }]}
            onPress={() => router.push('/(tabs)/tests/create')}
          >
            <IconSymbol name="plus" size={20} color="#FFFFFF" />
            <Text style={styles.createButtonText}>New Test</Text>
          </TouchableOpacity>
        </View>

        {/* Status Filters */}
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.filterRow}
        >
          {filters.map((f) => (
            <TouchableOpacity
              key={f.key}
              style={[
                styles.filterChip,
                {
                  backgroundColor:
                    filter === f.key ? colors.primary : colors.backgroundSecondary,
                  borderColor: filter === f.key ? colors.primary : colors.border,
                },
              ]}
              onPress={() => setFilter(f.key)}
            >
              <Text
                style={[
                  styles.filterText,
                  { color: filter === f.key ? '#FFFFFF' : colors.textSecondary },
                ]}
              >
                {f.label}
              </Text>
            </TouchableOpacity>
          ))}
        </ScrollView>

        {/* Summary Stats */}
        <View style={styles.statsRow}>
          <GlassCard style={styles.statCard}>
            <Text style={[styles.statNumber, { color: colors.primary }]}>
              {tests.length}
            </Text>
            <Text style={[styles.statLabel, { color: colors.textSecondary }]}>Total</Text>
          </GlassCard>
          <GlassCard style={styles.statCard}>
            <Text style={[styles.statNumber, { color: colors.success }]}>
              {tests.filter((t) => t.status === 'published').length}
            </Text>
            <Text style={[styles.statLabel, { color: colors.textSecondary }]}>Published</Text>
          </GlassCard>
          <GlassCard style={styles.statCard}>
            <Text style={[styles.statNumber, { color: colors.warning }]}>
              {tests.filter((t) => t.status === 'draft').length}
            </Text>
            <Text style={[styles.statLabel, { color: colors.textSecondary }]}>Drafts</Text>
          </GlassCard>
        </View>

        {/* Tests List */}
        {tests.length === 0 ? (
          <View style={styles.emptyState}>
            <IconSymbol name="doc.text.fill" size={48} color={colors.textTertiary} />
            <Text style={[styles.emptyTitle, { color: colors.text }]}>No tests yet</Text>
            <Text style={[styles.emptySubtitle, { color: colors.textSecondary }]}>
              Create your first test to get started
            </Text>
            <NativeButton
              title="Create Test"
              onPress={() => router.push('/(tabs)/tests/create')}
              variant="primary"
            />
          </View>
        ) : (
          tests.map((test) => (
            <TouchableOpacity
              key={test.id}
              onPress={() =>
                router.push({
                  pathname: '/(tabs)/tests/detail',
                  params: { testId: test.id },
                })
              }
              onLongPress={() => {
                if (test.status !== 'published') handleDelete(test.id);
              }}
            >
              <GlassCard style={styles.testCard}>
                <View style={styles.testHeader}>
                  <View style={styles.testTitleRow}>
                    <IconSymbol
                      name={getStatusIcon(test.status)}
                      size={20}
                      color={getStatusColor(test.status)}
                    />
                    <Text style={[styles.testTitle, { color: colors.text }]} numberOfLines={1}>
                      {test.title}
                    </Text>
                  </View>
                  <View
                    style={[
                      styles.statusBadge,
                      { backgroundColor: getStatusColor(test.status) + '20' },
                    ]}
                  >
                    <Text
                      style={[styles.statusText, { color: getStatusColor(test.status) }]}
                    >
                      {test.status}
                    </Text>
                  </View>
                </View>

                {test.subject_name && (
                  <Text style={[styles.testSubject, { color: colors.textSecondary }]}>
                    {test.subject_code} - {test.subject_name}
                  </Text>
                )}

                <View style={styles.testMeta}>
                  <View style={styles.metaItem}>
                    <IconSymbol name="doc.text" size={14} color={colors.textTertiary} />
                    <Text style={[styles.metaText, { color: colors.textTertiary }]}>
                      {test.total_questions} questions
                    </Text>
                  </View>
                  <View style={styles.metaItem}>
                    <IconSymbol name="star.fill" size={14} color={colors.textTertiary} />
                    <Text style={[styles.metaText, { color: colors.textTertiary }]}>
                      {test.total_marks} marks
                    </Text>
                  </View>
                  {test.duration_minutes && (
                    <View style={styles.metaItem}>
                      <IconSymbol name="clock" size={14} color={colors.textTertiary} />
                      <Text style={[styles.metaText, { color: colors.textTertiary }]}>
                        {test.duration_minutes} min
                      </Text>
                    </View>
                  )}
                  {test.submissions_count > 0 && (
                    <View style={styles.metaItem}>
                      <IconSymbol name="person.2.fill" size={14} color={colors.primary} />
                      <Text style={[styles.metaText, { color: colors.primary }]}>
                        {test.submissions_count} submissions
                      </Text>
                    </View>
                  )}
                </View>

                {test.average_score !== null && test.average_score !== undefined && (
                  <View style={[styles.avgScoreBar, { backgroundColor: colors.backgroundSecondary }]}>
                    <Text style={[styles.avgScoreText, { color: colors.textSecondary }]}>
                      Avg Score: {test.average_score}%
                    </Text>
                  </View>
                )}
              </GlassCard>
            </TouchableOpacity>
          ))
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  centered: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  content: {
    padding: Spacing.md,
    paddingBottom: 100,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: Spacing.md,
  },
  title: {
    fontSize: FontSizes.xxl,
    fontWeight: '700',
  },
  subtitle: {
    fontSize: FontSizes.sm,
    marginTop: 2,
  },
  createButton: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.lg,
    gap: 6,
  },
  createButtonText: {
    color: '#FFFFFF',
    fontWeight: '600',
    fontSize: FontSizes.sm,
  },
  filterRow: {
    flexDirection: 'row',
    gap: Spacing.sm,
    marginBottom: Spacing.md,
    paddingRight: Spacing.md,
  },
  filterChip: {
    paddingHorizontal: Spacing.md,
    paddingVertical: 6,
    borderRadius: BorderRadius.full,
    borderWidth: 1,
  },
  filterText: {
    fontSize: FontSizes.sm,
    fontWeight: '500',
  },
  statsRow: {
    flexDirection: 'row',
    gap: Spacing.sm,
    marginBottom: Spacing.lg,
  },
  statCard: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: Spacing.md,
  },
  statNumber: {
    fontSize: FontSizes.xl,
    fontWeight: '700',
  },
  statLabel: {
    fontSize: FontSizes.xs,
    marginTop: 2,
  },
  emptyState: {
    alignItems: 'center',
    paddingVertical: 60,
    gap: Spacing.md,
  },
  emptyTitle: {
    fontSize: FontSizes.lg,
    fontWeight: '600',
  },
  emptySubtitle: {
    fontSize: FontSizes.sm,
    textAlign: 'center',
  },
  testCard: {
    marginBottom: Spacing.sm,
    padding: Spacing.md,
  },
  testHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  testTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    flex: 1,
  },
  testTitle: {
    fontSize: FontSizes.md,
    fontWeight: '600',
    flex: 1,
  },
  statusBadge: {
    paddingHorizontal: 10,
    paddingVertical: 3,
    borderRadius: BorderRadius.full,
  },
  statusText: {
    fontSize: FontSizes.xs,
    fontWeight: '600',
    textTransform: 'capitalize',
  },
  testSubject: {
    fontSize: FontSizes.sm,
    marginBottom: 8,
    marginLeft: 28,
  },
  testMeta: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.md,
    marginLeft: 28,
  },
  metaItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  metaText: {
    fontSize: FontSizes.xs,
  },
  avgScoreBar: {
    marginTop: 8,
    marginLeft: 28,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: BorderRadius.md,
    alignSelf: 'flex-start',
  },
  avgScoreText: {
    fontSize: FontSizes.xs,
    fontWeight: '500',
  },
});
