import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  ActivityIndicator,
  Platform,
  StatusBar,
  Image,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { router } from 'expo-router';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { useAuthStore } from '@/stores/authStore';
import { questionsService, TeacherDashboard } from '@/services/questions';
import { API_BASE_URL } from '@/services/api';
import { AquaTokens as A } from '@/constants/theme';

export default function HomeScreen() {
  const colorScheme = useColorScheme();
  const isDark = colorScheme === 'dark';
  const { user } = useAuthStore();

  const getAvatarUrl = () => {
    if (!user?.avatar_url) return null;
    if (user.avatar_url.startsWith('/')) {
      const serverBase = API_BASE_URL.replace('/api/v1', '');
      return serverBase + user.avatar_url;
    }
    return user.avatar_url;
  };

  const [dashboard, setDashboard] = useState<TeacherDashboard | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async (showLoader = true) => {
    try {
      if (showLoader) setIsLoading(true);
      setError(null);
      const data = await questionsService.getTeacherDashboard();
      setDashboard(data);
    } catch (err: any) {
      console.error('Failed to load dashboard:', err);
      setError('Failed to load dashboard');
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleRefresh = () => { setIsRefreshing(true); loadData(false); };

  // ── Gel stat card (Aqua glossy button style) ──────────────────────────────
  const GelStatCard = ({
    title,
    value,
    gradientTop,
    gradientBottom,
    onPress,
  }: {
    title: string;
    value: number | string;
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
        colors={[gradientTop, gradientBottom] as [string, string]}
        start={{ x: 0, y: 0 }}
        end={{ x: 0, y: 1 }}
        style={styles.gelCard}
      >
        <View style={styles.gelShine} pointerEvents="none">
          <LinearGradient
            colors={[A.shine, 'rgba(255,255,255,0)'] as [string, string]}
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

  // ── Aqua chrome row ───────────────────────────────────────────────────────
  const AquaRow = ({
    label,
    value,
    isLast = false,
  }: {
    label: string;
    value: number | string;
    isLast?: boolean;
  }) => (
    <View style={[
      styles.aquaRow,
      !isLast && {
        borderBottomWidth: StyleSheet.hairlineWidth,
        borderBottomColor: isDark ? A.metalBorderDark : A.metalBorderLight,
      },
    ]}>
      <Text style={[styles.aquaRowLabel, { color: isDark ? '#AAC8E8' : '#334D6B' }]}>{label}</Text>
      <View style={[styles.aquaBadge, {
        backgroundColor: isDark ? '#1A3A5C' : '#D6EAF8',
        borderColor: isDark ? A.metalBorderDark : A.metalBorderLight,
      }]}>
        <Text style={[styles.aquaBadgeText, { color: isDark ? A.skyBlue : A.aquaBlue }]}>{value}</Text>
      </View>
    </View>
  );

  // ── Menu action item (Aqua gel card) ──────────────────────────────────────
  const MenuCard = ({
    title,
    subtitle,
    iconName,
    gradientTop,
    gradientBottom,
    onPress,
  }: {
    title: string;
    subtitle: string;
    iconName: string;
    gradientTop: string;
    gradientBottom: string;
    onPress: () => void;
  }) => (
    <TouchableOpacity style={styles.menuCardWrapper} onPress={onPress} activeOpacity={0.8}>
      <LinearGradient
        colors={[isDark ? A.cardDark : A.cardLight, isDark ? '#0A2240' : '#F0F8FF'] as [string, string]}
        start={{ x: 0, y: 0 }}
        end={{ x: 0, y: 1 }}
        style={[styles.menuCard, {
          borderColor: isDark ? A.metalBorderDark : A.metalBorderLight,
        }]}
      >
        {/* icon gel circle */}
        <LinearGradient
          colors={[gradientTop, gradientBottom] as [string, string]}
          start={{ x: 0, y: 0 }}
          end={{ x: 0, y: 1 }}
          style={styles.menuIconGel}
        >
          <View style={styles.menuIconGelShine} pointerEvents="none">
            <LinearGradient
              colors={[A.shine, 'rgba(255,255,255,0)'] as [string, string]}
              start={{ x: 0, y: 0 }}
              end={{ x: 0, y: 1 }}
              style={StyleSheet.absoluteFillObject}
            />
          </View>
          <IconSymbol name={iconName as any} size={24} color="#FFFFFF" weight="semibold" />
        </LinearGradient>
        <Text style={[styles.menuCardTitle, { color: isDark ? '#E0F2FF' : '#1A3A5C' }]} numberOfLines={1}>
          {title}
        </Text>
        <Text style={[styles.menuCardSubtitle, { color: isDark ? '#7BAFD4' : '#4A6FA5' }]} numberOfLines={2}>
          {subtitle}
        </Text>
      </LinearGradient>
    </TouchableOpacity>
  );

  if (isLoading) {
    return (
      <View style={[styles.centeredContainer, { backgroundColor: isDark ? A.bgDark : A.bgLight }]}>
        <ActivityIndicator size="large" color={A.aquaBlue} />
        <Text style={[styles.loadingText, { color: isDark ? A.iceBlue : A.aquaBlue }]}>
          Loading…
        </Text>
      </View>
    );
  }

  const menuItems = [
    {
      title: 'Subjects',
      subtitle: 'Manage your subjects',
      icon: 'books.vertical.fill',
      gradientTop: A.royalBlue,
      gradientBottom: A.aquaBlue,
      route: '/(tabs)/home/subjects',
    },
    {
      title: 'Rubrics',
      subtitle: 'Create questions from rubrics',
      icon: 'sparkles',
      gradientTop: A.gelPurple,
      gradientBottom: A.gelPurpleLight,
      route: '/(tabs)/home/generate',
    },
    {
      title: 'Vetting',
      subtitle: 'Review & approve questions',
      icon: 'checkmark.shield.fill',
      gradientTop: A.gelGreen,
      gradientBottom: A.gelGreenLight,
      route: '/(tabs)/home/vetting',
    },
    {
      title: 'Reports',
      subtitle: 'View analytics & exports',
      icon: 'chart.bar.fill',
      gradientTop: A.gelOrange,
      gradientBottom: A.gelOrangeLight,
      route: '/(tabs)/home/reports',
    },
  ];

  return (
    <View style={[styles.container, { backgroundColor: isDark ? A.bgDark : A.bgLight }]}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl
            refreshing={isRefreshing}
            onRefresh={handleRefresh}
            tintColor={A.skyBlue}
            colors={[A.aquaBlue, A.skyBlue]}
          />
        }
        showsVerticalScrollIndicator={false}
      >
        {/* ── Aqua Header ─────────────────────────────────────────────── */}
        <LinearGradient
          colors={isDark
            ? [A.deepBlue, A.aquaBlue, '#0097C7'] as [string, string, string]
            : ['#1E73BE', A.aquaBlue, '#29B6F6'] as [string, string, string]}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
          style={styles.aquaHeader}
        >
          {/* Top-half gloss */}
          <View style={styles.headerGloss} pointerEvents="none">
            <LinearGradient
              colors={['rgba(255,255,255,0.38)', 'rgba(255,255,255,0)'] as [string, string]}
              start={{ x: 0, y: 0 }}
              end={{ x: 0, y: 1 }}
              style={StyleSheet.absoluteFillObject}
            />
          </View>

          <View style={styles.headerContent}>
            <View style={styles.headerLeft}>
              <Text style={styles.headerGreeting}>Welcome back,</Text>
              <Text style={styles.headerName}>
                {user?.full_name?.split(' ')[0] || user?.username || 'Professor'}
              </Text>
              <View style={styles.rolePill}>
                <Text style={styles.rolePillText}>TEACHER</Text>
              </View>
            </View>

            <TouchableOpacity
              onPress={() => router.push('/(tabs)/home/profile')}
              style={styles.profileBtn}
              activeOpacity={0.75}
            >
              <LinearGradient
                colors={['rgba(255,255,255,0.3)', 'rgba(255,255,255,0.1)'] as [string, string]}
                style={styles.profileBtnGradient}
              >
                {getAvatarUrl() ? (
                  <Image source={{ uri: getAvatarUrl()! }} style={styles.profileImage} />
                ) : (
                  <IconSymbol name="person.fill" size={22} color="#FFFFFF" />
                )}
              </LinearGradient>
            </TouchableOpacity>
          </View>
        </LinearGradient>

        {/* ── Error Banner ─────────────────────────────────────────────── */}
        {error && (
          <View style={[styles.errorBanner, {
            backgroundColor: isDark ? '#3B0A0A' : '#FEE2E2',
            borderColor: '#EF4444',
          }]}>
            <IconSymbol name="exclamationmark.triangle.fill" size={16} color="#EF4444" />
            <Text style={[styles.errorText, { color: '#EF4444' }]}>{error}</Text>
            <TouchableOpacity onPress={() => loadData()} style={styles.retryBtn}>
              <Text style={styles.retryBtnText}>Retry</Text>
            </TouchableOpacity>
          </View>
        )}

        {dashboard && (
          <>
            {/* ── Section Label ────────────────────────────────────────── */}
            <View style={[styles.sectionHeader, { marginTop: 24 }]}>
              <View style={[styles.sectionAccent, { backgroundColor: A.aquaBlue }]} />
              <Text style={[styles.sectionTitle, { color: isDark ? A.iceBlue : A.deepBlue }]}>
                Quick Actions
              </Text>
            </View>

            {/* ── Aqua Menu Grid ────────────────────────────────────────── */}
            <View style={styles.menuGrid}>
              {menuItems.map((item) => (
                <MenuCard
                  key={item.title}
                  title={item.title}
                  subtitle={item.subtitle}
                  iconName={item.icon}
                  gradientTop={item.gradientTop}
                  gradientBottom={item.gradientBottom}
                  onPress={() => router.push(item.route as never)}
                />
              ))}
            </View>
            
            {/* ── Section Label ────────────────────────────────────────── */}
            <View style={styles.sectionHeader}>
              <View style={[styles.sectionAccent, { backgroundColor: A.aquaBlue }]} />
              <Text style={[styles.sectionTitle, { color: isDark ? A.iceBlue : A.deepBlue }]}>
                At a Glance
              </Text>
            </View>

            {/* ── Gel Stat Cards row 1 ─────────────────────────────────── */}
            <View style={styles.statsGrid}>
              <GelStatCard
                title="SUBJECTS"
                value={dashboard.subjects_count}
                gradientTop={A.royalBlue}
                gradientBottom={A.aquaBlue}
                onPress={() => router.push('/(tabs)/home/subjects')}
              />
              <GelStatCard
                title="DOCUMENTS"
                value={dashboard.documents_count}
                gradientTop={A.gelPurple}
                gradientBottom={A.gelPurpleLight}
              />
              <GelStatCard
                title="GENERATED"
                value={dashboard.total_questions}
                gradientTop={A.gelGreen}
                gradientBottom={A.gelGreenLight}
                onPress={() => router.push('/(tabs)/home/vetting')}
              />
            </View>

            {/* ── Gel Stat Cards row 2 ─────────────────────────────────── */}
            <View style={styles.statsGrid}>
              <GelStatCard
                title="PENDING"
                value={dashboard.pending_questions}
                gradientTop={A.gelOrange}
                gradientBottom={A.gelOrangeLight}
                onPress={() => router.push('/(tabs)/home/vetting')}
              />
              <GelStatCard
                title="APPROVED"
                value={dashboard.approved_questions}
                gradientTop={A.gelGreen}
                gradientBottom={A.gelGreenLight}
              />
              <GelStatCard
                title="APPROVAL %"
                value={`${dashboard.approval_rate}%`}
                gradientTop={dashboard.approval_rate >= 70 ? A.gelGreen : A.gelOrange}
                gradientBottom={dashboard.approval_rate >= 70 ? A.gelGreenLight : A.gelOrangeLight}
              />
            </View>
            
            {/* ── Chrome Summary Card ───────────────────────────────────── */}
            <View style={styles.sectionHeader}>
              <View style={[styles.sectionAccent, { backgroundColor: A.aquaBlue }]} />
              <Text style={[styles.sectionTitle, { color: isDark ? A.iceBlue : A.deepBlue }]}>
                Question Breakdown
              </Text>
            </View>

            <View style={[styles.chromeCard, {
              backgroundColor: isDark ? A.cardDark : A.cardLight,
              borderColor: isDark ? A.metalBorderDark : A.metalBorderLight,
            }]}>
              <LinearGradient
                colors={isDark
                  ? ['#1A3A5C', '#132F4C'] as [string, string]
                  : ['#EBF4FD', '#FFFFFF'] as [string, string]}
                start={{ x: 0, y: 0 }}
                end={{ x: 0, y: 1 }}
                style={styles.chromeTitleBar}
              >
                <IconSymbol name="doc.text.fill" size={16} color={isDark ? A.skyBlue : A.aquaBlue} />
                <Text style={[styles.chromeTitleText, { color: isDark ? '#E0F2FF' : '#1A3A5C' }]}>
                  By Question Type
                </Text>
              </LinearGradient>
              <View style={styles.chromeBody}>
                <AquaRow label="Multiple choice (MCQ)" value={dashboard.questions_by_type['mcq'] ?? 0} />
                <AquaRow label="Short answer" value={dashboard.questions_by_type['short_answer'] ?? 0} />
                <AquaRow label="Long answer / Essay" value={dashboard.questions_by_type['long_answer'] ?? 0} isLast />
              </View>
            </View>

            {/* ── Sessions chrome card ──────────────────────────────────── */}
            <View style={[styles.chromeCard, {
              backgroundColor: isDark ? A.cardDark : A.cardLight,
              borderColor: isDark ? A.metalBorderDark : A.metalBorderLight,
              marginTop: 12,
            }]}>
              <LinearGradient
                colors={isDark
                  ? ['#1A3A5C', '#132F4C'] as [string, string]
                  : ['#EBF4FD', '#FFFFFF'] as [string, string]}
                start={{ x: 0, y: 0 }}
                end={{ x: 0, y: 1 }}
                style={styles.chromeTitleBar}
              >
                <IconSymbol name="clock.fill" size={16} color={isDark ? A.skyBlue : A.aquaBlue} />
                <Text style={[styles.chromeTitleText, { color: isDark ? '#E0F2FF' : '#1A3A5C' }]}>
                  Activity
                </Text>
              </LinearGradient>
              <View style={styles.chromeBody}>
                <AquaRow label="Generation sessions" value={dashboard.sessions_count} />
                <AquaRow label="Rejected questions" value={dashboard.rejected_questions} isLast />
              </View>
            </View>
          </>
        )}

        <View style={{ height: Platform.OS === 'ios' ? 100 : 80 }} />
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  scrollContent: { paddingBottom: 24 },
  centeredContainer: {
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
    marginTop: Platform.OS === 'ios' ? 60 : (StatusBar.currentHeight ?? 24) + 12,
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
  headerLeft: { flex: 1 },
  headerGreeting: {
    color: 'rgba(255,255,255,0.75)',
    fontSize: 13,
    fontWeight: '500',
    letterSpacing: 0.3,
  },
  headerName: {
    color: '#FFFFFF',
    fontSize: 26,
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
  profileImage: {
    width: 44,
    height: 44,
    borderRadius: 22,
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
  errorText: { flex: 1, fontSize: 13, fontWeight: '500' },
  retryBtn: {
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderRadius: 8,
    backgroundColor: '#EF4444',
  },
  retryBtnText: { color: '#FFFFFF', fontSize: 12, fontWeight: '700' },

  // ── Section Header ─────────────────────────────────────────────────────────
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginHorizontal: 16,
    marginBottom: 12,
    marginTop: 12,
  },
  sectionAccent: { width: 4, height: 18, borderRadius: 2 },
  sectionTitle: { fontSize: 16, fontWeight: '700', letterSpacing: -0.2 },

  // ── Gel Stat Cards ─────────────────────────────────────────────────────────
  statsGrid: {
    flexDirection: 'row',
    gap: 10,
    marginHorizontal: 16,
    marginBottom: 10,
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
    paddingVertical: 18,
    paddingHorizontal: 6,
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
    fontSize: 28,
    fontWeight: '800',
    color: '#FFFFFF',
    textShadowColor: 'rgba(0,0,0,0.3)',
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 3,
  },
  gelTitle: {
    fontSize: 9,
    fontWeight: '700',
    color: 'rgba(255,255,255,0.88)',
    marginTop: 4,
    letterSpacing: 0.6,
    textTransform: 'uppercase',
    textAlign: 'center',
  },

  // ── Chrome Card ────────────────────────────────────────────────────────────
  chromeCard: {
    marginHorizontal: 16,
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
  chromeTitleText: { fontSize: 14, fontWeight: '700', letterSpacing: -0.1 },
  chromeBody: { paddingHorizontal: 16, paddingVertical: 6 },
  aquaRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 11,
  },
  aquaRowLabel: { fontSize: 13, fontWeight: '500', flex: 1, marginRight: 8 },
  aquaBadge: {
    paddingHorizontal: 12,
    paddingVertical: 3,
    borderRadius: 20,
    borderWidth: 1,
    minWidth: 36,
    alignItems: 'center',
  },
  aquaBadgeText: { fontSize: 13, fontWeight: '700' },

  // ── Menu Grid ─────────────────────────────────────────────────────────────
  menuGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginHorizontal: 16,
    gap: 10,
  },
  menuCardWrapper: {
    width: '47.5%',
    borderRadius: 16,
    overflow: 'hidden',
    shadowColor: '#0288D1',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 8,
    elevation: 4,
  },
  menuCard: {
    padding: 14,
    borderRadius: 16,
    borderWidth: 1,
    minHeight: 130,
    justifyContent: 'flex-start',
  },
  menuIconGel: {
    width: 48,
    height: 48,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.3)',
    marginBottom: 10,
  },
  menuIconGelShine: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    height: '48%',
    borderTopLeftRadius: 14,
    borderTopRightRadius: 14,
    overflow: 'hidden',
  },
  menuCardTitle: { fontSize: 14, fontWeight: '700', letterSpacing: -0.1 },
  menuCardSubtitle: { fontSize: 11, marginTop: 3, lineHeight: 15 },
});
