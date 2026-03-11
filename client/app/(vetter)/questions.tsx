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
  Platform,
} from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { useLocalSearchParams } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';

import { GlassCard } from '@/components/ui/glass-card';
import { NativeButton } from '@/components/ui/native-button';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { SwipeVetting } from '@/components/swipe-vetting';
import { Colors, Spacing, BorderRadius, FontSizes } from '@/constants/theme';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { useToast } from '@/components/toast';
import { useResponsive } from '@/hooks/use-responsive';
import {
  vetterService,
  QuestionForVetting,
  SubjectSummary,
  TeacherSummary,
  QuestionVersionEntry,
  VersionHistoryResponse,
} from '@/services/vetter.service';

type StatusFilter = 'pending' | 'approved' | 'rejected' | 'all';

const REJECTION_REASONS = [
  { id: 'duplicate', label: 'Duplicate question' },
  { id: 'off_topic', label: 'Off topic' },
  { id: 'unclear', label: 'Unclear wording' },
  { id: 'incorrect_answer', label: 'Incorrect answer' },
  { id: 'poor_options', label: 'Poor MCQ options' },
  { id: 'needs_improvement', label: 'Needs improvement' },
];

const CO_LEVELS = [
  { level: 1, label: 'Basic', color: '#34C759' },
  { level: 2, label: 'Intermediate', color: '#FF9500' },
  { level: 3, label: 'Advanced', color: '#FF3B30' },
];

const COURSE_OUTCOMES = ['CO1', 'CO2', 'CO3', 'CO4', 'CO5'];

const CO_DESCRIPTIONS: Record<string, string> = {
  CO1: 'Analyze',
  CO2: 'Knowledge',
  CO3: 'Apply',
  CO4: 'Evaluate',
  CO5: 'Create',
};

export default function QuestionsForVetting() {
  const colorScheme = useColorScheme();
  const colors = Colors[colorScheme ?? 'light'];
  const { showSuccess, showError } = useToast();
  const { desktopContentStyle, modalContentStyle } = useResponsive();
  const insets = useSafeAreaInsets();
  const params = useLocalSearchParams<{
    teacher_id?: string;
    subject_id?: string;
    topic_id?: string;
    status?: StatusFilter;
  }>();

  const [questions, setQuestions] = useState<QuestionForVetting[]>([]);
  const [subjects, setSubjects] = useState<SubjectSummary[]>([]);
  const [teachers, setTeachers] = useState<TeacherSummary[]>([]);
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

  // Question text search
  const [questionSearch, setQuestionSearch] = useState('');

  // Subject search dropdown
  const [showSubjectPicker, setShowSubjectPicker] = useState(false);
  const [subjectSearch, setSubjectSearch] = useState('');

  // Teacher picker
  const [showTeacherPicker, setShowTeacherPicker] = useState(false);
  const [teacherSearch, setTeacherSearch] = useState('');

  // Swipe vetting mode
  const [showSwipeVetting, setShowSwipeVetting] = useState(false);

  // Version history
  const [showVersionHistory, setShowVersionHistory] = useState(false);
  const [versionHistory, setVersionHistory] = useState<QuestionVersionEntry[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [isRestoringVersion, setIsRestoringVersion] = useState<string | null>(null);

  // Inline edit state (populated when modal opens)
  const [editQuestionText, setEditQuestionText] = useState('');
  const [editCorrectAnswer, setEditCorrectAnswer] = useState('');
  const [editOptions, setEditOptions] = useState<string[]>([]);
const [editCoMapping, setEditCoMapping] = useState<Record<string, number>>({});
  const [isEditingQuestion, setIsEditingQuestion] = useState(false);
  const [isEditingAnswer, setIsEditingAnswer] = useState(false);
  const [showSources, setShowSources] = useState(false);
  const [expandedSnippets, setExpandedSnippets] = useState<Set<number>>(new Set());

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

  // Fuzzy search filter for teachers
  const filteredTeachers = useMemo(() => {
    if (!teacherSearch.trim()) return teachers;
    const searchLower = teacherSearch.toLowerCase();
    return teachers.filter(
      (t) =>
        (t.full_name ?? '').toLowerCase().includes(searchLower) ||
        t.username.toLowerCase().includes(searchLower) ||
        t.email.toLowerCase().includes(searchLower)
    );
  }, [teachers, teacherSearch]);

  // Get selected teacher name for display
  const selectedTeacherName = useMemo(() => {
    if (!teacherFilter) return 'All Teachers';
    const teacher = teachers.find((t) => t.id === teacherFilter);
    return teacher ? (teacher.full_name || teacher.username) : 'All Teachers';
  }, [teacherFilter, teachers]);

  // Client-side fuzzy filter on loaded questions
  const filteredQuestions = useMemo(() => {
    if (!questionSearch.trim()) return questions;
    const searchLower = questionSearch.toLowerCase();
    return questions.filter(
      (q) =>
        q.question_text.toLowerCase().includes(searchLower) ||
        (q.topic_name ?? '').toLowerCase().includes(searchLower) ||
        (q.subject_name ?? '').toLowerCase().includes(searchLower) ||
        (q.teacher_name ?? '').toLowerCase().includes(searchLower)
    );
  }, [questions, questionSearch]);

  // Initialise editable fields whenever the selected question changes
  useEffect(() => {
    if (selectedQuestion) {
      setEditQuestionText(selectedQuestion.question_text);
      setEditCorrectAnswer(selectedQuestion.correct_answer ?? '');
      setEditOptions(selectedQuestion.options ?? []);
      const coMap: Record<string, number> = {};
      COURSE_OUTCOMES.forEach((co) => {
        const val = (selectedQuestion.course_outcome_mapping ?? {})[co];
        if (val !== undefined) coMap[co] = Number(val);
      });
      setEditCoMapping(coMap);
      setIsEditingQuestion(false);
      setIsEditingAnswer(false);
      setShowSources(false);
      setExpandedSnippets(new Set());
    }
  }, [selectedQuestion?.id]);

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

  const fetchTeachers = useCallback(async () => {
    try {
      const data = await vetterService.getTeachers();
      setTeachers(data);
    } catch (err) {
      console.error('Failed to load teachers', err);
    }
  }, []);

  useEffect(() => {
    fetchTeachers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    setPage(1);
    setSelectedIds(new Set());
    setQuestionSearch('');
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
      // Close any lingering modals before entering swipe mode
      setShowVetModal(false);
      setSelectedQuestion(null);
      setShowVersionHistory(false);
      setVersionHistory([]);
      setShowSwipeVetting(true);
    } catch (err) {
      setError('Failed to load questions');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  }, [teacherFilter, subjectFilter]);

  const handleApprove = async () => {
    if (!selectedQuestion) return;
    setIsVetting(true);
    try {
      const coMapping = Object.entries(editCoMapping)
        .filter(([, v]) => v > 0)
        .reduce((acc, [k, v]) => ({ ...acc, [k]: v }), {} as Record<string, number>);

      // Save any edits first
      const hasTextEdit = editQuestionText.trim() !== selectedQuestion.question_text.trim();
      const hasAnswerEdit = editCorrectAnswer !== (selectedQuestion.correct_answer ?? '');
      const hasOptionsEdit = JSON.stringify(editOptions) !== JSON.stringify(selectedQuestion.options ?? []);
      const existingCo = JSON.stringify(selectedQuestion.course_outcome_mapping ?? {});
      const hasCoEdit = JSON.stringify(coMapping) !== existingCo;

      if (hasTextEdit || hasAnswerEdit || hasOptionsEdit || hasCoEdit) {
        await vetterService.updateQuestion(selectedQuestion.id, {
          ...(hasTextEdit && { question_text: editQuestionText }),
          ...(hasAnswerEdit && { correct_answer: editCorrectAnswer || undefined }),
          ...(hasOptionsEdit && { options: editOptions }),
          ...(hasCoEdit && { course_outcome_mapping: coMapping }),
        });
      }

      await vetterService.vetQuestion(selectedQuestion.id, {
        status: 'approved',
        notes: vetNotes || undefined,
        ...(Object.keys(coMapping).length > 0 && { course_outcome_mapping: coMapping }),
      });

      setShowVetModal(false);
      setSelectedQuestion(null);
      setVetNotes('');
      setSelectedReasons([]);
      setVetStatus('approved');
      showSuccess('Question approved');

      if (statusFilter === 'pending') {
        setQuestions((prev) => prev.filter((q) => q.id !== selectedQuestion.id));
        setTotal((prev) => prev - 1);
      } else {
        fetchQuestions(1, false);
      }
    } catch (err) {
      showError('Failed to approve question');
      console.error(err);
    } finally {
      setIsVetting(false);
    }
  };

  const handleReject = async () => {
    if (!selectedQuestion) return;
    setIsVetting(true);
    try {
      const result = await vetterService.rejectAndRegenerate(selectedQuestion.id, {
        notes: vetNotes || undefined,
        rejection_reasons: selectedReasons.length > 0 ? selectedReasons : undefined,
      });

      if (result.regenerated && result.new_question) {
        const newQ: QuestionForVetting = {
          ...selectedQuestion,
          id: result.new_question.id,
          question_text: result.new_question.question_text,
          question_type: result.new_question.question_type,
          options: result.new_question.options,
          correct_answer: result.new_question.correct_answer,
          explanation: null,
          marks: result.new_question.marks,
          difficulty_level: result.new_question.difficulty_level,
          bloom_taxonomy_level: result.new_question.bloom_taxonomy_level,
          vetting_status: result.new_question.vetting_status,
          vetting_notes: null,
          version_number: result.new_question.version_number,
          replaces_id: selectedQuestion.id,
          replaced_by_id: null,
          source_info: result.new_question.source_info ?? null,
        };
        setSelectedQuestion(newQ);
        setVetStatus('approved');
        setVetNotes('');
        setSelectedReasons([]);

        if (statusFilter === 'pending') {
          setQuestions((prev) => prev.map((q) => (q.id === selectedQuestion.id ? newQ : q)));
        } else {
          fetchQuestions(1, false);
        }
        showSuccess('Rejected — review the replacement below');
      } else {
        setShowVetModal(false);
        setSelectedQuestion(null);
        setVetNotes('');
        setSelectedReasons([]);
        setVetStatus('approved');

        if (statusFilter === 'pending') {
          setQuestions((prev) => prev.filter((q) => q.id !== selectedQuestion.id));
          setTotal((prev) => prev - 1);
        } else {
          fetchQuestions(1, false);
        }
        showSuccess('Question rejected');
      }
    } catch (err) {
      showError('Failed to reject question');
      console.error(err);
    } finally {
      setIsVetting(false);
    }
  };

  const handleOpenVersionHistory = useCallback(async (questionId: string) => {
    setIsLoadingHistory(true);
    setVersionHistory([]);
    setShowVersionHistory(true);
    try {
      const data = await vetterService.getVersionHistory(questionId);
      setVersionHistory(data.versions);
    } catch (err) {
      showError('Failed to load version history');
      console.error(err);
      setShowVersionHistory(false);
    } finally {
      setIsLoadingHistory(false);
    }
  }, [showError]);

  const handleRestoreVersion = useCallback(async (versionId: string) => {
    setIsRestoringVersion(versionId);
    try {
      await vetterService.restoreVersion(versionId);
      showSuccess('Version restored — question is pending review');
      setShowVersionHistory(false);
      setShowVetModal(false);
      setSelectedQuestion(null);
      fetchQuestions(1, false);
    } catch (err) {
      showError('Failed to restore version');
      console.error(err);
    } finally {
      setIsRestoringVersion(null);
    }
  }, [showError, showSuccess, fetchQuestions]);

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

  const handleQuestionReplaced = useCallback((oldId: string, newQuestion: QuestionForVetting) => {
    // Swap the rejected question with its regenerated replacement at the same index
    setQuestions((prev) =>
      prev.map((q) => (q.id === oldId ? newQuestion : q))
    );
  }, []);

  const handleSelectSubject = useCallback((subjectId: string | undefined) => {
    setSubjectFilter(subjectId);
    setShowSubjectPicker(false);
    setSubjectSearch('');
  }, []);

  const handleSelectTeacher = useCallback((teacherId: string | undefined) => {
    setTeacherFilter(teacherId);
    setSubjectFilter(undefined); // reset subject when teacher changes
    setShowTeacherPicker(false);
    setTeacherSearch('');
  }, []);

  // Robust MCQ correct-answer matching (mirrors teacher vetting screen)
  const optionMatchesCorrect = (option: string, correct: string | null | undefined, index: number): boolean => {
    if (!correct) return false;
    const trimmedCorrect = correct.trim();
    const trimmedOption = option.trim();
    if (trimmedOption === trimmedCorrect) return true;
    if (trimmedOption.startsWith(trimmedCorrect)) return true;
    const letter = String.fromCharCode(65 + index);
    if (trimmedCorrect.length === 1 && trimmedCorrect.toUpperCase() === letter) return true;
    if (/^[A-Za-z][.)]?$/.test(trimmedCorrect) && trimmedOption.toUpperCase().startsWith(trimmedCorrect.toUpperCase())) return true;
    return false;
  };

  // Get pending questions for swipe mode
  const pendingQuestions = useMemo(() => {
    return questions.filter((q) => q.vetting_status === 'pending');
  }, [questions]);

  const QuestionCard = ({ question }: { question: QuestionForVetting }) => {
    const isSelected = selectedIds.has(question.id);

    return (
      <TouchableOpacity
        activeOpacity={0.7}
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
            {question.version_number > 1 && (
              <View style={[styles.statusTag, { backgroundColor: colors.primary + '20' }]}>
                <Text style={[styles.statusText, { color: colors.primary }]}>
                  v{question.version_number}
                </Text>
              </View>
            )}
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
          {questionSearch.trim() ? `${filteredQuestions.length} of ${total}` : `${total} questions found`}
        </Text>
      </View>

      {/* Question search bar */}
      <View style={[styles.searchContainer, { backgroundColor: colors.card, borderColor: colors.border, marginHorizontal: Spacing.md, marginBottom: Spacing.sm }]}>
        <IconSymbol name="magnifyingglass" size={18} color={colors.textSecondary} />
        <TextInput
          style={[styles.searchInput, { color: colors.text }]}
          placeholder="Search questions..."
          placeholderTextColor={colors.textTertiary}
          value={questionSearch}
          onChangeText={setQuestionSearch}
          autoCapitalize="none"
          autoCorrect={false}
          returnKeyType="search"
        />
        {questionSearch.length > 0 && (
          <TouchableOpacity onPress={() => setQuestionSearch('')}>
            <IconSymbol name="xmark.circle.fill" size={18} color={colors.textSecondary} />
          </TouchableOpacity>
        )}
      </View>

      {/* Teacher + Subject pickers row */}
      <View style={styles.pickerRow}>
        <TouchableOpacity
          style={[styles.pickerDropdown, { backgroundColor: colors.card, borderColor: teacherFilter ? colors.primary : colors.border }]}
          onPress={() => setShowTeacherPicker(true)}
        >
          <IconSymbol name="person.fill" size={14} color={teacherFilter ? colors.primary : colors.textSecondary} />
          <Text style={[styles.pickerDropdownText, { color: teacherFilter ? colors.primary : colors.text }]} numberOfLines={1}>
            {selectedTeacherName}
          </Text>
          {teacherFilter ? (
            <TouchableOpacity onPress={() => handleSelectTeacher(undefined)} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
              <IconSymbol name="xmark.circle.fill" size={14} color={colors.primary} />
            </TouchableOpacity>
          ) : (
            <IconSymbol name="chevron.down" size={12} color={colors.textSecondary} />
          )}
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.pickerDropdown, { backgroundColor: colors.card, borderColor: subjectFilter ? colors.primary : colors.border }]}
          onPress={() => setShowSubjectPicker(true)}
        >
          <IconSymbol name="book.fill" size={14} color={subjectFilter ? colors.primary : colors.textSecondary} />
          <Text style={[styles.pickerDropdownText, { color: subjectFilter ? colors.primary : colors.text }]} numberOfLines={1}>
            {selectedSubjectName}
          </Text>
          {subjectFilter ? (
            <TouchableOpacity onPress={() => handleSelectSubject(undefined)} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
              <IconSymbol name="xmark.circle.fill" size={14} color={colors.primary} />
            </TouchableOpacity>
          ) : (
            <IconSymbol name="chevron.down" size={12} color={colors.textSecondary} />
          )}
        </TouchableOpacity>
      </View>

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
        data={filteredQuestions}
        keyExtractor={(item) => String(item.id)}
        renderItem={({ item }) => <QuestionCard question={item} />}
        contentContainerStyle={[styles.listContent, desktopContentStyle]}
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
            <Text style={[styles.modalTitle, { color: colors.text }]}>
              {showVersionHistory ? 'Version History' : 'Review Question'}
            </Text>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: Spacing.md }}>
              {!showVersionHistory && selectedQuestion && (selectedQuestion.version_number > 1 || selectedQuestion.replaces_id) && (
                <TouchableOpacity onPress={() => handleOpenVersionHistory(selectedQuestion.id)}>
                  <Text style={[styles.closeButton, { color: colors.warning }]}>History</Text>
                </TouchableOpacity>
              )}
              {showVersionHistory && (
                <TouchableOpacity onPress={() => { setShowVersionHistory(false); setVersionHistory([]); }}>
                  <Text style={[styles.closeButton, { color: colors.primary }]}>← Back</Text>
                </TouchableOpacity>
              )}
              {!showVersionHistory && (
                <TouchableOpacity onPress={() => {
                  setShowVetModal(false);
                  setShowVersionHistory(false);
                  setVersionHistory([]);
                }}>
                  <Text style={[styles.closeButton, { color: colors.primary }]}>Close</Text>
                </TouchableOpacity>
              )}
            </View>
          </View>

          <ScrollView style={styles.modalContent}>
            {/* ── Version History panel (inline) ── */}
            {showVersionHistory ? (
              isLoadingHistory ? (
                <View style={{ paddingVertical: Spacing.xl, alignItems: 'center' }}>
                  <ActivityIndicator size="large" color={colors.primary} />
                  <Text style={[{ color: colors.textSecondary, marginTop: Spacing.md, fontSize: FontSizes.sm }]}>
                    Loading history...
                  </Text>
                </View>
              ) : versionHistory.length === 0 ? (
                <View style={{ paddingVertical: Spacing.xl, alignItems: 'center' }}>
                  <Text style={[{ color: colors.textSecondary, fontSize: FontSizes.md }]}>No version history found</Text>
                </View>
              ) : (
                versionHistory.map((version) => (
                  <GlassCard
                    key={version.id}
                    style={[
                      styles.detailCard,
                      version.is_latest && { borderWidth: 2, borderColor: colors.primary },
                    ]}
                  >
                    <View style={[styles.cardHeader, { justifyContent: 'space-between' }]}>
                      <View style={{ flexDirection: 'row', gap: Spacing.sm, alignItems: 'center' }}>
                        <View style={[styles.typeTag, { backgroundColor: colors.primary + '20' }]}>
                          <Text style={[styles.typeText, { color: colors.primary }]}>v{version.version_number}</Text>
                        </View>
                        <View style={[styles.statusTag, {
                          backgroundColor: version.vetting_status === 'pending' ? colors.warning + '20'
                            : version.vetting_status === 'approved' ? colors.success + '20' : colors.error + '20',
                        }]}>
                          <Text style={[styles.statusText, {
                            color: version.vetting_status === 'pending' ? colors.warning
                              : version.vetting_status === 'approved' ? colors.success : colors.error,
                          }]}>{version.vetting_status.toUpperCase()}</Text>
                        </View>
                        {version.is_latest && (
                          <View style={[styles.statusTag, { backgroundColor: colors.success + '20' }]}>
                            <Text style={[styles.statusText, { color: colors.success }]}>CURRENT</Text>
                          </View>
                        )}
                      </View>
                      {version.generated_at && (
                        <Text style={[styles.metaText, { color: colors.textSecondary }]}>
                          {new Date(version.generated_at).toLocaleDateString()}
                        </Text>
                      )}
                    </View>
                    <Text style={[styles.detailLabel, { color: colors.textSecondary }]}>Question:</Text>
                    <Text style={[styles.detailValue, { color: colors.text }]}>{version.question_text}</Text>
                    {version.options && version.options.length > 0 && (
                      <>
                        <Text style={[styles.detailLabel, { color: colors.textSecondary, marginTop: Spacing.sm }]}>Options:</Text>
                        {version.options.map((opt, oi) => (
                          <Text key={oi} style={[styles.optionText, { color: colors.text },
                            opt.startsWith(version.correct_answer || '~~') && { color: colors.success, fontWeight: '600' },
                          ]}>{opt}</Text>
                        ))}
                      </>
                    )}
                    <View style={[styles.tagsRow, { marginTop: Spacing.sm }]}>
                      {version.difficulty_level && (
                        <View style={[styles.tag, { backgroundColor: colors.card }]}>
                          <Text style={[styles.tagText, { color: colors.textSecondary }]}>{version.difficulty_level}</Text>
                        </View>
                      )}
                      {version.marks && (
                        <View style={[styles.tag, { backgroundColor: colors.card }]}>
                          <Text style={[styles.tagText, { color: colors.textSecondary }]}>{version.marks} marks</Text>
                        </View>
                      )}
                    </View>
                    {version.vetting_notes && (
                      <Text style={[styles.metaText, { color: colors.textSecondary, marginTop: Spacing.sm, fontStyle: 'italic' }]}>
                        Note: {version.vetting_notes}
                      </Text>
                    )}
                    {!version.is_latest && (
                      <NativeButton
                        title={isRestoringVersion === version.id ? 'Restoring...' : 'Restore This Version'}
                        onPress={() => handleRestoreVersion(version.id)}
                        loading={isRestoringVersion === version.id}
                        disabled={isRestoringVersion !== null}
                        fullWidth
                        size="small"
                        style={{ marginTop: Spacing.md, backgroundColor: colors.warning }}
                      />
                    )}
                  </GlassCard>
                ))
              )
            ) : (
            /* ── Normal review panel ── */
            selectedQuestion && (
              <>
                {/* ── Question content ── */}
                <GlassCard style={styles.detailCard}>
                  <View style={styles.cardHeader}>
                    <View style={[styles.typeTag, { backgroundColor: colors.primary + '20' }]}>
                      <Text style={[styles.typeText, { color: colors.primary }]}>
                        {selectedQuestion.question_type.replace('_', ' ').toUpperCase()}
                      </Text>
                    </View>
                    {selectedQuestion.version_number > 1 && (
                      <View style={[styles.typeTag, { backgroundColor: colors.primary + '20' }]}>
                        <Text style={[styles.typeText, { color: colors.primary }]}>
                          v{selectedQuestion.version_number}
                        </Text>
                      </View>
                    )}
                  </View>

                  <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                    <Text style={[styles.detailLabel, { color: colors.textSecondary }]}>Question:</Text>
                    <TouchableOpacity onPress={() => setIsEditingQuestion((v) => !v)} style={{ padding: 4 }}>
                      <IconSymbol name={isEditingQuestion ? 'checkmark' : 'pencil'} size={16} color={colors.primary} />
                    </TouchableOpacity>
                  </View>
                  {isEditingQuestion ? (
                    <TextInput
                      style={[styles.editableField, { color: colors.text, borderColor: colors.border, backgroundColor: colors.background }]}
                      value={editQuestionText}
                      onChangeText={setEditQuestionText}
                      multiline
                      textAlignVertical="top"
                      autoFocus
                    />
                  ) : (
                    <Text style={[styles.detailValue, { color: colors.text, marginTop: 4, lineHeight: 22 }]}>
                      {editQuestionText}
                    </Text>
                  )}

                  {/* MCQ: tappable options */}
                  {selectedQuestion.question_type === 'mcq' && editOptions.length > 0 && (
                    <>
                      <Text style={[styles.detailLabel, { color: colors.textSecondary, marginTop: Spacing.md }]}>
                        Options{'  '}
                        <Text style={{ fontWeight: '400', fontSize: FontSizes.xs, color: colors.textTertiary }}>
                          tap to mark correct
                        </Text>
                      </Text>
                      {editOptions.map((opt, idx) => {
                        const isCorrect = optionMatchesCorrect(opt, editCorrectAnswer, idx);
                        return (
                          <TouchableOpacity
                            key={idx}
                            activeOpacity={0.7}
                            onPress={async () => {
                              setEditCorrectAnswer(opt);
                              // Save immediately so other UIs see the change right away
                              try {
                                await vetterService.updateQuestion(selectedQuestion.id, { correct_answer: opt });
                                setSelectedQuestion((prev) => prev ? { ...prev, correct_answer: opt } : prev);
                                setQuestions((prev) => prev.map((q) => q.id === selectedQuestion.id ? { ...q, correct_answer: opt } : q));
                              } catch (err) {
                                console.error('Failed to save correct answer:', err);
                              }
                            }}
                            style={[
                              styles.optionSelectRow,
                              {
                                backgroundColor: isCorrect ? colors.success + '15' : 'transparent',
                                borderColor: isCorrect ? colors.success : colors.border,
                              },
                            ]}
                          >
                            <IconSymbol
                              name={isCorrect ? 'checkmark.circle.fill' : 'circle'}
                              size={18}
                              color={isCorrect ? colors.success : colors.textTertiary}
                            />
                            <Text
                              style={[
                                styles.optionText,
                                { flex: 1, color: isCorrect ? colors.success : colors.text },
                                isCorrect && { fontWeight: '600' },
                              ]}
                            >
                              {opt}
                            </Text>
                          </TouchableOpacity>
                        );
                      })}
                    </>
                  )}

                  {/* Non-MCQ: editable answer */}
                  {selectedQuestion.question_type !== 'mcq' && (
                    <>
                      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: Spacing.md, marginBottom: 4 }}>
                        <Text style={[styles.detailLabel, { color: colors.textSecondary }]}>Answer:</Text>
                        <TouchableOpacity onPress={() => setIsEditingAnswer((v) => !v)} style={{ padding: 4 }}>
                          <IconSymbol name={isEditingAnswer ? 'checkmark' : 'pencil'} size={16} color={colors.primary} />
                        </TouchableOpacity>
                      </View>
                      {isEditingAnswer ? (
                        <TextInput
                          style={[styles.editableField, { color: colors.text, borderColor: colors.border, backgroundColor: colors.background }]}
                          value={editCorrectAnswer}
                          onChangeText={setEditCorrectAnswer}
                          multiline
                          textAlignVertical="top"
                          placeholder="Expected answer..."
                          placeholderTextColor={colors.textTertiary}
                          autoFocus
                        />
                      ) : (
                        <Text style={[styles.detailValue, { color: editCorrectAnswer ? colors.text : colors.textTertiary, lineHeight: 22, fontStyle: editCorrectAnswer ? 'normal' : 'italic' }]}>
                          {editCorrectAnswer || 'No answer — tap ✏ to edit'}
                        </Text>
                      )}
                    </>
                  )}

                  {selectedQuestion.explanation && (
                    <>
                      <Text style={[styles.detailLabel, { color: colors.textSecondary, marginTop: Spacing.md }]}>
                        Explanation:
                      </Text>
                      <Text style={[styles.detailValue, { color: colors.text }]}>
                        {selectedQuestion.explanation}
                      </Text>
                    </>
                  )}
                </GlassCard>

                {/* ── Source References (collapsible) ── */}
                {selectedQuestion.source_info && selectedQuestion.source_info.sources.length > 0 && (
                  <GlassCard style={styles.detailCard}>
                    <TouchableOpacity
                      activeOpacity={0.7}
                      onPress={() => setShowSources((v) => !v)}
                      style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}
                    >
                      <View style={{ flexDirection: 'row', alignItems: 'center', gap: Spacing.xs }}>
                        <IconSymbol name="doc.text" size={14} color={colors.primary} />
                        <Text style={[styles.detailLabel, { color: colors.text, marginBottom: 0 }]}>
                          Source References ({selectedQuestion.source_info.sources.length})
                        </Text>
                      </View>
                      <IconSymbol name={showSources ? 'chevron.up' : 'chevron.down'} size={14} color={colors.textSecondary} />
                    </TouchableOpacity>
                    {showSources && (
                      <View style={{ marginTop: Spacing.sm }}>
                        {selectedQuestion.source_info.sources.map((src, idx) => (
                          <View
                            key={idx}
                            style={[
                              styles.sourceRow,
                              { borderLeftColor: colors.primary, backgroundColor: colors.primary + '1A' },
                              idx > 0 && { marginTop: Spacing.sm },
                            ]}
                          >
                            <View style={{ flexDirection: 'row', alignItems: 'center', gap: Spacing.xs, marginBottom: 2 }}>
                              <IconSymbol name="doc.text" size={13} color={colors.primary} />
                              <Text style={[styles.sourceDoc, { color: colors.primary }]}>
                                {src.document_name ?? 'Document'}
                                {src.page_number != null ? `  ·  p.${src.page_number}` : ''}
                                {src.page_range != null ? `  ·  pp.${src.page_range[0]}–${src.page_range[1]}` : ''}
                              </Text>
                            </View>
                            {src.section_heading ? (
                              <Text style={[styles.sourceSection, { color: colors.textSecondary }]}>
                                {src.section_heading}
                              </Text>
                            ) : null}
                            {src.content_snippet ? (
                              <>
                                <Text
                                  style={[styles.sourceSnippet, { color: colors.textTertiary }]}
                                  numberOfLines={expandedSnippets.has(idx) ? undefined : 3}
                                >
                                  "{src.content_snippet}"
                                </Text>
                                {src.content_snippet.length > 120 && (
                                  <TouchableOpacity
                                    onPress={() =>
                                      setExpandedSnippets((prev) => {
                                        const next = new Set(prev);
                                        next.has(idx) ? next.delete(idx) : next.add(idx);
                                        return next;
                                      })
                                    }
                                    style={{ marginTop: 4 }}
                                  >
                                    <Text style={{ fontSize: FontSizes.xs, color: colors.primary, fontWeight: '600' }}>
                                      {expandedSnippets.has(idx) ? 'Show less' : 'Show more'}
                                    </Text>
                                  </TouchableOpacity>
                                )}
                              </>
                            ) : null}
                          </View>
                        ))}
                        {selectedQuestion.source_info.generation_reasoning ? (
                          <Text style={[styles.metaText, { color: colors.textSecondary, marginTop: Spacing.sm, fontStyle: 'italic' }]}>
                            {selectedQuestion.source_info.generation_reasoning}
                          </Text>
                        ) : null}
                      </View>
                    )}
                  </GlassCard>
                )}

                {/* ── CO Mapping ── */}
                <GlassCard style={styles.detailCard}>
                  <LinearGradient
                    colors={['#5856D6', '#4A4ADE'] as const}
                    style={[styles.coSectionHeader, { marginBottom: Spacing.md }]}
                  >
                    <IconSymbol name="list.number" size={16} color="#FFFFFF" />
                    <Text style={styles.coSectionHeaderText}>Course Outcome Mapping</Text>
                  </LinearGradient>
                  <View style={styles.coMappingGrid}>
                    {COURSE_OUTCOMES.map((co) => (
                      <View key={co} style={styles.coMappingRow}>
                        <View style={styles.coLabelColumn}>
                          <Text style={[styles.coLabel, { color: colors.text }]}>{co}</Text>
                          <Text style={[styles.coDesc, { color: colors.textSecondary }]}>{CO_DESCRIPTIONS[co]}</Text>
                        </View>
                        <View style={styles.levelButtons}>
                          {CO_LEVELS.map(({ level, label, color }) => {
                            const isActive = editCoMapping[co] === level;
                            return (
                              <TouchableOpacity
                                key={level}
                                activeOpacity={0.7}
                                style={[
                                  styles.levelButton,
                                  { borderColor: color },
                                  isActive && { backgroundColor: color },
                                ]}
                                onPress={() =>
                                  setEditCoMapping((prev) => ({
                                    ...prev,
                                    [co]: isActive ? 0 : level,
                                  }))
                                }
                              >
                                <Text style={[styles.levelButtonText, { color: isActive ? '#FFFFFF' : color }]}>
                                  {label}
                                </Text>
                              </TouchableOpacity>
                            );
                          })}
                        </View>
                      </View>
                    ))}
                  </View>
                </GlassCard>

                {/* ── Rejection reasons — expanded when Reject tapped ── */}
                {vetStatus === 'rejected' && (
                  <GlassCard style={[styles.reasonsCard, { borderWidth: 1, borderColor: colors.error + '40' }]}>
                    <Text style={[styles.detailLabel, { color: colors.text }]}>Rejection Reasons:</Text>
                    <View style={styles.reasonsGrid}>
                      {REJECTION_REASONS.map((reason) => (
                        <TouchableOpacity
                          key={reason.id}
                          activeOpacity={0.7}
                          style={[
                            styles.reasonChip,
                            {
                              backgroundColor: selectedReasons.includes(reason.id) ? colors.error : colors.card,
                              borderColor: colors.error,
                            },
                          ]}
                          onPress={() => toggleReason(reason.id)}
                        >
                          <Text style={[styles.reasonText, { color: selectedReasons.includes(reason.id) ? '#fff' : colors.text }]}>
                            {reason.label}
                          </Text>
                        </TouchableOpacity>
                      ))}
                    </View>
                    <NativeButton
                      title="Confirm Rejection"
                      onPress={handleReject}
                      loading={isVetting}
                      disabled={isVetting}
                      fullWidth
                      size="large"
                      style={{ backgroundColor: colors.error, marginTop: Spacing.md }}
                    />
                  </GlassCard>
                )}

                {/* ── Decision buttons ── */}
                <View style={[styles.decisionRow, { marginBottom: Spacing.xl }]}>
                  <TouchableOpacity
                    activeOpacity={0.7}
                    style={[styles.decisionButton, { backgroundColor: colors.success, borderColor: colors.success }]}
                    onPress={handleApprove}
                    disabled={isVetting}
                  >
                    {isVetting && vetStatus !== 'rejected' ? (
                      <ActivityIndicator size="small" color="#fff" />
                    ) : (
                      <Text style={[styles.decisionText, { color: '#fff' }]}>✓ Approve</Text>
                    )}
                  </TouchableOpacity>
                  <TouchableOpacity
                    activeOpacity={0.7}
                    style={[
                      styles.decisionButton,
                      {
                        backgroundColor: vetStatus === 'rejected' ? colors.error : colors.card,
                        borderColor: colors.error,
                      },
                    ]}
                    onPress={() => setVetStatus((s) => (s === 'rejected' ? 'approved' : 'rejected'))}
                    disabled={isVetting}
                  >
                    <Text style={[styles.decisionText, { color: vetStatus === 'rejected' ? '#fff' : colors.error }]}>
                      ✕ Reject
                    </Text>
                  </TouchableOpacity>
                </View>
              </>
            )
            )}
          </ScrollView>
        </SafeAreaView>
      </Modal>

      {/* Teacher Picker Modal */}
      <Modal
        visible={showTeacherPicker}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => {
          setShowTeacherPicker(false);
          setTeacherSearch('');
        }}
      >
        <SafeAreaView style={[styles.modalContainer, { backgroundColor: colors.background }]}>
          <View style={styles.modalHeader}>
            <Text style={[styles.modalTitle, { color: colors.text }]}>Select Teacher</Text>
            <TouchableOpacity onPress={() => { setShowTeacherPicker(false); setTeacherSearch(''); }}>
              <Text style={[styles.closeButton, { color: colors.primary }]}>Close</Text>
            </TouchableOpacity>
          </View>

          <View style={[styles.searchContainer, { backgroundColor: colors.card, borderColor: colors.border }]}>
            <IconSymbol name="magnifyingglass" size={18} color={colors.textSecondary} />
            <TextInput
              style={[styles.searchInput, { color: colors.text }]}
              placeholder="Search teachers..."
              placeholderTextColor={colors.textTertiary}
              value={teacherSearch}
              onChangeText={setTeacherSearch}
              autoCapitalize="none"
              autoCorrect={false}
            />
            {teacherSearch.length > 0 && (
              <TouchableOpacity onPress={() => setTeacherSearch('')}>
                <IconSymbol name="xmark.circle.fill" size={18} color={colors.textSecondary} />
              </TouchableOpacity>
            )}
          </View>

          <ScrollView style={styles.modalContent}>
            <TouchableOpacity
              style={[
                styles.subjectItem,
                { borderColor: colors.border },
                !teacherFilter && { backgroundColor: colors.primary + '15' },
              ]}
              onPress={() => handleSelectTeacher(undefined)}
            >
              <View style={styles.subjectItemContent}>
                <Text style={[styles.subjectItemName, { color: colors.text }]}>All Teachers</Text>
                <Text style={[styles.subjectItemMeta, { color: colors.textSecondary }]}>
                  Show questions from all teachers
                </Text>
              </View>
              {!teacherFilter && (
                <IconSymbol name="checkmark.circle.fill" size={22} color={colors.primary} />
              )}
            </TouchableOpacity>

            {filteredTeachers.map((teacher) => (
              <TouchableOpacity
                key={teacher.id}
                style={[
                  styles.subjectItem,
                  { borderColor: colors.border },
                  teacherFilter === teacher.id && { backgroundColor: colors.primary + '15' },
                ]}
                onPress={() => handleSelectTeacher(teacher.id)}
              >
                <View style={styles.subjectItemContent}>
                  <Text style={[styles.subjectItemName, { color: colors.text }]}>
                    {teacher.full_name || teacher.username}
                  </Text>
                  <Text style={[styles.subjectItemMeta, { color: colors.textSecondary }]}>
                    {teacher.email} • {teacher.pending_count} pending
                  </Text>
                  {teacher.subjects.length > 0 && (
                    <Text style={[styles.subjectItemMeta, { color: colors.textTertiary, marginTop: 2 }]} numberOfLines={1}>
                      {teacher.subjects.slice(0, 3).join(' · ')}{teacher.subjects.length > 3 ? ` +${teacher.subjects.length - 3}` : ''}
                    </Text>
                  )}
                </View>
                {teacher.pending_count > 0 && (
                  <View style={[styles.pendingBadge, { backgroundColor: colors.warning }]}>
                    <Text style={styles.pendingBadgeText}>{teacher.pending_count}</Text>
                  </View>
                )}
                {teacherFilter === teacher.id && (
                  <IconSymbol name="checkmark.circle.fill" size={22} color={colors.primary} />
                )}
              </TouchableOpacity>
            ))}

            {filteredTeachers.length === 0 && teacherSearch && (
              <View style={styles.emptyContainer}>
                <Text style={[styles.emptyText, { color: colors.textSecondary }]}>
                  No teachers match "{teacherSearch}"
                </Text>
              </View>
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
          style={[styles.floatingButton, { bottom: Platform.OS === 'ios' ? 90 + Spacing.md : Spacing.md }]}
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
        onQuestionReplaced={handleQuestionReplaced}
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
    maxWidth: 700,
    width: '100%',
    alignSelf: 'center',
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
  // Picker row (teacher + subject side by side)
  pickerRow: {
    flexDirection: 'row',
    marginHorizontal: Spacing.md,
    marginBottom: Spacing.sm,
    gap: Spacing.sm,
  },
  pickerDropdown: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: Spacing.sm,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.md,
    borderWidth: 1,
    gap: Spacing.xs,
  },
  pickerDropdownText: {
    flex: 1,
    fontSize: FontSizes.xs,
    fontWeight: '500',
  },
  // Subject Dropdown styles (kept for backward compat)
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
    left: Spacing.lg,
    right: Spacing.lg,
    borderRadius: BorderRadius.lg,
    overflow: 'hidden',
    boxShadow: '0px 4px 8px rgba(88,86,214,0.3)',
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
  // Editable field
  editableField: {
    borderWidth: 1,
    borderRadius: BorderRadius.md,
    padding: Spacing.md,
    minHeight: 70,
    textAlignVertical: 'top',
    fontSize: FontSizes.md,
    lineHeight: 22,
    marginTop: 4,
  },
  // Option selection row (MCQ)
  optionSelectRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    padding: Spacing.sm,
    borderRadius: BorderRadius.md,
    borderWidth: 1,
    marginBottom: Spacing.xs,
  },
  // Source references
  sourceRow: {
    borderLeftWidth: 3,
    paddingLeft: Spacing.sm,
    paddingVertical: Spacing.sm,
    paddingRight: Spacing.xs,
    borderRadius: 4,
  },
  sourceDoc: {
    fontSize: FontSizes.sm,
    fontWeight: '600',
  },
  sourceSection: {
    fontSize: FontSizes.xs,
    fontStyle: 'italic',
    marginBottom: 2,
  },
  sourceSnippet: {
    fontSize: FontSizes.xs,
    lineHeight: 16,
    marginTop: 2,
  },
  // CO Mapping
  addCoButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: Spacing.sm,
    paddingVertical: 4,
    borderWidth: 1,
    borderRadius: BorderRadius.sm,
  },
  coRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    marginBottom: Spacing.sm,
  },
  coKeyInput: {
    borderWidth: 1,
    borderRadius: BorderRadius.sm,
    paddingHorizontal: Spacing.sm,
    paddingVertical: Spacing.xs,
    width: 72,
    fontSize: FontSizes.sm,
  },
  coValueInput: {
    borderWidth: 1,
    borderRadius: BorderRadius.sm,
    paddingHorizontal: Spacing.sm,
    paddingVertical: Spacing.xs,
    width: 60,
    fontSize: FontSizes.sm,
  },
  // Teacher-style CO mapping
  coSectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: Spacing.sm,
    borderRadius: BorderRadius.sm,
    gap: Spacing.sm,
  },
  coSectionHeaderText: {
    fontSize: FontSizes.sm,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  coMappingGrid: {
    marginBottom: Spacing.xs,
  },
  coMappingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: Spacing.sm,
  },
  coLabelColumn: {
    width: 80,
  },
  coLabel: {
    fontSize: FontSizes.md,
    fontWeight: '600',
  },
  coDesc: {
    fontSize: FontSizes.xs,
    marginTop: 2,
  },
  levelButtons: {
    flexDirection: 'row',
    flex: 1,
    gap: Spacing.xs,
  },
  levelButton: {
    flex: 1,
    paddingVertical: Spacing.xs,
    borderRadius: BorderRadius.sm,
    borderWidth: 2,
    alignItems: 'center',
  },
  levelButtonText: {
    fontSize: FontSizes.xs,
    fontWeight: '600',
  },
});
