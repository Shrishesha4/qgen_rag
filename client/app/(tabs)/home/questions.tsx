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
} from 'react-native';
import { Stack, useLocalSearchParams } from 'expo-router';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { Colors, Spacing, BorderRadius, FontSizes } from '@/constants/theme';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { questionsService, Question, QuestionUpdateRequest } from '@/services/questions';
import { subjectsService, Topic } from '@/services/subjects';
import { useToast } from '@/components/toast';
import { ExportModal } from '@/components/export-modal';

const FILTER_OPTIONS = [
  { label: 'All', value: '' },
  { label: 'MCQ', value: 'mcq' },
  { label: 'Short Answer', value: 'short_answer' },
  { label: 'Long Answer', value: 'long_answer' },
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
  const [topics, setTopics] = useState<Topic[]>([]);
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

  // Export modal state
  const [showExportModal, setShowExportModal] = useState(false);

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

  const loadTopics = useCallback(async () => {
    if (!subjectId) return;
    try {
      const data = await subjectsService.listTopics(subjectId, 1, 100);
      setTopics(data.topics || []);
    } catch (error) {
      console.error('Failed to load topics:', error);
    }
  }, [subjectId]);

  useEffect(() => {
    loadSubject();
    loadTopics();
    setIsLoading(true);
    setPage(1);
    loadQuestions(1);
  }, [filterType, showArchived, loadQuestions, loadSubject, loadTopics]);

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
      topic_id: selectedQuestion.topic_id || undefined,
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
          {/* iOS-style drag indicator */}
          <View style={styles.dragIndicatorBar}>
            <View style={[styles.dragIndicator, { backgroundColor: colors.border }]} />
          </View>

          {/* iOS Navigation Bar */}
          <View style={[styles.modalNavBar, { borderBottomColor: colors.border }]}>
            {!isEditing ? (
              <>
                <TouchableOpacity
                  style={styles.navButton}
                  onPress={() => { setSelectedQuestion(null); cancelEditing(); }}
                  hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                >
                  <Text style={[styles.navButtonText, { color: colors.primary }]}>Close</Text>
                </TouchableOpacity>
                <Text style={[styles.navTitle, { color: colors.text }]} numberOfLines={1}>
                  Question Details
                </Text>
                <View style={styles.navRightActions}>
                  <TouchableOpacity
                    style={styles.navIconButton}
                    onPress={startEditing}
                    hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                  >
                    <IconSymbol name="pencil" size={20} color={colors.primary} />
                    <Text style={[styles.navIconLabel, { color: colors.primary }]}>Edit</Text>
                  </TouchableOpacity>
                  {showArchived ? (
                    <TouchableOpacity
                      style={styles.navIconButton}
                      onPress={() => handleUnarchive(selectedQuestion.id)}
                      hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                    >
                      <IconSymbol name="arrow.uturn.backward" size={20} color="#10b981" />
                      <Text style={[styles.navIconLabel, { color: '#10b981' }]}>Restore</Text>
                    </TouchableOpacity>
                  ) : (
                    <TouchableOpacity
                      style={styles.navIconButton}
                      onPress={() => handleArchive(selectedQuestion.id)}
                      hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                    >
                      <IconSymbol name="archivebox" size={20} color="#ef4444" />
                      <Text style={[styles.navIconLabel, { color: '#ef4444' }]}>Archive</Text>
                    </TouchableOpacity>
                  )}
                </View>
              </>
            ) : (
              <>
                <TouchableOpacity
                  style={styles.navButton}
                  onPress={cancelEditing}
                  hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                >
                  <Text style={[styles.navButtonText, { color: colors.textSecondary }]}>Cancel</Text>
                </TouchableOpacity>
                <Text style={[styles.navTitle, { color: colors.text }]} numberOfLines={1}>
                  Edit Question
                </Text>
                <TouchableOpacity
                  style={[styles.navSaveButton, { backgroundColor: colors.primary, opacity: isSaving ? 0.6 : 1 }]}
                  onPress={handleSaveEdit}
                  disabled={isSaving}
                  hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                >
                  {isSaving ? (
                    <ActivityIndicator size="small" color="#FFFFFF" />
                  ) : (
                    <Text style={styles.navSaveButtonText}>Save</Text>
                  )}
                </TouchableOpacity>
              </>
            )}
          </View>

          <ScrollView
            style={styles.modalScrollContent}
            contentContainerStyle={styles.modalScrollInner}
            showsVerticalScrollIndicator={false}
          >
            {/* Vetting Status + Badges Row */}
            <View style={styles.modalBadgeRow}>
              <View style={[styles.vettingBadge, { backgroundColor: VETTING_COLORS[selectedQuestion.vetting_status] + '18' }]}>
                <View style={[styles.vettingDot, { backgroundColor: VETTING_COLORS[selectedQuestion.vetting_status] }]} />
                <Text style={[styles.vettingBadgeText, { color: VETTING_COLORS[selectedQuestion.vetting_status] }]}>
                  {selectedQuestion.vetting_status.charAt(0).toUpperCase() + selectedQuestion.vetting_status.slice(1)}
                </Text>
              </View>
              <View style={[styles.typeBadge, { backgroundColor: colors.primary + '15' }]}>
                <Text style={[styles.typeBadgeText, { color: colors.primary }]}>
                  {selectedQuestion.question_type.replace('_', ' ')}
                </Text>
              </View>
              {selectedQuestion.difficulty_level && (
                <View style={[styles.typeBadge, { backgroundColor: '#f59e0b15' }]}>
                  <Text style={[styles.typeBadgeText, { color: '#f59e0b' }]}>
                    {selectedQuestion.difficulty_level}
                  </Text>
                </View>
              )}
              {selectedQuestion.marks != null && (
                <View style={[styles.typeBadge, { backgroundColor: colors.text + '08' }]}>
                  <Text style={[styles.typeBadgeText, { color: colors.textSecondary }]}>
                    {selectedQuestion.marks} marks
                  </Text>
                </View>
              )}
            </View>

            {selectedQuestion.bloom_taxonomy_level && (
              <View style={[styles.bloomRow, { marginBottom: Spacing.lg }]}>
                <View style={[styles.bloomBadge, { backgroundColor: getBloomColor(selectedQuestion.bloom_taxonomy_level) + '15' }]}>
                  <Text style={[styles.bloomBadgeText, { color: getBloomColor(selectedQuestion.bloom_taxonomy_level) }]}>
                    Bloom: {selectedQuestion.bloom_taxonomy_level}
                  </Text>
                </View>
              </View>
            )}

            {/* Question Text */}
            <View style={[styles.modalSection, { backgroundColor: colors.card }]}>
              <Text style={[styles.modalSectionTitle, { color: colors.textSecondary }]}>QUESTION</Text>
              {isEditing ? (
                <TextInput
                  style={[styles.editInput, { color: colors.text, borderColor: colors.border, backgroundColor: colors.background }]}
                  value={editData.question_text || ''}
                  onChangeText={(text) => setEditData((prev) => ({ ...prev, question_text: text }))}
                  multiline
                  numberOfLines={5}
                  textAlignVertical="top"
                />
              ) : (
                <Text style={[styles.modalQuestionText, { color: colors.text }]}>
                  {selectedQuestion.question_text}
                </Text>
              )}
            </View>

            {/* Options (MCQ) */}
            {selectedQuestion.question_type === 'mcq' && selectedQuestion.options && (
              <View style={[styles.modalSection, { backgroundColor: colors.card }]}>
                <Text style={[styles.modalSectionTitle, { color: colors.textSecondary }]}>OPTIONS</Text>
                {(isEditing ? (editData.options || selectedQuestion.options) : selectedQuestion.options).map((option, index) => {
                  const isCorrect = !isEditing && option === selectedQuestion.correct_answer;
                  return (
                    <View
                      key={index}
                      style={[
                        styles.modalOptionRow,
                        { backgroundColor: isCorrect ? '#34C75912' : colors.background },
                        isCorrect && { borderColor: '#34C759', borderWidth: 1.5 },
                      ]}
                    >
                      <View style={[
                        styles.optionLetterCircle,
                        { backgroundColor: isCorrect ? '#34C759' : colors.primary + '15' },
                      ]}>
                        <Text style={[
                          styles.optionLetterText,
                          { color: isCorrect ? '#FFFFFF' : colors.primary },
                        ]}>
                          {String.fromCharCode(65 + index)}
                        </Text>
                      </View>
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
                        <Text style={[styles.modalOptionText, { color: colors.text }]}>{option}</Text>
                      )}
                      {isCorrect && (
                        <IconSymbol name="checkmark.circle.fill" size={22} color="#34C759" />
                      )}
                    </View>
                  );
                })}
              </View>
            )}

            {/* Answer / Solution */}
            <View style={[styles.modalSection, { backgroundColor: colors.card }]}>
              <Text style={[styles.modalSectionTitle, { color: colors.textSecondary }]}>
                {selectedQuestion.question_type === 'mcq' ? 'CORRECT ANSWER' : 'MODEL ANSWER'}
              </Text>
              {isEditing ? (
                <TextInput
                  style={[styles.editInput, { color: colors.text, borderColor: colors.border, backgroundColor: colors.background }]}
                  value={editData.correct_answer || selectedQuestion.correct_answer || ''}
                  onChangeText={(text) => setEditData((prev) => ({ ...prev, correct_answer: text }))}
                  multiline
                  numberOfLines={3}
                  textAlignVertical="top"
                />
              ) : (
                <View style={[styles.answerBox, { backgroundColor: '#34C75908' }]}>
                  <View style={styles.answerAccent} />
                  <Text style={[styles.modalAnswerText, { color: colors.text }]}>
                    {selectedQuestion.correct_answer || 'No answer provided'}
                  </Text>
                </View>
              )}
            </View>

            {/* Explanation */}
            {selectedQuestion.explanation && !isEditing && (
              <View style={[styles.modalSection, { backgroundColor: colors.card }]}>
                <Text style={[styles.modalSectionTitle, { color: colors.textSecondary }]}>EXPLANATION</Text>
                <Text style={[styles.modalDetailText, { color: colors.text }]}>
                  {selectedQuestion.explanation}
                </Text>
              </View>
            )}

            {/* CO Mapping */}
            <View style={[styles.modalSection, { backgroundColor: colors.card }]}>
              <Text style={[styles.modalSectionTitle, { color: colors.textSecondary }]}>COURSE OUTCOME (CO)</Text>
              {isEditing ? (
                <View>
                  <Text style={[styles.editHint, { color: colors.textTertiary }]}>
                    Tap to toggle Course Outcomes
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
                            {
                              backgroundColor: isActive ? '#8b5cf615' : colors.background,
                              borderColor: isActive ? '#8b5cf6' : colors.border,
                            },
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
                            {co}{isActive ? ` · L${currentMapping[co]}` : ''}
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
                      <View key={co} style={[styles.coChip, { backgroundColor: '#8b5cf615', borderColor: '#8b5cf6' }]}>
                        <Text style={[styles.coChipText, { color: '#8b5cf6' }]}>
                          {co} · Level {level}
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
            <View style={[styles.modalSection, { backgroundColor: colors.card }]}>
              <Text style={[styles.modalSectionTitle, { color: colors.textSecondary }]}>LEARNING OUTCOME (LO)</Text>
              {isEditing ? (
                <TextInput
                  style={[styles.editInputSmall, { color: colors.text, borderColor: colors.border, backgroundColor: colors.background }]}
                  value={editData.learning_outcome_id || selectedQuestion.learning_outcome_id || ''}
                  onChangeText={(text) => setEditData((prev) => ({ ...prev, learning_outcome_id: text }))}
                  placeholder="e.g., LO1, LO2"
                  placeholderTextColor={colors.textTertiary}
                />
              ) : (
                selectedQuestion.learning_outcome_id ? (
                  <View style={[styles.loBadgeInline, { backgroundColor: '#06b6d412' }]}>
                    <Text style={[styles.loBadgeText, { color: '#06b6d4' }]}>
                      {selectedQuestion.learning_outcome_id}
                    </Text>
                  </View>
                ) : (
                  <Text style={[styles.emptyField, { color: colors.textTertiary }]}>Not assigned</Text>
                )
              )}
            </View>

            {/* Chapter (Topic) */}
            {subjectId && topics.length > 0 && (
              <View style={[styles.modalSection, { backgroundColor: colors.card }]}>
                <Text style={[styles.modalSectionTitle, { color: colors.textSecondary }]}>CHAPTER</Text>
                {isEditing ? (
                  <View>
                    <Text style={[styles.editHint, { color: colors.textTertiary }]}>Tap to assign this question to a chapter</Text>
                    <View style={styles.chapterChipsContainer}>
                      {topics.map((topic) => {
                        const isSelected = (editData.topic_id || selectedQuestion.topic_id) === topic.id;
                        return (
                          <TouchableOpacity
                            key={topic.id}
                            style={[
                              styles.chapterChip,
                              {
                                backgroundColor: isSelected ? '#3b82f615' : colors.background,
                                borderColor: isSelected ? '#3b82f6' : colors.border,
                              },
                            ]}
                            onPress={() => {
                              setEditData((prev) => ({
                                ...prev,
                                topic_id: isSelected ? undefined : topic.id,
                              }));
                            }}
                          >
                            <IconSymbol
                              name={isSelected ? 'checkmark.circle.fill' : 'circle'}
                              size={16}
                              color={isSelected ? '#3b82f6' : colors.textTertiary}
                            />
                            <Text
                              style={[
                                styles.chapterChipText,
                                { color: isSelected ? '#3b82f6' : colors.text },
                              ]}
                              numberOfLines={1}
                            >
                              {topic.name}
                            </Text>
                          </TouchableOpacity>
                        );
                      })}
                    </View>
                  </View>
                ) : (
                  (() => {
                    const linked = topics.find((t) => t.id === selectedQuestion.topic_id);
                    return linked ? (
                      <View style={[styles.chapterBadgeInline, { backgroundColor: '#3b82f612' }]}>
                        <IconSymbol name="book.closed.fill" size={14} color="#3b82f6" />
                        <Text style={[styles.chapterBadgeText, { color: '#3b82f6' }]}>
                          {linked.name}
                        </Text>
                      </View>
                    ) : (
                      <Text style={[styles.emptyField, { color: colors.textTertiary }]}>Not linked to a chapter</Text>
                    );
                  })()
                )}
              </View>
            )}

            {/* Marks (editable) */}
            {isEditing && (
              <View style={[styles.modalSection, { backgroundColor: colors.card }]}>
                <Text style={[styles.modalSectionTitle, { color: colors.textSecondary }]}>MARKS</Text>
                <TextInput
                  style={[styles.editInputSmall, { color: colors.text, borderColor: colors.border, backgroundColor: colors.background }]}
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
              <View style={[styles.modalSection, { backgroundColor: colors.card }]}>
                <Text style={[styles.modalSectionTitle, { color: colors.textSecondary }]}>RATE QUALITY</Text>
                <View style={styles.ratingRow}>
                  {renderStars(selectedQuestion.user_rating, selectedQuestion.id)}
                </View>
              </View>
            )}

            {/* Metadata */}
            {!isEditing && (
              <View style={[styles.modalSection, { backgroundColor: colors.card }]}>
                <Text style={[styles.modalSectionTitle, { color: colors.textSecondary }]}>INFO</Text>
                <View style={styles.metaGrid}>
                  <View style={[styles.metaCell, { borderBottomColor: colors.border }]}>
                    <IconSymbol name="target" size={18} color={colors.primary} />
                    <View style={styles.metaCellContent}>
                      <Text style={[styles.metaCellLabel, { color: colors.textSecondary }]}>Marks</Text>
                      <Text style={[styles.metaCellValue, { color: colors.text }]}>{selectedQuestion.marks || 0}</Text>
                    </View>
                  </View>
                  <View style={[styles.metaCell, { borderBottomColor: colors.border }]}>
                    <IconSymbol name="calendar" size={18} color={colors.primary} />
                    <View style={styles.metaCellContent}>
                      <Text style={[styles.metaCellLabel, { color: colors.textSecondary }]}>Created</Text>
                      <Text style={[styles.metaCellValue, { color: colors.text }]}>
                        {new Date(selectedQuestion.generated_at).toLocaleDateString()}
                      </Text>
                    </View>
                  </View>
                  {selectedQuestion.vetted_at && (
                    <View style={[styles.metaCell, { borderBottomColor: colors.border }]}>
                      <IconSymbol name="checkmark.shield" size={18} color={VETTING_COLORS[selectedQuestion.vetting_status]} />
                      <View style={styles.metaCellContent}>
                        <Text style={[styles.metaCellLabel, { color: colors.textSecondary }]}>Vetted</Text>
                        <Text style={[styles.metaCellValue, { color: colors.text }]}>
                          {new Date(selectedQuestion.vetted_at).toLocaleDateString()}
                        </Text>
                      </View>
                    </View>
                  )}
                </View>
                {selectedQuestion.vetting_notes && (
                  <View style={[styles.vettingNotesBox, { backgroundColor: colors.background }]}>
                    <Text style={[styles.vettingNotesLabel, { color: colors.textSecondary }]}>Vetting Notes</Text>
                    <Text style={[styles.vettingNotesText, { color: colors.text }]}>
                      {selectedQuestion.vetting_notes}
                    </Text>
                  </View>
                )}
              </View>
            )}

            {/* Bottom spacing */}
            <View style={{ height: 40 }} />
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
          headerRight: () => (
            <TouchableOpacity
              onPress={() => setShowExportModal(true)}
              hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
              style={{ width: 35, height: 20, alignItems: 'center', justifyContent: 'center' }}
            >
              <IconSymbol name="square.and.arrow.up" size={22} color={colors.primary} />
            </TouchableOpacity>
          ),
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

        {/* Export Modal */}
        <ExportModal
          visible={showExportModal}
          onClose={() => setShowExportModal(false)}
          questions={questions}
          defaultFilename={subject?.code ? `${subject.code}_questions` : 'questions'}
        />
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
    paddingTop: Spacing.headerInset + 10,
    paddingBottom: Spacing.md,
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
    paddingBottom: Spacing.xxl,
  },
  questionCard: {
    borderRadius: BorderRadius.lg,
    padding: Spacing.md,
    marginBottom: Spacing.md,
    marginTop: Spacing.lg,
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
  // iOS drag indicator
  dragIndicatorBar: {
    alignItems: 'center',
    paddingTop: Spacing.sm,
    paddingBottom: Spacing.xs,
  },
  dragIndicator: {
    width: 36,
    height: 5,
    borderRadius: 2.5,
  },
  // iOS navigation bar
  modalNavBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    minHeight: 48,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  navButton: {
    minWidth: 60,
    minHeight: 44,
    justifyContent: 'center',
  },
  navButtonText: {
    fontSize: FontSizes.md,
    fontWeight: '400',
  },
  navTitle: {
    fontSize: FontSizes.md,
    fontWeight: '600',
    flex: 1,
    textAlign: 'center',
    marginHorizontal: Spacing.sm,
  },
  navRightActions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    minWidth: 60,
    justifyContent: 'flex-end',
  },
  navIconButton: {
    alignItems: 'center',
    justifyContent: 'center',
    minWidth: 44,
    minHeight: 44,
    gap: 2,
  },
  navIconLabel: {
    fontSize: 10,
    fontWeight: '600',
  },
  navSaveButton: {
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.md,
    minHeight: 36,
    alignItems: 'center',
    justifyContent: 'center',
  },
  navSaveButtonText: {
    color: '#FFFFFF',
    fontSize: FontSizes.sm,
    fontWeight: '700',
  },
  // Scroll content
  modalScrollContent: {
    flex: 1,
  },
  modalScrollInner: {
    paddingTop: Spacing.md,
    paddingBottom: Spacing.xxl,
  },
  // Badge rows
  modalBadgeRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.sm,
    paddingHorizontal: Spacing.lg,
    marginBottom: Spacing.sm,
  },
  vettingBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: Spacing.md,
    paddingVertical: 6,
    borderRadius: BorderRadius.full,
    gap: 6,
  },
  vettingDot: {
    width: 7,
    height: 7,
    borderRadius: 3.5,
  },
  vettingBadgeText: {
    fontSize: FontSizes.xs,
    fontWeight: '600',
  },
  typeBadge: {
    paddingHorizontal: Spacing.md,
    paddingVertical: 6,
    borderRadius: BorderRadius.full,
  },
  typeBadgeText: {
    fontSize: FontSizes.xs,
    fontWeight: '600',
    textTransform: 'capitalize',
  },
  bloomRow: {
    paddingHorizontal: Spacing.lg,
  },
  bloomBadge: {
    alignSelf: 'flex-start',
    paddingHorizontal: Spacing.md,
    paddingVertical: 6,
    borderRadius: BorderRadius.full,
  },
  bloomBadgeText: {
    fontSize: FontSizes.xs,
    fontWeight: '600',
    textTransform: 'capitalize',
  },
  // Sections
  modalSection: {
    marginHorizontal: Spacing.md,
    marginBottom: Spacing.md,
    borderRadius: BorderRadius.xl,
    padding: Spacing.lg,
  },
  modalSectionTitle: {
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 0.8,
    marginBottom: Spacing.md,
  },
  modalQuestionText: {
    fontSize: FontSizes.md,
    lineHeight: 24,
    fontWeight: '400',
  },
  modalDetailText: {
    fontSize: FontSizes.sm,
    lineHeight: 22,
  },
  // Options (modal)
  modalOptionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: Spacing.md,
    borderRadius: BorderRadius.lg,
    marginBottom: Spacing.sm,
    gap: Spacing.md,
    borderWidth: 1,
    borderColor: 'transparent',
  },
  optionLetterCircle: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
  },
  optionLetterText: {
    fontSize: FontSizes.sm,
    fontWeight: '700',
  },
  modalOptionText: {
    fontSize: FontSizes.sm,
    flex: 1,
    lineHeight: 20,
  },
  // Answer box
  answerBox: {
    flexDirection: 'row',
    borderRadius: BorderRadius.lg,
    overflow: 'hidden',
  },
  answerAccent: {
    width: 4,
    backgroundColor: '#34C759',
  },
  modalAnswerText: {
    fontSize: FontSizes.md,
    lineHeight: 22,
    padding: Spacing.md,
    flex: 1,
  },
  // LO badge
  loBadgeInline: {
    alignSelf: 'flex-start',
    paddingHorizontal: Spacing.md,
    paddingVertical: 6,
    borderRadius: BorderRadius.md,
  },
  loBadgeText: {
    fontSize: FontSizes.sm,
    fontWeight: '700',
  },
  // Rating
  ratingRow: {
    paddingVertical: Spacing.xs,
  },
  // Meta grid
  metaGrid: {
    gap: 0,
  },
  metaCell: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: Spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
    gap: Spacing.md,
  },
  metaCellContent: {
    flex: 1,
  },
  metaCellLabel: {
    fontSize: 11,
    fontWeight: '600',
    letterSpacing: 0.5,
    textTransform: 'uppercase' as const,
  },
  metaCellValue: {
    fontSize: FontSizes.sm,
    fontWeight: '500',
    marginTop: 2,
  },
  // Vetting notes
  vettingNotesBox: {
    marginTop: Spacing.md,
    borderRadius: BorderRadius.lg,
    padding: Spacing.md,
  },
  vettingNotesLabel: {
    fontSize: 11,
    fontWeight: '600',
    letterSpacing: 0.5,
    textTransform: 'uppercase' as const,
    marginBottom: Spacing.xs,
  },
  vettingNotesText: {
    fontSize: FontSizes.sm,
    lineHeight: 20,
  },
  // Edit mode styles
  editInput: {
    borderWidth: 1,
    borderRadius: BorderRadius.lg,
    padding: Spacing.md,
    fontSize: FontSizes.md,
    lineHeight: 22,
    minHeight: 100,
  },
  editInputSmall: {
    borderWidth: 1,
    borderRadius: BorderRadius.lg,
    padding: Spacing.md,
    fontSize: FontSizes.md,
    height: 48,
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
    borderRadius: BorderRadius.lg,
    borderWidth: 1,
  },
  coChipText: {
    fontSize: FontSizes.sm,
    fontWeight: '600',
  },
  // Chapter styles
  chapterChipsContainer: {
    gap: Spacing.sm,
  },
  chapterChip: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.md,
    borderRadius: BorderRadius.lg,
    borderWidth: 1,
    gap: Spacing.sm,
  },
  chapterChipText: {
    fontSize: FontSizes.sm,
    fontWeight: '500',
    flex: 1,
  },
  chapterBadgeInline: {
    flexDirection: 'row',
    alignSelf: 'flex-start',
    alignItems: 'center',
    paddingHorizontal: Spacing.md,
    paddingVertical: 6,
    borderRadius: BorderRadius.md,
    gap: 6,
  },
  chapterBadgeText: {
    fontSize: FontSizes.sm,
    fontWeight: '700',
  },
  emptyField: {
    fontSize: FontSizes.sm,
    fontStyle: 'italic',
  },
});

