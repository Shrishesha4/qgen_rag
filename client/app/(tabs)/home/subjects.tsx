import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
  ActivityIndicator,
  TextInput,
  Modal,
} from 'react-native';
import { router } from 'expo-router';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { Colors, Spacing, BorderRadius, FontSizes } from '@/constants/theme';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { subjectsService, Subject, SubjectCreateData } from '@/services/subjects';
import { useToast } from '@/components/toast';
import { mediumImpact, heavyImpact } from '@/utils/haptics';
import { showConfirmDialog } from '@/utils/alert';
import { useResponsive } from '@/hooks/use-responsive';

export default function SubjectsScreen() {
  const colorScheme = useColorScheme();
  const colors = Colors[colorScheme ?? 'light'];
  const { showError, showSuccess, showWarning } = useToast();
  const { isDesktop, desktopContentStyle } = useResponsive();

  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);
  const [newSubject, setNewSubject] = useState<SubjectCreateData>({ name: '', code: '' });
  const [isCreating, setIsCreating] = useState(false);

  const loadSubjects = useCallback(async () => {
    try {
      const response = await subjectsService.listSubjects(1, 100, searchQuery || undefined);
      setSubjects(response.subjects);
    } catch (error) {
      showError(error, 'Failed to Load');
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [searchQuery]);

  useEffect(() => {
    const debounceTimer = setTimeout(() => {
      loadSubjects();
    }, 300);

    return () => clearTimeout(debounceTimer);
  }, [loadSubjects]);

  const handleRefresh = () => {
    setIsRefreshing(true);
    loadSubjects();
  };

  const handleCreateSubject = async () => {
    if (!newSubject.name.trim() || !newSubject.code.trim()) {
      showWarning('Please fill in all required fields', 'Missing Information');
      return;
    }

    setIsCreating(true);
    try {
      await subjectsService.createSubject(newSubject);
      setShowAddModal(false);
      setNewSubject({ name: '', code: '' });
      loadSubjects();
      showSuccess('Subject created successfully');
    } catch (error) {
      showError(error, 'Failed to Create');
    } finally {
      setIsCreating(false);
    }
  };

  const handleDeleteSubject = async (subject: Subject) => {
    mediumImpact();
    showConfirmDialog(
      'Delete Subject',
      `Are you sure you want to delete "${subject.name}"? This will also delete all topics and questions.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              heavyImpact();
              await subjectsService.deleteSubject(subject.id);
              loadSubjects();
              showSuccess('Subject deleted');
            } catch (error) {
              showError(error, 'Failed to Delete');
            }
          },
        },
      ]
    );
  };

  const getSubjectInitials = (name: string, code: string) => {
    return code.substring(0, 2).toUpperCase();
  };

  const getInitialsColor = (index: number) => {
    const colorPalette = ['#007AFF', '#5856D6', '#34C759', '#FF9500', '#FF3B30'];
    return colorPalette[index % colorPalette.length];
  };

  const renderSubject = ({ item, index }: { item: Subject; index: number }) => (
    <TouchableOpacity
      style={[styles.subjectCard, { backgroundColor: colors.card }]}
      onPress={() => router.push(`/(tabs)/home/subject-detail?id=${item.id}` as never)}
      onLongPress={() => handleDeleteSubject(item)}
      activeOpacity={0.7}
    >
      <View style={[styles.initialsContainer, { backgroundColor: getInitialsColor(index) + '20' }]}>
        <Text style={[styles.initials, { color: getInitialsColor(index) }]}>
          {getSubjectInitials(item.name, item.code)}
        </Text>
      </View>

      <View style={styles.subjectInfo}>
        <Text style={[styles.subjectName, { color: colors.text }]}>{item.name}</Text>
        <Text style={[styles.subjectCode, { color: colors.textSecondary }]}>
          {item.code} • {item.total_topics} Topics
        </Text>
      </View>

      <View style={styles.questionsBadge}>
        <IconSymbol name="questionmark.circle" size={14} color={colors.primary} />
        <Text style={[styles.questionsCount, { color: colors.primary }]}>
          {item.total_questions}
        </Text>
      </View>

      <IconSymbol name="chevron.right" size={16} color={colors.textTertiary} />
    </TouchableOpacity>
  );

  if (isLoading) {
    return (
      <View style={[styles.loadingContainer, { backgroundColor: colors.background }]}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      {/* Responsive inner container */}
      <View style={[{ flex: 1 }, desktopContentStyle]}>
      {/* Search Bar */}}
      <View style={[styles.searchContainer, { backgroundColor: colors.card }]}>
        <IconSymbol name="magnifyingglass" size={18} color={colors.textSecondary} />
        <TextInput
          style={[styles.searchInput, { color: colors.text }]}
          placeholder="Search subjects..."
          placeholderTextColor={colors.textSecondary}
          value={searchQuery}
          onChangeText={setSearchQuery}
        />
      </View>

      {/* Subject List */}
      <FlatList
        data={subjects}
        renderItem={renderSubject}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={isRefreshing} onRefresh={handleRefresh} />
        }
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <IconSymbol name="book" size={64} color={colors.textTertiary} />
            <Text style={[styles.emptyTitle, { color: colors.text }]}>No Subjects Yet</Text>
            <Text style={[styles.emptyText, { color: colors.textSecondary }]}>
              Create your first subject to start generating questions.
            </Text>
          </View>
        }
      />

      {/* Add Button */}
      <TouchableOpacity
        style={[styles.addButton, { backgroundColor: colors.primary }]}
        onPress={() => {
          mediumImpact();
          setShowAddModal(true);
        }}
      >
        <IconSymbol name="plus" size={24} color="#FFFFFF" />
      </TouchableOpacity>
      </View>

      {/* Add Subject Modal */}
      <Modal
        visible={showAddModal}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => setShowAddModal(false)}
      >
        <View style={[styles.modalContainer, { backgroundColor: colors.background }]}>
          <View style={[styles.modalHeader, { backgroundColor: '#4A90D9' }]}>
            <TouchableOpacity onPress={() => setShowAddModal(false)}>
              <Text style={styles.modalCancel}>Cancel</Text>
            </TouchableOpacity>
            <Text style={styles.modalTitle}>New Subject</Text>
            <TouchableOpacity onPress={handleCreateSubject} disabled={isCreating}>
              {isCreating ? (
                <ActivityIndicator size="small" color="#FFFFFF" />
              ) : (
                <Text style={styles.modalSave}>Save</Text>
              )}
            </TouchableOpacity>
          </View>

          <View style={styles.modalContent}>
            <View style={[styles.inputGroup, { backgroundColor: colors.card }]}>
              <Text style={[styles.inputLabel, { color: colors.textSecondary }]}>
                SUBJECT NAME
              </Text>
              <TextInput
                style={[styles.input, { color: colors.text }]}
                placeholder="e.g., Computer Science"
                placeholderTextColor={colors.textTertiary}
                value={newSubject.name}
                onChangeText={(text) => setNewSubject({ ...newSubject, name: text })}
              />
            </View>

            <View style={[styles.inputGroup, { backgroundColor: colors.card }]}>
              <Text style={[styles.inputLabel, { color: colors.textSecondary }]}>
                SUBJECT CODE
              </Text>
              <TextInput
                style={[styles.input, { color: colors.text }]}
                placeholder="e.g., CS301"
                placeholderTextColor={colors.textTertiary}
                value={newSubject.code}
                onChangeText={(text) => setNewSubject({ ...newSubject, code: text })}
                autoCapitalize="characters"
              />
            </View>

            <View style={[styles.inputGroup, { backgroundColor: colors.card }]}>
              <Text style={[styles.inputLabel, { color: colors.textSecondary }]}>
                DESCRIPTION (OPTIONAL)
              </Text>
              <TextInput
                style={[styles.input, styles.textArea, { color: colors.text }]}
                placeholder="Enter a brief description..."
                placeholderTextColor={colors.textTertiary}
                value={newSubject.description}
                onChangeText={(text) => setNewSubject({ ...newSubject, description: text })}
                multiline
                numberOfLines={3}
              />
            </View>
          </View>
        </View>
      </Modal>
    </View>
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
  searchContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: Spacing.headerInset + 20,
    marginHorizontal: Spacing.lg,
    marginBottom: Spacing.lg,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.md,
    gap: Spacing.sm,
  },
  searchInput: {
    flex: 1,
    fontSize: FontSizes.md,
    paddingVertical: Spacing.xs,
  },
  listContent: {
    paddingHorizontal: Spacing.lg,
    paddingBottom: 100,
  },
  subjectCard: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: Spacing.md,
    borderRadius: BorderRadius.md,
    marginBottom: Spacing.sm,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 1,
  },
  initialsContainer: {
    width: 44,
    height: 44,
    borderRadius: BorderRadius.sm,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: Spacing.md,
  },
  initials: {
    fontSize: FontSizes.md,
    fontWeight: '700',
  },
  subjectInfo: {
    flex: 1,
  },
  subjectName: {
    fontSize: FontSizes.md,
    fontWeight: '600',
    marginBottom: Spacing.xs,
  },
  subjectCode: {
    fontSize: FontSizes.sm,
  },
  questionsBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    marginRight: Spacing.sm,
    gap: Spacing.xs,
  },
  questionsCount: {
    fontSize: FontSizes.sm,
    fontWeight: '600',
  },
  emptyContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: Spacing.xxxl * 2,
  },
  emptyTitle: {
    fontSize: FontSizes.lg,
    fontWeight: '600',
    marginTop: Spacing.lg,
    marginBottom: Spacing.sm,
  },
  emptyText: {
    fontSize: FontSizes.md,
    textAlign: 'center',
    paddingHorizontal: Spacing.xxl,
  },
  addButton: {
    position: 'absolute',
    bottom: Spacing.xxl + 90,
    right: Spacing.lg + 10,
    width: 56,
    height: 56,
    borderRadius: 28,
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 8,
  },
  modalContainer: {
    flex: 1,
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingTop: 20,
    paddingBottom: Spacing.lg,
    paddingHorizontal: Spacing.lg,
  },
  modalTitle: {
    fontSize: FontSizes.xl,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  modalCancel: {
    fontSize: FontSizes.lg,
    color: '#FFFFFF',
  },
  modalSave: {
    fontSize: FontSizes.lg,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  modalContent: {
    padding: Spacing.lg,
    gap: Spacing.md,
  },
  inputGroup: {
    padding: Spacing.md,
    borderRadius: BorderRadius.md,
  },
  inputLabel: {
    fontSize: FontSizes.xs,
    fontWeight: '600',
    marginBottom: Spacing.sm,
  },
  input: {
    fontSize: FontSizes.md,
    paddingVertical: Spacing.xs,
  },
  textArea: {
    height: 80,
    textAlignVertical: 'top',
  },
});
