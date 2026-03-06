import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Alert } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';

import { GlassCard } from '@/components/ui/glass-card';
import { NativeButton } from '@/components/ui/native-button';
import { Colors, Spacing, BorderRadius, FontSizes } from '@/constants/theme';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { useToast } from '@/components/toast';
import useAuthStore from '@/stores/authStore';

export default function VetterSettings() {
  const colorScheme = useColorScheme();
  const colors = Colors[colorScheme ?? 'light'];
  const { showSuccess } = useToast();
  const { user, logout } = useAuthStore();

  const handleLogout = () => {
    Alert.alert('Logout', 'Are you sure you want to logout?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Logout',
        style: 'destructive',
        onPress: async () => {
          await logout();
          showSuccess('Logged out');
          router.replace('/(auth)/login');
        },
      },
    ]);
  };

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]}>
      <View style={styles.header}>
        <Text style={[styles.title, { color: colors.text }]}>Settings</Text>
      </View>

      {/* Profile Card */}
      <GlassCard style={styles.profileCard}>
        <View style={[styles.avatar, { backgroundColor: colors.primary }]}>
          <Text style={styles.avatarText}>
            {user?.full_name?.charAt(0)?.toUpperCase() || user?.username?.charAt(0)?.toUpperCase() || 'V'}
          </Text>
        </View>
        <View style={styles.profileInfo}>
          <Text style={[styles.profileName, { color: colors.text }]}>{user?.full_name || user?.username}</Text>
          <Text style={[styles.profileEmail, { color: colors.textSecondary }]}>
            {user?.email}
          </Text>
          <View style={[styles.roleTag, { backgroundColor: colors.primary + '20' }]}>
            <Text style={[styles.roleText, { color: colors.primary }]}>Vetter</Text>
          </View>
        </View>
      </GlassCard>

      {/* Settings Options */}
      <View style={styles.section}>
        <Text style={[styles.sectionTitle, { color: colors.textSecondary }]}>Account</Text>
        
        <GlassCard style={styles.optionsCard}>
          <TouchableOpacity style={styles.optionRow}>
            <Text style={[styles.optionText, { color: colors.text }]}>
              Change Password
            </Text>
            <Text style={[styles.optionArrow, { color: colors.textSecondary }]}>›</Text>
          </TouchableOpacity>

          <View style={[styles.divider, { backgroundColor: colors.border }]} />

          <TouchableOpacity style={styles.optionRow}>
            <Text style={[styles.optionText, { color: colors.text }]}>
              Notification Preferences
            </Text>
            <Text style={[styles.optionArrow, { color: colors.textSecondary }]}>›</Text>
          </TouchableOpacity>
        </GlassCard>
      </View>

      <View style={styles.section}>
        <Text style={[styles.sectionTitle, { color: colors.textSecondary }]}>Support</Text>
        
        <GlassCard style={styles.optionsCard}>
          <TouchableOpacity style={styles.optionRow}>
            <Text style={[styles.optionText, { color: colors.text }]}>Help Center</Text>
            <Text style={[styles.optionArrow, { color: colors.textSecondary }]}>›</Text>
          </TouchableOpacity>

          <View style={[styles.divider, { backgroundColor: colors.border }]} />

          <TouchableOpacity style={styles.optionRow}>
            <Text style={[styles.optionText, { color: colors.text }]}>Report an Issue</Text>
            <Text style={[styles.optionArrow, { color: colors.textSecondary }]}>›</Text>
          </TouchableOpacity>
        </GlassCard>
      </View>

      <View style={styles.logoutContainer}>
        <NativeButton
          title="Logout"
          onPress={handleLogout}
          variant="outline"
          fullWidth
          style={{ borderColor: colors.error }}
          textStyle={{ color: colors.error }}
        />
      </View>

      <Text style={[styles.version, { color: colors.textTertiary }]}>
        QGen v1.0.0
      </Text>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  header: {
    padding: Spacing.md,
    paddingBottom: Spacing.sm,
  },
  title: {
    fontSize: FontSizes.xl,
    fontWeight: '700',
  },
  profileCard: {
    flexDirection: 'row',
    alignItems: 'center',
    margin: Spacing.md,
    marginTop: 0,
    gap: Spacing.md,
  },
  avatar: {
    width: 60,
    height: 60,
    borderRadius: 30,
    justifyContent: 'center',
    alignItems: 'center',
  },
  avatarText: {
    color: '#fff',
    fontSize: FontSizes.xl,
    fontWeight: '700',
  },
  profileInfo: {
    flex: 1,
  },
  profileName: {
    fontSize: FontSizes.lg,
    fontWeight: '600',
  },
  profileEmail: {
    fontSize: FontSizes.sm,
    marginTop: 2,
  },
  roleTag: {
    alignSelf: 'flex-start',
    paddingHorizontal: Spacing.sm,
    paddingVertical: 4,
    borderRadius: BorderRadius.sm,
    marginTop: Spacing.sm,
  },
  roleText: {
    fontSize: FontSizes.xs,
    fontWeight: '700',
  },
  section: {
    marginVertical: Spacing.sm,
  },
  sectionTitle: {
    fontSize: FontSizes.xs,
    fontWeight: '600',
    textTransform: 'uppercase',
    marginHorizontal: Spacing.md,
    marginBottom: Spacing.sm,
  },
  optionsCard: {
    marginHorizontal: Spacing.md,
  },
  optionRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: Spacing.sm,
  },
  optionText: {
    fontSize: FontSizes.md,
  },
  optionArrow: {
    fontSize: FontSizes.lg,
    fontWeight: '300',
  },
  divider: {
    height: StyleSheet.hairlineWidth,
  },
  logoutContainer: {
    marginHorizontal: Spacing.md,
    marginTop: Spacing.xl,
  },
  version: {
    textAlign: 'center',
    fontSize: FontSizes.xs,
    marginTop: Spacing.md,
  },
});
