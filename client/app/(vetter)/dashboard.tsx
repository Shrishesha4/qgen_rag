import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  ActivityIndicator,
  TouchableOpacity,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';

import { GlassCard } from '@/components/ui/glass-card';
import { Colors, Spacing, BorderRadius, FontSizes } from '@/constants/theme';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { useAuthStore } from '@/stores/authStore';
import { vetterService, VetterDashboard as Dashboard } from '@/services/vetter.service';

export default function VetterDashboard() {
  const colorScheme = useColorScheme();
  const colors = Colors[colorScheme ?? 'light'];
  const router = useRouter();
  const { user, logout } = useAuthStore();
  
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchDashboard = useCallback(async (showLoader = true) => {
    try {
      if (showLoader) setIsLoading(true);
      setError(null);
      const data = await vetterService.getDashboard();
      setDashboard(data);
    } catch (err) {
      setError('Failed to load dashboard');
      console.error(err);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  const onRefresh = useCallback(() => {
    setIsRefreshing(true);
    fetchDashboard(false);
  }, [fetchDashboard]);

  const StatCard = ({ 
    title, 
    value, 
    color, 
    onPress 
  }: { 
    title: string; 
    value: number; 
    color: string; 
    onPress?: () => void;
  }) => (
    <TouchableOpacity 
      onPress={onPress} 
      disabled={!onPress}
      style={styles.statCardWrapper}
    >
      <GlassCard style={[styles.statCard, { borderLeftColor: color, borderLeftWidth: 4 }]}>
        <Text style={[styles.statValue, { color }]}>{value}</Text>
        <Text style={[styles.statTitle, { color: colors.textSecondary }]}>{title}</Text>
      </GlassCard>
    </TouchableOpacity>
  );

  if (isLoading) {
    return (
      <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.primary} />
          <Text style={[styles.loadingText, { color: colors.textSecondary }]}>
            Loading dashboard...
          </Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl refreshing={isRefreshing} onRefresh={onRefresh} />
        }
      >
        {/* Header */}
        <View style={styles.header}>
          <View>
            <Text style={[styles.greeting, { color: colors.textSecondary }]}>
              Welcome back,
            </Text>
            <Text style={[styles.userName, { color: colors.text }]}>
              {user?.full_name || user?.username}
            </Text>
          </View>
          <TouchableOpacity 
            onPress={logout}
            style={[styles.logoutButton, { backgroundColor: colors.error + '20' }]}
          >
            <Text style={[styles.logoutText, { color: colors.error }]}>Logout</Text>
          </TouchableOpacity>
        </View>

        <Text style={[styles.sectionTitle, { color: colors.text }]}>Vetter Dashboard</Text>
        <Text style={[styles.roleLabel, { color: colors.primary, backgroundColor: colors.primary + '20' }]}>
          Vetter Portal
        </Text>

        {error && (
          <GlassCard style={[styles.errorCard, { borderColor: colors.error }]}>
            <Text style={[styles.errorText, { color: colors.error }]}>{error}</Text>
            <TouchableOpacity onPress={() => fetchDashboard()}>
              <Text style={[styles.retryText, { color: colors.primary }]}>Retry</Text>
            </TouchableOpacity>
          </GlassCard>
        )}

        {dashboard && (
          <>
            {/* Main Stats */}
            <View style={styles.statsGrid}>
              <StatCard
                title="Pending"
                value={dashboard.total_pending}
                color={colors.warning}
                onPress={() => router.push({ pathname: '/(vetter)/questions' as any, params: { status: 'pending' } })}
              />
              <StatCard
                title="Approved"
                value={dashboard.total_approved}
                color={colors.success}
                onPress={() => router.push({ pathname: '/(vetter)/questions' as any, params: { status: 'approved' } })}
              />
              <StatCard
                title="Rejected"
                value={dashboard.total_rejected}
                color={colors.error}
                onPress={() => router.push({ pathname: '/(vetter)/questions' as any, params: { status: 'rejected' } })}
              />
            </View>

            {/* Summary Stats */}
            <GlassCard style={styles.summaryCard}>
              <Text style={[styles.summaryTitle, { color: colors.text }]}>Overview</Text>
              
              <View style={styles.summaryRow}>
                <Text style={[styles.summaryLabel, { color: colors.textSecondary }]}>
                  Teachers with pending questions
                </Text>
                <Text style={[styles.summaryValue, { color: colors.text }]}>
                  {dashboard.teachers_with_pending}
                </Text>
              </View>
              
              <View style={styles.summaryRow}>
                <Text style={[styles.summaryLabel, { color: colors.textSecondary }]}>
                  Subjects with pending questions
                </Text>
                <Text style={[styles.summaryValue, { color: colors.text }]}>
                  {dashboard.subjects_with_pending}
                </Text>
              </View>
              
              <View style={styles.summaryRow}>
                <Text style={[styles.summaryLabel, { color: colors.textSecondary }]}>
                  Submissions today
                </Text>
                <Text style={[styles.summaryValue, { color: colors.text }]}>
                  {dashboard.recent_submissions}
                </Text>
              </View>
            </GlassCard>

            {/* Quick Actions */}
            <Text style={[styles.sectionTitle, { color: colors.text, marginTop: Spacing.lg }]}>
              Quick Actions
            </Text>
            
            <View style={styles.actionsGrid}>
              <TouchableOpacity
                style={[styles.actionButton, { backgroundColor: colors.primary }]}
                onPress={() => router.push({ pathname: '/(vetter)/questions' as any, params: { status: 'pending' } })}
              >
                <Text style={styles.actionButtonText}>Review Pending</Text>
              </TouchableOpacity>
              
              <TouchableOpacity
                style={[styles.actionButton, { backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border }]}
                onPress={() => router.push('/(vetter)/teachers' as any)}
              >
                <Text style={[styles.actionButtonText, { color: colors.text }]}>View Teachers</Text>
              </TouchableOpacity>
            </View>
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  scrollContent: {
    padding: Spacing.md,
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
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: Spacing.lg,
  },
  greeting: {
    fontSize: FontSizes.sm,
  },
  userName: {
    fontSize: FontSizes.xl,
    fontWeight: '700',
  },
  logoutButton: {
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.md,
  },
  logoutText: {
    fontWeight: '600',
  },
  sectionTitle: {
    fontSize: FontSizes.lg,
    fontWeight: '700',
    marginBottom: Spacing.sm,
  },
  roleLabel: {
    alignSelf: 'flex-start',
    paddingHorizontal: Spacing.sm,
    paddingVertical: 4,
    borderRadius: BorderRadius.sm,
    fontSize: FontSizes.xs,
    fontWeight: '600',
    marginBottom: Spacing.lg,
  },
  errorCard: {
    borderWidth: 1,
    marginBottom: Spacing.md,
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
  statsGrid: {
    flexDirection: 'row',
    gap: Spacing.sm,
    marginBottom: Spacing.lg,
  },
  statCardWrapper: {
    flex: 1,
  },
  statCard: {
    alignItems: 'center',
    paddingVertical: Spacing.lg,
  },
  statValue: {
    fontSize: 32,
    fontWeight: '700',
  },
  statTitle: {
    fontSize: FontSizes.sm,
    marginTop: 4,
  },
  summaryCard: {
    padding: Spacing.lg,
  },
  summaryTitle: {
    fontSize: FontSizes.md,
    fontWeight: '700',
    marginBottom: Spacing.md,
  },
  summaryRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: Spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: '#00000010',
  },
  summaryLabel: {
    fontSize: FontSizes.sm,
    flex: 1,
  },
  summaryValue: {
    fontSize: FontSizes.md,
    fontWeight: '600',
  },
  actionsGrid: {
    flexDirection: 'row',
    gap: Spacing.sm,
  },
  actionButton: {
    flex: 1,
    paddingVertical: Spacing.md,
    borderRadius: BorderRadius.md,
    alignItems: 'center',
  },
  actionButtonText: {
    color: '#fff',
    fontWeight: '600',
    fontSize: FontSizes.md,
  },
});
