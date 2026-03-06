import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  RefreshControl,
  ActivityIndicator,
  TouchableOpacity,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';

import { GlassCard } from '@/components/ui/glass-card';
import { Colors, Spacing, BorderRadius, FontSizes } from '@/constants/theme';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { vetterService, TeacherSummary } from '@/services/vetter.service';

export default function TeachersList() {
  const colorScheme = useColorScheme();
  const colors = Colors[colorScheme ?? 'light'];
  const router = useRouter();
  
  const [teachers, setTeachers] = useState<TeacherSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchTeachers = useCallback(async (showLoader = true) => {
    try {
      if (showLoader) setIsLoading(true);
      setError(null);
      const data = await vetterService.getTeachers();
      setTeachers(data);
    } catch (err) {
      setError('Failed to load teachers');
      console.error(err);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchTeachers();
  }, [fetchTeachers]);

  const onRefresh = useCallback(() => {
    setIsRefreshing(true);
    fetchTeachers(false);
  }, [fetchTeachers]);

  const TeacherCard = ({ teacher }: { teacher: TeacherSummary }) => (
    <TouchableOpacity
      onPress={() => router.push({
        pathname: '/(vetter)/questions',
        params: { teacher_id: teacher.id, status: 'pending' }
      } as never)}
    >
      <GlassCard style={styles.teacherCard}>
        <View style={styles.teacherHeader}>
          <View style={[styles.avatar, { backgroundColor: colors.primary + '20' }]}>
            <Text style={[styles.avatarText, { color: colors.primary }]}>
              {(teacher.full_name || teacher.username).charAt(0).toUpperCase()}
            </Text>
          </View>
          <View style={styles.teacherInfo}>
            <Text style={[styles.teacherName, { color: colors.text }]}>
              {teacher.full_name || teacher.username}
            </Text>
            <Text style={[styles.teacherEmail, { color: colors.textSecondary }]}>
              {teacher.email}
            </Text>
          </View>
          {teacher.pending_count > 0 && (
            <View style={[styles.badge, { backgroundColor: colors.warning }]}>
              <Text style={styles.badgeText}>{teacher.pending_count}</Text>
            </View>
          )}
        </View>

        <View style={styles.statsRow}>
          <View style={styles.stat}>
            <Text style={[styles.statValue, { color: colors.warning }]}>
              {teacher.pending_count}
            </Text>
            <Text style={[styles.statLabel, { color: colors.textSecondary }]}>Pending</Text>
          </View>
          <View style={styles.stat}>
            <Text style={[styles.statValue, { color: colors.success }]}>
              {teacher.approved_count}
            </Text>
            <Text style={[styles.statLabel, { color: colors.textSecondary }]}>Approved</Text>
          </View>
          <View style={styles.stat}>
            <Text style={[styles.statValue, { color: colors.error }]}>
              {teacher.rejected_count}
            </Text>
            <Text style={[styles.statLabel, { color: colors.textSecondary }]}>Rejected</Text>
          </View>
        </View>

        {teacher.subjects.length > 0 && (
          <View style={styles.subjectsRow}>
            <Text style={[styles.subjectsLabel, { color: colors.textSecondary }]}>
              Subjects:
            </Text>
            <Text style={[styles.subjectsList, { color: colors.text }]} numberOfLines={1}>
              {teacher.subjects.join(', ')}
            </Text>
          </View>
        )}
      </GlassCard>
    </TouchableOpacity>
  );

  if (isLoading) {
    return (
      <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.primary} />
          <Text style={[styles.loadingText, { color: colors.textSecondary }]}>
            Loading teachers...
          </Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]}>
      <View style={styles.header}>
        <Text style={[styles.title, { color: colors.text }]}>Teachers</Text>
        <Text style={[styles.subtitle, { color: colors.textSecondary }]}>
          {teachers.length} teachers with questions
        </Text>
      </View>

      {error && (
        <GlassCard style={[styles.errorCard, { borderColor: colors.error }]}>
          <Text style={[styles.errorText, { color: colors.error }]}>{error}</Text>
          <TouchableOpacity onPress={() => fetchTeachers()}>
            <Text style={[styles.retryText, { color: colors.primary }]}>Retry</Text>
          </TouchableOpacity>
        </GlassCard>
      )}

      <FlatList
        data={teachers}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => <TeacherCard teacher={item} />}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={isRefreshing} onRefresh={onRefresh} />
        }
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Text style={[styles.emptyText, { color: colors.textSecondary }]}>
              No teachers with questions found
            </Text>
          </View>
        }
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: Spacing.md,
    fontSize: FontSizes.md,
  },
  header: {
    padding: Spacing.md,
    paddingBottom: 0,
  },
  title: {
    fontSize: FontSizes.xl,
    fontWeight: '700',
  },
  subtitle: {
    fontSize: FontSizes.sm,
    marginTop: 4,
  },
  listContent: {
    padding: Spacing.md,
    gap: Spacing.sm,
  },
  teacherCard: {
    marginBottom: Spacing.sm,
  },
  teacherHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: Spacing.md,
  },
  avatar: {
    width: 48,
    height: 48,
    borderRadius: 24,
    justifyContent: 'center',
    alignItems: 'center',
  },
  avatarText: {
    fontSize: FontSizes.lg,
    fontWeight: '700',
  },
  teacherInfo: {
    flex: 1,
    marginLeft: Spacing.md,
  },
  teacherName: {
    fontSize: FontSizes.md,
    fontWeight: '600',
  },
  teacherEmail: {
    fontSize: FontSizes.sm,
    marginTop: 2,
  },
  badge: {
    minWidth: 24,
    height: 24,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 8,
  },
  badgeText: {
    color: '#fff',
    fontSize: FontSizes.xs,
    fontWeight: '700',
  },
  statsRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: '#00000010',
    paddingTop: Spacing.md,
  },
  stat: {
    alignItems: 'center',
  },
  statValue: {
    fontSize: FontSizes.lg,
    fontWeight: '700',
  },
  statLabel: {
    fontSize: FontSizes.xs,
    marginTop: 2,
  },
  subjectsRow: {
    flexDirection: 'row',
    marginTop: Spacing.md,
    paddingTop: Spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: '#00000010',
  },
  subjectsLabel: {
    fontSize: FontSizes.sm,
    marginRight: Spacing.sm,
  },
  subjectsList: {
    fontSize: FontSizes.sm,
    flex: 1,
  },
  errorCard: {
    margin: Spacing.md,
    borderWidth: 1,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  errorText: {
    fontSize: FontSizes.sm,
  },
  retryText: {
    fontWeight: '600',
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: Spacing.xl,
  },
  emptyText: {
    fontSize: FontSizes.md,
  },
});
