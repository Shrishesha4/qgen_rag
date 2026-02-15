import React, { useState, useEffect } from 'react';
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
  Platform,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { GlassCard } from '@/components/ui/glass-card';
import { Colors, Spacing, BorderRadius, FontSizes } from '@/constants/theme';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { useAuthStore } from '@/stores/authStore';
import { useToast } from '@/components/toast';

type ModalType = 'editProfile' | 'changePassword' | 'notifications' | 'appearance' | 'help' | 'about' | null;

export default function ProfileScreen() {
  const colorScheme = useColorScheme();
  const colors = Colors[colorScheme ?? 'light'];
  const isDark = colorScheme === 'dark';
  const { user, logout } = useAuthStore();
  const navigation = useNavigation();
  const { showError, showSuccess, showWarning } = useToast();
  
  const [activeModal, setActiveModal] = useState<ModalType>(null);
  
  useEffect(() => {
    // Hide tab bar on this screen
    navigation.getParent()?.setOptions({
      tabBarStyle: { display: 'none' },
    });
    
    return () => {
      // Show tab bar again when leaving
      navigation.getParent()?.setOptions({
        tabBarStyle: { 
          backgroundColor: colors.card,
          borderTopColor: colors.border,
          height: 60,
        },
      });
    };
  }, [navigation, colors]);
  
  // Edit Profile State
  const [fullName, setFullName] = useState(user?.full_name || '');
  const [email, setEmail] = useState(user?.email || '');
  
  // Change Password State
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  
  // Notification Settings
  const [pushNotifications, setPushNotifications] = useState(true);
  const [emailNotifications, setEmailNotifications] = useState(true);
  const [questionGenerated, setQuestionGenerated] = useState(true);
  const [vettingReminders, setVettingReminders] = useState(false);

  const handleLogout = () => {
    Alert.alert(
      'Logout',
      'Are you sure you want to logout?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Logout',
          style: 'destructive',
          onPress: logout,
        },
      ]
    );
  };

  const handleSaveProfile = () => {
    showSuccess('Profile updated successfully');
    setActiveModal(null);
  };

  const handleChangePassword = () => {
    if (newPassword !== confirmPassword) {
      showWarning('Passwords do not match', 'Validation Error');
      return;
    }
    if (newPassword.length < 8) {
      showWarning('Password must be at least 8 characters', 'Validation Error');
      return;
    }
    showSuccess('Password changed successfully');
    setCurrentPassword('');
    setNewPassword('');
    setConfirmPassword('');
    setActiveModal(null);
  };

  const menuSections = [
    {
      title: 'Account',
      items: [
        { 
          icon: 'person.fill', 
          label: 'Edit Profile', 
          color: colors.primary,
          onPress: () => setActiveModal('editProfile'),
        },
        { 
          icon: 'lock.fill', 
          label: 'Change Password', 
          color: '#FF9500',
          onPress: () => setActiveModal('changePassword'),
        },
      ],
    },
    {
      title: 'Preferences',
      items: [
        { 
          icon: 'bell.fill', 
          label: 'Notifications', 
          color: '#FF3B30',
          onPress: () => setActiveModal('notifications'),
        },
        { 
          icon: 'paintbrush.fill', 
          label: 'Appearance', 
          color: '#AF52DE',
          onPress: () => setActiveModal('appearance'),
        },
      ],
    },
    {
      title: 'Support',
      items: [
        { 
          icon: 'questionmark.circle.fill', 
          label: 'Help Center', 
          color: '#34C759',
          onPress: () => setActiveModal('help'),
        },
        { 
          icon: 'info.circle.fill', 
          label: 'About', 
          color: '#007AFF',
          onPress: () => setActiveModal('about'),
        },
      ],
    },
  ];

  const renderModalContent = () => {
    switch (activeModal) {
      case 'editProfile':
        return (
          <View style={styles.modalContent}>
            <Text style={[styles.modalTitle, { color: colors.text }]}>Edit Profile</Text>
            <Text style={[styles.inputLabel, { color: colors.textSecondary }]}>Full Name</Text>
            <TextInput
              style={[styles.input, { 
                backgroundColor: colors.card, 
                color: colors.text,
                borderColor: colors.border 
              }]}
              value={fullName}
              onChangeText={setFullName}
              placeholder="Enter your full name"
              placeholderTextColor={colors.textTertiary}
            />
            <Text style={[styles.inputLabel, { color: colors.textSecondary }]}>Email</Text>
            <TextInput
              style={[styles.input, { 
                backgroundColor: colors.card, 
                color: colors.text,
                borderColor: colors.border 
              }]}
              value={email}
              onChangeText={setEmail}
              placeholder="Enter your email"
              placeholderTextColor={colors.textTertiary}
              keyboardType="email-address"
              autoCapitalize="none"
            />
            <View style={styles.modalButtons}>
              <TouchableOpacity 
                style={[styles.modalButton, { backgroundColor: colors.card }]}
                onPress={() => setActiveModal(null)}
              >
                <Text style={[styles.modalButtonText, { color: colors.text }]}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity 
                style={[styles.modalButton, { backgroundColor: colors.primary }]}
                onPress={handleSaveProfile}
              >
                <Text style={[styles.modalButtonText, { color: '#FFFFFF' }]}>Save</Text>
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
              style={[styles.input, { 
                backgroundColor: colors.card, 
                color: colors.text,
                borderColor: colors.border 
              }]}
              value={currentPassword}
              onChangeText={setCurrentPassword}
              placeholder="Enter current password"
              placeholderTextColor={colors.textTertiary}
              secureTextEntry
            />
            <Text style={[styles.inputLabel, { color: colors.textSecondary }]}>New Password</Text>
            <TextInput
              style={[styles.input, { 
                backgroundColor: colors.card, 
                color: colors.text,
                borderColor: colors.border 
              }]}
              value={newPassword}
              onChangeText={setNewPassword}
              placeholder="Enter new password"
              placeholderTextColor={colors.textTertiary}
              secureTextEntry
            />
            <Text style={[styles.inputLabel, { color: colors.textSecondary }]}>Confirm Password</Text>
            <TextInput
              style={[styles.input, { 
                backgroundColor: colors.card, 
                color: colors.text,
                borderColor: colors.border 
              }]}
              value={confirmPassword}
              onChangeText={setConfirmPassword}
              placeholder="Confirm new password"
              placeholderTextColor={colors.textTertiary}
              secureTextEntry
            />
            <View style={styles.modalButtons}>
              <TouchableOpacity 
                style={[styles.modalButton, { backgroundColor: colors.card }]}
                onPress={() => setActiveModal(null)}
              >
                <Text style={[styles.modalButtonText, { color: colors.text }]}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity 
                style={[styles.modalButton, { backgroundColor: '#FF9500' }]}
                onPress={handleChangePassword}
              >
                <Text style={[styles.modalButtonText, { color: '#FFFFFF' }]}>Change</Text>
              </TouchableOpacity>
            </View>
          </View>
        );
        
      case 'notifications':
        return (
          <View style={styles.modalContent}>
            <Text style={[styles.modalTitle, { color: colors.text }]}>Notifications</Text>
            <View style={[styles.settingRow, { borderColor: colors.border }]}>
              <View style={styles.settingInfo}>
                <Text style={[styles.settingLabel, { color: colors.text }]}>Push Notifications</Text>
                <Text style={[styles.settingDesc, { color: colors.textSecondary }]}>Receive push notifications</Text>
              </View>
              <Switch
                value={pushNotifications}
                onValueChange={setPushNotifications}
                trackColor={{ false: colors.border, true: colors.primary + '60' }}
                thumbColor={pushNotifications ? colors.primary : '#F4F3F4'}
              />
            </View>
            <View style={[styles.settingRow, { borderColor: colors.border }]}>
              <View style={styles.settingInfo}>
                <Text style={[styles.settingLabel, { color: colors.text }]}>Email Notifications</Text>
                <Text style={[styles.settingDesc, { color: colors.textSecondary }]}>Receive email updates</Text>
              </View>
              <Switch
                value={emailNotifications}
                onValueChange={setEmailNotifications}
                trackColor={{ false: colors.border, true: colors.primary + '60' }}
                thumbColor={emailNotifications ? colors.primary : '#F4F3F4'}
              />
            </View>
            <View style={[styles.settingRow, { borderColor: colors.border }]}>
              <View style={styles.settingInfo}>
                <Text style={[styles.settingLabel, { color: colors.text }]}>Question Generated</Text>
                <Text style={[styles.settingDesc, { color: colors.textSecondary }]}>Notify when questions are ready</Text>
              </View>
              <Switch
                value={questionGenerated}
                onValueChange={setQuestionGenerated}
                trackColor={{ false: colors.border, true: colors.primary + '60' }}
                thumbColor={questionGenerated ? colors.primary : '#F4F3F4'}
              />
            </View>
            <View style={[styles.settingRow, { borderColor: colors.border }]}>
              <View style={styles.settingInfo}>
                <Text style={[styles.settingLabel, { color: colors.text }]}>Vetting Reminders</Text>
                <Text style={[styles.settingDesc, { color: colors.textSecondary }]}>Remind to review pending questions</Text>
              </View>
              <Switch
                value={vettingReminders}
                onValueChange={setVettingReminders}
                trackColor={{ false: colors.border, true: colors.primary + '60' }}
                thumbColor={vettingReminders ? colors.primary : '#F4F3F4'}
              />
            </View>
            <TouchableOpacity 
              style={[styles.modalButtonFull, { backgroundColor: colors.primary }]}
              onPress={() => setActiveModal(null)}
            >
              <Text style={[styles.modalButtonText, { color: '#FFFFFF' }]}>Done</Text>
            </TouchableOpacity>
          </View>
        );
        
      case 'appearance':
        return (
          <View style={styles.modalContent}>
            <Text style={[styles.modalTitle, { color: colors.text }]}>Appearance</Text>
            <Text style={[styles.modalSubtitle, { color: colors.textSecondary }]}>
              Theme follows your system settings
            </Text>
            <View style={styles.themeOptions}>
              <TouchableOpacity style={[styles.themeOption, { 
                backgroundColor: '#F5F5F5',
                borderColor: !isDark ? colors.primary : colors.border,
                borderWidth: !isDark ? 2 : 1,
              }]}>
                <IconSymbol name="sun.max.fill" size={32} color="#FF9500" />
                <Text style={[styles.themeLabel, { color: '#000000' }]}>Light</Text>
                {!isDark && <IconSymbol name="checkmark.circle.fill" size={20} color={colors.primary} style={styles.themeCheck} />}
              </TouchableOpacity>
              <TouchableOpacity style={[styles.themeOption, { 
                backgroundColor: '#1C1C1E',
                borderColor: isDark ? colors.primary : 'transparent',
                borderWidth: isDark ? 2 : 1,
              }]}>
                <IconSymbol name="moon.fill" size={32} color="#AF52DE" />
                <Text style={[styles.themeLabel, { color: '#FFFFFF' }]}>Dark</Text>
                {isDark && <IconSymbol name="checkmark.circle.fill" size={20} color={colors.primary} style={styles.themeCheck} />}
              </TouchableOpacity>
            </View>
            <Text style={[styles.modalNote, { color: colors.textTertiary }]}>
              To change theme, go to your device Settings {'>'} Display & Brightness
            </Text>
            <TouchableOpacity 
              style={[styles.modalButtonFull, { backgroundColor: colors.primary }]}
              onPress={() => setActiveModal(null)}
            >
              <Text style={[styles.modalButtonText, { color: '#FFFFFF' }]}>Done</Text>
            </TouchableOpacity>
          </View>
        );
        
      case 'help':
        return (
          <View style={styles.modalContent}>
            <Text style={[styles.modalTitle, { color: colors.text }]}>Help Center</Text>
            <ScrollView style={styles.helpContent}>
              <TouchableOpacity style={[styles.helpItem, { borderColor: colors.border }]}>
                <IconSymbol name="doc.text.fill" size={24} color={colors.primary} />
                <View style={styles.helpItemContent}>
                  <Text style={[styles.helpItemTitle, { color: colors.text }]}>Getting Started</Text>
                  <Text style={[styles.helpItemDesc, { color: colors.textSecondary }]}>Learn how to generate questions</Text>
                </View>
                <IconSymbol name="chevron.right" size={16} color={colors.textTertiary} />
              </TouchableOpacity>
              <TouchableOpacity style={[styles.helpItem, { borderColor: colors.border }]}>
                <IconSymbol name="checkmark.shield.fill" size={24} color="#34C759" />
                <View style={styles.helpItemContent}>
                  <Text style={[styles.helpItemTitle, { color: colors.text }]}>Vetting Process</Text>
                  <Text style={[styles.helpItemDesc, { color: colors.textSecondary }]}>How to review and approve questions</Text>
                </View>
                <IconSymbol name="chevron.right" size={16} color={colors.textTertiary} />
              </TouchableOpacity>
              <TouchableOpacity style={[styles.helpItem, { borderColor: colors.border }]}>
                <IconSymbol name="folder.fill" size={24} color="#FF9500" />
                <View style={styles.helpItemContent}>
                  <Text style={[styles.helpItemTitle, { color: colors.text }]}>Managing Subjects</Text>
                  <Text style={[styles.helpItemDesc, { color: colors.textSecondary }]}>Organize your content by subject</Text>
                </View>
                <IconSymbol name="chevron.right" size={16} color={colors.textTertiary} />
              </TouchableOpacity>
              <TouchableOpacity style={[styles.helpItem, { borderColor: colors.border }]}>
                <IconSymbol name="envelope.fill" size={24} color="#AF52DE" />
                <View style={styles.helpItemContent}>
                  <Text style={[styles.helpItemTitle, { color: colors.text }]}>Contact Support</Text>
                  <Text style={[styles.helpItemDesc, { color: colors.textSecondary }]}>support@questiongen.ai</Text>
                </View>
                <IconSymbol name="chevron.right" size={16} color={colors.textTertiary} />
              </TouchableOpacity>
            </ScrollView>
            <TouchableOpacity 
              style={[styles.modalButtonFull, { backgroundColor: colors.primary }]}
              onPress={() => setActiveModal(null)}
            >
              <Text style={[styles.modalButtonText, { color: '#FFFFFF' }]}>Done</Text>
            </TouchableOpacity>
          </View>
        );
        
      case 'about':
        return (
          <View style={styles.modalContent}>
            <Text style={[styles.modalTitle, { color: colors.text }]}>About</Text>
            <View style={styles.aboutHeader}>
              <View style={[styles.aboutIconContainer, { backgroundColor: colors.primary + '20' }]}>
                <IconSymbol name="sparkles" size={48} color={colors.primary} />
              </View>
              <Text style={[styles.aboutAppName, { color: colors.text }]}>QuestionGen AI</Text>
              <Text style={[styles.aboutVersion, { color: colors.textSecondary }]}>Version 1.0.0</Text>
            </View>
            <View style={[styles.aboutSection, { borderColor: colors.border }]}>
              <Text style={[styles.aboutSectionTitle, { color: colors.textSecondary }]}>ABOUT</Text>
              <Text style={[styles.aboutText, { color: colors.text }]}>
                QuestionGen AI is an intelligent question generation system powered by advanced AI. 
                Generate high-quality examination questions from your course materials instantly.
              </Text>
            </View>
            <View style={[styles.aboutSection, { borderColor: colors.border }]}>
              <Text style={[styles.aboutSectionTitle, { color: colors.textSecondary }]}>FEATURES</Text>
              <View style={styles.featureList}>
                <View style={styles.featureItem}>
                  <IconSymbol name="checkmark.circle.fill" size={16} color={colors.success} />
                  <Text style={[styles.featureText, { color: colors.text }]}>AI-Powered Question Generation</Text>
                </View>
                <View style={styles.featureItem}>
                  <IconSymbol name="checkmark.circle.fill" size={16} color={colors.success} />
                  <Text style={[styles.featureText, { color: colors.text }]}>Multiple Question Types</Text>
                </View>
                <View style={styles.featureItem}>
                  <IconSymbol name="checkmark.circle.fill" size={16} color={colors.success} />
                  <Text style={[styles.featureText, { color: colors.text }]}>Question Vetting Workflow</Text>
                </View>
                <View style={styles.featureItem}>
                  <IconSymbol name="checkmark.circle.fill" size={16} color={colors.success} />
                  <Text style={[styles.featureText, { color: colors.text }]}>Bloom's Taxonomy Support</Text>
                </View>
              </View>
            </View>
            <Text style={[styles.copyright, { color: colors.textTertiary }]}>
              © 2025 QuestionGen AI. All rights reserved.
            </Text>
            <TouchableOpacity 
              style={[styles.modalButtonFull, { backgroundColor: colors.primary }]}
              onPress={() => setActiveModal(null)}
            >
              <Text style={[styles.modalButtonText, { color: '#FFFFFF' }]}>Done</Text>
            </TouchableOpacity>
          </View>
        );
        
      default:
        return null;
    }
  };

  return (
    <ScrollView
      style={[styles.container, { backgroundColor: colors.background }]}
      contentContainerStyle={styles.contentContainer}
      showsVerticalScrollIndicator={false}
    >
      {/* Profile Header */}
      <GlassCard style={styles.headerCard}>
        <View style={[styles.avatarContainer, { backgroundColor: colors.primary + '20' }]}>
          <IconSymbol name="person.circle.fill" size={64} color={colors.primary} />
        </View>
        <Text style={[styles.userName, { color: colors.text }]}>
          {user?.full_name || user?.username || 'User'}
        </Text>
        <Text style={[styles.userEmail, { color: colors.textSecondary }]}>
          {user?.email || 'user@example.com'}
        </Text>
        <View style={styles.statsRow}>
          <View style={styles.statItem}>
            <Text style={[styles.statValue, { color: colors.primary }]}>0</Text>
            <Text style={[styles.statLabel, { color: colors.textSecondary }]}>Questions</Text>
          </View>
          <View style={[styles.statDivider, { backgroundColor: colors.border }]} />
          <View style={styles.statItem}>
            <Text style={[styles.statValue, { color: colors.success }]}>0</Text>
            <Text style={[styles.statLabel, { color: colors.textSecondary }]}>Approved</Text>
          </View>
          <View style={[styles.statDivider, { backgroundColor: colors.border }]} />
          <View style={styles.statItem}>
            <Text style={[styles.statValue, { color: '#FF9500' }]}>0</Text>
            <Text style={[styles.statLabel, { color: colors.textSecondary }]}>Subjects</Text>
          </View>
        </View>
      </GlassCard>

      {/* Menu Sections */}
      {menuSections.map((section, sectionIndex) => (
        <View key={sectionIndex} style={styles.section}>
          <Text style={[styles.sectionTitle, { color: colors.textSecondary }]}>
            {section.title}
          </Text>
          <GlassCard style={styles.menuCard}>
            {section.items.map((item, itemIndex) => (
              <TouchableOpacity
                key={itemIndex}
                style={[
                  styles.menuItem,
                  itemIndex < section.items.length - 1 && { borderBottomWidth: 1, borderBottomColor: colors.border }
                ]}
                onPress={item.onPress}
                activeOpacity={0.7}
              >
                <View style={[styles.menuIconContainer, { backgroundColor: item.color + '20' }]}>
                  <IconSymbol name={item.icon as any} size={20} color={item.color} />
                </View>
                <Text style={[styles.menuItemText, { color: colors.text }]}>{item.label}</Text>
                <IconSymbol name="chevron.right" size={16} color={colors.textTertiary} />
              </TouchableOpacity>
            ))}
          </GlassCard>
        </View>
      ))}

      {/* Logout Button */}
      <View style={styles.logoutContainer}>
        <TouchableOpacity
          style={[styles.logoutButton, { backgroundColor: '#FF3B30' + '15' }]}
          onPress={handleLogout}
          activeOpacity={0.7}
        >
          <IconSymbol name="rectangle.portrait.and.arrow.right.fill" size={20} color="#FF3B30" />
          <Text style={styles.logoutText}>Logout</Text>
        </TouchableOpacity>
      </View>

      {/* Version */}
      <Text style={[styles.versionText, { color: colors.textTertiary }]}>
        QuestionGen AI v1.0.0
      </Text>

      {/* Bottom padding for floating tab bar */}
      <View style={{ height: 100 }} />

      {/* Modal */}
      <Modal
        visible={activeModal !== null}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => setActiveModal(null)}
      >
        <View style={[styles.modalContainer, { backgroundColor: colors.background }]}>
          <View style={styles.modalHeader}>
            <TouchableOpacity onPress={() => setActiveModal(null)} style={styles.closeButton}>
              <IconSymbol name="xmark.circle.fill" size={28} color={colors.textTertiary} />
            </TouchableOpacity>
          </View>
          {renderModalContent()}
        </View>
      </Modal>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  contentContainer: {
    paddingTop: Spacing.lg,
  },
  headerCard: {
    marginHorizontal: Spacing.lg,
    alignItems: 'center',
    paddingVertical: Spacing.xl,
  },
  avatarContainer: {
    width: 88,
    height: 88,
    borderRadius: 44,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: Spacing.md,
  },
  userName: {
    fontSize: FontSizes.xl,
    fontWeight: '700',
  },
  userEmail: {
    fontSize: FontSizes.sm,
    marginTop: Spacing.xs,
  },
  statsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: Spacing.lg,
    paddingTop: Spacing.lg,
    borderTopWidth: 1,
    borderTopColor: 'rgba(128, 128, 128, 0.2)',
    width: '100%',
    justifyContent: 'space-around',
  },
  statItem: {
    alignItems: 'center',
    flex: 1,
  },
  statValue: {
    fontSize: FontSizes.xl,
    fontWeight: '700',
  },
  statLabel: {
    fontSize: FontSizes.xs,
    marginTop: 2,
  },
  statDivider: {
    width: 1,
    height: 30,
  },
  section: {
    marginTop: Spacing.xl,
  },
  sectionTitle: {
    fontSize: FontSizes.xs,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginHorizontal: Spacing.lg,
    marginBottom: Spacing.sm,
  },
  menuCard: {
    marginHorizontal: Spacing.lg,
    paddingVertical: 0,
    paddingHorizontal: 0,
    overflow: 'hidden',
  },
  menuItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: Spacing.md,
    paddingHorizontal: Spacing.md,
  },
  menuIconContainer: {
    width: 36,
    height: 36,
    borderRadius: BorderRadius.md,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: Spacing.md,
  },
  menuItemText: {
    fontSize: FontSizes.md,
    fontWeight: '500',
    flex: 1,
  },
  logoutContainer: {
    marginTop: Spacing.xxl,
    marginHorizontal: Spacing.lg,
  },
  logoutButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: Spacing.md,
    borderRadius: BorderRadius.lg,
    gap: Spacing.sm,
  },
  logoutText: {
    fontSize: FontSizes.md,
    fontWeight: '600',
    color: '#FF3B30',
  },
  versionText: {
    fontSize: FontSizes.xs,
    textAlign: 'center',
    marginTop: Spacing.xl,
  },
  
  // Modal Styles
  modalContainer: {
    flex: 1,
    paddingTop: Platform.OS === 'ios' ? 20 : 0,
  },
  modalHeader: {
    alignItems: 'flex-end',
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.md,
  },
  closeButton: {
    padding: Spacing.xs,
  },
  modalContent: {
    flex: 1,
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.lg,
  },
  modalTitle: {
    fontSize: FontSizes.xxl,
    fontWeight: '700',
    marginBottom: Spacing.lg,
  },
  modalSubtitle: {
    fontSize: FontSizes.sm,
    marginBottom: Spacing.lg,
  },
  inputLabel: {
    fontSize: FontSizes.sm,
    fontWeight: '500',
    marginBottom: Spacing.xs,
    marginTop: Spacing.md,
  },
  input: {
    borderWidth: 1,
    borderRadius: BorderRadius.md,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.md,
    fontSize: FontSizes.md,
  },
  modalButtons: {
    flexDirection: 'row',
    gap: Spacing.md,
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
  modalButtonText: {
    fontSize: FontSizes.md,
    fontWeight: '600',
  },
  
  // Settings Row
  settingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: Spacing.md,
    borderBottomWidth: 1,
  },
  settingInfo: {
    flex: 1,
    marginRight: Spacing.md,
  },
  settingLabel: {
    fontSize: FontSizes.md,
    fontWeight: '500',
  },
  settingDesc: {
    fontSize: FontSizes.xs,
    marginTop: 2,
  },
  
  // Theme Options
  themeOptions: {
    flexDirection: 'row',
    gap: Spacing.md,
    marginTop: Spacing.md,
  },
  themeOption: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: Spacing.xl,
    borderRadius: BorderRadius.lg,
    position: 'relative',
  },
  themeLabel: {
    fontSize: FontSizes.sm,
    fontWeight: '600',
    marginTop: Spacing.sm,
  },
  themeCheck: {
    position: 'absolute',
    top: 8,
    right: 8,
  },
  modalNote: {
    fontSize: FontSizes.xs,
    textAlign: 'center',
    marginTop: Spacing.lg,
  },
  
  // Help Items
  helpContent: {
    maxHeight: 300,
  },
  helpItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: Spacing.md,
    borderBottomWidth: 1,
  },
  helpItemContent: {
    flex: 1,
    marginLeft: Spacing.md,
  },
  helpItemTitle: {
    fontSize: FontSizes.md,
    fontWeight: '500',
  },
  helpItemDesc: {
    fontSize: FontSizes.xs,
    marginTop: 2,
  },
  
  // About
  aboutHeader: {
    alignItems: 'center',
    marginBottom: Spacing.xl,
  },
  aboutIconContainer: {
    width: 80,
    height: 80,
    borderRadius: BorderRadius.lg,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: Spacing.md,
  },
  aboutAppName: {
    fontSize: FontSizes.xl,
    fontWeight: '700',
  },
  aboutVersion: {
    fontSize: FontSizes.sm,
    marginTop: Spacing.xs,
  },
  aboutSection: {
    paddingVertical: Spacing.md,
    borderBottomWidth: 1,
    marginBottom: Spacing.md,
  },
  aboutSectionTitle: {
    fontSize: FontSizes.xs,
    fontWeight: '600',
    marginBottom: Spacing.sm,
  },
  aboutText: {
    fontSize: FontSizes.sm,
    lineHeight: 20,
  },
  featureList: {
    gap: Spacing.sm,
  },
  featureItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  featureText: {
    fontSize: FontSizes.sm,
  },
  copyright: {
    fontSize: FontSizes.xs,
    textAlign: 'center',
    marginTop: Spacing.lg,
  },
});
