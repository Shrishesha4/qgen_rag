import React, { useEffect, useState, useCallback, useMemo } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  RefreshControl,
  ActivityIndicator,
  TouchableOpacity,
  Modal,
  TextInput,
  ScrollView,
  Dimensions,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';

import { GlassCard } from '@/components/ui/glass-card';
import { NativeButton } from '@/components/ui/native-button';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { SwipeVetting } from '@/components/swipe-vetting';
import { Colors, Spacing, BorderRadius, FontSizes } from '@/constants/theme';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { useToast } from '@/components/toast';
import {
  vetterService,
  QuestionForVetting,
  SubjectSummary,
} from '@/services/vetter.service';

type StatusFilter = 'pending' | 'approved' | 'rejected' | 'all';

const REJECTION_REASONS = [
  { id: 'duplicate', label: 'Duplicate question' },
  { id: 'off_topic', label: 'Off topic' },
  { id: 'too_easy', label: 'Too easy' },
  { id: 'too_hard', label: 'Too hard' },
  { id: 'unclear', label: 'Unclear wording' },
  { id: 'incorrect_answer', label: 'Incorrect answer' },
  { id: 'poor_options', label: 'Poor MCQ options' },
  { id: 'needs_improvement', label: 'Needs improvement' },
];

export default function QuestionsForVetting() {
  const colorScheme = useColorScheme();
  const colors = Colors[colorScheme ?? 'light'];
  const { showSuccess, showError } = useToast();
  const params = useLocalSearchParams<{
    teacher_id?: string;
    subject_id?: string;
    topic_id?: string;
    status?: StatusFilter;
  }>();

  const [questions, setQuestions] = useState<QuestionForVetting[]>([]);
  const [subjects, setSubjects] = useState<SubjectSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(true);

  // Filters
  const [statusFilter, setStatusFilter] = useState<StatusFilter>(
    (params.status as StatusFilter) || 'pending'
  );
  const [teacherFilter, setTeacherFilter] = useState<string | undefined>(params.teacher_id);
  const [subjectFilter, setSubjectFilter] = useState<string | undefined>(params.subject_id);

  // Vetting modal
  const [selectedQuestion, setSelectedQuestion] = useState<QuestionForVetting | null>(null);
  const [showVetModal, setShowVetModal] = useState(false);
  const [vetStatus, setVetStatus] = useState<'approved' | 'rejected'>('approved');
  const [vetNotes, setVetNotes] = useState('');
  const [selectedReasons, setSelectedReasons] = useState<string[]>([]);
  const [isVetting, setIsVetting] = useState(false);

  // Selected for bulk action
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // Subject search dropdown
  const [showSubjectPicker, setShowSubjectPicker] = useState(false);
  const [subjectSearch, setSubjectSearch] = useState('');

  // Swipe vetting mode
  const [showSwipeVetting, setShowSwipeVetting] = useState(false);

  // Fuzzy search filter for subjects
  const filteredSubjects = useMemo(() => {
    if (!subjectSearch.trim()) return subjects;
    const searchLower = subjectSearch.toLowerCase();
    return subjects.filter(
      (s) =>
        s.name.toLowerCase().includes(searchLower) ||
        s.code.toLowerCase().includes(searchLower) ||
        s.teacher_name.toLowerCase().includes(searchLower)
    );
  }, [subjects, subjectSearch]);

  // Get selected subject name for display
  const selectedSubjectName = useMemo(() => {
    if (!subjectFilter) return 'All Subjects';
    const subject = subjects.find((s) => s.id === subjectFilter);
    return subject ? `${subject.code} - ${subject.name}` : 'All Subjects';
  }, [subjectFilter, subjects]);

  const fetchQuestions = useCallback(
    async (pageNum = 1, showLoader = true) => {
      try {
        if (showLoader) setIsLoading(true);
        setError(null);

        const data = await vetterService.getQuestions({
          page: pageNum,
          limit: 20,
          status: statusFilter,
          teacher_id: teacherFilter,
          subject_id: subjectFilter,
        });

        if (pageNum === 1) {
          setQuestions(data.questions);
        } else {
          // Deduplicate when appending pages
          setQuestions((prev) => {
            const existingIds = new Set(prev.map((q) => q.id));
            const newQuestions = data.questions.filter((q) => !existingIds.has(q.id));
            return [...prev, ...newQuestions];
          });
        }

        setTotal(data.total);
        setHasMore(pageNum < data.pages);
        setPage(pageNum);
      } catch (err) {
        setError('Failed to load questions');
        console.error(err);
      } finally {
        setIsLoading(false);
        setIsRefreshing(false);
      }
    },
    [statusFilter, teacherFilter, subjectFilter]
  );

  const fetchSubjects = useCallback(async () => {
    try {
      const data = await vetterService.getSubjects(teacherFilter);
      setSubjects(data);
    } catch (err) {
      console.error('Failed to load subjects', err);
    }
  }, [teacherFilter]);

  useEffect(() => {
    setPage(1);
    setSelectedIds(new Set());
    fetchQuestions(1);
    fetchSubjects();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter, teacherFilter, subjectFilter]);

  const onRefresh = useCallback(() => {
    setIsRefreshing(true);
    setSelectedIds(new Set());
    fetchQuestions(1, false);
  }, [fetchQuestions]);

  const loadMore = useCallback(() => {
    if (!isLoading && hasMore) {
      fetchQuestions(page + 1, false);
    }
  }, [isLoading, hasMore, page, fetchQuestions]);

  // Load more questions for swipe mode if needed
  const loadAllPendingQuestions = useCallback(async () => {
    try {
      setIsLoading(true);
      // Fetch a reasonable batch (100 questions) - SwipeVetting will call onLoadMore for more
      const data = await vetterService.getQuestions({
        page: 1,
        limit: 100,
        status: 'pending',
        teacher_id: teacherFilter,
        subject_id: subjectFilter,
      });
      setQuestions(data.questions);
      setTotal(data.total);
      setHasMore(data.pages > 1);
      setPage(1);
      setShowSwipeVetting(true);
    } catch (err) {
      setError('Failed to load questions');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  }, [teacherFilter, subjectFilter]);

  const handleVet = async () => {
    if (!selectedQuestion) return;

    setIsVetting(true);
    try {
      await vetterService.vetQuestion(selectedQuestion.id, {
        status: vetStatus,
        notes: vetNotes || undefined,
        rejection_reasons: vetStatus === 'rejected' ? selectedReasons : undefined,
      });

      showSuccess(`Question ${vetStatus}`);
      setShowVetModal(false);
      setSelectedQuestion(null);
      setVetNotes('');
      setSelectedReasons([]);

      // Remove from list if we're filtering by pending
      if (statusFilter === 'pending') {
        setQuestions((prev) => prev.filter((q) => q.id !== selectedQuestion.id));
        setTotal((prev) => prev - 1);
      } else {
        // Refresh the current question
        fetchQuestions(1, false);
      }
    } catch (err) {
      showError('Failed to vet question');
      console.error(err);
    } finally {
      setIsVetting(false);
    }
  };

  const handleBulkApprove = async () => {
    if (selectedIds.size === 0) return;

    setIsVetting(true);
    try {
      await vetterService.bulkVet({
        question_ids: Array.from(selectedIds),
        status: 'approved',
      });

      showSuccess(`${selectedIds.size} questions approved`);
      setSelectedIds(new Set());
      fetchQuestions(1, false);
    } catch (err) {
      showError('Failed to approve questions');
      console.error(err);
    } finally {
      setIsVetting(false);
    }
  };

  const toggleSelection = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const toggleReason = (reason: string) => {
    setSelectedReasons((prev) =>
      prev.includes(reason) ? prev.filter((r) => r !== reason) : [...prev, reason]
    );
  };

  // Handle swipe vetting callbacks
  const handleQuestionVetted = useCallback((questionId: string, status: 'approved' | 'rejected' | 'skipped') => {
    if (status !== 'skipped') {
      // Remove from list if we're filtering by pending
      if (statusFilter === 'pending') {
        setQuestions((prev) => prev.filter((q) => q.id !== questionId));
        setTotal((prev) => prev - 1);
      }
    }
  }, [statusFilter]);

  const handleQuestionUpdated = useCallback((questionId: string, updates: Partial<QuestionForVetting>) => {
    setQuestions((prev) =>
      prev.map((q) => (q.id === questionId ? { ...q, ...updates } : q))
    );
  }, []);

  const handleSelectSubject = useCallback((subjectId: string | undefined) => {
    setSubjectFilter(subjectId);
    setShowSubjectPicker(false);
    setSubjectSearch('');
  }, []);

  // Get pending questions for swipe mode
  const pendingQuestions = useMemo(() => {
    return questions.filter((q) => q.vetting_status === 'pending');
  }, [questions]);

  const QuestionCard = ({ question }: { question: QuestionForVetting }) => {
    const isSelected = selectedIds.has(question.id);

    return (
      <TouchableOpacity
        onPress={() => {
          setSelectedQuestion(question);
          setVetStatus('approved');
          setVetNotes('');
          setSelectedReasons([]);
          setShowVetModal(true);
        }}
        onLongPress={() => toggleSelection(question.id)}
      >
        <GlassCard
          style={[
            styles.questionCard,
            isSelected && { borderWidth: 2, borderColor: colors.primary },
          ]}
        >
          {/* Header */}
          <View style={styles.cardHeader}>
            <View
              style={[
                styles.typeTag,
                {
                  backgroundColor:
                    question.question_type === 'mcq'
                      ? colors.primary + '20'
                      : question.question_type === 'short_answer'
                      ? colors.warning + '20'
                      : colors.success + '20',
                },
              ]}
            >
              <Text
                style={[
                  styles.typeText,
                  {
                    color:
                      question.question_type === 'mcq'
                        ? colors.primary
                        : question.question_type === 'short_answer'
                        ? colors.warning
                        : colors.success,
                  },
                ]}
              >
                {question.question_type.replace('_', ' ').toUpperCase()}
              </Text>
            </View>
            <View
              style={[
                styles.statusTag,
                {
                  backgroundColor:
                    question.vetting_status === 'pending'
                      ? colors.warning + '20'
                      : question.vetting_status === 'approved'
                      ? colors.success + '20'
                      : colors.error + '20',
                },
              ]}
            >
              <Text
                style={[
                  styles.statusText,
                  {
                    color:
                      question.vetting_status === 'pending'
                        ? colors.warning
                        : question.vetting_status === 'approved'
                        ? colors.success
                        : colors.error,
                  },
                ]}
              >
                {question.vetting_status.toUpperCase()}
              </Text>
            </View>
          </View>

          {/* Question text */}
          <Text style={[styles.questionText, { color: colors.text }]} numberOfLines={3}>
            {question.question_text}
          </Text>

          {/* Meta info */}
          <View style={styles.metaRow}>
            {question.teacher_name && (
              <Text style={[styles.metaText, { color: colors.textSecondary }]}>
                By: {question.teacher_name}
              </Text>
            )}
            {question.subject_name && (
              <Text style={[styles.metaText, { color: colors.textSecondary }]}>
                {question.subject_code || question.subject_name}
              </Text>
            )}
            {question.topic_name && (
              <Text style={[styles.metaText, { color: colors.textSecondary }]}>
                {question.topic_name}
              </Text>
            )}
          </View>

          {/* Difficulty and Bloom */}
          <View style={styles.tagsRow}>
            {question.difficulty_level && (
              <View style={[styles.tag, { backgroundColor: colors.card }]}>
                <Text style={[styles.tagText, { color: colors.textSecondary }]}>
                  {question.difficulty_level}
                </Text>
              </View>
            )}
            {question.bloom_taxonomy_level && (
              <View style={[styles.tag, { backgroundColor: colors.card }]}>
                <Text style={[styles.tagText, { color: colors.textSecondary }]}>
                  {question.bloom_taxonomy_level}
                </Text>
              </View>
            )}
            {question.marks && (
              <View style={[styles.tag, { backgroundColor: colors.card }]}>
                <Text style={[styles.tagText, { color: colors.textSecondary }]}>
                  {question.marks} marks
                </Text>
              </View>
            )}
          </View>
        </GlassCard>
      </TouchableOpacity>
    );
  };

  const FilterBar = () => (
    <View style={styles.filterBar}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false}>
        {(['pending', 'approved', 'rejected', 'all'] as StatusFilter[]).map((status) => (
          <TouchableOpacity
            key={status}
            onPress={() => {
              setStatusFilter(status);
              setSelectedIds(new Set());
            }}
            style={[
              styles.filterChip,
              {
                backgroundColor: statusFilter === status ? colors.primary : colors.card,
                borderColor: statusFilter === status ? colors.primary : colors.border,
              },
            ]}
          >
            <Text
              style={[
                styles.filterChipText,
                { color: statusFilter === status ? '#fff' : colors.text },
              ]}
            >
              {status.charAt(0).toUpperCase() + status.slice(1)}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>
    </View>
  );

  if (isLoading && page === 1) {
    return (
      <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.primary} />
          <Text style={[styles.loadingText, { color: colors.textSecondary }]}>
            Loading questions...
          </Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]}>
      <View style={styles.header}>
        <Text style={[styles.title, { color: colors.text }]}>Questions</Text>
        <Text style={[styles.subtitle, { color: colors.textSecondary }]}>
          {total} questions found
        </Text>
      </View>

      {/* Subject Dropdown */}
      <TouchableOpacity
        style={[styles.subjectDropdown, { backgroundColor: colors.card, borderColor: colors.border }]}
        onPress={() => setShowSubjectPicker(true)}
      >
        <IconSymbol name="book.fill" size={16} color={colors.primary} />
        <Text style={[styles.subjectDropdownText, { color: colors.text }]} numberOfLines={1}>
          {selectedSubjectName}
        </Text>
        <IconSymbol name="chevron.down" size={14} color={colors.textSecondary} />
      </TouchableOpacity>

      <FilterBar />

      {/* Bulk action bar */}
      {selectedIds.size > 0 && (
        <View style={[styles.bulkBar, { backgroundColor: colors.primary }]}>
          <Text style={styles.bulkText}>{selectedIds.size} selected</Text>
          <TouchableOpacity
            onPress={handleBulkApprove}
            style={[styles.bulkButton, { backgroundColor: colors.success }]}
            disabled={isVetting}
          >
            <Text style={styles.bulkButtonText}>Approve All</Text>
          </TouchableOpacity>
          <TouchableOpacity
            onPress={() => setSelectedIds(new Set())}
            style={[styles.bulkButton, { backgroundColor: 'rgba(255,255,255,0.2)' }]}
          >
            <Text style={styles.bulkButtonText}>Clear</Text>
          </TouchableOpacity>
        </View>
      )}

      {error && (
        <GlassCard style={[styles.errorCard, { borderColor: colors.error }]}>
          <Text style={[styles.errorText, { color: colors.error }]}>{error}</Text>
          <TouchableOpacity onPress={() => fetchQuestions(1)}>
            <Text style={[styles.retryText, { color: colors.primary }]}>Retry</Text>
          </TouchableOpacity>
        </GlassCard>
      )}

      <FlatList
        data={questions}
        keyExtractor={(item) => String(item.id)}
        renderItem={({ item }) => <QuestionCard question={item} />}
        contentContainerStyle={styles.listContent}
        refreshControl={<RefreshControl refreshing={isRefreshing} onRefresh={onRefresh} />}
        onEndReached={loadMore}
        onEndReachedThreshold={0.5}
        ListFooterComponent={
          isLoading && page > 1 ? (
            <ActivityIndicator style={{ padding: Spacing.md }} color={colors.primary} />
          ) : null
        }
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Text style={[styles.emptyText, { color: colors.textSecondary }]}>
              No questions found
            </Text>
          </View>
        }
      />

      {/* Vetting Modal */}
      <Modal
        visible={showVetModal}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => setShowVetModal(false)}
      >
        <SafeAreaView style={[styles.modalContainer, { backgroundColor: colors.background }]}>
          <View style={styles.modalHeader}>
            <Text style={[styles.modalTitle, { color: colors.text }]}>Review Question</Text>
            <TouchableOpacity onPress={() => setShowVetModal(false)}>
              <Text style={[styles.closeButton, { color: colors.primary }]}>Close</Text>
            </TouchableOpacity>
          </View>

          <ScrollView style={styles.modalContent}>
            {selectedQuestion && (
              <>
                {/* Question details */}
                <GlassCard style={styles.detailCard}>
                  <View style={styles.cardHeader}>
                    <View
                      style={[
                        styles.typeTag,
                        { backgroundColor: colors.primary + '20' },
                      ]}
                    >
                      <Text style={[styles.typeText, { color: colors.primary }]}>
                        {selectedQuestion.question_type.replace('_', ' ').toUpperCase()}
                      </Text>
                    </View>
                  </View>

                  <Text style={[styles.detailLabel, { color: colors.textSecondary }]}>
                    Question:
                  </Text>
                  <Text style={[styles.detailValue, { color: colors.text }]}>
                    {selectedQuestion.question_text}
                  </Text>

                  {selectedQuestion.options && (
                    <>
                      <Text
                        style={[
                          styles.detailLabel,
                          { color: colors.textSecondary, marginTop: Spacing.md },
                        ]}
                      >
                        Options:
                      </Text>
                      {selectedQuestion.options.map((opt, idx) => (
                        <Text
                          key={idx}
                          style={[
                            styles.optionText,
                            { color: colors.text },
                            opt.startsWith(selectedQuestion.correct_answer || '') && {
                              color: colors.success,
                              fontWeight: '600',
                            },
                          ]}
                        >
                          {opt}
                        </Text>
                      ))}
                    </>
                  )}

                  {selectedQuestion.correct_answer && (
                    <>
                      <Text
                        style={[
                          styles.detailLabel,
                          { color: colors.textSecondary, marginTop: Spacing.md },
                        ]}
                      >
                        Answer:
                      </Text>
                      <Text style={[styles.detailValue, { color: colors.success }]}>
                        {selectedQuestion.correct_answer}
                      </Text>
                    </>
                  )}

                  {selectedQuestion.explanation && (
                    <>
                      <Text
                        style={[
                          styles.detailLabel,
                          { color: colors.textSecondary, marginTop: Spacing.md },
                        ]}
                      >
                        Explanation:
                      </Text>
                      <Text style={[styles.detailValue, { color: colors.text }]}>
                        {selectedQuestion.explanation}
                      </Text>
                    </>
                  )}
                </GlassCard>

                {/* Decision buttons */}
                <View style={styles.decisionRow}>
                  <TouchableOpacity
                    style={[
                      styles.decisionButton,
                      {
                        backgroundColor:
                          vetStatus === 'approved' ? colors.success : colors.card,
                        borderColor: colors.success,
                      },
                    ]}
                    onPress={() => setVetStatus('approved')}
                  >
                    <Text
                      style={[
                        styles.decisionText,
                        { color: vetStatus === 'approved' ? '#fff' : colors.success },
                      ]}
                    >
                      Approve
                    </Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[
                      styles.decisionButton,
                      {
                        backgroundColor:
                          vetStatus === 'rejected' ? colors.error : colors.card,
                        borderColor: colors.error,
                      },
                    ]}
                    onPress={() => setVetStatus('rejected')}
                  >
                    <Text
                      style={[
                        styles.decisionText,
                        { color: vetStatus === 'rejected' ? '#fff' : colors.error },
                      ]}
                    >
                      Reject
                    </Text>
                  </TouchableOpacity>
                </View>

                {/* Rejection reasons */}
                {vetStatus === 'rejected' && (
                  <GlassCard style={styles.reasonsCard}>
                    <Text style={[styles.detailLabel, { color: colors.text }]}>
                      Rejection Reasons:
                    </Text>
                    <View style={styles.reasonsGrid}>
                      {REJECTION_REASONS.map((reason) => (
                        <TouchableOpacity
                          key={reason.id}
                          style={[
                            styles.reasonChip,
                            {
                              backgroundColor: selectedReasons.includes(reason.id)
                                ? colors.error
                                : colors.card,
                              borderColor: colors.error,
                            },
                          ]}
                          onPress={() => toggleReason(reason.id)}
                        >
                          <Text
                            style={[
                              styles.reasonText,
                              {
                                color: selectedReasons.includes(reason.id)
                                  ? '#fff'
                                  : colors.text,
                              },
                            ]}
                          >
                            {reason.label}
                          </Text>
                        </TouchableOpacity>
                      ))}
                    </View>
                  </GlassCard>
                )}

                {/* Notes */}
                <GlassCard style={styles.notesCard}>
                  <Text style={[styles.detailLabel, { color: colors.text }]}>
                    Notes (optional):
                  </Text>
                  <TextInput
                    style={[
                      styles.notesInput,
                      {
                        backgroundColor: colors.card,
                        color: colors.text,
                        borderColor: colors.border,
                      },
                    ]}
                    placeholder="Add notes for the teacher..."
                    placeholderTextColor={colors.textTertiary}
                    value={vetNotes}
                    onChangeText={setVetNotes}
                    multiline
                    numberOfLines={3}
                  />
                </GlassCard>

                {/* Submit button */}
                <NativeButton
                  title={vetStatus === 'approved' ? 'Approve Question' : 'Reject Question'}
                  onPress={handleVet}
                  loading={isVetting}
                  disabled={isVetting}
                  fullWidth
                  size="large"
                  style={{
                    backgroundColor:
                      vetStatus === 'approved' ? colors.success : colors.error,
                    marginTop: Spacing.md,
                  }}
                />
              </>
            )}
          </ScrollView>
        </SafeAreaView>
      </Modal>

      {/* Subject Picker Modal */}
      <Modal
        visible={showSubjectPicker}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => {
          setShowSubjectPicker(false);
          setSubjectSearch('');
        }}
      >
        <SafeAreaView style={[styles.modalContainer, { backgroundColor: colors.background }]}>
          <View style={styles.modalHeader}>
            <Text style={[styles.modalTitle, { color: colors.text }]}>Select Subject</Text>
            <TouchableOpacity onPress={() => {
              setShowSubjectPicker(false);
              setSubjectSearch('');
            }}>
              <Text style={[styles.closeButton, { color: colors.primary }]}>Close</Text>
            </TouchableOpacity>
          </View>

          {/* Search Bar */}
          <View style={[styles.searchContainer, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <IconSymbol name="magnifyingglass" size={18} color={colors.textSecondary} />
            <TextInput
              style={[styles.searchInput, { color: colors.text }]}
              placeholder="Search subjects..."
              placeholderTextColor={colors.textTertiary}
              value={subjectSearch}
              onChangeText={setSubjectSearch}
              autoCapitalize="none"
              autoCorrect={false}
            />
            {subjectSearch.length > 0 && (
              <TouchableOpacity onPress={() => setSubjectSearch('')}>
                <IconSymbol name="xmark.circle.fill" size={18} color={colors.textSecondary} />
              </TouchableOpacity>
            )}
          </View>

          <ScrollView style={styles.modalContent}>
            {/* All Subjects option */}
            <TouchableOpacity
              style={[
                styles.subjectItem,
                { borderColor: colors.border },
                !subjectFilter && { backgroundColor: colors.primary + '15' },
              ]}
              onPress={() => handleSelectSubject(undefined)}
            >
              <View style={styles.subjectItemContent}>
                <Text style={[styles.subjectItemName, { color: colors.text }]}>All Subjects</Text>
                <Text style={[styles.subjectItemMeta, { color: colors.textSecondary }]}>
                  Show questions from all subjects
                </Text>
              </View>
              {!subjectFilter && (
                <IconSymbol name="checkmark.circle.fill" size={22} color={colors.primary} />
              )}
            </TouchableOpacity>

            {/* Subject list */}
            {filteredSubjects.map((subject) => (
              <TouchableOpacity
                key={subject.id}
                style={[
                  styles.subjectItem,
                  { borderColor: colors.border },
                  subjectFilter === subject.id && { backgroundColor: colors.primary + '15' },
                ]}
                onPress={() => handleSelectSubject(subject.id)}
              >
                <View style={styles.subjectItemContent}>
                  <Text style={[styles.subjectItemName, { color: colors.text }]}>
                    {subject.code} - {subject.name}
                  </Text>
                  <Text style={[styles.subjectItemMeta, { color: colors.textSecondary }]}>
                    {subject.teacher_name} • {subject.pending_count} pending
                  </Text>
                </View>
                {subject.pending_count > 0 && (
                  <View style={[styles.pendingBadge, { backgroundColor: colors.warning }]}>
                    <Text style={styles.pendingBadgeText}>{subject.pending_count}</Text>
                  </View>
                )}
                {subjectFilter === subject.id && (
                  <IconSymbol name="checkmark.circle.fill" size={22} color={colors.primary} />
                )}
              </TouchableOpacity>
            ))}

            {filteredSubjects.length === 0 && subjectSearch && (
              <View style={styles.emptyContainer}>
                <Text style={[styles.emptyText, { color: colors.textSecondary }]}>
                  No subjects match "{subjectSearch}"
                </Text>
              </View>
            )}
          </ScrollView>
        </SafeAreaView>
      </Modal>

      {/* Floating Start Vetting Button */}
      {pendingQuestions.length > 0 && statusFilter === 'pending' && (
        <TouchableOpacity
          style={styles.floatingButton}
          onPress={loadAllPendingQuestions}
          activeOpacity={0.9}
        >
          <LinearGradient
            colors={['#5856D6', '#4A4ADE']}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 0 }}
            style={styles.floatingButtonGradient}
          >
            <IconSymbol name="hand.draw.fill" size={20} color="#FFFFFF" />
            <Text style={styles.floatingButtonText}>Start Vetting</Text>
            <View style={styles.floatingButtonBadge}>
              <Text style={styles.floatingButtonBadgeText}>{total}</Text>
            </View>
          </LinearGradient>
        </TouchableOpacity>
      )}

      {/* Swipe Vetting Modal */}
      <SwipeVetting
        visible={showSwipeVetting}
        onClose={() => {
          setShowSwipeVetting(false);
          fetchQuestions(1, false); // Refresh after vetting session
        }}
        questions={pendingQuestions}
        onQuestionVetted={handleQuestionVetted}
        onQuestionUpdated={handleQuestionUpdated}
        onLoadMore={loadMore}
        hasMore={hasMore}
        total={total}
      />
    </SafeAreaView>
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
  loadingText: {
    marginTop: Spacing.md,
    fontSize: FontSizes.md,
  },
  header: {
    padding: Spacing.md,
    paddingBottom: Spacing.sm,
  },
  title: {
    fontSize: FontSizes.xl,
    fontWeight: '700',
  },
  subtitle: {
    fontSize: FontSizes.sm,
    marginTop: 4,
  },
  filterBar: {
    paddingHorizontal: Spacing.md,
    paddingBottom: Spacing.sm,
  },
  filterChip: {
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.full,
    marginRight: Spacing.sm,
    borderWidth: 1,
  },
  filterChipText: {
    fontSize: FontSizes.sm,
    fontWeight: '600',
  },
  bulkBar: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: Spacing.sm,
    paddingHorizontal: Spacing.md,
    gap: Spacing.sm,
  },
  bulkText: {
    color: '#fff',
    fontWeight: '600',
    flex: 1,
  },
  bulkButton: {
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.md,
  },
  bulkButtonText: {
    color: '#fff',
    fontWeight: '600',
    fontSize: FontSizes.sm,
  },
  listContent: {
    padding: Spacing.md,
    gap: Spacing.sm,
  },
  questionCard: {
    marginBottom: Spacing.sm,
  },
  cardHeader: {
    flexDirection: 'row',
    gap: Spacing.sm,
    marginBottom: Spacing.sm,
  },
  typeTag: {
    paddingHorizontal: Spacing.sm,
    paddingVertical: 4,
    borderRadius: BorderRadius.sm,
  },
  typeText: {
    fontSize: FontSizes.xs,
    fontWeight: '700',
  },
  statusTag: {
    paddingHorizontal: Spacing.sm,
    paddingVertical: 4,
    borderRadius: BorderRadius.sm,
  },
  statusText: {
    fontSize: FontSizes.xs,
    fontWeight: '700',
  },
  questionText: {
    fontSize: FontSizes.md,
    lineHeight: 22,
    marginBottom: Spacing.sm,
  },
  metaRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.sm,
    marginBottom: Spacing.sm,
  },
  metaText: {
    fontSize: FontSizes.xs,
  },
  tagsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.xs,
  },
  tag: {
    paddingHorizontal: Spacing.sm,
    paddingVertical: 2,
    borderRadius: BorderRadius.sm,
  },
  tagText: {
    fontSize: FontSizes.xs,
  },
  errorCard: {
    margin: Spacing.md,
    borderWidth: 1,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  errorText: {
    fontSize: FontSizes.sm,
  },
  retryText: {
    fontWeight: '600',
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: Spacing.xl,
  },
  emptyText: {
    fontSize: FontSizes.md,
  },
  // Modal styles
  modalContainer: {
    flex: 1,
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: Spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: '#00000010',
  },
  modalTitle: {
    fontSize: FontSizes.lg,
    fontWeight: '700',
  },
  closeButton: {
    fontSize: FontSizes.md,
    fontWeight: '600',
  },
  modalContent: {
    flex: 1,
    padding: Spacing.md,
  },
  detailCard: {
    marginBottom: Spacing.md,
  },
  detailLabel: {
    fontSize: FontSizes.sm,
    fontWeight: '600',
    marginBottom: 4,
  },
  detailValue: {
    fontSize: FontSizes.md,
    lineHeight: 22,
  },
  optionText: {
    fontSize: FontSizes.md,
    paddingVertical: 4,
    paddingLeft: Spacing.sm,
  },
  decisionRow: {
    flexDirection: 'row',
    gap: Spacing.md,
    marginBottom: Spacing.md,
  },
  decisionButton: {
    flex: 1,
    paddingVertical: Spacing.md,
    borderRadius: BorderRadius.md,
    borderWidth: 2,
    alignItems: 'center',
  },
  decisionText: {
    fontSize: FontSizes.md,
    fontWeight: '700',
  },
  reasonsCard: {
    marginBottom: Spacing.md,
  },
  reasonsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.sm,
    marginTop: Spacing.sm,
  },
  reasonChip: {
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.full,
    borderWidth: 1,
  },
  reasonText: {
    fontSize: FontSizes.sm,
  },
  notesCard: {
    marginBottom: Spacing.md,
  },
  notesInput: {
    borderWidth: 1,
    borderRadius: BorderRadius.md,
    padding: Spacing.md,
    minHeight: 80,
    textAlignVertical: 'top',
    marginTop: Spacing.sm,
  },
  // Subject Dropdown styles
  subjectDropdown: {
    flexDirection: 'row',
    alignItems: 'center',
    marginHorizontal: Spacing.md,
    marginBottom: Spacing.sm,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.md,
    borderWidth: 1,
    gap: Spacing.sm,
  },
  subjectDropdownText: {
    flex: 1,
    fontSize: FontSizes.sm,
    fontWeight: '500',
  },
  // Search styles
  searchContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginHorizontal: Spacing.md,
    marginVertical: Spacing.sm,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.md,
    borderWidth: 1,
    gap: Spacing.sm,
  },
  searchInput: {
    flex: 1,
    fontSize: FontSizes.md,
    paddingVertical: Spacing.xs,
  },
  // Subject Item styles
  subjectItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: Spacing.md,
    marginBottom: Spacing.sm,
    borderRadius: BorderRadius.md,
    borderWidth: 1,
  },
  subjectItemContent: {
    flex: 1,
  },
  subjectItemName: {
    fontSize: FontSizes.md,
    fontWeight: '600',
  },
  subjectItemMeta: {
    fontSize: FontSizes.sm,
    marginTop: 2,
  },
  pendingBadge: {
    paddingHorizontal: Spacing.sm,
    paddingVertical: 2,
    borderRadius: BorderRadius.full,
    marginRight: Spacing.sm,
  },
  pendingBadgeText: {
    color: '#FFFFFF',
    fontSize: FontSizes.xs,
    fontWeight: '700',
  },
  // Floating Button styles
  floatingButton: {
    position: 'absolute',
    bottom: 100,
    left: Spacing.lg,
    right: Spacing.lg,
    borderRadius: BorderRadius.lg,
    overflow: 'hidden',
    shadowColor: '#5856D6',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 8,
  },
  floatingButtonGradient: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: Spacing.md,
    paddingHorizontal: Spacing.lg,
    gap: Spacing.sm,
  },
  floatingButtonText: {
    color: '#FFFFFF',
    fontSize: FontSizes.md,
    fontWeight: '700',
  },
  floatingButtonBadge: {
    backgroundColor: 'rgba(255,255,255,0.3)',
    paddingHorizontal: Spacing.sm,
    paddingVertical: 2,
    borderRadius: BorderRadius.full,
    marginLeft: Spacing.xs,
  },
  floatingButtonBadgeText: {
    color: '#FFFFFF',
    fontSize: FontSizes.xs,
    fontWeight: '700',
  },
});
