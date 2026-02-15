import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
  Alert,
  ActivityIndicator,
  Modal,
  ScrollView,
  Platform,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { GlassCard } from '@/components/ui/glass-card';
import { NativeButton } from '@/components/ui/native-button';
import { Colors, Spacing, BorderRadius, FontSizes } from '@/constants/theme';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { questionsService, Question } from '@/services/questions';
import { useToast } from '@/components/toast';

const FILTER_OPTIONS = [
  { label: 'All', value: '' },
  { label: 'MCQ', value: 'mcq' },
  { label: 'Short Answer', value: 'short_answer' },
  { label: 'Long Answer', value: 'long_answer' },
];

export default function QuestionsScreen() {
  const colorScheme = useColorScheme();
  const colors = Colors[colorScheme ?? 'light'];
  const { showError, showSuccess } = useToast();
  
  const [questions, setQuestions] = useState<Question[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [filterType, setFilterType] = useState('');
  const [selectedQuestion, setSelectedQuestion] = useState<Question | null>(null);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);

  const loadQuestions = useCallback(async (pageNum: number, append: boolean = false) => {
    try {
      const response = await questionsService.listQuestions(
        pageNum,
        20,
        filterType || undefined,
        undefined,
        undefined
      );
      
      if (append) {
        setQuestions((prev) => [...prev, ...response.questions]);
      } else {
        setQuestions(response.questions);
      }
      
      setHasMore(response.questions.length === 20);
    } catch (error) {
      showError(error, 'Failed to Load');
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [filterType]);

  useEffect(() => {
    setIsLoading(true);
    setPage(1);
    loadQuestions(1);
  }, [filterType, loadQuestions]);

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
        prev.map((q) => (q.id === questionId ? { ...q, quality_rating: rating } : q))
      );
      if (selectedQuestion?.id === questionId) {
        setSelectedQuestion((prev) => prev ? { ...prev, quality_rating: rating } : null);
      }
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

  const renderStars = (rating: number | null, questionId: string) => {
    return (
      <View style={styles.starsContainer}>
        {[1, 2, 3, 4, 5].map((star) => (
          <TouchableOpacity
            key={star}
            onPress={() => handleRate(questionId, star)}
          >
            <IconSymbol
              name={star <= (rating || 0) ? 'star.fill' : 'star'}
              size={20}
              color={star <= (rating || 0) ? '#f59e0b' : '#d1d5db'}
            />
          </TouchableOpacity>
        ))}
      </View>
    );
  };

  const renderQuestion = ({ item }: { item: Question }) => (
    <TouchableOpacity
      style={styles.questionCard}
      onPress={() => setSelectedQuestion(item)}
    >
      <View style={styles.questionHeader}>
        <View style={styles.typeBadge}>
          <Text style={styles.typeText}>{item.question_type.replace('_', ' ').toUpperCase()}</Text>
        </View>
        <View style={styles.difficultyBadge}>
          <Text style={styles.difficultyText}>{(item.difficulty_level || 'medium').toUpperCase()}</Text>
        </View>
      </View>
      <Text style={styles.questionText} numberOfLines={2}>
        {item.question_text}
      </Text>
      <View style={styles.questionFooter}>
        {renderStars(item.user_rating, item.id)}
        <Text style={styles.marksText}>{item.marks || 0} marks</Text>
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
        <View style={styles.modalContainer}>
          <View style={styles.modalHeader}>
            <TouchableOpacity onPress={() => setSelectedQuestion(null)}>
              <IconSymbol name="xmark" size={24} color="#374151" />
            </TouchableOpacity>
            <Text style={styles.modalTitle}>Question Details</Text>
            <TouchableOpacity onPress={() => handleArchive(selectedQuestion.id)}>
              <IconSymbol name="archivebox" size={24} color="#ef4444" />
            </TouchableOpacity>
          </View>
          
          <ScrollView style={styles.modalContent}>
            <View style={styles.detailSection}>
              <View style={styles.badgeRow}>
                <View style={styles.typeBadge}>
                  <Text style={styles.typeText}>
                    {selectedQuestion.question_type.replace('_', ' ').toUpperCase()}
                  </Text>
                </View>
                <View style={styles.difficultyBadge}>
                  <Text style={styles.difficultyText}>
                    {(selectedQuestion.difficulty_level || 'medium').toUpperCase()}
                  </Text>
                </View>
                {selectedQuestion.bloom_taxonomy_level && (
                  <View style={[styles.difficultyBadge, { backgroundColor: '#8b5cf620' }]}>
                    <Text style={[styles.difficultyText, { color: '#8b5cf6' }]}>
                      {selectedQuestion.bloom_taxonomy_level.toUpperCase()}
                    </Text>
                  </View>
                )}
              </View>
            </View>

            <View style={styles.detailSection}>
              <Text style={styles.sectionLabel}>Question</Text>
              <Text style={styles.questionDetailText}>{selectedQuestion.question_text}</Text>
            </View>

            {selectedQuestion.question_type === 'mcq' && selectedQuestion.options && (
              <View style={styles.detailSection}>
                <Text style={styles.sectionLabel}>Options</Text>
                {selectedQuestion.options.map((option, index) => (
                  <View
                    key={index}
                    style={[
                      styles.optionRow,
                      option === selectedQuestion.correct_answer && styles.correctOption,
                    ]}
                  >
                    <Text style={styles.optionLetter}>
                      {String.fromCharCode(65 + index)}.
                    </Text>
                    <Text style={styles.optionText}>{option}</Text>
                    {option === selectedQuestion.correct_answer && (
                      <IconSymbol name="checkmark.circle.fill" size={20} color="#10b981" />
                    )}
                  </View>
                ))}
              </View>
            )}

            <View style={styles.detailSection}>
              <Text style={styles.sectionLabel}>
                {selectedQuestion.question_type === 'mcq' ? 'Correct Answer' : 'Model Answer'}
              </Text>
              <Text style={styles.answerText}>{selectedQuestion.correct_answer}</Text>
            </View>

            <View style={styles.detailSection}>
              <Text style={styles.sectionLabel}>Rate this Question</Text>
              {renderStars(selectedQuestion.user_rating, selectedQuestion.id)}
            </View>

            <View style={styles.metaInfo}>
              <Text style={styles.metaText}>Marks: {selectedQuestion.marks}</Text>
              <Text style={styles.metaText}>
                Created: {new Date(selectedQuestion.generated_at).toLocaleDateString()}
              </Text>
            </View>
          </ScrollView>
        </View>
      </Modal>
    );
  };

  if (isLoading && questions.length === 0) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#2563eb" />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Questions</Text>
        <Text style={styles.headerSubtitle}>{questions.length} total</Text>
      </View>

      <View style={styles.filterContainer}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false}>
          {FILTER_OPTIONS.map((option) => (
            <TouchableOpacity
              key={option.value}
              style={[
                styles.filterChip,
                filterType === option.value && styles.filterChipActive,
              ]}
              onPress={() => setFilterType(option.value)}
            >
              <Text
                style={[
                  styles.filterChipText,
                  filterType === option.value && styles.filterChipTextActive,
                ]}
              >
                {option.label}
              </Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      </View>

      <FlatList
        data={questions}
        renderItem={renderQuestion}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={isRefreshing} onRefresh={handleRefresh} />
        }
        onEndReached={handleLoadMore}
        onEndReachedThreshold={0.5}
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <IconSymbol name="list.bullet" size={64} color="#9ca3af" />
            <Text style={styles.emptyTitle}>No Questions Yet</Text>
            <Text style={styles.emptyText}>
              Generate questions from your documents to see them here.
            </Text>
          </View>
        }
        ListFooterComponent={
          hasMore && questions.length > 0 ? (
            <ActivityIndicator style={styles.loadingMore} color="#2563eb" />
          ) : null
        }
      />

      {renderQuestionDetail()}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  header: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: '#fff',
    borderBottomWidth: 1,
    borderBottomColor: '#e5e7eb',
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: '#111827',
  },
  headerSubtitle: {
    fontSize: 14,
    color: '#6b7280',
    marginTop: 2,
  },
  filterContainer: {
    backgroundColor: '#fff',
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#e5e7eb',
  },
  filterChip: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: '#f3f4f6',
    marginRight: 8,
  },
  filterChipActive: {
    backgroundColor: '#2563eb',
  },
  filterChipText: {
    fontSize: 14,
    color: '#4b5563',
  },
  filterChipTextActive: {
    color: '#fff',
    fontWeight: '500',
  },
  listContent: {
    padding: 16,
  },
  questionCard: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 2,
  },
  questionHeader: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 8,
  },
  typeBadge: {
    backgroundColor: '#2563eb20',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 4,
  },
  typeText: {
    fontSize: 10,
    fontWeight: '600',
    color: '#2563eb',
  },
  difficultyBadge: {
    backgroundColor: '#f59e0b20',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 4,
  },
  difficultyText: {
    fontSize: 10,
    fontWeight: '600',
    color: '#f59e0b',
  },
  questionText: {
    fontSize: 14,
    color: '#374151',
    lineHeight: 20,
    marginBottom: 12,
  },
  questionFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  starsContainer: {
    flexDirection: 'row',
    gap: 4,
  },
  marksText: {
    fontSize: 12,
    color: '#6b7280',
  },
  emptyContainer: {
    alignItems: 'center',
    paddingTop: 60,
    paddingHorizontal: 32,
  },
  emptyTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: '#374151',
    marginTop: 16,
    marginBottom: 8,
  },
  emptyText: {
    fontSize: 14,
    color: '#6b7280',
    textAlign: 'center',
  },
  loadingMore: {
    paddingVertical: 16,
  },
  modalContainer: {
    flex: 1,
    backgroundColor: '#fff',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#e5e7eb',
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#111827',
  },
  modalContent: {
    flex: 1,
    padding: 16,
  },
  detailSection: {
    marginBottom: 20,
  },
  badgeRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  sectionLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: '#6b7280',
    marginBottom: 8,
    textTransform: 'uppercase',
  },
  questionDetailText: {
    fontSize: 16,
    color: '#111827',
    lineHeight: 24,
  },
  optionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#f9fafb',
    padding: 12,
    borderRadius: 8,
    marginBottom: 8,
    gap: 8,
  },
  correctOption: {
    backgroundColor: '#10b98120',
    borderWidth: 1,
    borderColor: '#10b981',
  },
  optionLetter: {
    fontSize: 14,
    fontWeight: '600',
    color: '#6b7280',
  },
  optionText: {
    fontSize: 14,
    color: '#374151',
    flex: 1,
  },
  answerText: {
    fontSize: 14,
    color: '#374151',
    backgroundColor: '#f0fdf4',
    padding: 12,
    borderRadius: 8,
    borderLeftWidth: 4,
    borderLeftColor: '#10b981',
  },
  explanationText: {
    fontSize: 14,
    color: '#4b5563',
    backgroundColor: '#f9fafb',
    padding: 12,
    borderRadius: 8,
    lineHeight: 20,
  },
  metaInfo: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: '#e5e7eb',
  },
  metaText: {
    fontSize: 12,
    color: '#9ca3af',
  },
});
