import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
  ActivityIndicator,
  Modal,
  ScrollView,
  TextInput,
  Alert,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Stack, useLocalSearchParams } from 'expo-router';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { Colors, Spacing, BorderRadius, FontSizes } from '@/constants/theme';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { questionsService, Question, QuestionUpdateRequest } from '@/services/questions';
import { subjectsService } from '@/services/subjects';
import { useToast } from '@/components/toast';

const FILTER_OPTIONS = [
  { label: 'All', value: '' },
  { label: 'MCQ', value: 'mcq' },
  { label: 'Short Answer', value: 'short_answer' },
  { label: 'Long Answer', value: 'long_answer' },
  { label: 'Essay', value: 'essay' },
];

const BLOOM_COLORS: Record<string, string> = {
  remember: '#ef4444',
  understand: '#f97316',
  apply: '#eab308',
  analyze: '#22c55e',
  evaluate: '#3b82f6',
  create: '#8b5cf6',
};

const VETTING_COLORS: Record<string, string> = {
  pending: '#f59e0b',
  approved: '#22c55e',
  rejected: '#ef4444',
};

export default function QuestionsScreen() {
  const colorScheme = useColorScheme();
  const colors = Colors[colorScheme ?? 'light'];
  const { showError, showSuccess } = useToast();
  const { subjectId } = useLocalSearchParams<{ subjectId?: string }>();

  const [questions, setQuestions] = useState<Question[]>([]);
  const [subject, setSubject] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [filterType, setFilterType] = useState('');
  const [selectedQuestion, setSelectedQuestion] = useState<Question | null>(null);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [showArchived, setShowArchived] = useState(false);

  // Edit mode state
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [editData, setEditData] = useState<QuestionUpdateRequest>({});

  const loadQuestions = useCallback(async (pageNum: number, append: boolean = false) => {
    try {
      // When viewing a subject's questions (not archived), only show approved questions
      const vettingStatus = (subjectId && !showArchived) ? 'approved' : undefined;

      const response = await questionsService.listQuestions(
        pageNum,
        20,
        filterType || undefined,
        undefined,
        undefined,
        subjectId,
        showArchived,
        vettingStatus,
      );

      if (append) {
        setQuestions((prev) => [...prev, ...response.questions]);
      } else {
        setQuestions(response.questions);
      }

      setHasMore(response.pagination.page < response.pagination.total_pages);
    } catch (error) {
      showError(error, 'Failed to Load Questions');
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [filterType, subjectId, showArchived]);

  const loadSubject = useCallback(async () => {
    if (!subjectId) return;
    try {
      const data = await subjectsService.getSubject(subjectId);
      setSubject(data);
    } catch (error) {
      console.error('Failed to load subject:', error);
    }
  }, [subjectId]);

  useEffect(() => {
    loadSubject();
    setIsLoading(true);
    setPage(1);
    loadQuestions(1);
  }, [filterType, showArchived, loadQuestions, loadSubject]);

  const handleRefresh = () => {
    setIsRefreshing(true);
    setPage(1);
    loadQuestions(1);
  };

  const handleLoadMore = () => {
    if (hasMore && !isLoading) {
      const nextPage = page + 1;
      setPage(nextPage);
      loadQuestions(nextPage, true);
    }
  };

  const handleRate = async (questionId: string, rating: number) => {
    try {
      await questionsService.rateQuestion(questionId, rating);
      setQuestions((prev) =>
        prev.map((q) => (q.id === questionId ? { ...q, user_rating: rating } : q))
      );
      if (selectedQuestion?.id === questionId) {
        setSelectedQuestion((prev) => prev ? { ...prev, user_rating: rating } : null);
      }
      showSuccess('Question rated');
    } catch (error) {
      showError(error, 'Rating Failed');
    }
  };

  const handleArchive = async (questionId: string) => {
    try {
      await questionsService.archiveQuestion(questionId);
      setQuestions((prev) => prev.filter((q) => q.id !== questionId));
      setSelectedQuestion(null);
      showSuccess('Question archived');
    } catch (error) {
      showError(error, 'Archive Failed');
    }
  };

  const handleUnarchive = async (questionId: string) => {
    try {
      await questionsService.unarchiveQuestion(questionId);
      setQuestions((prev) => prev.filter((q) => q.id !== questionId));
      setSelectedQuestion(null);
      showSuccess('Question restored');
    } catch (error) {
      showError(error, 'Restore Failed');
    }
  };

  // Enter edit mode with current question values
  const startEditing = () => {
    if (!selectedQuestion) return;
    setEditData({
      question_text: selectedQuestion.question_text,
      correct_answer: selectedQuestion.correct_answer || undefined,
      options: selectedQuestion.options || undefined,
      marks: selectedQuestion.marks || undefined,
      learning_outcome_id: selectedQuestion.learning_outcome_id || undefined,
      course_outcome_mapping: selectedQuestion.course_outcome_mapping || undefined,
    });
    setIsEditing(true);
  };

  const cancelEditing = () => {
    setIsEditing(false);
    setEditData({});
  };

  const handleSaveEdit = async () => {
    if (!selectedQuestion) return;
    setIsSaving(true);
    try {
      const updated = await questionsService.updateQuestion(selectedQuestion.id, editData);
      // Update in list
      setQuestions((prev) =>
        prev.map((q) => (q.id === updated.id ? updated : q))
      );
      setSelectedQuestion(updated);
      setIsEditing(false);
      setEditData({});
      showSuccess('Question updated');
    } catch (error) {
      showError(error, 'Update Failed');
    } finally {
      setIsSaving(false);
    }
  };

  const renderStars = (rating: number | null, questionId: string, readonly: boolean = false) => {
    return (
      <View style={styles.starsContainer}>
        {[1, 2, 3, 4, 5].map((star) => (
          <TouchableOpacity
            key={star}
            onPress={() => !readonly && handleRate(questionId, star)}
            disabled={readonly}
          >
            <IconSymbol
              name={star <= (rating || 0) ? 'star.fill' : 'star'}
              size={16}
              color={star <= (rating || 0) ? '#f59e0b' : colors.border}
            />
          </TouchableOpacity>
        ))}
      </View>
    );
  };

  const getBloomColor = (level: string | null): string => {
    if (!level) return colors.primary;
    return BLOOM_COLORS[level.toLowerCase()] || colors.primary;
  };

  const renderQuestion = ({ item }: { item: Question }) => (
    <TouchableOpacity
      style={[styles.questionCard, { backgroundColor: colors.card }]}
      onPress={() => setSelectedQuestion(item)}
      activeOpacity={0.7}
    >
      <View style={styles.questionHeader}>
        <View style={styles.badgesContainer}>
          <View style={[styles.badge, { backgroundColor: colors.primary + '20' }]}>
            <Text style={[styles.badgeText, { color: colors.primary }]}>
              {item.question_type.replace('_', ' ')}
            </Text>
          </View>
          {item.difficulty_level && (
            <View style={[styles.badge, { backgroundColor: '#f59e0b20' }]}>
              <Text style={[styles.badgeText, { color: '#f59e0b' }]}>
                {item.difficulty_level}
              </Text>
            </View>
          )}
          {item.bloom_taxonomy_level && (
            <View style={[styles.badge, { backgroundColor: getBloomColor(item.bloom_taxonomy_level) + '20' }]}>
              <Text style={[styles.badgeText, { color: getBloomColor(item.bloom_taxonomy_level) }]}>
                {item.bloom_taxonomy_level}
              </Text>
            </View>
          )}
          {/* CO badge */}
          {item.course_outcome_mapping && Object.keys(item.course_outcome_mapping).length > 0 && (
            <View style={[styles.badge, { backgroundColor: '#8b5cf620' }]}>
              <Text style={[styles.badgeText, { color: '#8b5cf6' }]}>
                {Object.keys(item.course_outcome_mapping).join(', ')}
              </Text>
            </View>
          )}
          {/* LO badge */}
          {item.learning_outcome_id && (
            <View style={[styles.badge, { backgroundColor: '#06b6d420' }]}>
              <Text style={[styles.badgeText, { color: '#06b6d4' }]}>
                {item.learning_outcome_id}
              </Text>
            </View>
          )}
        </View>
        <Text style={[styles.marksText, { color: colors.textSecondary }]}>
          {item.marks || '0'} marks
        </Text>
      </View>

      <Text style={[styles.questionText, { color: colors.text }]} numberOfLines={3}>
        {item.question_text}
      </Text>

      {/* Show correct answer preview for MCQs */}
      {item.question_type === 'mcq' && item.correct_answer && (
        <View style={[styles.answerPreview, { backgroundColor: '#22c55e10' }]}>
          <IconSymbol name="checkmark.circle.fill" size={14} color="#22c55e" />
          <Text style={[styles.answerPreviewText, { color: '#22c55e' }]} numberOfLines={1}>
            {item.correct_answer}
          </Text>
        </View>
      )}

      <View style={styles.questionFooter}>
        {renderStars(item.user_rating, item.id, true)}
      </View>
    </TouchableOpacity>
  );

  const renderQuestionDetail = () => {
    if (!selectedQuestion) return null;

    return (
      <Modal
        visible={!!selectedQuestion}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => { setSelectedQuestion(null); cancelEditing(); }}
      >
        <View style={[styles.modalContainer, { backgroundColor: colors.background }]}>
          <View style={[styles.modalHeader, { backgroundColor: colors.card, borderBottomColor: colors.border }]}>
            <TouchableOpacity onPress={() => { setSelectedQuestion(null); cancelEditing(); }}>
              <IconSymbol name="xmark" size={24} color={colors.text} />
            </TouchableOpacity>
            <Text style={[styles.modalTitle, { color: colors.text }]}>Question Details</Text>
            <View style={styles.modalHeaderActions}>
              {!isEditing ? (
                <>
                  <TouchableOpacity onPress={startEditing} style={{ marginRight: Spacing.sm }}>
                    <IconSymbol name="pencil" size={22} color={colors.primary} />
                  </TouchableOpacity>
                  {showArchived ? (
                    <TouchableOpacity onPress={() => handleUnarchive(selectedQuestion.id)}>
                      <IconSymbol name="arrow.uturn.backward" size={22} color="#10b981" />
                    </TouchableOpacity>
                  ) : (
                    <TouchableOpacity onPress={() => handleArchive(selectedQuestion.id)}>
                      <IconSymbol name="archivebox" size={22} color="#ef4444" />
                    </TouchableOpacity>
                  )}
                </>
              ) : (
                <>
                  <TouchableOpacity onPress={cancelEditing} style={{ marginRight: Spacing.sm }}>
                    <Text style={{ color: colors.textSecondary, fontWeight: '600' }}>Cancel</Text>
                  </TouchableOpacity>
                  <TouchableOpacity onPress={handleSaveEdit} disabled={isSaving}>
                    {isSaving ? (
                      <ActivityIndicator size="small" color={colors.primary} />
                    ) : (
                      <Text style={{ color: colors.primary, fontWeight: '700' }}>Save</Text>
                    )}
                  </TouchableOpacity>
                </>
              )}
            </View>
          </View>

          <ScrollView style={styles.modalContent}>
            {/* Vetting Status + Badges */}
            <View style={styles.badgeSection}>
              <View style={styles.badgesContainer}>
                {/* Vetting status badge */}
                <View style={[styles.badge, { backgroundColor: VETTING_COLORS[selectedQuestion.vetting_status] + '20' }]}>
                  <Text style={[styles.badgeText, { color: VETTING_COLORS[selectedQuestion.vetting_status] }]}>
                    {selectedQuestion.vetting_status}
                  </Text>
                </View>
                <View style={[styles.badge, { backgroundColor: colors.primary + '20' }]}>
                  <Text style={[styles.badgeText, { color: colors.primary }]}>
                    {selectedQuestion.question_type.replace('_', ' ')}
                  </Text>
                </View>
                {selectedQuestion.difficulty_level && (
                  <View style={[styles.badge, { backgroundColor: '#f59e0b20' }]}>
                    <Text style={[styles.badgeText, { color: '#f59e0b' }]}>
                      {selectedQuestion.difficulty_level}
                    </Text>
                  </View>
                )}
                {selectedQuestion.bloom_taxonomy_level && (
                  <View style={[styles.badge, { backgroundColor: getBloomColor(selectedQuestion.bloom_taxonomy_level) + '20' }]}>
                    <Text style={[styles.badgeText, { color: getBloomColor(selectedQuestion.bloom_taxonomy_level) }]}>
                      {selectedQuestion.bloom_taxonomy_level}
                    </Text>
                  </View>
                )}
              </View>
            </View>

            {/* Question Text */}
            <View style={[styles.section, { backgroundColor: colors.card }]}>
              <Text style={[styles.sectionLabel, { color: colors.textSecondary }]}>Question</Text>
              {isEditing ? (
                <TextInput
                  style={[styles.editInput, { color: colors.text, borderColor: colors.border }]}
                  value={editData.question_text || ''}
                  onChangeText={(text) => setEditData((prev) => ({ ...prev, question_text: text }))}
                  multiline
                  numberOfLines={4}
                  textAlignVertical="top"
                />
              ) : (
                <Text style={[styles.questionDetailText, { color: colors.text }]}>
                  {selectedQuestion.question_text}
                </Text>
              )}
            </View>

            {/* Options (for MCQ) */}
            {selectedQuestion.question_type === 'mcq' && selectedQuestion.options && (
              <View style={[styles.section, { backgroundColor: colors.card }]}>
                <Text style={[styles.sectionLabel, { color: colors.textSecondary }]}>Options</Text>
                {(isEditing ? (editData.options || selectedQuestion.options) : selectedQuestion.options).map((option, index) => (
                  <View
                    key={index}
                    style={[
                      styles.optionRow,
                      !isEditing && option === selectedQuestion.correct_answer && [styles.correctOption, { borderColor: '#34C759' }],
                      { backgroundColor: !isEditing && option === selectedQuestion.correct_answer ? '#34C75920' : colors.background },
                    ]}
                  >
                    <Text style={[styles.optionLetter, { color: colors.textSecondary }]}>
                      {String.fromCharCode(65 + index)}
                    </Text>
                    {isEditing ? (
                      <TextInput
                        style={[styles.editOptionInput, { color: colors.text, flex: 1 }]}
                        value={option}
                        onChangeText={(text) => {
                          const newOptions = [...(editData.options || selectedQuestion.options || [])];
                          newOptions[index] = text;
                          setEditData((prev) => ({ ...prev, options: newOptions }));
                        }}
                      />
                    ) : (
                      <Text style={[styles.optionText, { color: colors.text }]}>{option}</Text>
                    )}
                    {!isEditing && option === selectedQuestion.correct_answer && (
                      <IconSymbol name="checkmark.circle.fill" size={20} color="#34C759" />
                    )}
                  </View>
                ))}
              </View>
            )}

            {/* Answer/Solution */}
            <View style={[styles.section, { backgroundColor: colors.card }]}>
              <Text style={[styles.sectionLabel, { color: colors.textSecondary }]}>
                {selectedQuestion.question_type === 'mcq' ? 'Correct Answer' : 'Model Answer'}
              </Text>
              {isEditing ? (
                <TextInput
                  style={[styles.editInput, { color: colors.text, borderColor: colors.border }]}
                  value={editData.correct_answer || selectedQuestion.correct_answer || ''}
                  onChangeText={(text) => setEditData((prev) => ({ ...prev, correct_answer: text }))}
                  multiline
                  numberOfLines={3}
                  textAlignVertical="top"
                />
              ) : (
                <Text style={[styles.answerText, { color: colors.text, backgroundColor: '#34C75910' }]}>
                  {selectedQuestion.correct_answer || 'No answer provided'}
                </Text>
              )}
            </View>

            {/* Explanation */}
            {selectedQuestion.explanation && !isEditing && (
              <View style={[styles.section, { backgroundColor: colors.card }]}>
                <Text style={[styles.sectionLabel, { color: colors.textSecondary }]}>Explanation</Text>
                <Text style={[styles.questionDetailText, { color: colors.text }]}>
                  {selectedQuestion.explanation}
                </Text>
              </View>
            )}

            {/* CO Mapping */}
            <View style={[styles.section, { backgroundColor: colors.card }]}>
              <Text style={[styles.sectionLabel, { color: colors.textSecondary }]}>Course Outcome (CO)</Text>
              {isEditing ? (
                <View>
                  <Text style={[styles.editHint, { color: colors.textTertiary }]}>
                    Format: CO1, CO2, etc. Tap to toggle.
                  </Text>
                  <View style={styles.coChipsContainer}>
                    {['CO1', 'CO2', 'CO3', 'CO4', 'CO5'].map((co) => {
                      const currentMapping = editData.course_outcome_mapping || selectedQuestion.course_outcome_mapping || {};
                      const isActive = co in currentMapping;
                      return (
                        <TouchableOpacity
                          key={co}
                          style={[
                            styles.coChip,
                            { backgroundColor: isActive ? '#8b5cf620' : colors.background, borderColor: isActive ? '#8b5cf6' : colors.border },
                          ]}
                          onPress={() => {
                            const newMapping = { ...(editData.course_outcome_mapping || selectedQuestion.course_outcome_mapping || {}) };
                            if (isActive) {
                              delete newMapping[co];
                            } else {
                              newMapping[co] = 1;
                            }
                            setEditData((prev) => ({ ...prev, course_outcome_mapping: newMapping }));
                          }}
                        >
                          <Text style={[styles.coChipText, { color: isActive ? '#8b5cf6' : colors.textSecondary }]}>
                            {co}{isActive ? `: L${currentMapping[co]}` : ''}
                          </Text>
                        </TouchableOpacity>
                      );
                    })}
                  </View>
                </View>
              ) : (
                selectedQuestion.course_outcome_mapping && Object.keys(selectedQuestion.course_outcome_mapping).length > 0 ? (
                  <View style={styles.coChipsContainer}>
                    {Object.entries(selectedQuestion.course_outcome_mapping).map(([co, level]) => (
                      <View key={co} style={[styles.coChip, { backgroundColor: '#8b5cf620', borderColor: '#8b5cf6' }]}>
                        <Text style={[styles.coChipText, { color: '#8b5cf6' }]}>
                          {co}: Level {level}
                        </Text>
                      </View>
                    ))}
                  </View>
                ) : (
                  <Text style={[styles.emptyField, { color: colors.textTertiary }]}>Not assigned</Text>
                )
              )}
            </View>

            {/* LO Mapping */}
            <View style={[styles.section, { backgroundColor: colors.card }]}>
              <Text style={[styles.sectionLabel, { color: colors.textSecondary }]}>Learning Outcome (LO)</Text>
              {isEditing ? (
                <TextInput
                  style={[styles.editInputSmall, { color: colors.text, borderColor: colors.border }]}
                  value={editData.learning_outcome_id || selectedQuestion.learning_outcome_id || ''}
                  onChangeText={(text) => setEditData((prev) => ({ ...prev, learning_outcome_id: text }))}
                  placeholder="e.g., LO1, LO2"
                  placeholderTextColor={colors.textTertiary}
                />
              ) : (
                <Text style={[
                  selectedQuestion.learning_outcome_id ? styles.loValueText : styles.emptyField,
                  { color: selectedQuestion.learning_outcome_id ? '#06b6d4' : colors.textTertiary }
                ]}>
                  {selectedQuestion.learning_outcome_id || 'Not assigned'}
                </Text>
              )}
            </View>

            {/* Marks (editable) */}
            {isEditing && (
              <View style={[styles.section, { backgroundColor: colors.card }]}>
                <Text style={[styles.sectionLabel, { color: colors.textSecondary }]}>Marks</Text>
                <TextInput
                  style={[styles.editInputSmall, { color: colors.text, borderColor: colors.border }]}
                  value={String(editData.marks ?? selectedQuestion.marks ?? '')}
                  onChangeText={(text) => {
                    const num = parseInt(text, 10);
                    if (!isNaN(num)) {
                      setEditData((prev) => ({ ...prev, marks: num }));
                    } else if (text === '') {
                      setEditData((prev) => ({ ...prev, marks: undefined }));
                    }
                  }}
                  keyboardType="numeric"
                  placeholder="Enter marks"
                  placeholderTextColor={colors.textTertiary}
                />
              </View>
            )}

            {/* Rating */}
            {!isEditing && (
              <View style={[styles.section, { backgroundColor: colors.card }]}>
                <Text style={[styles.sectionLabel, { color: colors.textSecondary }]}>Rate Quality</Text>
                {renderStars(selectedQuestion.user_rating, selectedQuestion.id)}
              </View>
            )}

            {/* Metadata */}
            {!isEditing && (
              <View style={[styles.metaSection, { backgroundColor: colors.card, borderTopColor: colors.border }]}>
                <View style={styles.metaRow}>
                  <IconSymbol name="target" size={16} color={colors.primary} />
                  <View style={{ flex: 1, marginLeft: Spacing.sm }}>
                    <Text style={[styles.metaLabel, { color: colors.textSecondary }]}>Marks</Text>
                    <Text style={[styles.metaValue, { color: colors.text }]}>{selectedQuestion.marks || 0}</Text>
                  </View>
                </View>
                <View style={styles.metaRow}>
                  <IconSymbol name="calendar" size={16} color={colors.primary} />
                  <View style={{ flex: 1, marginLeft: Spacing.sm }}>
                    <Text style={[styles.metaLabel, { color: colors.textSecondary }]}>Created</Text>
                    <Text style={[styles.metaValue, { color: colors.text }]}>
                      {new Date(selectedQuestion.generated_at).toLocaleDateString()}
                    </Text>
                  </View>
                </View>
                {selectedQuestion.vetted_at && (
                  <View style={styles.metaRow}>
                    <IconSymbol name="checkmark.shield" size={16} color={VETTING_COLORS[selectedQuestion.vetting_status]} />
                    <View style={{ flex: 1, marginLeft: Spacing.sm }}>
                      <Text style={[styles.metaLabel, { color: colors.textSecondary }]}>Vetted</Text>
                      <Text style={[styles.metaValue, { color: colors.text }]}>
                        {new Date(selectedQuestion.vetted_at).toLocaleDateString()}
                      </Text>
                    </View>
                  </View>
                )}
                {selectedQuestion.vetting_notes && (
                  <View style={styles.metaRow}>
                    <IconSymbol name="text.bubble" size={16} color={colors.primary} />
                    <View style={{ flex: 1, marginLeft: Spacing.sm }}>
                      <Text style={[styles.metaLabel, { color: colors.textSecondary }]}>Vetting Notes</Text>
                      <Text style={[styles.metaValue, { color: colors.text }]}>
                        {selectedQuestion.vetting_notes}
                      </Text>
                    </View>
                  </View>
                )}
              </View>
            )}
          </ScrollView>
        </View>
      </Modal>
    );
  };

  if (isLoading && questions.length === 0) {
    return (
      <View style={[styles.centerContainer, { backgroundColor: colors.background }]}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  return (
    <>
      <Stack.Screen
        options={{
          title: subject?.code || 'Questions',
          headerBackTitle: 'Subjects',
        }}
      />
      <View style={[styles.container, { backgroundColor: colors.background }]}>
        {/* Filter Chips */}
        <View style={[styles.filterContainer, { backgroundColor: colors.card }]}>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filterContent}>
            {FILTER_OPTIONS.map((option) => (
              <TouchableOpacity
                key={option.value}
                style={[
                  styles.filterChip,
                  filterType === option.value && [
                    styles.filterChipActive,
                    { backgroundColor: colors.primary },
                  ],
                  filterType !== option.value && { backgroundColor: colors.background },
                ]}
                onPress={() => setFilterType(option.value)}
              >
                <Text
                  style={[
                    styles.filterChipText,
                    filterType === option.value && styles.filterChipTextActive,
                    filterType !== option.value && { color: colors.textSecondary },
                  ]}
                >
                  {option.label}
                </Text>
              </TouchableOpacity>
            ))}
            {/* Archived Toggle */}
            <TouchableOpacity
              style={[
                styles.filterChip,
                showArchived && [
                  styles.filterChipActive,
                  { backgroundColor: '#ef4444' },
                ],
                !showArchived && { backgroundColor: colors.background },
              ]}
              onPress={() => setShowArchived(!showArchived)}
            >
              <IconSymbol
                name={showArchived ? "archivebox.fill" : "archivebox"}
                size={14}
                color={showArchived ? '#FFFFFF' : colors.textSecondary}
              />
              <Text
                style={[
                  styles.filterChipText,
                  showArchived && styles.filterChipTextActive,
                  !showArchived && { color: colors.textSecondary },
                  { marginLeft: 4 }
                ]}
              >
                Archived
              </Text>
            </TouchableOpacity>
          </ScrollView>
        </View>

        {/* Questions List */}
        <FlatList
          data={questions}
          renderItem={renderQuestion}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.listContent}
          refreshControl={
            <RefreshControl
              refreshing={isRefreshing}
              onRefresh={handleRefresh}
              tintColor={colors.primary}
            />
          }
          onEndReached={handleLoadMore}
          onEndReachedThreshold={0.5}
          ListEmptyComponent={
            <View style={styles.emptyContainer}>
              <IconSymbol name="questionmark.circle" size={64} color={colors.textTertiary} />
              <Text style={[styles.emptyTitle, { color: colors.text }]}>
                {showArchived ? 'No Archived Questions' : 'No Questions Yet'}
              </Text>
              <Text style={[styles.emptyText, { color: colors.textSecondary }]}>
                {showArchived
                  ? 'Archived questions will appear here.'
                  : filterType
                    ? 'No questions match your filter'
                    : subjectId
                      ? 'Approved questions for this subject will appear here.'
                      : 'Generate questions from your documents to see them here.'}
              </Text>
            </View>
          }
          ListFooterComponent={
            hasMore && questions.length > 0 ? (
              <ActivityIndicator style={styles.loadingMore} color={colors.primary} />
            ) : null
          }
        />

        {renderQuestionDetail()}
      </View>
    </>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  filterContainer: {
    paddingVertical: Spacing.md,
    paddingHorizontal: Spacing.md,
  },
  filterContent: {
    paddingHorizontal: Spacing.xs,
    gap: Spacing.sm,
  },
  filterChip: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.full,
    borderWidth: 1,
    borderColor: 'transparent',
  },
  filterChipActive: {
    borderWidth: 0,
  },
  filterChipText: {
    fontSize: FontSizes.sm,
    fontWeight: '500',
  },
  filterChipTextActive: {
    color: '#FFFFFF',
    fontWeight: '600',
  },
  listContent: {
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.md,
    paddingBottom: Spacing.xxl,
  },
  questionCard: {
    borderRadius: BorderRadius.lg,
    padding: Spacing.md,
    marginBottom: Spacing.md,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.08,
    shadowRadius: 3,
    elevation: 2,
  },
  questionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: Spacing.md,
  },
  badgesContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.xs,
    flex: 1,
  },
  badge: {
    paddingHorizontal: Spacing.sm,
    paddingVertical: Spacing.xs,
    borderRadius: BorderRadius.sm,
  },
  badgeText: {
    fontSize: FontSizes.xs,
    fontWeight: '600',
    textTransform: 'capitalize',
  },
  marksText: {
    fontSize: FontSizes.xs,
    fontWeight: '600',
    marginLeft: Spacing.sm,
  },
  questionText: {
    fontSize: FontSizes.md,
    lineHeight: 22,
    marginBottom: Spacing.md,
  },
  answerPreview: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: Spacing.sm,
    paddingVertical: Spacing.xs,
    borderRadius: BorderRadius.sm,
    marginBottom: Spacing.sm,
    gap: Spacing.xs,
  },
  answerPreviewText: {
    fontSize: FontSizes.xs,
    fontWeight: '500',
    flex: 1,
  },
  questionFooter: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  starsContainer: {
    flexDirection: 'row',
    gap: Spacing.xs,
  },
  emptyContainer: {
    alignItems: 'center',
    paddingVertical: Spacing.xxl + Spacing.xl,
    paddingHorizontal: Spacing.xl,
  },
  emptyTitle: {
    fontSize: FontSizes.lg,
    fontWeight: '600',
    marginTop: Spacing.md,
    marginBottom: Spacing.sm,
  },
  emptyText: {
    fontSize: FontSizes.sm,
    textAlign: 'center',
    lineHeight: 20,
  },
  loadingMore: {
    paddingVertical: Spacing.xl,
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
  modalTitle: {
    fontSize: FontSizes.lg,
    fontWeight: '600',
    flex: 1,
    textAlign: 'center',
  },
  modalHeaderActions: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  modalContent: {
    flex: 1,
    paddingVertical: Spacing.md,
  },
  badgeSection: {
    paddingHorizontal: Spacing.md,
    paddingBottom: Spacing.md,
  },
  section: {
    marginHorizontal: Spacing.md,
    marginBottom: Spacing.md,
    borderRadius: BorderRadius.lg,
    padding: Spacing.md,
  },
  sectionLabel: {
    fontSize: FontSizes.xs,
    fontWeight: '600',
    letterSpacing: 0.5,
    marginBottom: Spacing.sm,
    textTransform: 'uppercase',
  },
  questionDetailText: {
    fontSize: FontSizes.md,
    lineHeight: 24,
  },
  optionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: Spacing.md,
    borderRadius: BorderRadius.md,
    marginBottom: Spacing.sm,
    gap: Spacing.sm,
    borderWidth: 1,
    borderColor: 'transparent',
  },
  correctOption: {
    borderWidth: 1.5,
  },
  optionLetter: {
    fontSize: FontSizes.md,
    fontWeight: '600',
    width: 24,
  },
  optionText: {
    fontSize: FontSizes.sm,
    flex: 1,
    lineHeight: 20,
  },
  answerText: {
    fontSize: FontSizes.md,
    lineHeight: 22,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.md,
    borderRadius: BorderRadius.md,
    borderLeftWidth: 4,
    borderLeftColor: '#34C759',
  },
  metaSection: {
    marginHorizontal: Spacing.md,
    marginBottom: Spacing.xl,
    borderRadius: BorderRadius.lg,
    padding: Spacing.md,
    borderTopWidth: 1,
    gap: Spacing.md,
  },
  metaRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  metaLabel: {
    fontSize: FontSizes.xs,
    fontWeight: '600',
    letterSpacing: 0.5,
    textTransform: 'uppercase',
  },
  metaValue: {
    fontSize: FontSizes.sm,
    fontWeight: '500',
    marginTop: Spacing.xs,
  },
  // Edit mode styles
  editInput: {
    borderWidth: 1,
    borderRadius: BorderRadius.md,
    padding: Spacing.md,
    fontSize: FontSizes.md,
    lineHeight: 22,
    minHeight: 80,
  },
  editInputSmall: {
    borderWidth: 1,
    borderRadius: BorderRadius.md,
    padding: Spacing.md,
    fontSize: FontSizes.md,
    height: 44,
  },
  editOptionInput: {
    fontSize: FontSizes.sm,
    lineHeight: 20,
    padding: 0,
  },
  editHint: {
    fontSize: FontSizes.xs,
    marginBottom: Spacing.sm,
  },
  coChipsContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.sm,
  },
  coChip: {
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.md,
    borderWidth: 1,
  },
  coChipText: {
    fontSize: FontSizes.sm,
    fontWeight: '600',
  },
  loValueText: {
    fontSize: FontSizes.md,
    fontWeight: '600',
    paddingHorizontal: Spacing.sm,
    paddingVertical: Spacing.xs,
  },
  emptyField: {
    fontSize: FontSizes.sm,
    fontStyle: 'italic',
  },
});
