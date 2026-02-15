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
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Stack, useLocalSearchParams } from 'expo-router';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { Colors, Spacing, BorderRadius, FontSizes } from '@/constants/theme';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { questionsService, Question } from '@/services/questions';
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

  const loadQuestions = useCallback(async (pageNum: number, append: boolean = false) => {
    try {
      const response = await questionsService.listQuestions(
        pageNum,
        20,
        filterType || undefined,
        undefined,
        undefined,
        subjectId,
        showArchived
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
  }, [filterType, subjectId]);

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
        </View>
        <Text style={[styles.marksText, { color: colors.textSecondary }]}>
          {item.marks || '0'} marks
        </Text>
      </View>
      
      <Text style={[styles.questionText, { color: colors.text }]} numberOfLines={3}>
        {item.question_text}
      </Text>
      
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
        onRequestClose={() => setSelectedQuestion(null)}
      >
        <View style={[styles.modalContainer, { backgroundColor: colors.background }]}>
          <View style={[styles.modalHeader, { backgroundColor: colors.card, borderBottomColor: colors.border }]}>
            <TouchableOpacity onPress={() => setSelectedQuestion(null)}>
              <IconSymbol name="xmark" size={24} color={colors.text} />
            </TouchableOpacity>
            <Text style={[styles.modalTitle, { color: colors.text }]}>Question Details</Text>
            {showArchived ? (
              <TouchableOpacity onPress={() => handleUnarchive(selectedQuestion.id)}>
                <IconSymbol name="arrow.uturn.backward" size={24} color="#10b981" />
              </TouchableOpacity>
            ) : (
              <TouchableOpacity onPress={() => handleArchive(selectedQuestion.id)}>
                <IconSymbol name="archivebox" size={24} color="#ef4444" />
              </TouchableOpacity>
            )}
          </View>
          
          <ScrollView style={styles.modalContent}>
            {/* Question Type Badges */}
            <View style={styles.badgeSection}>
              <View style={styles.badgesContainer}>
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
              <Text style={[styles.questionDetailText, { color: colors.text }]}>
                {selectedQuestion.question_text}
              </Text>
            </View>

            {/* Options (for MCQ) */}
            {selectedQuestion.question_type === 'mcq' && selectedQuestion.options && (
              <View style={[styles.section, { backgroundColor: colors.card }]}>
                <Text style={[styles.sectionLabel, { color: colors.textSecondary }]}>Options</Text>
                {selectedQuestion.options.map((option, index) => (
                  <View
                    key={index}
                    style={[
                      styles.optionRow,
                      option === selectedQuestion.correct_answer && [styles.correctOption, { borderColor: '#34C759' }],
                      { backgroundColor: option === selectedQuestion.correct_answer ? '#34C75920' : colors.background },
                    ]}
                  >
                    <Text style={[styles.optionLetter, { color: colors.textSecondary }]}>
                      {String.fromCharCode(65 + index)}
                    </Text>
                    <Text style={[styles.optionText, { color: colors.text }]}>{option}</Text>
                    {option === selectedQuestion.correct_answer && (
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
              <Text style={[styles.answerText, { color: colors.text }]}>
                {selectedQuestion.correct_answer}
              </Text>
            </View>

            {/* Rating */}
            <View style={[styles.section, { backgroundColor: colors.card }]}>
              <Text style={[styles.sectionLabel, { color: colors.textSecondary }]}>Rate Quality</Text>
              {renderStars(selectedQuestion.user_rating, selectedQuestion.id)}
            </View>

            {/* Metadata */}
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
            </View>
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
        {/* Header with Gradient */}
        <LinearGradient
          colors={['#4A90D9', '#357ABD'] as const}
          style={styles.headerCard}
        >
          <View>
            <Text style={styles.headerTitle}>Questions</Text>
            <Text style={styles.headerSubtitle}>
              {questions.length} question{questions.length !== 1 ? 's' : ''} generated
            </Text>
            {subject && (
              <Text style={styles.headerSubject}>
                {subject.code} • {subject.name}
              </Text>
            )}
          </View>
        </LinearGradient>

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
              <Text style={[styles.emptyTitle, { color: colors.text }]}>No Questions Yet</Text>
              <Text style={[styles.emptyText, { color: colors.textSecondary }]}>
                {filterType
                  ? 'No questions match your filter'
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
  headerCard: {
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.xl,
    paddingBottom: Spacing.lg,
  },
  headerTitle: {
    fontSize: FontSizes.xxl,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  headerSubtitle: {
    fontSize: FontSizes.sm,
    color: 'rgba(255,255,255,0.9)',
    marginTop: Spacing.xs,
  },
  headerSubject: {
    fontSize: FontSizes.xs,
    color: 'rgba(255,255,255,0.8)',
    marginTop: Spacing.xs,
    letterSpacing: 0.5,
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
});
