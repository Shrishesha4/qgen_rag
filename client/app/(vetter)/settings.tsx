import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Alert,
  Modal,
  TextInput,
  Switch,
  ActivityIndicator,
  Platform,
  KeyboardAvoidingView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';

import { GlassCard } from '@/components/ui/glass-card';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { Colors, Spacing, BorderRadius, FontSizes } from '@/constants/theme';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { useToast } from '@/components/toast';
import { useAuthStore } from '@/stores/authStore';
import { selectionImpact } from '@/utils/haptics';

type ModalType = 'editProfile' | 'changePassword' | 'notifications' | 'help' | 'reportIssue' | null;

export default function VetterSettings() {
  const colorScheme = useColorScheme();
  const colors = Colors[colorScheme ?? 'light'];
  const { showSuccess, showError, showWarning } = useToast();
  const { user, logout, updateProfile, changePassword } = useAuthStore();

  const [activeModal, setActiveModal] = useState<ModalType>(null);

  // Edit Profile State
  const [fullName, setFullName] = useState(user?.full_name || '');
  const [isSaving, setIsSaving] = useState(false);

  // Change Password State
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  // Notification Settings
  const [pushNotifications, setPushNotifications] = useState(true);
  const [emailNotifications, setEmailNotifications] = useState(true);
  const [vettingReminders, setVettingReminders] = useState(true);

  // Report Issue State
  const [issueText, setIssueText] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

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

  const handleSaveProfile = async () => {
    setIsSaving(true);
    try {
      await updateProfile({ full_name: fullName });
      showSuccess('Profile updated successfully');
      setActiveModal(null);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to update profile';
      showError(message);
    } finally {
      setIsSaving(false);
    }
  };

  const handleChangePassword = async () => {
    if (newPassword !== confirmPassword) {
      showWarning('Passwords do not match', 'Validation Error');
      return;
    }
    if (newPassword.length < 8) {
      showWarning('Password must be at least 8 characters', 'Validation Error');
      return;
    }
    setIsSaving(true);
    try {
      await changePassword(currentPassword, newPassword);
      showSuccess('Password changed successfully');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setActiveModal(null);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to change password';
      showError(message);
    } finally {
      setIsSaving(false);
    }
  };

  const handleSubmitIssue = async () => {
    if (!issueText.trim()) {
      showWarning('Please describe the issue');
      return;
    }
    setIsSubmitting(true);
    // Simulate submission (no backend endpoint yet)
    await new Promise((r) => setTimeout(r, 800));
    setIsSubmitting(false);
    setIssueText('');
    showSuccess('Issue reported. Thank you!');
    setActiveModal(null);
  };

  const menuSections = [
    {
      title: 'Account',
      items: [
        {
          icon: 'person.fill' as const,
          label: 'Edit Profile',
          color: colors.primary,
          onPress: () => {
            setFullName(user?.full_name || '');
            setActiveModal('editProfile');
          },
        },
        {
          icon: 'lock.fill' as const,
          label: 'Change Password',
          color: '#FF9500',
          onPress: () => setActiveModal('changePassword'),
        },
        {
          icon: 'bell.fill' as const,
          label: 'Notification Preferences',
          color: '#FF3B30',
          onPress: () => setActiveModal('notifications'),
        },
      ],
    },
    {
      title: 'Support',
      items: [
        {
          icon: 'questionmark.circle.fill' as const,
          label: 'Help Center',
          color: '#34C759',
          onPress: () => setActiveModal('help'),
        },
        {
          icon: 'exclamationmark.bubble.fill' as const,
          label: 'Report an Issue',
          color: '#FF3B30',
          onPress: () => setActiveModal('reportIssue'),
        },
      ],
    },
  ];

  const renderModal = () => {
    switch (activeModal) {
      case 'editProfile':
        return (
          <View style={styles.modalContent}>
            <Text style={[styles.modalTitle, { color: colors.text }]}>Edit Profile</Text>

            <Text style={[styles.inputLabel, { color: colors.textSecondary }]}>Full Name</Text>
            <TextInput
              style={[styles.input, { backgroundColor: colors.card, color: colors.text, borderColor: colors.border }]}
              value={fullName}
              onChangeText={setFullName}
              placeholder="Enter your full name"
              placeholderTextColor={colors.textTertiary}
              autoCapitalize="words"
            />

            <Text style={[styles.inputLabel, { color: colors.textSecondary }]}>Email</Text>
            <TextInput
              style={[styles.input, { backgroundColor: colors.card, color: colors.textSecondary, borderColor: colors.border }]}
              value={user?.email || ''}
              editable={false}
              placeholderTextColor={colors.textTertiary}
            />
            <Text style={[styles.inputHint, { color: colors.textTertiary }]}>Email cannot be changed</Text>

            <View style={styles.modalButtons}>
              <TouchableOpacity
                style={[styles.modalButton, { backgroundColor: colors.card }]}
                onPress={() => setActiveModal(null)}
                disabled={isSaving}
              >
                <Text style={[styles.modalButtonText, { color: colors.text }]}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.modalButton, { backgroundColor: colors.primary, opacity: isSaving ? 0.7 : 1 }]}
                onPress={handleSaveProfile}
                disabled={isSaving}
              >
                {isSaving ? (
                  <ActivityIndicator color="#fff" size="small" />
                ) : (
                  <Text style={[styles.modalButtonText, { color: '#fff' }]}>Save</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        );

      case 'changePassword':
        return (
          <View style={styles.modalContent}>
            <Text style={[styles.modalTitle, { color: colors.text }]}>Change Password</Text>

            <Text style={[styles.inputLabel, { color: colors.textSecondary }]}>Current Password</Text>
            <TextInput
              style={[styles.input, { backgroundColor: colors.card, color: colors.text, borderColor: colors.border }]}
              value={currentPassword}
              onChangeText={setCurrentPassword}
              placeholder="Enter current password"
              placeholderTextColor={colors.textTertiary}
              secureTextEntry
            />

            <Text style={[styles.inputLabel, { color: colors.textSecondary }]}>New Password</Text>
            <TextInput
              style={[styles.input, { backgroundColor: colors.card, color: colors.text, borderColor: colors.border }]}
              value={newPassword}
              onChangeText={setNewPassword}
              placeholder="Min. 8 characters"
              placeholderTextColor={colors.textTertiary}
              secureTextEntry
            />

            <Text style={[styles.inputLabel, { color: colors.textSecondary }]}>Confirm New Password</Text>
            <TextInput
              style={[styles.input, { backgroundColor: colors.card, color: colors.text, borderColor: colors.border }]}
              value={confirmPassword}
              onChangeText={setConfirmPassword}
              placeholder="Repeat new password"
              placeholderTextColor={colors.textTertiary}
              secureTextEntry
            />

            <View style={styles.modalButtons}>
              <TouchableOpacity
                style={[styles.modalButton, { backgroundColor: colors.card }]}
                onPress={() => setActiveModal(null)}
                disabled={isSaving}
              >
                <Text style={[styles.modalButtonText, { color: colors.text }]}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.modalButton, { backgroundColor: '#FF9500', opacity: isSaving ? 0.7 : 1 }]}
                onPress={handleChangePassword}
                disabled={isSaving}
              >
                {isSaving ? (
                  <ActivityIndicator color="#fff" size="small" />
                ) : (
                  <Text style={[styles.modalButtonText, { color: '#fff' }]}>Update</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        );

      case 'notifications':
        return (
          <View style={styles.modalContent}>
            <Text style={[styles.modalTitle, { color: colors.text }]}>Notification Preferences</Text>

            {[
              { label: 'Push Notifications', desc: 'Receive in-app notifications', value: pushNotifications, set: setPushNotifications },
              { label: 'Email Notifications', desc: 'Receive email updates', value: emailNotifications, set: setEmailNotifications },
              { label: 'Vetting Reminders', desc: 'Remind me of pending reviews', value: vettingReminders, set: setVettingReminders },
            ].map((item) => (
              <View key={item.label} style={[styles.settingRow, { borderColor: colors.border }]}>
                <View style={styles.settingInfo}>
                  <Text style={[styles.settingLabel, { color: colors.text }]}>{item.label}</Text>
                  <Text style={[styles.settingDesc, { color: colors.textSecondary }]}>{item.desc}</Text>
                </View>
                <Switch
                  value={item.value}
                  onValueChange={(val) => { selectionImpact(); item.set(val); }}
                  trackColor={{ false: colors.border, true: colors.primary + '60' }}
                  thumbColor={item.value ? colors.primary : '#F4F3F4'}
                />
              </View>
            ))}

            <TouchableOpacity
              style={[styles.modalButtonFull, { backgroundColor: colors.primary }]}
              onPress={() => setActiveModal(null)}
            >
              <Text style={[styles.modalButtonText, { color: '#fff' }]}>Done</Text>
            </TouchableOpacity>
          </View>
        );

      case 'help':
        return (
          <View style={styles.modalContent}>
            <Text style={[styles.modalTitle, { color: colors.text }]}>Help Center</Text>

            {[
              { icon: 'checkmark.shield.fill' as const, color: '#34C759', title: 'Reviewing Questions', desc: 'Swipe or tap to approve/reject questions submitted by teachers.' },
              { icon: 'arrow.triangle.2.circlepath' as const, color: '#FF2D55', title: 'Reject & Regenerate', desc: 'When you reject a question, a new one is automatically regenerated for the teacher.' },
              { icon: 'person.2.fill' as const, color: colors.primary, title: 'Teachers', desc: 'View all teachers with pending questions. Search by name, email, or subject.' },
              { icon: 'chart.bar.fill' as const, color: '#FF9500', title: 'Dashboard Stats', desc: 'Track pending, approved, and rejected counts across all teachers.' },
            ].map((item) => (
              <View key={item.title} style={[styles.helpItem, { borderColor: colors.border }]}>
                <IconSymbol name={item.icon} size={24} color={item.color} />
                <View style={styles.helpItemContent}>
                  <Text style={[styles.helpItemTitle, { color: colors.text }]}>{item.title}</Text>
                  <Text style={[styles.helpItemDesc, { color: colors.textSecondary }]}>{item.desc}</Text>
                </View>
              </View>
            ))}

            <TouchableOpacity
              style={[styles.modalButtonFull, { backgroundColor: colors.primary }]}
              onPress={() => setActiveModal(null)}
            >
              <Text style={[styles.modalButtonText, { color: '#fff' }]}>Got it</Text>
            </TouchableOpacity>
          </View>
        );

      case 'reportIssue':
        return (
          <View style={styles.modalContent}>
            <Text style={[styles.modalTitle, { color: colors.text }]}>Report an Issue</Text>
            <Text style={[styles.inputLabel, { color: colors.textSecondary }]}>Describe the issue</Text>
            <TextInput
              style={[styles.textArea, { backgroundColor: colors.card, color: colors.text, borderColor: colors.border }]}
              value={issueText}
              onChangeText={setIssueText}
              placeholder="Describe the issue you encountered..."
              placeholderTextColor={colors.textTertiary}
              multiline
              numberOfLines={5}
              textAlignVertical="top"
            />
            <View style={styles.modalButtons}>
              <TouchableOpacity
                style={[styles.modalButton, { backgroundColor: colors.card }]}
                onPress={() => setActiveModal(null)}
                disabled={isSubmitting}
              >
                <Text style={[styles.modalButtonText, { color: colors.text }]}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.modalButton, { backgroundColor: '#FF3B30', opacity: isSubmitting ? 0.7 : 1 }]}
                onPress={handleSubmitIssue}
                disabled={isSubmitting}
              >
                {isSubmitting ? (
                  <ActivityIndicator color="#fff" size="small" />
                ) : (
                  <Text style={[styles.modalButtonText, { color: '#fff' }]}>Submit</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        );

      default:
        return null;
    }
  };

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]}>
      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        <View style={styles.header}>
          <Text style={[styles.title, { color: colors.text }]}>Profile</Text>
        </View>

        {/* Profile Card */}
        <GlassCard style={styles.profileCard}>
          <TouchableOpacity
            style={[styles.avatarCircle, { backgroundColor: colors.primary }]}
            onPress={() => { setFullName(user?.full_name || ''); setActiveModal('editProfile'); }}
          >
            <Text style={styles.avatarInitial}>
              {user?.full_name?.charAt(0)?.toUpperCase() || user?.username?.charAt(0)?.toUpperCase() || 'V'}
            </Text>
          </TouchableOpacity>
          <View style={styles.profileInfo}>
            <Text style={[styles.profileName, { color: colors.text }]}>{user?.full_name || user?.username}</Text>
            <Text style={[styles.profileEmail, { color: colors.textSecondary }]}>{user?.email}</Text>
            <View style={[styles.roleTag, { backgroundColor: colors.primary + '20' }]}>
              <Text style={[styles.roleText, { color: colors.primary }]}>Vetter</Text>
            </View>
          </View>
        </GlassCard>

        {/* Menu sections */}
        {menuSections.map((section) => (
          <View key={section.title} style={styles.section}>
            <Text style={[styles.sectionTitle, { color: colors.textSecondary }]}>{section.title}</Text>
            <GlassCard style={styles.optionsCard}>
              {section.items.map((item, idx) => (
                <React.Fragment key={item.label}>
                  {idx > 0 && <View style={[styles.divider, { backgroundColor: colors.border }]} />}
                  <TouchableOpacity style={styles.optionRow} onPress={item.onPress}>
                    <View style={[styles.iconBadge, { backgroundColor: item.color + '15' }]}>
                      <IconSymbol name={item.icon} size={18} color={item.color} />
                    </View>
                    <Text style={[styles.optionText, { color: colors.text }]}>{item.label}</Text>
                    <IconSymbol name="chevron.right" size={16} color={colors.textTertiary} />
                  </TouchableOpacity>
                </React.Fragment>
              ))}
            </GlassCard>
          </View>
        ))}

        {/* Logout */}
        <TouchableOpacity
          style={[styles.logoutButton, { borderColor: colors.error }]}
          onPress={handleLogout}
        >
          <IconSymbol name="rectangle.portrait.and.arrow.right" size={18} color={colors.error} />
          <Text style={[styles.logoutText, { color: colors.error }]}>Logout</Text>
        </TouchableOpacity>

        <Text style={[styles.version, { color: colors.textTertiary }]}>QGen v1.0.0</Text>
        <View style={{ height: 40 }} />
      </ScrollView>

      {/* Modal overlay */}
      <Modal
        visible={activeModal !== null}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => setActiveModal(null)}
      >
        <KeyboardAvoidingView
          style={{ flex: 1 }}
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        >
          <View style={[styles.modalContainer, { backgroundColor: colors.background }]}>
            <TouchableOpacity style={styles.modalCloseRow} onPress={() => setActiveModal(null)}>
              <IconSymbol name="xmark.circle.fill" size={28} color={colors.textTertiary} />
            </TouchableOpacity>
            <ScrollView showsVerticalScrollIndicator={false}>
              {renderModal()}
            </ScrollView>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  scrollContent: { paddingBottom: Spacing.xl },
  header: {
    paddingHorizontal: Spacing.md,
    paddingTop: Spacing.md,
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
  avatarCircle: {
    width: 60,
    height: 60,
    borderRadius: 30,
    justifyContent: 'center',
    alignItems: 'center',
  },
  avatarInitial: {
    color: '#fff',
    fontSize: FontSizes.xl,
    fontWeight: '700',
  },
  profileInfo: { flex: 1 },
  profileName: { fontSize: FontSizes.lg, fontWeight: '600' },
  profileEmail: { fontSize: FontSizes.sm, marginTop: 2 },
  roleTag: {
    alignSelf: 'flex-start',
    paddingHorizontal: Spacing.sm,
    paddingVertical: 4,
    borderRadius: BorderRadius.sm,
    marginTop: Spacing.sm,
  },
  roleText: { fontSize: FontSizes.xs, fontWeight: '700' },
  section: { marginBottom: Spacing.sm },
  sectionTitle: {
    fontSize: FontSizes.xs,
    fontWeight: '600',
    textTransform: 'uppercase',
    marginHorizontal: Spacing.md,
    marginBottom: Spacing.sm,
  },
  optionsCard: { marginHorizontal: Spacing.md },
  optionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    paddingVertical: Spacing.sm,
  },
  iconBadge: {
    width: 34,
    height: 34,
    borderRadius: BorderRadius.sm,
    justifyContent: 'center',
    alignItems: 'center',
  },
  optionText: { flex: 1, fontSize: FontSizes.md },
  divider: { height: StyleSheet.hairlineWidth },
  logoutButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginHorizontal: Spacing.md,
    marginTop: Spacing.lg,
    paddingVertical: Spacing.md,
    borderRadius: BorderRadius.md,
    borderWidth: 1,
    gap: Spacing.sm,
  },
  logoutText: { fontWeight: '600', fontSize: FontSizes.md },
  version: {
    textAlign: 'center',
    fontSize: FontSizes.xs,
    marginTop: Spacing.md,
  },
  // Modal
  modalContainer: { flex: 1, paddingTop: Spacing.sm },
  modalCloseRow: {
    alignItems: 'flex-end',
    paddingHorizontal: Spacing.md,
    paddingBottom: Spacing.sm,
  },
  modalContent: { padding: Spacing.md },
  modalTitle: {
    fontSize: FontSizes.xl,
    fontWeight: '700',
    marginBottom: Spacing.lg,
  },
  inputLabel: {
    fontSize: FontSizes.sm,
    fontWeight: '600',
    marginBottom: Spacing.xs,
    marginTop: Spacing.md,
  },
  input: {
    borderWidth: 1,
    borderRadius: BorderRadius.md,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    fontSize: FontSizes.md,
  },
  inputHint: { fontSize: FontSizes.xs, marginTop: 4 },
  textArea: {
    borderWidth: 1,
    borderRadius: BorderRadius.md,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    fontSize: FontSizes.md,
    minHeight: 120,
  },
  modalButtons: {
    flexDirection: 'row',
    gap: Spacing.sm,
    marginTop: Spacing.xl,
  },
  modalButton: {
    flex: 1,
    paddingVertical: Spacing.md,
    borderRadius: BorderRadius.md,
    alignItems: 'center',
  },
  modalButtonFull: {
    paddingVertical: Spacing.md,
    borderRadius: BorderRadius.md,
    alignItems: 'center',
    marginTop: Spacing.xl,
  },
  modalButtonText: { fontWeight: '600', fontSize: FontSizes.md },
  settingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: Spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  settingInfo: { flex: 1 },
  settingLabel: { fontSize: FontSizes.md, fontWeight: '500' },
  settingDesc: { fontSize: FontSizes.sm, marginTop: 2 },
  helpItem: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: Spacing.md,
    paddingVertical: Spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  helpItemContent: { flex: 1 },
  helpItemTitle: { fontSize: FontSizes.md, fontWeight: '600' },
  helpItemDesc: { fontSize: FontSizes.sm, marginTop: 4, lineHeight: 20 },
});
