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
import { LinearGradient } from 'expo-linear-gradient';
import { useRouter } from 'expo-router';

import { IconSymbol } from '@/components/ui/icon-symbol';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { useAuthStore } from '@/stores/authStore';
import { vetterService, VetterDashboard as Dashboard } from '@/services/vetter.service';
import { AquaTokens as A } from '@/constants/theme';
import { useResponsive } from '@/hooks/use-responsive';

export default function VetterDashboard() {
  const colorScheme = useColorScheme();
  const isDark = colorScheme === 'dark';
  const router = useRouter();
  const { user } = useAuthStore();
  const { desktopContentStyle } = useResponsive();

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

  // Aqua Gel stat card with glossy shine overlay
  const GelStatCard = ({
    title,
    value,
    gradientTop,
    gradientBottom,
    onPress,
  }: {
    title: string;
    value: number;
    gradientTop: string;
    gradientBottom: string;
    onPress?: () => void;
  }) => (
    <TouchableOpacity
      onPress={onPress}
      disabled={!onPress}
      activeOpacity={0.82}
      style={styles.gelCardWrapper}
    >
      <LinearGradient
        colors={[gradientTop, gradientBottom]}
        start={{ x: 0, y: 0 }}
        end={{ x: 0, y: 1 }}
        style={styles.gelCard}
      >
        {/* Gloss shine overlay (top half) */}
        <View style={styles.gelShine} pointerEvents="none">
          <LinearGradient
            colors={[A.shine, 'rgba(255,255,255,0)']}
            start={{ x: 0, y: 0 }}
            end={{ x: 0, y: 1 }}
            style={StyleSheet.absoluteFillObject}
          />
        </View>
        <Text style={styles.gelValue}>{value}</Text>
        <Text style={styles.gelTitle}>{title}</Text>
      </LinearGradient>
    </TouchableOpacity>
  );

  // Aqua chrome row inside summary card
  const AquaRow = ({
    label,
    value,
    isLast = false,
  }: {
    label: string;
    value: number;
    isLast?: boolean;
  }) => (
    <View style={[styles.aquaRow, !isLast && {
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: isDark ? A.metalBorderDark : A.metalBorderLight,
    }]}>
      <Text style={[styles.aquaRowLabel, { color: isDark ? '#AAC8E8' : '#334D6B' }]}>{label}</Text>
      <View style={[styles.aquaBadge, { backgroundColor: isDark ? '#1A3A5C' : '#D6EAF8', borderColor: isDark ? A.metalBorderDark : A.metalBorderLight }]}>
        <Text style={[styles.aquaBadgeText, { color: isDark ? A.skyBlue : A.aquaBlue }]}>{value}</Text>
      </View>
    </View>
  );

  if (isLoading) {
    return (
      <SafeAreaView style={[styles.container, { backgroundColor: isDark ? A.bgDark : A.bgLight }]}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={A.aquaBlue} />
          <Text style={[styles.loadingText, { color: isDark ? A.iceBlue : A.aquaBlue }]}>
            Loading dashboard...
          </Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: isDark ? A.bgDark : A.bgLight }]}>
      <ScrollView
        contentContainerStyle={[styles.scrollContent, desktopContentStyle]}
        refreshControl={
          <RefreshControl
            refreshing={isRefreshing}
            onRefresh={onRefresh}
            tintColor={A.skyBlue}
            colors={[A.aquaBlue, A.skyBlue]}
          />
        }
        showsVerticalScrollIndicator={false}
      >
        {/* ── Aqua Header ───────────────────────────────────────────────── */}
        <LinearGradient
          colors={isDark
            ? [A.deepBlue, A.aquaBlue, '#0097C7']
            : ['#1E73BE', A.aquaBlue, '#29B6F6']}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
          style={styles.aquaHeader}
        >
          {/* Top-half gloss */}
          <View style={styles.headerGloss} pointerEvents="none">
            <LinearGradient
              colors={['rgba(255,255,255,0.38)', 'rgba(255,255,255,0)']}
              start={{ x: 0, y: 0 }}
              end={{ x: 0, y: 1 }}
              style={StyleSheet.absoluteFillObject}
            />
          </View>
          <View style={styles.headerContent}>
            <View style={styles.headerLeft}>
              <Text style={styles.headerGreeting}>Welcome back</Text>
              <Text style={styles.headerName} numberOfLines={1}>
                {user?.full_name || user?.username}
              </Text>
              <View style={styles.rolePill}>
                <Text style={styles.rolePillText}>VETTER</Text>
              </View>
            </View>
            <TouchableOpacity
              onPress={() => router.push('/(vetter)/settings' as any)}
              style={styles.profileBtn}
              activeOpacity={0.75}
            >
              <LinearGradient
                colors={['rgba(255,255,255,0.3)', 'rgba(255,255,255,0.1)']}
                style={styles.profileBtnGradient}
              >
                <IconSymbol name="person.fill" size={22} color="#FFFFFF" />
              </LinearGradient>
            </TouchableOpacity>
          </View>
        </LinearGradient>

        {/* ── Error Banner ──────────────────────────────────────────────── */}
        {error && (
          <View style={[styles.errorBanner, { backgroundColor: isDark ? '#3B0A0A' : '#FEE2E2', borderColor: '#EF4444' }]}>
            <IconSymbol name="exclamationmark.triangle.fill" size={16} color="#EF4444" />
            <Text style={[styles.errorText, { color: '#EF4444' }]}>{error}</Text>
            <TouchableOpacity onPress={() => fetchDashboard()} style={styles.retryBtn}>
              <Text style={styles.retryBtnText}>Retry</Text>
            </TouchableOpacity>
          </View>
        )}

        {dashboard && (
          <>
            {/* ── Section Label ─────────────────────────────────────────── */}
            <View style={styles.sectionHeader}>
              <View style={[styles.sectionAccent, { backgroundColor: A.aquaBlue }]} />
              <Text style={[styles.sectionTitle, { color: isDark ? A.iceBlue : A.deepBlue }]}>
                Overview
              </Text>
            </View>

            {/* ── Gel Stat Cards ────────────────────────────────────────── */}
            <View style={styles.statsGrid}>
              <GelStatCard
                title="Pending"
                value={dashboard.total_pending}
                gradientTop={A.gelOrangeLight}
                gradientBottom={A.gelOrange}
                onPress={() => router.push({ pathname: '/(vetter)/questions' as any, params: { status: 'pending' } })}
              />
              <GelStatCard
                title="Approved"
                value={dashboard.total_approved}
                gradientTop={A.gelGreenLight}
                gradientBottom={A.gelGreen}
                onPress={() => router.push({ pathname: '/(vetter)/questions' as any, params: { status: 'approved' } })}
              />
              <GelStatCard
                title="Rejected"
                value={dashboard.total_rejected}
                gradientTop={A.gelRedLight}
                gradientBottom={A.gelRed}
                onPress={() => router.push({ pathname: '/(vetter)/questions' as any, params: { status: 'rejected' } })}
              />
            </View>

            {/* ── Summary Chrome Card ───────────────────────────────────── */}
            <View style={[styles.chromeCard, {
              backgroundColor: isDark ? A.cardDark : A.cardLight,
              borderColor: isDark ? A.metalBorderDark : A.metalBorderLight,
            }]}>
              {/* Card title bar */}
              <LinearGradient
                colors={isDark ? ['#1A3A5C', '#0D2644'] : ['#DAF0FF', '#FFFFFF']}
                style={styles.chromeTitleBar}
              >
                <IconSymbol name="chart.bar.fill" size={14} color={isDark ? A.skyBlue : A.aquaBlue} />
                <Text style={[styles.chromeTitleText, { color: isDark ? A.skyBlue : A.deepBlue }]}>
                  Statistics
                </Text>
              </LinearGradient>
              <View style={styles.chromeBody}>
                <AquaRow label="Teachers with pending questions" value={dashboard.teachers_with_pending} />
                <AquaRow label="Subjects with pending questions" value={dashboard.subjects_with_pending} />
                <AquaRow label="Submissions today" value={dashboard.recent_submissions} isLast />
              </View>
            </View>

            {/* ── Aqua Action Buttons ───────────────────────────────────── */}
            <View style={[styles.sectionHeader, { marginTop: 20 }]}>
              <View style={[styles.sectionAccent, { backgroundColor: A.aquaBlue }]} />
              <Text style={[styles.sectionTitle, { color: isDark ? A.iceBlue : A.deepBlue }]}>
                Quick Actions
              </Text>
            </View>

            <View style={styles.actionsRow}>
              {/* Primary Aqua button */}
              <TouchableOpacity
                activeOpacity={0.82}
                style={styles.aquaBtnWrapper}
                onPress={() => router.push({ pathname: '/(vetter)/questions' as any, params: { status: 'pending' } })}
              >
                <LinearGradient
                  colors={[A.gelOrange, A.gelOrange, A.gelOrangeLight]}
                  start={{ x: 0, y: 0 }}
                  end={{ x: 0, y: 1 }}
                  style={styles.aquaBtn}
                >
                  <View style={styles.aquaBtnShine} pointerEvents="none">
                    <LinearGradient
                      colors={['rgba(255,255,255,0.45)', 'rgba(255,255,255,0)']}
                      start={{ x: 0, y: 0 }}
                      end={{ x: 0, y: 1 }}
                      style={StyleSheet.absoluteFillObject}
                    />
                  </View>
                  <IconSymbol name="checkmark.shield.fill" size={18} color="#FFFFFF" />
                  <Text style={styles.aquaBtnText}>Review Pending</Text>
                </LinearGradient>
              </TouchableOpacity>

              {/* Secondary chrome button */}
              <TouchableOpacity
                activeOpacity={0.82}
                style={styles.chromeBtnWrapper}
                onPress={() => router.push('/(vetter)/teachers' as any)}
              >
                <LinearGradient
                  colors={isDark ? ['#2A4A6C', '#1A3050'] : ['#F0F8FF', '#D4E8FA']}
                  start={{ x: 0, y: 0 }}
                  end={{ x: 0, y: 1 }}
                  style={[styles.chromeBtn, {
                    borderColor: isDark ? A.metalBorderDark : A.metalBorderLight,
                  }]}
                >
                  <View style={styles.aquaBtnShine} pointerEvents="none">
                    <LinearGradient
                      colors={['rgba(255,255,255,0.35)', 'rgba(255,255,255,0)']}
                      start={{ x: 0, y: 0 }}
                      end={{ x: 0, y: 1 }}
                      style={StyleSheet.absoluteFillObject}
                    />
                  </View>
                  <IconSymbol name="person.2.fill" size={18} color={isDark ? A.skyBlue : A.deepBlue} />
                  <Text style={[styles.chromeBtnText, { color: isDark ? A.skyBlue : A.deepBlue }]}>
                    View Teachers
                  </Text>
                </LinearGradient>
              </TouchableOpacity>
            </View>
          </>
        )}

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  scrollContent: {
    paddingBottom: 24,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingTop: 80,
  },
  loadingText: {
    marginTop: 12,
    fontSize: 15,
    fontWeight: '500',
  },

  // ── Aqua Header ────────────────────────────────────────────────────────────
  aquaHeader: {
    marginHorizontal: 16,
    marginTop: 12,
    marginBottom: 20,
    borderRadius: 20,
    overflow: 'hidden',
    shadowColor: '#0288D1',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.4,
    shadowRadius: 12,
    elevation: 10,
  },
  headerGloss: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    height: '50%',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    overflow: 'hidden',
  },
  headerContent: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 22,
  },
  headerLeft: {
    flex: 1,
  },
  headerGreeting: {
    color: 'rgba(255,255,255,0.75)',
    fontSize: 13,
    fontWeight: '500',
    letterSpacing: 0.3,
  },
  headerName: {
    color: '#FFFFFF',
    fontSize: 24,
    fontWeight: '800',
    marginTop: 2,
    letterSpacing: -0.5,
    textShadowColor: 'rgba(0,0,0,0.3)',
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 4,
  },
  rolePill: {
    marginTop: 8,
    alignSelf: 'flex-start',
    backgroundColor: 'rgba(255,255,255,0.22)',
    borderRadius: 20,
    paddingHorizontal: 10,
    paddingVertical: 3,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.35)',
  },
  rolePillText: {
    color: '#FFFFFF',
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 1.5,
  },
  profileBtn: {
    marginLeft: 16,
    borderRadius: 22,
    overflow: 'hidden',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 4,
  },
  profileBtnGradient: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1.5,
    borderColor: 'rgba(255,255,255,0.5)',
  },

  // ── Error Banner ───────────────────────────────────────────────────────────
  errorBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginHorizontal: 16,
    marginBottom: 16,
    padding: 12,
    borderRadius: 12,
    borderWidth: 1,
  },
  errorText: {
    flex: 1,
    fontSize: 13,
    fontWeight: '500',
  },
  retryBtn: {
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderRadius: 8,
    backgroundColor: '#EF4444',
  },
  retryBtnText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '700',
  },

  // ── Section Header ─────────────────────────────────────────────────────────
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginHorizontal: 16,
    marginBottom: 12,
  },
  sectionAccent: {
    width: 4,
    height: 18,
    borderRadius: 2,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '700',
    letterSpacing: -0.2,
  },

  // ── Gel Stat Cards ─────────────────────────────────────────────────────────
  statsGrid: {
    flexDirection: 'row',
    gap: 10,
    marginHorizontal: 16,
    marginBottom: 20,
  },
  gelCardWrapper: {
    flex: 1,
    borderRadius: 16,
    overflow: 'hidden',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.22,
    shadowRadius: 8,
    elevation: 6,
  },
  gelCard: {
    alignItems: 'center',
    paddingVertical: 20,
    paddingHorizontal: 8,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.3)',
  },
  gelShine: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    height: '45%',
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    overflow: 'hidden',
  },
  gelValue: {
    fontSize: 34,
    fontWeight: '800',
    color: '#FFFFFF',
    textShadowColor: 'rgba(0,0,0,0.3)',
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 3,
  },
  gelTitle: {
    fontSize: 11,
    fontWeight: '600',
    color: 'rgba(255,255,255,0.88)',
    marginTop: 4,
    letterSpacing: 0.4,
    textTransform: 'uppercase',
  },

  // ── Chrome Summary Card ────────────────────────────────────────────────────
  chromeCard: {
    marginHorizontal: 16,
    marginBottom: 4,
    borderRadius: 16,
    borderWidth: 1,
    overflow: 'hidden',
    shadowColor: '#0288D1',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.12,
    shadowRadius: 8,
    elevation: 3,
  },
  chromeTitleBar: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: 'rgba(0,0,0,0.08)',
  },
  chromeTitleText: {
    fontSize: 14,
    fontWeight: '700',
    letterSpacing: -0.1,
  },
  chromeBody: {
    paddingHorizontal: 16,
    paddingVertical: 6,
  },
  aquaRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 11,
  },
  aquaRowLabel: {
    fontSize: 13,
    fontWeight: '500',
    flex: 1,
    marginRight: 8,
  },
  aquaBadge: {
    paddingHorizontal: 12,
    paddingVertical: 3,
    borderRadius: 20,
    borderWidth: 1,
    minWidth: 36,
    alignItems: 'center',
  },
  aquaBadgeText: {
    fontSize: 13,
    fontWeight: '700',
  },

  // ── Aqua Action Buttons ────────────────────────────────────────────────────
  actionsRow: {
    flexDirection: 'row',
    gap: 10,
    marginHorizontal: 16,
  },
  aquaBtnWrapper: {
    flex: 1,
    borderRadius: 14,
    overflow: 'hidden',
    shadowColor: A.aquaBlue,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.45,
    shadowRadius: 10,
    elevation: 7,
  },
  aquaBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 14,
    paddingHorizontal: 16,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.25)',
  },
  aquaBtnShine: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    height: '48%',
    borderTopLeftRadius: 14,
    borderTopRightRadius: 14,
    overflow: 'hidden',
  },
  aquaBtnText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '700',
    letterSpacing: -0.1,
    textShadowColor: 'rgba(0,0,0,0.25)',
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 2,
  },
  chromeBtnWrapper: {
    flex: 1,
    borderRadius: 14,
    overflow: 'hidden',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 6,
    elevation: 3,
  },
  chromeBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 14,
    paddingHorizontal: 16,
    borderRadius: 14,
    borderWidth: 1,
  },
  chromeBtnText: {
    fontSize: 14,
    fontWeight: '700',
    letterSpacing: -0.1,
  },
});
