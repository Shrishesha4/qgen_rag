import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  Alert,
  ActivityIndicator,
  TextInput,
  Modal,
  Platform,
} from 'react-native';
import { router, useLocalSearchParams, Stack } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { GlassCard } from '@/components/ui/glass-card';
import { NativeButton } from '@/components/ui/native-button';
import { Colors, Spacing, BorderRadius, FontSizes } from '@/constants/theme';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { 
  subjectsService, 
  Subject, 
  Topic,
  TopicCreateData,
  TopicUpdateData, 
} from '@/services/subjects';
import * as DocumentPicker from 'expo-document-picker';
import { useToast } from '@/components/toast';

export default function SubjectDetailScreen() {
  const colorScheme = useColorScheme();
  const colors = Colors[colorScheme ?? 'light'];
  const { id } = useLocalSearchParams<{ id: string }>();
  const { showError, showSuccess, showWarning } = useToast();
  
  const [subject, setSubject] = useState<Subject | null>(null);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [showAddTopicModal, setShowAddTopicModal] = useState(false);
  const [showTopicDetailModal, setShowTopicDetailModal] = useState(false);
  const [selectedTopic, setSelectedTopic] = useState<Topic | null>(null);
  const [newTopicName, setNewTopicName] = useState('');
  const [newTopicDescription, setNewTopicDescription] = useState('');
  const [isCreatingTopic, setIsCreatingTopic] = useState(false);
  const [isUploadingDoc, setIsUploadingDoc] = useState(false);
  const [uploadStatus, setUploadStatus] = useState('');
  const [syllabusContent, setSyllabusContent] = useState('');

  const loadData = useCallback(async () => {
    if (!id) return;
    try {
      const [subjectData, topicsData] = await Promise.all([
        subjectsService.getSubject(id),
        subjectsService.listTopics(id, 1, 100),
      ]);
      setSubject(subjectData);
      setTopics(topicsData.topics);
    } catch (error) {
      console.error('Error loading subject:', error);
      showError(error, 'Failed to Load');
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [id]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleRefresh = () => {
    setIsRefreshing(true);
    loadData();
  };

  const handleCreateTopic = async () => {
    if (!newTopicName.trim() || !id) {
      showWarning('Please enter a topic name', 'Missing Information');
      return;
    }
    
    setIsCreatingTopic(true);
    try {
      const data: TopicCreateData = {
        subject_id: id,
        name: newTopicName.trim(),
        description: newTopicDescription.trim() || undefined,
        order_index: topics.length,
      };
      await subjectsService.createTopic(id, data);
      setShowAddTopicModal(false);
      setNewTopicName('');
      setNewTopicDescription('');
      loadData();
      showSuccess('Chapter created successfully');
    } catch (error) {
      showError(error, 'Failed to Create');
    } finally {
      setIsCreatingTopic(false);
    }
  };

  const handleDeleteTopic = async (topic: Topic) => {
    if (!id) return;
    Alert.alert(
      'Delete Chapter',
      `Are you sure you want to delete "${topic.name}"? This will also delete all associated questions.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              await subjectsService.deleteTopic(id, topic.id);
              loadData();
              showSuccess('Chapter deleted');
            } catch (error) {
              showError(error, 'Failed to Delete');
            }
          },
        },
      ]
    );
  };

  const handleTopicPress = (topic: Topic) => {
    setSelectedTopic(topic);
    setSyllabusContent(topic.syllabus_content || '');
    setShowTopicDetailModal(true);
  };

  const handleUploadSyllabus = async () => {
    if (!selectedTopic || !id) return;
    
    setIsUploadingDoc(true);
    setUploadStatus('Selecting file...');
    try {
      // Pick a document
      const result = await DocumentPicker.getDocumentAsync({
        type: ['application/pdf', 'text/plain', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
        copyToCacheDirectory: true,
      });

      if (result.canceled || !result.assets || result.assets.length === 0) {
        setIsUploadingDoc(false);
        setUploadStatus('');
        return;
      }

      const file = result.assets[0];
      const fileSizeMB = file.size ? (file.size / (1024 * 1024)).toFixed(1) : '?';
      
      setUploadStatus(`Uploading ${file.name} (${fileSizeMB}MB)...`);
      
      // Small delay to ensure UI updates
      await new Promise(resolve => setTimeout(resolve, 100));
      
      setUploadStatus('Extracting text from document...');
      
      // Upload directly to topic - this extracts text and saves to syllabus_content
      await subjectsService.uploadTopicSyllabus(
        id,
        selectedTopic.id,
        file.uri,
        file.name,
        file.mimeType || 'application/pdf'
      );
      
      setUploadStatus('Complete!');
      showSuccess('Syllabus content extracted and saved');
      setShowTopicDetailModal(false);
      loadData();
    } catch (error: unknown) {
      showError(error, 'Upload Failed');
    } finally {
      setIsUploadingDoc(false);
      setUploadStatus('');
    }
  };

  const handleSaveSyllabus = async () => {
    if (!selectedTopic || !id) return;
    
    try {
      await subjectsService.updateTopic(id, selectedTopic.id, {
        syllabus_content: syllabusContent,
        has_syllabus: syllabusContent.trim().length > 0,
      });
      showSuccess('Syllabus content saved');
      setShowTopicDetailModal(false);
      loadData();
    } catch (error) {
      showError(error, 'Failed to Save');
    }
  };

  const getTopicColor = (index: number) => {
    const colorPalette = ['#007AFF', '#5856D6', '#34C759', '#FF9500', '#FF3B30', '#AF52DE'];
    return colorPalette[index % colorPalette.length];
  };

  if (isLoading) {
    return (
      <View style={[styles.loadingContainer, { backgroundColor: colors.background }]}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  if (!subject) {
    return (
      <View style={[styles.errorContainer, { backgroundColor: colors.background }]}>
        <IconSymbol name="exclamationmark.triangle" size={48} color={colors.error} />
        <Text style={[styles.errorText, { color: colors.text }]}>Subject not found</Text>
        <TouchableOpacity
          style={[styles.backButton, { backgroundColor: colors.primary }]}
          onPress={() => router.back()}
        >
          <Text style={styles.backButtonText}>Go Back</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <>
      <Stack.Screen 
        options={{ 
          title: subject.code,
          headerBackTitle: 'Subjects',
        }} 
      />
      <View style={[styles.container, { backgroundColor: colors.background }]}>
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          refreshControl={<RefreshControl refreshing={isRefreshing} onRefresh={handleRefresh} />}
        >
          {/* Subject Header */}
          <LinearGradient
            colors={['#4A90D9', '#357ABD'] as const}
            style={styles.headerCard}
          >
            <View style={styles.headerContent}>
              <Text style={styles.subjectCode}>{subject.code}</Text>
              <Text style={styles.subjectName}>{subject.name}</Text>
              {subject.description && (
                <Text style={styles.subjectDescription}>{subject.description}</Text>
              )}
            </View>
            <View style={styles.statsRow}>
              <View style={styles.statItem}>
                <Text style={styles.statValue}>{topics.length}</Text>
                <Text style={styles.statLabel}>Chapters</Text>
              </View>
              <View style={styles.statDivider} />
              <View style={styles.statItem}>
                <Text style={styles.statValue}>{subject.total_questions}</Text>
                <Text style={styles.statLabel}>Questions</Text>
              </View>
              <View style={styles.statDivider} />
              <View style={styles.statItem}>
                <Text style={styles.statValue}>{Math.round(subject.syllabus_coverage)}%</Text>
                <Text style={styles.statLabel}>Coverage</Text>
              </View>
            </View>
          </LinearGradient>

          {/* Quick Actions */}
          <View style={styles.actionsRow}>
            <TouchableOpacity
              style={[styles.actionButton, { backgroundColor: colors.primary }]}
              onPress={() => router.push(`/(tabs)/home/generate?subjectId=${id}` as never)}
            >
              <IconSymbol name="sparkles" size={18} color="#FFFFFF" />
              <Text style={styles.actionButtonText}>Generate Exam</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.actionButton, { backgroundColor: colors.secondary }]}
              onPress={() => router.push(`/(tabs)/home/questions?subjectId=${id}` as never)}
            >
              <IconSymbol name="list.bullet" size={18} color="#FFFFFF" />
              <Text style={styles.actionButtonText}>View Questions</Text>
            </TouchableOpacity>
          </View>

          {/* Chapters Section */}
          <View style={styles.section}>
            <View style={styles.sectionHeader}>
              <Text style={[styles.sectionTitle, { color: colors.textSecondary }]}>
                CHAPTERS ({topics.length})
              </Text>
              <TouchableOpacity
                style={[styles.addButton, { backgroundColor: colors.primary + '15' }]}
                onPress={() => setShowAddTopicModal(true)}
              >
                <IconSymbol name="plus" size={16} color={colors.primary} />
                <Text style={[styles.addButtonText, { color: colors.primary }]}>Add</Text>
              </TouchableOpacity>
            </View>

            {topics.length === 0 ? (
              <View style={[styles.emptyCard, { backgroundColor: colors.card }]}>
                <IconSymbol name="book.closed" size={48} color={colors.textTertiary} />
                <Text style={[styles.emptyTitle, { color: colors.text }]}>No Chapters Yet</Text>
                <Text style={[styles.emptyText, { color: colors.textSecondary }]}>
                  Add chapters to organize your syllabus and enable question generation.
                </Text>
              </View>
            ) : (
              <View style={[styles.topicsList, { backgroundColor: colors.card }]}>
                {topics.map((topic, index) => (
                  <TouchableOpacity
                    key={topic.id}
                    style={[
                      styles.topicCard,
                      index < topics.length - 1 && { borderBottomWidth: 1, borderBottomColor: colors.border },
                    ]}
                    onPress={() => handleTopicPress(topic)}
                    onLongPress={() => handleDeleteTopic(topic)}
                    activeOpacity={0.7}
                  >
                    <View style={[styles.topicIndex, { backgroundColor: getTopicColor(index) + '20' }]}>
                      <Text style={[styles.topicIndexText, { color: getTopicColor(index) }]}>
                        {index + 1}
                      </Text>
                    </View>
                    <View style={styles.topicInfo}>
                      <Text style={[styles.topicName, { color: colors.text }]}>{topic.name}</Text>
                      <View style={styles.topicMeta}>
                        {topic.has_syllabus && (
                          <View style={[styles.badge, { backgroundColor: '#34C75920' }]}>
                            <IconSymbol name="checkmark.circle.fill" size={12} color="#34C759" />
                            <Text style={[styles.badgeText, { color: '#34C759' }]}>Syllabus</Text>
                          </View>
                        )}
                        <View style={[styles.badge, { backgroundColor: colors.primary + '20' }]}>
                          <IconSymbol name="questionmark.circle" size={12} color={colors.primary} />
                          <Text style={[styles.badgeText, { color: colors.primary }]}>
                            {topic.total_questions} Q's
                          </Text>
                        </View>
                      </View>
                    </View>
                    <IconSymbol name="chevron.right" size={16} color={colors.textTertiary} />
                  </TouchableOpacity>
                ))}
              </View>
            )}
          </View>

          {/* Learning Outcomes (if any) */}
          {subject.learning_outcomes?.outcomes && subject.learning_outcomes.outcomes.length > 0 && (
            <View style={styles.section}>
              <Text style={[styles.sectionTitle, { color: colors.textSecondary }]}>
                LEARNING OUTCOMES
              </Text>
              <View style={[styles.loList, { backgroundColor: colors.card }]}>
                {subject.learning_outcomes.outcomes.map((lo, index) => (
                  <View 
                    key={lo.id} 
                    style={[
                      styles.loItem,
                      index < subject.learning_outcomes!.outcomes.length - 1 && { borderBottomWidth: 1, borderBottomColor: colors.border },
                    ]}
                  >
                    <View style={[styles.loBadge, { backgroundColor: getTopicColor(index) }]}>
                      <Text style={styles.loBadgeText}>{lo.id}</Text>
                    </View>
                    <View style={styles.loContent}>
                      <Text style={[styles.loName, { color: colors.text }]}>{lo.name}</Text>
                      {lo.description && (
                        <Text style={[styles.loDescription, { color: colors.textSecondary }]}>
                          {lo.description}
                        </Text>
                      )}
                    </View>
                  </View>
                ))}
              </View>
            </View>
          )}
        </ScrollView>

        {/* Add Topic Modal */}
        <Modal
          visible={showAddTopicModal}
          animationType="slide"
          presentationStyle="pageSheet"
          onRequestClose={() => setShowAddTopicModal(false)}
        >
          <View style={[styles.modalContainer, { backgroundColor: colors.background }]}>
            <View style={[styles.modalHeader, { backgroundColor: colors.card, borderBottomColor: colors.border }]}>
              <TouchableOpacity onPress={() => setShowAddTopicModal(false)}>
                <Text style={[styles.modalCancel, { color: colors.primary }]}>Cancel</Text>
              </TouchableOpacity>
              <Text style={[styles.modalTitle, { color: colors.text }]}>Add Chapter</Text>
              <TouchableOpacity onPress={handleCreateTopic} disabled={isCreatingTopic}>
                {isCreatingTopic ? (
                  <ActivityIndicator size="small" color={colors.primary} />
                ) : (
                  <Text style={[styles.modalDone, { color: colors.primary }]}>Add</Text>
                )}
              </TouchableOpacity>
            </View>
            <ScrollView style={styles.modalContent}>
              <View style={[styles.formSection, { backgroundColor: colors.card }]}>
                <Text style={[styles.formLabel, { color: colors.textSecondary }]}>CHAPTER NAME *</Text>
                <TextInput
                  style={[styles.textInput, { color: colors.text, borderColor: colors.border }]}
                  placeholder="e.g., Introduction to Data Structures"
                  placeholderTextColor={colors.textTertiary}
                  value={newTopicName}
                  onChangeText={setNewTopicName}
                  autoFocus
                />
                <Text style={[styles.formLabel, { color: colors.textSecondary, marginTop: Spacing.md }]}>
                  DESCRIPTION (OPTIONAL)
                </Text>
                <TextInput
                  style={[styles.textAreaInput, { color: colors.text, borderColor: colors.border }]}
                  placeholder="Brief description of this chapter..."
                  placeholderTextColor={colors.textTertiary}
                  value={newTopicDescription}
                  onChangeText={setNewTopicDescription}
                  multiline
                  numberOfLines={3}
                />
              </View>
            </ScrollView>
          </View>
        </Modal>

        {/* Topic Detail Modal */}
        <Modal
          visible={showTopicDetailModal}
          animationType="slide"
          presentationStyle="pageSheet"
          onRequestClose={() => setShowTopicDetailModal(false)}
        >
          <View style={[styles.modalContainer, { backgroundColor: colors.background }]}>
            <View style={[styles.modalHeader, { backgroundColor: colors.card, borderBottomColor: colors.border }]}>
              <TouchableOpacity onPress={() => setShowTopicDetailModal(false)}>
                <Text style={[styles.modalCancel, { color: colors.primary }]}>Close</Text>
              </TouchableOpacity>
              <Text style={[styles.modalTitle, { color: colors.text }]} numberOfLines={1}>
                {selectedTopic?.name}
              </Text>
              <TouchableOpacity onPress={handleSaveSyllabus}>
                <Text style={[styles.modalDone, { color: colors.primary }]}>Save</Text>
              </TouchableOpacity>
            </View>
            <ScrollView style={styles.modalContent}>
              {/* Upload Document */}
              <View style={[styles.formSection, { backgroundColor: colors.card }]}>
                <Text style={[styles.formLabel, { color: colors.textSecondary }]}>UPLOAD SYLLABUS/NOTES</Text>
                <TouchableOpacity
                  style={[
                    styles.uploadButton, 
                    { borderColor: isUploadingDoc ? colors.textTertiary : colors.primary },
                    isUploadingDoc && { backgroundColor: colors.background }
                  ]}
                  onPress={handleUploadSyllabus}
                  disabled={isUploadingDoc}
                >
                  {isUploadingDoc ? (
                    <View style={styles.uploadProgressContainer}>
                      <ActivityIndicator size="small" color={colors.primary} />
                      <Text style={[styles.uploadStatusText, { color: colors.primary }]}>
                        {uploadStatus || 'Processing...'}
                      </Text>
                    </View>
                  ) : (
                    <>
                      <IconSymbol name="doc.badge.plus" size={24} color={colors.primary} />
                      <Text style={[styles.uploadButtonText, { color: colors.primary }]}>
                        Upload PDF, DOCX, or TXT
                      </Text>
                    </>
                  )}
                </TouchableOpacity>
                {isUploadingDoc && (
                  <Text style={[styles.formHint, { color: colors.textSecondary, marginTop: Spacing.sm }]}>
                    This may take a minute for large documents...
                  </Text>
                )}
                <Text style={[styles.formHint, { color: colors.textTertiary }]}>
                  Documents will be processed and used for question generation
                </Text>
              </View>

              {/* Manual Syllabus Content */}
              <View style={[styles.formSection, { backgroundColor: colors.card }]}>
                <Text style={[styles.formLabel, { color: colors.textSecondary }]}>
                  OR PASTE SYLLABUS CONTENT
                </Text>
                <TextInput
                  style={[styles.syllabusInput, { color: colors.text, borderColor: colors.border, backgroundColor: colors.background }]}
                  placeholder="Paste your syllabus content here..."
                  placeholderTextColor={colors.textTertiary}
                  value={syllabusContent}
                  onChangeText={setSyllabusContent}
                  multiline
                  numberOfLines={10}
                  textAlignVertical="top"
                />
              </View>

              {/* Topic Stats */}
              {selectedTopic && (
                <View style={[styles.formSection, { backgroundColor: colors.card }]}>
                  <Text style={[styles.formLabel, { color: colors.textSecondary }]}>STATISTICS</Text>
                  <View style={styles.topicStatsRow}>
                    <View style={styles.topicStatItem}>
                      <Text style={[styles.topicStatValue, { color: colors.text }]}>
                        {selectedTopic.total_questions}
                      </Text>
                      <Text style={[styles.topicStatLabel, { color: colors.textSecondary }]}>
                        Questions
                      </Text>
                    </View>
                    <View style={styles.topicStatItem}>
                      <Text style={[styles.topicStatValue, { color: colors.text }]}>
                        {selectedTopic.has_syllabus ? 'Yes' : 'No'}
                      </Text>
                      <Text style={[styles.topicStatLabel, { color: colors.textSecondary }]}>
                        Has Content
                      </Text>
                    </View>
                  </View>
                </View>
              )}
            </ScrollView>
          </View>
        </Modal>
      </View>
    </>
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
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: Spacing.xl,
  },
  errorText: {
    fontSize: FontSizes.lg,
    fontWeight: '600',
    marginTop: Spacing.md,
    marginBottom: Spacing.lg,
  },
  backButton: {
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.md,
  },
  backButtonText: {
    color: '#FFFFFF',
    fontWeight: '600',
  },
  scrollContent: {
    paddingBottom: Spacing.xxl,
  },
  headerCard: {
    margin: Spacing.md,
    borderRadius: BorderRadius.lg,
    padding: Spacing.lg,
  },
  headerContent: {
    marginBottom: Spacing.md,
  },
  subjectCode: {
    fontSize: FontSizes.sm,
    fontWeight: '600',
    color: 'rgba(255,255,255,0.8)',
    textTransform: 'uppercase',
    letterSpacing: 1,
  },
  subjectName: {
    fontSize: FontSizes.xxl,
    fontWeight: '700',
    color: '#FFFFFF',
    marginTop: Spacing.xs,
  },
  subjectDescription: {
    fontSize: FontSizes.sm,
    color: 'rgba(255,255,255,0.8)',
    marginTop: Spacing.sm,
  },
  statsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(255,255,255,0.15)',
    borderRadius: BorderRadius.md,
    padding: Spacing.md,
  },
  statItem: {
    flex: 1,
    alignItems: 'center',
  },
  statValue: {
    fontSize: FontSizes.xl,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  statLabel: {
    fontSize: FontSizes.xs,
    color: 'rgba(255,255,255,0.8)',
    marginTop: 2,
  },
  statDivider: {
    width: 1,
    height: 30,
    backgroundColor: 'rgba(255,255,255,0.3)',
  },
  actionsRow: {
    flexDirection: 'row',
    paddingHorizontal: Spacing.md,
    gap: Spacing.sm,
    marginBottom: Spacing.md,
  },
  actionButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.md,
    gap: Spacing.xs,
  },
  actionButtonText: {
    color: '#FFFFFF',
    fontWeight: '600',
    fontSize: FontSizes.sm,
  },
  section: {
    paddingHorizontal: Spacing.md,
    marginBottom: Spacing.lg,
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: Spacing.sm,
  },
  sectionTitle: {
    fontSize: FontSizes.xs,
    fontWeight: '600',
    letterSpacing: 0.5,
  },
  addButton: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: Spacing.sm,
    paddingVertical: Spacing.xs,
    borderRadius: BorderRadius.sm,
    gap: 4,
  },
  addButtonText: {
    fontSize: FontSizes.sm,
    fontWeight: '600',
  },
  emptyCard: {
    borderRadius: BorderRadius.lg,
    padding: Spacing.xl,
    alignItems: 'center',
  },
  emptyTitle: {
    fontSize: FontSizes.lg,
    fontWeight: '600',
    marginTop: Spacing.md,
  },
  emptyText: {
    fontSize: FontSizes.sm,
    textAlign: 'center',
    marginTop: Spacing.xs,
    lineHeight: 20,
  },
  topicsList: {
    borderRadius: BorderRadius.lg,
    overflow: 'hidden',
  },
  topicCard: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: Spacing.md,
  },
  topicIndex: {
    width: 36,
    height: 36,
    borderRadius: BorderRadius.md,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: Spacing.sm,
  },
  topicIndexText: {
    fontSize: FontSizes.md,
    fontWeight: '700',
  },
  topicInfo: {
    flex: 1,
  },
  topicName: {
    fontSize: FontSizes.md,
    fontWeight: '500',
    marginBottom: 4,
  },
  topicMeta: {
    flexDirection: 'row',
    gap: Spacing.xs,
  },
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: BorderRadius.sm,
    gap: 4,
  },
  badgeText: {
    fontSize: FontSizes.xs,
    fontWeight: '500',
  },
  loList: {
    borderRadius: BorderRadius.lg,
    overflow: 'hidden',
  },
  loItem: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    padding: Spacing.md,
  },
  loBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: BorderRadius.sm,
    marginRight: Spacing.sm,
  },
  loBadgeText: {
    color: '#FFFFFF',
    fontSize: FontSizes.xs,
    fontWeight: '700',
  },
  loContent: {
    flex: 1,
  },
  loName: {
    fontSize: FontSizes.sm,
    fontWeight: '500',
  },
  loDescription: {
    fontSize: FontSizes.xs,
    marginTop: 2,
  },
  modalContainer: {
    flex: 1,
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.md,
    borderBottomWidth: 1,
  },
  modalCancel: {
    fontSize: FontSizes.md,
  },
  modalTitle: {
    fontSize: FontSizes.md,
    fontWeight: '600',
    flex: 1,
    textAlign: 'center',
    marginHorizontal: Spacing.sm,
  },
  modalDone: {
    fontSize: FontSizes.md,
    fontWeight: '600',
  },
  modalContent: {
    flex: 1,
    padding: Spacing.md,
  },
  formSection: {
    borderRadius: BorderRadius.lg,
    padding: Spacing.md,
    marginBottom: Spacing.md,
  },
  formLabel: {
    fontSize: FontSizes.xs,
    fontWeight: '600',
    letterSpacing: 0.5,
    marginBottom: Spacing.sm,
  },
  formHint: {
    fontSize: FontSizes.xs,
    marginTop: Spacing.sm,
  },
  textInput: {
    borderWidth: 1,
    borderRadius: BorderRadius.md,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    fontSize: FontSizes.md,
  },
  textAreaInput: {
    borderWidth: 1,
    borderRadius: BorderRadius.md,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    fontSize: FontSizes.md,
    minHeight: 80,
    textAlignVertical: 'top',
  },
  uploadButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderStyle: 'dashed',
    borderRadius: BorderRadius.md,
    paddingVertical: Spacing.lg,
    gap: Spacing.sm,
  },
  uploadButtonText: {
    fontSize: FontSizes.md,
    fontWeight: '500',
  },
  uploadProgressContainer: {
    flexDirection: 'column',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  uploadStatusText: {
    fontSize: FontSizes.sm,
    fontWeight: '500',
    textAlign: 'center',
  },
  syllabusInput: {
    borderWidth: 1,
    borderRadius: BorderRadius.md,
    padding: Spacing.md,
    fontSize: FontSizes.sm,
    minHeight: 200,
  },
  topicStatsRow: {
    flexDirection: 'row',
    gap: Spacing.lg,
  },
  topicStatItem: {
    flex: 1,
  },
  topicStatValue: {
    fontSize: FontSizes.xl,
    fontWeight: '700',
  },
  topicStatLabel: {
    fontSize: FontSizes.xs,
    marginTop: 2,
  },
});
