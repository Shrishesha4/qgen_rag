import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  FlatList,
  TouchableOpacity,
  RefreshControl,
  Alert,
  ActivityIndicator,
  TextInput,
  Modal,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { BlurView } from 'expo-blur';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { Colors, Spacing, BorderRadius, FontSizes } from '@/constants/theme';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { vettingService, PendingQuestion, VettingStats, CourseOutcomeMapping, REJECTION_REASONS, determineRegenerationMode } from '@/services/vetting';
import { questionsService } from '@/services/questions';
import { subjectsService, Subject, Topic } from '@/services/subjects';
import { useToast } from '@/components/toast';
import { extractErrorDetails } from '@/utils/errors';
import { mediumImpact, selectionImpact } from '@/utils/haptics';
import { QuestionSources } from '@/components/question-sources';
import { VoiceInput, isSpeechRecognitionAvailable } from '@/components/voice-input';

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

export default function VettingScreen() {
  const colorScheme = useColorScheme();
  const colors = Colors[colorScheme ?? 'light'];
  const isDark = colorScheme === 'dark';
  const { showError, showSuccess } = useToast();

  const [questions, setQuestions] = useState<PendingQuestion[]>([]);
  const [stats, setStats] = useState<VettingStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [expandedQuestion, setExpandedQuestion] = useState<string | null>(null);
  const [coMappings, setCoMappings] = useState<Record<string, CourseOutcomeMapping>>({});
  const [replacedQuestionId, setReplacedQuestionId] = useState<string | null>(null);
  const [regenerating, setRegenerating] = useState<Record<string, boolean>>({});

  // Edit state for marks and subject/topic
  const [editMarks, setEditMarks] = useState<Record<string, number>>({});
  const [editDifficulty, setEditDifficulty] = useState<Record<string, string>>({});
  const [editSubjectId, setEditSubjectId] = useState<Record<string, string | null>>({});
  const [editTopicId, setEditTopicId] = useState<Record<string, string | null>>({});

  // Answer editing state (short/long answers and MCQ correct answer draft)
  const [answerEditMode, setAnswerEditMode] = useState<Record<string, boolean>>({});
  const [answerDraft, setAnswerDraft] = useState<Record<string, string | null>>({});
  const [savingAnswer, setSavingAnswer] = useState<string | null>(null);

  // Rejection reason modal state
  const [showRejectModal, setShowRejectModal] = useState<string | null>(null);
  const [selectedRejectReasons, setSelectedRejectReasons] = useState<string[]>([]);
  const [customFeedback, setCustomFeedback] = useState<string>('');
  const [feedbackInputMode, setFeedbackInputMode] = useState<'text' | 'voice'>('text');

  // Subject/Topic picker state
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [topics, setTopics] = useState<Record<string, Topic[]>>({});
  const [loadingSubjects, setLoadingSubjects] = useState(false);
  const [showSubjectPicker, setShowSubjectPicker] = useState<string | null>(null);
  const [showTopicPicker, setShowTopicPicker] = useState<string | null>(null);
  const [savingQuestion, setSavingQuestion] = useState<string | null>(null);

  const loadPendingQuestions = useCallback(async (pageNum: number = 1, append: boolean = false) => {
    try {
      if (pageNum === 1) {
        setIsLoading(true);
      }
      if (append) {
        setIsLoadingMore(true);
      }

      const [questionsResponse, statsResponse] = await Promise.all([
        vettingService.getPendingQuestions(pageNum, 20),
        vettingService.getVettingStats(),
      ]);

      if (append) {
        setQuestions((prev) => [...prev, ...questionsResponse.questions]);
      } else {
        setQuestions(questionsResponse.questions);
      }

      setStats(statsResponse);
      setPage(questionsResponse.pagination.page);
      setHasMore(questionsResponse.pagination.page < questionsResponse.pagination.total_pages);

      // Merge defaults into existing state using functional updates so this function
      // doesn't depend on current edit-state values (prevents unnecessary remounts)
      const defaultsFor = questionsResponse.questions.reduce((acc, q) => {
        acc.coMappings[q.id] = q.course_outcome_mapping || acc.coMappings[q.id] || undefined;
        acc.editMarks[q.id] = acc.editMarks[q.id] ?? q.marks ?? 1;
        acc.editDifficulty[q.id] = acc.editDifficulty[q.id] ?? q.difficulty_level ?? 'medium';
        acc.editSubjectId[q.id] = acc.editSubjectId[q.id] ?? q.subject_id ?? null;
        acc.editTopicId[q.id] = acc.editTopicId[q.id] ?? q.topic_id ?? null;
        acc.answerDraft[q.id] = acc.answerDraft[q.id] ?? q.correct_answer ?? null;
        acc.answerEditMode[q.id] = acc.answerEditMode[q.id] ?? false;
        return acc;
      }, { coMappings: {} as Record<string, CourseOutcomeMapping | undefined>, editMarks: {} as Record<string, number>, editDifficulty: {} as Record<string, string>, editSubjectId: {} as Record<string, string | null>, editTopicId: {} as Record<string, string | null>, answerDraft: {} as Record<string, string | null>, answerEditMode: {} as Record<string, boolean> });

      // Apply functional merges (only adds missing keys)
      setCoMappings((prev) => {
        const toAdd: Record<string, CourseOutcomeMapping> = {};
        for (const id of Object.keys(defaultsFor.coMappings)) {
          if (!(id in prev) && defaultsFor.coMappings[id] !== undefined) toAdd[id] = defaultsFor.coMappings[id] as CourseOutcomeMapping;
        }
        return Object.keys(toAdd).length ? { ...prev, ...toAdd } : prev;
      });

      setEditMarks((prev) => {
        const toAdd: Record<string, number> = {};
        for (const [id, v] of Object.entries(defaultsFor.editMarks)) {
          if (!(id in prev)) toAdd[id] = v;
        }
        return Object.keys(toAdd).length ? { ...prev, ...toAdd } : prev;
      });

      setEditDifficulty((prev) => {
        const toAdd: Record<string, string> = {};
        for (const [id, v] of Object.entries(defaultsFor.editDifficulty)) {
          if (!(id in prev)) toAdd[id] = v;
        }
        return Object.keys(toAdd).length ? { ...prev, ...toAdd } : prev;
      });

      setEditSubjectId((prev) => {
        const toAdd: Record<string, string | null> = {};
        for (const [id, v] of Object.entries(defaultsFor.editSubjectId)) {
          if (!(id in prev)) toAdd[id] = v;
        }
        return Object.keys(toAdd).length ? { ...prev, ...toAdd } : prev;
      });

      setEditTopicId((prev) => {
        const toAdd: Record<string, string | null> = {};
        for (const [id, v] of Object.entries(defaultsFor.editTopicId)) {
          if (!(id in prev)) toAdd[id] = v;
        }
        return Object.keys(toAdd).length ? { ...prev, ...toAdd } : prev;
      });

      setAnswerDraft((prev) => {
        const toAdd: Record<string, string | null> = {};
        for (const [id, v] of Object.entries(defaultsFor.answerDraft)) {
          if (!(id in prev)) toAdd[id] = v;
        }
        return Object.keys(toAdd).length ? { ...prev, ...toAdd } : prev;
      });

      setAnswerEditMode((prev) => {
        const toAdd: Record<string, boolean> = {};
        for (const [id, v] of Object.entries(defaultsFor.answerEditMode)) {
          if (!(id in prev)) toAdd[id] = v;
        }
        return Object.keys(toAdd).length ? { ...prev, ...toAdd } : prev;
      });
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
      setIsLoadingMore(false);
    }
  }, []);

  const loadData = useCallback(() => {
    // initial fetch
    loadPendingQuestions(1, false);
    loadSubjects();
  }, [loadPendingQuestions]);

  const loadSubjects = useCallback(async () => {
    if (subjects.length > 0) return;
    setLoadingSubjects(true);
    try {
      const response = await subjectsService.listSubjects(1, 100);
      setSubjects(response.subjects);
    } catch (error) {
      const details = extractErrorDetails(error);
      if (details.isAuthError) {
        // Already redirected by interceptor — don't spam console
        return;
      }
      console.error('Failed to load subjects:', error);
      showError(error, 'Failed to load subjects');
    } finally {
      setLoadingSubjects(false);
    }
  }, [subjects.length]);

  const refreshStatsOnly = useCallback(async () => {
    try {
      const statsResponse = await vettingService.getVettingStats();
      setStats(statsResponse);
    } catch (error) {
      console.error('Failed to refresh stats:', error);
    }
  }, []);

  const loadTopicsForSubject = useCallback(async (subjectId: string) => {
    if (topics[subjectId]) return;
    try {
      const response = await subjectsService.listTopics(subjectId, 1, 100);
      setTopics(prev => ({ ...prev, [subjectId]: response.topics }));
    } catch (error) {
      console.error('Failed to load topics:', error);
    }
  }, [topics]);

  const handleLoadMore = () => {
    if (!hasMore || isLoadingMore || isLoading) return;
    const next = page + 1;
    setPage(next);
    loadPendingQuestions(next, true);
  };

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleRefresh = () => {
    setIsRefreshing(true);
    setPage(1);
    loadPendingQuestions(1, false);
  };

  const handleSaveQuestionEdits = async (questionId: string) => {
    setSavingQuestion(questionId);
    try {
      const payload: any = {
        marks: editMarks[questionId],
        difficulty_level: editDifficulty[questionId] as 'easy' | 'medium' | 'hard' | undefined,
        subject_id: editSubjectId[questionId] || undefined,
        topic_id: editTopicId[questionId] || undefined,
        course_outcome_mapping: coMappings[questionId],
      };

      // include correct_answer (MCQ or short/long) if edited
      if (answerDraft[questionId] !== undefined) {
        payload.correct_answer = answerDraft[questionId] || null;
      }

      await questionsService.updateQuestion(questionId, payload);

      // update local question so UI reflects change immediately
      setQuestions((prev) => prev.map((q) => (q.id === questionId ? { ...q, correct_answer: payload.correct_answer ?? q.correct_answer, marks: payload.marks ?? q.marks, difficulty_level: payload.difficulty_level ?? q.difficulty_level, subject_id: payload.subject_id ?? q.subject_id, topic_id: payload.topic_id ?? q.topic_id } : q)));

      showSuccess('Question updated successfully');
    } catch (error) {
      showError(error, 'Failed to save changes');
    } finally {
      setSavingQuestion(null);
    }
  };

  const getSubjectName = (subjectId: string | null) => {
    if (!subjectId) return null;
    return subjects.find(s => s.id === subjectId)?.name || null;
  };

  const getTopicName = (subjectId: string | null, topicId: string | null) => {
    if (!subjectId || !topicId) return null;
    return topics[subjectId]?.find(t => t.id === topicId)?.name || null;
  };

  const handleApprove = async (questionId: string) => {
    try {
      await vettingService.vetQuestion(questionId, 'approved');
      setQuestions((prev) => prev.filter((q) => q.id !== questionId));
      showSuccess('Question approved');
      refreshStatsOnly();
    } catch (error) {
      showError(error, 'Approval Failed');
    }
  };

  const openRejectModal = (questionId: string) => {
    setSelectedRejectReasons([]);
    setCustomFeedback('');
    setFeedbackInputMode('text');
    setShowRejectModal(questionId);
    selectionImpact();
  };

  const toggleRejectReason = (reasonId: string) => {
    setSelectedRejectReasons(prev => 
      prev.includes(reasonId) 
        ? prev.filter(r => r !== reasonId)
        : [...prev, reasonId]
    );
    selectionImpact();
  };

  const confirmReject = async () => {
    const questionId = showRejectModal;
    if (!questionId) return;
    
    setShowRejectModal(null);
    
    try {
      // show regenerating indicator for this question while backend generates replacement
      setRegenerating(prev => ({ ...prev, [questionId]: true }));

      // Determine regeneration mode based on selected reasons
      const regenerationMode = selectedRejectReasons.length > 0 
        ? determineRegenerationMode(selectedRejectReasons) 
        : undefined;

      const replacement = await vettingService.vetQuestion(
        questionId, 
        'rejected', 
        'Rejected by reviewer',
        selectedRejectReasons.length > 0 ? selectedRejectReasons : undefined,
        customFeedback.trim() || undefined,
        regenerationMode
      );

              // clear regenerating flag
              setRegenerating(prev => ({ ...prev, [questionId]: false }));

              console.log('Replacement question received:', replacement);
              console.log('Replacement ID:', replacement?.id);
              console.log('Original question ID:', questionId);
              console.log('Is different ID?', replacement?.id !== questionId);

              if (replacement && replacement.id && replacement.id !== questionId) {
                console.log('Replacing question with new one');
                // Filter out both the original question AND any existing question with the replacement ID
                // to prevent duplicate key errors (replacement might already be in the pending list)
                setQuestions((prev) => {
                  const filtered = prev.filter((q) => q.id !== questionId && q.id !== replacement.id);
                  // Find the index where the original was to insert replacement at same position
                  const originalIndex = prev.findIndex((q) => q.id === questionId);
                  if (originalIndex >= 0 && originalIndex < filtered.length) {
                    filtered.splice(originalIndex, 0, replacement as PendingQuestion);
                  } else {
                    filtered.push(replacement as PendingQuestion);
                  }
                  return filtered;
                });
                setExpandedQuestion((prev) => (prev === questionId ? replacement.id : prev));
                setCoMappings((prev) => {
                  const next = { ...prev };
                  delete next[questionId];
                  next[replacement.id] = (replacement as any).course_outcome_mapping || {};
                  return next;
                });
                setEditMarks((prev) => {
                  const next = { ...prev };
                  delete next[questionId];
                  next[replacement.id] = replacement.marks || 1;
                  return next;
                });
                setEditDifficulty((prev) => {
                  const next = { ...prev };
                  delete next[questionId];
                  next[replacement.id] = (replacement.difficulty_level || 'medium') as any;
                  return next;
                });
                setEditSubjectId((prev) => {
                  const next = { ...prev };
                  delete next[questionId];
                  next[replacement.id] = replacement.subject_id || null;
                  return next;
                });
                setEditTopicId((prev) => {
                  const next = { ...prev };
                  delete next[questionId];
                  next[replacement.id] = replacement.topic_id || null;
                  return next;
                });
                setAnswerDraft((prev) => {
                  const next = { ...prev };
                  delete next[questionId];
                  next[replacement.id] = replacement.correct_answer || null;
                  return next;
                });
                setAnswerEditMode((prev) => {
                  const next = { ...prev };
                  delete next[questionId];
                  next[replacement.id] = false;
                  return next;
                });
                setRegenerating((prev) => {
                  const next = { ...prev };
                  delete next[questionId];
                  return next;
                });
                setReplacedQuestionId(replacement.id);
                setTimeout(() => setReplacedQuestionId(null), 1200);
                showSuccess('Question rejected and replaced');
                refreshStatsOnly();
              } else {
                setQuestions((prev) => prev.filter((q) => q.id !== questionId));
                showSuccess('Question rejected');
                refreshStatsOnly();
              }
            } catch (error) {
              // clear regenerating flag on error too
              setRegenerating(prev => ({ ...prev, [questionId]: false }));
              showError(error, 'Rejection Failed');
            }
  };

  const updateCoMapping = (questionId: string, co: string, level: number) => {
    setCoMappings((prev) => ({
      ...prev,
      [questionId]: {
        ...prev[questionId],
        [co]: level,
      },
    }));
  };

  const saveCoMapping = async (questionId: string) => {
    try {
      await vettingService.updateCourseOutcomeMapping(questionId, coMappings[questionId] || {});
      showSuccess('Course outcomes saved');
    } catch (error) {
      showError(error, 'Save Failed');
    }
  };

  // Return true when an MCQ option should be treated as the correct answer.
  const optionMatchesCorrect = (option: string, correct: string | null | undefined, index: number) => {
    if (!correct) return false;
    const trimmedCorrect = correct.trim();
    const trimmedOption = option.trim();

    if (trimmedOption === trimmedCorrect) return true;
    if (trimmedOption.startsWith(trimmedCorrect)) return true;

    // handle single-letter correct answers like 'A' / 'B'
    const letter = String.fromCharCode(65 + index); // 'A', 'B', ...
    if (trimmedCorrect.length === 1 && trimmedCorrect.toUpperCase() === letter) return true;

    // handle cases where correct is like 'A.' or 'A)'
    if (/^[A-Za-z][\.|\)]?$/.test(trimmedCorrect) && trimmedOption.toUpperCase().startsWith(trimmedCorrect.toUpperCase())) return true;

    return false;
  };

  const handleSaveAnswerEdit = async (questionId: string) => {
    setSavingAnswer(questionId);
    try {
      const newAnswer: string | undefined = answerDraft[questionId] ?? undefined;
      const updated = await questionsService.updateQuestion(questionId, { correct_answer: newAnswer });
      setQuestions((prev) => prev.map((q) => (q.id === questionId ? { ...q, correct_answer: updated.correct_answer } : q)));
      setAnswerEditMode((prev) => ({ ...prev, [questionId]: false }));
      showSuccess('Answer updated');
    } catch (err) {
      showError(err, 'Failed to save answer');
    } finally {
      setSavingAnswer(null);
    }
  };

  const renderStatsCard = () => {
    if (!stats) return null;

    const approvalRate = stats.total_vetted > 0
      ? Math.round((stats.approved / stats.total_vetted) * 100)
      : 0;

    return (
      <View style={[styles.statsContainer, { backgroundColor: colors.card }]}>
        <View style={styles.statsRow}>
          <View style={styles.statItem}>
            <Text style={[styles.statValue, { color: colors.warning }]}>{stats.pending}</Text>
            <Text style={[styles.statLabel, { color: colors.textSecondary }]}>Pending</Text>
          </View>
          <View style={styles.statItem}>
            <Text style={[styles.statValue, { color: colors.success }]}>{stats.approved}</Text>
            <Text style={[styles.statLabel, { color: colors.textSecondary }]}>Approved</Text>
          </View>
          <View style={styles.statItem}>
            <Text style={[styles.statValue, { color: colors.error }]}>{stats.rejected}</Text>
            <Text style={[styles.statLabel, { color: colors.textSecondary }]}>Rejected</Text>
          </View>
          <View style={styles.statItem}>
            <Text style={[styles.statValue, { color: colors.primary }]}>{approvalRate}%</Text>
            <Text style={[styles.statLabel, { color: colors.textSecondary }]}>Approval</Text>
          </View>
        </View>
      </View>
    );
  };

  const renderQuestionCard = (question: PendingQuestion) => {
    const isExpanded = expandedQuestion === question.id;
    const mapping = coMappings[question.id] || {};

    // Debug logging
    console.log('Rendering question:', question.id);
    console.log('Question has source_info?', !!(question as any).source_info);
    if ((question as any).source_info) {
      console.log('Source info:', JSON.stringify((question as any).source_info, null, 2));
    }

    return (
      <View
        key={question.id}
        style={[
          styles.questionCard,
          { backgroundColor: colors.card },
          replacedQuestionId === question.id && {
            borderWidth: 2,
            borderColor: colors.primary,
            boxShadow: `0px 2px 8px ${colors.primary}4D`,
          },
        ]}
      >
        {/* centered regenerating overlay (blurs card and blocks interaction) */}
        {regenerating[question.id] && (
          <BlurView intensity={80} tint={isDark ? 'dark' : 'light'} style={styles.regenerationOverlay}>
            <ActivityIndicator size="large" color={colors.primary} />
            <Text style={[styles.regeneratingText, { color: colors.primary, marginTop: Spacing.sm, fontSize: FontSizes.lg }]}>Regenerating…</Text>
          </BlurView>
        )}
        {/* Question Header */}
        <TouchableOpacity
          style={styles.questionHeader}
          onPress={() => setExpandedQuestion(isExpanded ? null : question.id)}
        >
          <View style={[styles.typeBadge, { backgroundColor: colors.primary + '20' }]}>
            <Text style={[styles.typeBadgeText, { color: colors.primary }]}>
              {question.question_type.toUpperCase()}
            </Text>
          </View>
          {replacedQuestionId === question.id && (
            <View style={[styles.typeBadge, { backgroundColor: '#34C75920', marginLeft: Spacing.xs }]}>
              <Text style={[styles.typeBadgeText, { color: '#34C759' }]}>NEW</Text>
            </View>
          )}
          <View style={styles.questionMeta}>
            <Text style={[styles.difficultyText, { color: colors.textSecondary }]}>
              {question.difficulty_level || 'N/A'} • {question.marks || 0} marks
            </Text>
          </View>
          <IconSymbol
            name={isExpanded ? 'chevron.up' : 'chevron.down'}
            size={16}
            color={colors.textTertiary}
          />
        </TouchableOpacity>

        {/* Question Text */}
        <Text style={[styles.questionText, { color: colors.text }]}>
          {question.question_text}
        </Text>

        {/* Show expected answer preview for short/long questions */}
        {question.question_type !== 'mcq' && question.correct_answer ? (
          <View style={[styles.answerPreview, { backgroundColor: colors.card }]}>
            <Text style={[styles.answerPreviewLabel, { color: colors.textSecondary }]}>Expected answer</Text>
            <Text style={[styles.answerPreviewText, { color: colors.text }]}>{question.correct_answer}</Text>
          </View>
        ) : null}

        {/* Explanation (always visible in card) */}
        {question.explanation ? (
          <View style={[styles.answerPreview, { backgroundColor: colors.primary + '10', marginTop: 6 }]}>
            <Text style={[styles.answerPreviewLabel, { color: colors.primary }]}>Explanation</Text>
            <Text style={[styles.answerPreviewText, { color: colors.text }]}>{question.explanation}</Text>
          </View>
        ) : null}

        {/* MCQ Options */}
        {question.question_type === 'mcq' && question.options && (
          <View style={styles.optionsContainer}>
            {(question.options as string[]).map((option: string, index: number) => {
              const currentCorrect = answerDraft[question.id] ?? question.correct_answer;
              const isCorrect = optionMatchesCorrect(option, currentCorrect, index);

              return (
                <TouchableOpacity
                  key={index}
                  activeOpacity={isExpanded ? 0.7 : 1}
                  onPress={async () => {
                    if (!isExpanded) return; // only allow changing when expanded
                    const newCorrect = option;
                    // update draft and local question so UI shows change immediately
                    setAnswerDraft(prev => ({ ...prev, [question.id]: newCorrect }));
                    setQuestions(prev => prev.map((q) => (q.id === question.id ? { ...q, correct_answer: newCorrect } : q)));

                    // persist immediately and show feedback
                    try {
                      setSavingAnswer(question.id);
                      await questionsService.updateQuestion(question.id, { correct_answer: newCorrect });
                      showSuccess('Correct answer updated');
                    } catch (err) {
                      showError(err, 'Failed to update correct answer');
                    } finally {
                      setSavingAnswer(null);
                    }
                  }}
                >
                  <View
                    style={[
                      styles.optionRow,
                      isCorrect && { backgroundColor: colors.success + '15' },
                      isExpanded && { borderWidth: 1, borderColor: colors.border },
                    ]}
                  >
                    <View style={[
                      styles.optionLetter,
                      { backgroundColor: isCorrect ? colors.success : colors.border },
                    ]}>
                      <Text style={[
                        styles.optionLetterText,
                        { color: isCorrect ? '#FFFFFF' : colors.textSecondary },
                      ]}>
                        {String.fromCharCode(65 + index)}
                      </Text>
                    </View>
                    <Text style={[styles.optionText, { color: isCorrect ? colors.success : colors.text }]}>{option}</Text>
                    {isCorrect && (
                      <IconSymbol name="checkmark.circle.fill" size={18} color={colors.success} />
                    )}
                  </View>
                </TouchableOpacity>
              );
            })}
            {isExpanded && (
              <Text style={[styles.optionHint, { color: colors.textSecondary }]}>Tap an option to mark it as correct (changes saved with &apos;Save All Changes&apos;)</Text>
            )}
          </View>
        )}

        {/* Expanded Content - Edit Section */}
        {isExpanded && (
          <View style={styles.expandedContent}>
            {/* Marks & Difficulty Section */}
            <LinearGradient
              colors={['#4A90D9', '#357ABD'] as const}
              style={styles.coHeader}
            >
              <IconSymbol name="slider.horizontal.3" size={16} color="#FFFFFF" />
              <Text style={styles.coHeaderText}>Marks & Difficulty</Text>
            </LinearGradient>

            <View style={styles.editRow}>
              <Text style={[styles.editLabel, { color: colors.text }]}>Marks</Text>
              <View style={styles.marksInputWrapper}>
                <TouchableOpacity
                  style={[styles.marksButton, { backgroundColor: colors.border }]}
                  onPress={() => {
                    mediumImpact();
                    setEditMarks(prev => ({ ...prev, [question.id]: Math.max(1, (prev[question.id] || 1) - 1) }));
                  }}
                >
                  <IconSymbol name="minus" size={14} color={colors.text} />
                </TouchableOpacity>
                <TextInput
                  style={[styles.marksInput, { backgroundColor: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.04)', color: colors.text, borderColor: colors.border }]}
                  value={(editMarks[question.id] || 1).toString()}
                  onChangeText={(v) => setEditMarks(prev => ({ ...prev, [question.id]: parseInt(v) || 1 }))}
                  keyboardType="numeric"
                />
                <TouchableOpacity
                  style={[styles.marksButton, { backgroundColor: colors.border }]}
                  onPress={() => {
                    mediumImpact();
                    setEditMarks(prev => ({ ...prev, [question.id]: (prev[question.id] || 1) + 1 }));
                  }}
                >
                  <IconSymbol name="plus" size={14} color={colors.text} />
                </TouchableOpacity>
              </View>
            </View>

            <View style={[styles.editRow, { marginTop: Spacing.md }]}>
              <Text style={[styles.editLabel, { color: colors.text }]}>Difficulty</Text>
              <View style={styles.difficultyButtons}>
                {[
                  { value: 'easy', label: 'Easy', color: '#34C759' },
                  { value: 'medium', label: 'Medium', color: '#FF9500' },
                  { value: 'hard', label: 'Hard', color: '#FF3B30' },
                ].map(({ value, label, color }) => (
                  <TouchableOpacity
                    key={value}
                    style={[
                      styles.difficultyButton,
                      { borderColor: color },
                      editDifficulty[question.id] === value && { backgroundColor: color },
                    ]}
                    onPress={() => {
                      selectionImpact();
                      setEditDifficulty(prev => ({ ...prev, [question.id]: value }));
                    }}
                  >
                    <Text style={[
                      styles.difficultyButtonText,
                      { color: editDifficulty[question.id] === value ? '#FFFFFF' : color },
                    ]}>
                      {label}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>

            {/* Subject/Topic Linking */}
            <LinearGradient
              colors={['#34C759', '#30B350'] as const}
              style={[styles.coHeader, { marginTop: Spacing.lg }]}
            >
              <IconSymbol name="link" size={16} color="#FFFFFF" />
              <Text style={styles.coHeaderText}>Subject & Chapter</Text>
            </LinearGradient>

            <View style={styles.editRow}>
              <Text style={[styles.editLabel, { color: colors.text }]}>Subject</Text>
              <TouchableOpacity
                style={[styles.pickerButton, { backgroundColor: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.04)', borderColor: colors.border }]}
                onPress={() => {
                  loadSubjects();
                  setShowSubjectPicker(question.id);
                }}
              >
                <Text style={[styles.pickerText, { color: editSubjectId[question.id] ? colors.text : colors.textTertiary }]} numberOfLines={1}>
                  {getSubjectName(editSubjectId[question.id]) || 'Select subject'}
                </Text>
                <IconSymbol name="chevron.down" size={14} color={colors.textSecondary} />
              </TouchableOpacity>
            </View>

            {editSubjectId[question.id] && (
              <View style={[styles.editRow, { marginTop: Spacing.sm }]}>
                <Text style={[styles.editLabel, { color: colors.text }]}>Chapter</Text>
                <TouchableOpacity
                  style={[styles.pickerButton, { backgroundColor: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.04)', borderColor: colors.border }]}
                  onPress={() => {
                    loadTopicsForSubject(editSubjectId[question.id]!);
                    setShowTopicPicker(question.id);
                  }}
                >
                  <Text style={[styles.pickerText, { color: editTopicId[question.id] ? colors.text : colors.textTertiary }]} numberOfLines={1}>
                    {getTopicName(editSubjectId[question.id], editTopicId[question.id]) || 'Select chapter (optional)'}
                  </Text>
                  <IconSymbol name="chevron.down" size={14} color={colors.textSecondary} />
                </TouchableOpacity>
              </View>
            )}

            {/* CO Mapping Section */}
            <LinearGradient
              colors={['#5856D6', '#4A4ADE'] as const}
              style={[styles.coHeader, { marginTop: Spacing.lg }]}
            >
              <IconSymbol name="list.number" size={16} color="#FFFFFF" />
              <Text style={styles.coHeaderText}>Course Outcome Mapping</Text>
            </LinearGradient>

            <View style={styles.coMappingGrid}>
              {COURSE_OUTCOMES.map((co) => (
                <View key={co} style={styles.coRow}>
                  <View style={styles.coLabelColumn}>
                    <Text style={[styles.coLabel, { color: colors.text }]}>{co}</Text>
                    <Text style={[styles.coDesc, { color: colors.textSecondary }]}>{CO_DESCRIPTIONS[co]}</Text>
                  </View>
                  <View style={styles.levelButtons}>
                    {CO_LEVELS.map(({ level, label, color }) => (
                      <TouchableOpacity
                        key={level}
                        style={[
                          styles.levelButton,
                          { borderColor: color },
                          mapping[co] === level && { backgroundColor: color },
                        ]}
                        onPress={() => updateCoMapping(question.id, co, level)}
                      >
                        <Text style={[
                          styles.levelButtonText,
                          { color: mapping[co] === level ? '#FFFFFF' : color },
                        ]}>
                          {level}
                        </Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                </View>
              ))}
            </View>

            {/* Expected answer editor (short / long / MCQ manual override) */}
            <LinearGradient
              colors={['#34C759', '#30B350'] as const}
              style={[styles.coHeader, { marginTop: Spacing.lg }]}
            >
              <IconSymbol name="doc.text.fill" size={16} color="#FFFFFF" />
              <Text style={styles.coHeaderText}>Expected Answer</Text>
            </LinearGradient>

            <View style={{ marginBottom: Spacing.md }}>
              {!answerEditMode[question.id] ? (
                <>
                  <View style={[styles.answerContainer, { backgroundColor: isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.02)', borderColor: colors.border }]}>
                    <Text style={[styles.answerLabel, { color: colors.textSecondary }]}>Answer</Text>
                    <Text style={[styles.answerText, { color: colors.text }]}>{answerDraft[question.id] ?? question.correct_answer ?? '—'}</Text>
                    <TouchableOpacity onPress={() => setAnswerEditMode(prev => ({ ...prev, [question.id]: true }))} style={{ marginLeft: Spacing.sm }}>
                      <Text style={{ color: colors.primary, fontWeight: '600' }}>Edit</Text>
                    </TouchableOpacity>
                  </View>
                  {question.question_type === 'mcq' && (
                    <Text style={[styles.optionHint, { color: colors.textSecondary }]}>Tap an option above to mark it as correct, or click Edit to type a manual answer.</Text>
                  )}
                </>
              ) : (
                <>
                  <TextInput
                    value={answerDraft[question.id] ?? ''}
                    onChangeText={(v) => setAnswerDraft(prev => ({ ...prev, [question.id]: v }))}
                    placeholder="Type expected/approved answer here"
                    multiline
                    style={[styles.answerInput, { color: colors.text, borderColor: colors.border, backgroundColor: isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.02)' }]}
                  />
                  <View style={{ flexDirection: 'row', gap: Spacing.sm, marginTop: Spacing.sm }}>
                    <TouchableOpacity
                      style={[styles.saveAnswerButton, { backgroundColor: colors.primary }]}
                      onPress={() => handleSaveAnswerEdit(question.id)}
                      disabled={savingAnswer === question.id}
                    >
                      {savingAnswer === question.id ? (
                        <ActivityIndicator color="#FFFFFF" />
                      ) : (
                        <Text style={{ color: '#FFFFFF', fontWeight: '600' }}>Save Answer</Text>
                      )}
                    </TouchableOpacity>
                    <TouchableOpacity
                      style={[styles.saveAnswerButton, { backgroundColor: colors.border }]}
                      onPress={() => {
                        setAnswerEditMode(prev => ({ ...prev, [question.id]: false }));
                        setAnswerDraft(prev => ({ ...prev, [question.id]: question.correct_answer || null }));
                      }}
                    >
                      <Text style={{ color: colors.text, fontWeight: '600' }}>Cancel</Text>
                    </TouchableOpacity>
                  </View>
                </>
              )}
            </View>

            {/* Explanation (read-only in expanded view) */}
            {question.explanation && (
              <>
                <LinearGradient
                  colors={['#4A90D9', '#357ABD'] as const}
                  style={[styles.coHeader, { marginTop: Spacing.lg }]}
                >
                  <IconSymbol name="text.bubble.fill" size={16} color="#FFFFFF" />
                  <Text style={styles.coHeaderText}>Explanation</Text>
                </LinearGradient>
                <View style={[styles.answerContainer, { backgroundColor: isDark ? 'rgba(74,144,217,0.08)' : 'rgba(74,144,217,0.06)', borderColor: colors.primary + '30', marginBottom: Spacing.md }]}>
                  <Text style={[styles.answerText, { color: colors.text }]}>{question.explanation}</Text>
                </View>
              </>
            )}

            <TouchableOpacity
              style={[styles.saveAllButton, { backgroundColor: colors.primary }]}
              onPress={() => handleSaveQuestionEdits(question.id)}
              disabled={savingQuestion === question.id}
            >
              {savingQuestion === question.id ? (
                <ActivityIndicator size="small" color="#FFFFFF" />
              ) : (
                <>
                  <IconSymbol name="checkmark.circle.fill" size={18} color="#FFFFFF" />
                  <Text style={styles.saveAllButtonText}>Save All Changes</Text>
                </>
              )}
            </TouchableOpacity>
          </View>
        )}

        {/* Action Buttons */}
        <View style={styles.actionButtons}>
          <TouchableOpacity
            style={[styles.actionButton, styles.rejectButton, regenerating[question.id] && { opacity: 0.6 }]}
            onPress={() => {
              mediumImpact();
              openRejectModal(question.id);
            }}
            disabled={!!regenerating[question.id]}
          >
            <IconSymbol name="xmark" size={16} color="#FF3B30" />
            <Text style={[styles.actionButtonText, { color: '#FF3B30' }]}>Reject</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.actionButton, { backgroundColor: colors.border }]}
            onPress={() => {
              mediumImpact();
              setExpandedQuestion(isExpanded ? null : question.id);
            }}
          >
            <IconSymbol name="pencil" size={16} color={colors.text} />
            <Text style={[styles.actionButtonText, { color: colors.text }]}>Edit</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.actionButton, styles.approveButton]}
            onPress={() => {
              mediumImpact();
              handleApprove(question.id);
            }}
          >
            <IconSymbol name="checkmark" size={16} color="#FFFFFF" />
            <Text style={[styles.actionButtonText, { color: '#FFFFFF' }]}>Approve</Text>
          </TouchableOpacity>
        </View>

        {/* Source References - shown below action buttons */}
        {(question as any).source_info && (
          <View style={{ marginTop: Spacing.md }}>
            <QuestionSources sourceInfo={(question as any).source_info} />
          </View>
        )}

        {/* Debug: Always show a test source to verify component works */}
        {!((question as any).source_info) && __DEV__ && (
          <View style={{ marginTop: Spacing.md, padding: Spacing.sm, backgroundColor: '#FFF3CD', borderRadius: BorderRadius.md }}>
            <Text style={{ fontSize: FontSizes.xs, color: '#856404' }}>
              ⚠️ No source_info found. This question was likely generated before source tracking was enabled. 
              Upload a new document and generate questions to see RAG sources.
            </Text>
          </View>
        )}
      </View>
    );
  };

  if (isLoading) {
    return (
      <View style={[styles.loadingContainer, { backgroundColor: colors.background }]}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      <FlatList<PendingQuestion>
        data={questions}
        keyExtractor={(item: PendingQuestion) => item.id}
        renderItem={({ item }: { item: PendingQuestion }) => renderQuestionCard(item)}
        contentContainerStyle={styles.scrollContent}
        ListHeaderComponent={() => (
          <>
            {/* Header */}
            {/* <LinearGradient
              colors={['#FF9500', '#FF7F00'] as const}
              style={styles.headerCard}
            >
              <IconSymbol name="checkmark.shield.fill" size={28} color="#FFFFFF" />
              <View style={styles.headerContent}>
                <Text style={styles.headerTitle}>Question Vetting</Text>
                <Text style={styles.headerDescription}>
                  Review, approve, and map course outcomes for generated questions
                </Text>
              </View>
            </LinearGradient> */}

            {/* Stats */}
            {renderStatsCard()}

            <View style={styles.section}>
              <Text style={[styles.sectionTitle, { color: colors.textSecondary }]}>PENDING REVIEW ({stats?.pending ?? questions.length})</Text>
            </View>
          </>
        )}
        ListEmptyComponent={() => (
          <View style={[styles.section, { paddingTop: 20 }]}>
            <View style={[styles.emptyCard, { backgroundColor: colors.card }]}>
              <IconSymbol name="checkmark.circle" size={48} color={colors.success} />
              <Text style={[styles.emptyTitle, { color: colors.text }]}>All Caught Up!</Text>
              <Text style={[styles.emptyDescription, { color: colors.textSecondary }]}>No questions pending review</Text>
            </View>
          </View>
        )}
        ListFooterComponent={() => (
          isLoadingMore ? (
            <View style={styles.loadingMore}>
              <ActivityIndicator size="small" color={colors.primary} />
            </View>
          ) : null
        )}
        refreshing={isRefreshing}
        onRefresh={handleRefresh}
        onEndReached={handleLoadMore}
        onEndReachedThreshold={0.6}
      />

      {/* Subject Picker Modal */}
      <Modal
        visible={showSubjectPicker !== null}
        transparent
        animationType="slide"
        onRequestClose={() => setShowSubjectPicker(null)}
      >
        <View style={styles.modalOverlay}>
          <View style={[styles.modalContent, { backgroundColor: colors.card }]}>
            <View style={styles.modalHeader}>
              <Text style={[styles.modalTitle, { color: colors.text }]}>Select Subject</Text>
              <TouchableOpacity onPress={() => setShowSubjectPicker(null)}>
                <IconSymbol name="xmark.circle.fill" size={28} color={colors.textSecondary} />
              </TouchableOpacity>
            </View>
            <ScrollView style={styles.modalList}>
              {loadingSubjects ? (
                <View style={styles.emptyList}>
                  <ActivityIndicator size="small" color={colors.primary} />
                </View>
              ) : subjects.length === 0 ? (
                <View style={styles.emptyList}>
                  <Text style={[styles.emptyListText, { color: colors.textSecondary }]}>
                    No subjects available.
                  </Text>
                </View>
              ) : (
                <>
                  <TouchableOpacity
                    style={[styles.modalItem, { borderBottomColor: colors.border }]}
                    onPress={() => {
                      if (showSubjectPicker) {
                        setEditSubjectId(prev => ({ ...prev, [showSubjectPicker]: null }));
                        setEditTopicId(prev => ({ ...prev, [showSubjectPicker]: null }));
                      }
                      setShowSubjectPicker(null);
                    }}
                  >
                    <View style={styles.modalItemContent}>
                      <Text style={[styles.modalItemTitle, { color: colors.textSecondary }]}>None (Clear selection)</Text>
                    </View>
                  </TouchableOpacity>
                  {subjects.map((subject) => (
                    <TouchableOpacity
                      key={subject.id}
                      style={[
                        styles.modalItem,
                        { borderBottomColor: colors.border },
                        showSubjectPicker && editSubjectId[showSubjectPicker] === subject.id && { backgroundColor: colors.primary + '15' }
                      ]}
                      onPress={() => {
                        if (showSubjectPicker) {
                          setEditSubjectId(prev => ({ ...prev, [showSubjectPicker]: subject.id }));
                          setEditTopicId(prev => ({ ...prev, [showSubjectPicker]: null }));
                          loadTopicsForSubject(subject.id);
                        }
                        setShowSubjectPicker(null);
                      }}
                    >
                      <View style={styles.modalItemContent}>
                        <Text style={[styles.modalItemTitle, { color: colors.text }]}>{subject.name}</Text>
                        <Text style={[styles.modalItemSubtitle, { color: colors.textSecondary }]}>
                          {subject.code} • {subject.total_topics} topics
                        </Text>
                      </View>
                      {showSubjectPicker && editSubjectId[showSubjectPicker] === subject.id && (
                        <IconSymbol name="checkmark.circle.fill" size={22} color={colors.primary} />
                      )}
                    </TouchableOpacity>
                  ))}
                </>
              )}
            </ScrollView>
          </View>
        </View>
      </Modal>

      {/* Topic Picker Modal */}
      <Modal
        visible={showTopicPicker !== null}
        transparent
        animationType="slide"
        onRequestClose={() => setShowTopicPicker(null)}
      >
        <View style={styles.modalOverlay}>
          <View style={[styles.modalContent, { backgroundColor: colors.card }]}>
            <View style={styles.modalHeader}>
              <Text style={[styles.modalTitle, { color: colors.text }]}>Select Chapter</Text>
              <TouchableOpacity onPress={() => setShowTopicPicker(null)}>
                <IconSymbol name="xmark.circle.fill" size={28} color={colors.textSecondary} />
              </TouchableOpacity>
            </View>
            <ScrollView style={styles.modalList}>
              {showTopicPicker && editSubjectId[showTopicPicker] ? (
                <>
                  <TouchableOpacity
                    style={[styles.modalItem, { borderBottomColor: colors.border }]}
                    onPress={() => {
                      if (showTopicPicker) {
                        setEditTopicId(prev => ({ ...prev, [showTopicPicker]: null }));
                      }
                      setShowTopicPicker(null);
                    }}
                  >
                    <View style={styles.modalItemContent}>
                      <Text style={[styles.modalItemTitle, { color: colors.textSecondary }]}>None (Link to subject only)</Text>
                    </View>
                  </TouchableOpacity>
                  {(topics[editSubjectId[showTopicPicker]!] || []).map((topic) => (
                    <TouchableOpacity
                      key={topic.id}
                      style={[
                        styles.modalItem,
                        { borderBottomColor: colors.border },
                        showTopicPicker && editTopicId[showTopicPicker] === topic.id && { backgroundColor: colors.primary + '15' }
                      ]}
                      onPress={() => {
                        if (showTopicPicker) {
                          setEditTopicId(prev => ({ ...prev, [showTopicPicker]: topic.id }));
                        }
                        setShowTopicPicker(null);
                      }}
                    >
                      <View style={styles.modalItemContent}>
                        <Text style={[styles.modalItemTitle, { color: colors.text }]}>{topic.name}</Text>
                        {topic.description && (
                          <Text style={[styles.modalItemSubtitle, { color: colors.textSecondary }]} numberOfLines={1}>
                            {topic.description}
                          </Text>
                        )}
                      </View>
                      {showTopicPicker && editTopicId[showTopicPicker] === topic.id && (
                        <IconSymbol name="checkmark.circle.fill" size={22} color={colors.primary} />
                      )}
                    </TouchableOpacity>
                  ))}
                </>
              ) : (
                <View style={styles.emptyList}>
                  <Text style={[styles.emptyListText, { color: colors.textSecondary }]}>
                    No topics available.
                  </Text>
                </View>
              )}
            </ScrollView>
          </View>
        </View>
      </Modal>

      {/* Rejection Reason Modal */}
      <Modal
        visible={!!showRejectModal}
        transparent
        animationType="fade"
        onRequestClose={() => setShowRejectModal(null)}
      >
        <View style={styles.modalOverlay}>
          <View style={[styles.modalContent, { backgroundColor: colors.card }]}>
            <View style={styles.rejectModalHeader}>
              <Text style={[styles.modalTitle, { color: colors.text }]}>Reject Question</Text>
              <TouchableOpacity onPress={() => setShowRejectModal(null)}>
                <IconSymbol name="xmark.circle.fill" size={24} color={colors.textSecondary} />
              </TouchableOpacity>
            </View>
            
            <Text style={[styles.rejectModalSubtitle, { color: colors.textSecondary }]}>
              Why are you rejecting this question? (Optional)
            </Text>
            
            <ScrollView style={styles.rejectReasonsList}>
              {REJECTION_REASONS.map((reason) => {
                const isSelected = selectedRejectReasons.includes(reason.id);
                return (
                  <TouchableOpacity
                    key={reason.id}
                    style={[
                      styles.rejectReasonItem,
                      { borderColor: isSelected ? colors.primary : colors.border },
                      isSelected && { backgroundColor: `${colors.primary}15` }
                    ]}
                    onPress={() => toggleRejectReason(reason.id)}
                  >
                    <View style={[
                      styles.rejectReasonCheckbox,
                      { borderColor: isSelected ? colors.primary : colors.border },
                      isSelected && { backgroundColor: colors.primary }
                    ]}>
                      {isSelected && (
                        <IconSymbol name="checkmark" size={12} color="#fff" />
                      )}
                    </View>
                    <View style={styles.rejectReasonText}>
                      <Text style={[styles.rejectReasonLabel, { color: colors.text }]}>
                        {reason.label}
                      </Text>
                      <Text style={[styles.rejectReasonDesc, { color: colors.textSecondary }]}>
                        {reason.description}
                      </Text>
                    </View>
                  </TouchableOpacity>
                );
              })}
            </ScrollView>
            
            <View style={styles.customFeedbackSection}>
              <View style={styles.feedbackHeaderRow}>
                <Text style={[styles.customFeedbackLabel, { color: colors.text }]}>
                  Additional feedback (optional)
                </Text>
                {isSpeechRecognitionAvailable && (
                  <View style={[styles.inputModeTabs, { backgroundColor: colors.background }]}>
                    <TouchableOpacity
                      style={[
                        styles.inputModeTab,
                        feedbackInputMode === 'text' && { backgroundColor: colors.primary }
                      ]}
                      onPress={() => setFeedbackInputMode('text')}
                    >
                      <IconSymbol 
                        name="keyboard" 
                        size={16} 
                        color={feedbackInputMode === 'text' ? '#fff' : colors.textSecondary} 
                      />
                    </TouchableOpacity>
                    <TouchableOpacity
                      style={[
                        styles.inputModeTab,
                        feedbackInputMode === 'voice' && { backgroundColor: colors.primary }
                      ]}
                      onPress={() => setFeedbackInputMode('voice')}
                    >
                      <IconSymbol 
                        name="mic.fill" 
                        size={16} 
                        color={feedbackInputMode === 'voice' ? '#fff' : colors.textSecondary} 
                      />
                    </TouchableOpacity>
                  </View>
                )}
              </View>
              
              {feedbackInputMode === 'text' || !isSpeechRecognitionAvailable ? (
                <TextInput
                  style={[
                    styles.customFeedbackInput,
                    { 
                      backgroundColor: colors.background, 
                      color: colors.text,
                      borderColor: colors.border
                    }
                  ]}
                  value={customFeedback}
                  onChangeText={setCustomFeedback}
                  placeholder="Describe what's wrong or how you'd like this question improved..."
                  placeholderTextColor={colors.textSecondary}
                  multiline
                  numberOfLines={3}
                  textAlignVertical="top"
                />
              ) : (
                <VoiceInput
                  value={customFeedback}
                  onChangeText={setCustomFeedback}
                  placeholder="Tap mic to speak your feedback..."
                  colors={{
                    text: colors.text,
                    textSecondary: colors.textSecondary,
                    primary: colors.primary,
                    background: colors.background,
                    border: colors.border,
                    error: colors.error,
                  }}
                />
              )}
            </View>
            
            <View style={styles.rejectModalButtons}>
              <TouchableOpacity
                style={[styles.rejectModalButton, { backgroundColor: colors.border }]}
                onPress={() => setShowRejectModal(null)}
              >
                <Text style={[styles.rejectModalButtonText, { color: colors.text }]}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.rejectModalButton, styles.rejectConfirmButton]}
                onPress={confirmReject}
              >
                <Text style={[styles.rejectModalButtonText, { color: '#fff' }]}>
                  Reject & Regenerate
                </Text>
              </TouchableOpacity>
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
  scrollContent: {
    paddingTop: Spacing.headerInset,
    paddingHorizontal: Spacing.lg,
    paddingBottom: 100,
  },
  headerCard: {
    flexDirection: 'row',
    padding: Spacing.lg,
    borderRadius: BorderRadius.md,
    marginBottom: Spacing.lg,
  },
  headerContent: {
    flex: 1,
    marginLeft: Spacing.md,
  },
  headerTitle: {
    fontSize: FontSizes.lg,
    fontWeight: '700',
    color: '#FFFFFF',
    marginBottom: Spacing.xs,
  },
  headerDescription: {
    fontSize: FontSizes.sm,
    color: 'rgba(255, 255, 255, 0.9)',
  },
  statsContainer: {
    borderRadius: BorderRadius.md,
    padding: Spacing.lg,
    marginBottom: Spacing.lg,
  },
  statsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  statItem: {
    alignItems: 'center',
  },
  statValue: {
    fontSize: FontSizes.xl,
    fontWeight: '700',
  },
  statLabel: {
    fontSize: FontSizes.xs,
    marginTop: Spacing.xs,
  },
  section: {
    marginBottom: Spacing.lg,
  },
  sectionTitle: {
    fontSize: FontSizes.xs,
    fontWeight: '600',
    marginBottom: Spacing.md,
  },
  questionCard: {
    borderRadius: BorderRadius.md,
    padding: Spacing.lg,
    marginBottom: Spacing.md,
  },
  questionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: Spacing.md,
  },
  typeBadge: {
    paddingHorizontal: Spacing.sm,
    paddingVertical: Spacing.xs,
    borderRadius: BorderRadius.sm,
  },
  typeBadgeText: {
    fontSize: FontSizes.xs,
    fontWeight: '600',
  },
  questionMeta: {
    flex: 1,
    marginLeft: Spacing.sm,
  },
  difficultyText: {
    fontSize: FontSizes.sm,
  },
  questionText: {
    fontSize: FontSizes.md,
    lineHeight: 24,
    marginBottom: Spacing.md,
  },
  optionsContainer: {
    marginBottom: Spacing.md,
  },
  optionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: Spacing.sm,
    paddingHorizontal: Spacing.sm,
    borderRadius: BorderRadius.sm,
    marginBottom: Spacing.xs,
  },
  optionLetter: {
    width: 28,
    height: 28,
    borderRadius: 14,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: Spacing.sm,
  },
  optionLetterText: {
    fontSize: FontSizes.sm,
    fontWeight: '600',
  },
  optionText: {
    flex: 1,
    fontSize: FontSizes.sm,
  },
  optionHint: {
    fontSize: FontSizes.xs,
    marginTop: Spacing.xs,
  },
  answerPreview: {
    padding: Spacing.sm,
    borderRadius: BorderRadius.sm,
    marginBottom: Spacing.sm,
  },
  answerPreviewLabel: {
    fontSize: FontSizes.xs,
    fontWeight: '600',
    marginBottom: Spacing.xs,
  },
  answerPreviewText: {
    fontSize: FontSizes.sm,
  },
  answerContainer: {
    marginTop: Spacing.md,
    padding: Spacing.sm,
    borderRadius: BorderRadius.sm,
    borderWidth: 1,
  },
  answerLabel: {
    fontSize: FontSizes.xs,
    fontWeight: '600',
    marginBottom: 4,
  },
  answerText: {
    fontSize: FontSizes.sm,
    lineHeight: 18,
  },
  answerInput: {
    minHeight: 80,
    padding: Spacing.sm,
    borderRadius: BorderRadius.sm,
    borderWidth: 1,
    fontSize: FontSizes.sm,
  },
  saveAnswerButton: {
    padding: Spacing.sm,
    borderRadius: BorderRadius.sm,
    alignItems: 'center',
  },
  expandedContent: {
    marginTop: Spacing.md,
    borderTopWidth: 1,
    borderTopColor: '#E5E5EA',
    paddingTop: Spacing.md,
  },
  coHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: Spacing.sm,
    borderRadius: BorderRadius.sm,
    marginBottom: Spacing.md,
    gap: Spacing.sm,
  },
  coHeaderText: {
    fontSize: FontSizes.sm,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  coMappingGrid: {
    marginBottom: Spacing.md,
  },
  coRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: Spacing.sm,
  },
  coLabelColumn: {
    width: 96,
  },
  coLabel: {
    fontSize: FontSizes.md,
    fontWeight: '600',
  },
  coDesc: {
    fontSize: FontSizes.xs,
    marginTop: Spacing.xs,
  },
  levelButtons: {
    flexDirection: 'row',
    flex: 1,
    gap: Spacing.sm,
  },
  levelButton: {
    flex: 1,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.sm,
    borderWidth: 2,
    alignItems: 'center',
  },
  levelButtonText: {
    fontSize: FontSizes.sm,
    fontWeight: '600',
  },
  saveCoButton: {
    padding: Spacing.sm,
    borderRadius: BorderRadius.sm,
    alignItems: 'center',
  },
  saveCoButtonText: {
    fontSize: FontSizes.sm,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  actionButtons: {
    flexDirection: 'row',
    gap: Spacing.sm,
    marginTop: Spacing.md,
    borderTopWidth: 1,
    borderTopColor: '#E5E5EA',
    paddingTop: Spacing.md,
  },
  regenerationOverlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    borderRadius: BorderRadius.md,
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 10,
    overflow: 'hidden',
  },
  regeneratingText: {
    fontSize: FontSizes.xs,
    fontWeight: '600',
  },
  actionButton: {
    flex: 1,
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.sm,
    gap: Spacing.xs,
  },
  actionButtonText: {
    fontSize: FontSizes.sm,
    fontWeight: '600',
  },
  rejectButton: {
    backgroundColor: '#FFE5E5',
  },
  approveButton: {
    backgroundColor: '#34C759',
  },
  emptyCard: {
    alignItems: 'center',
    padding: Spacing.xl,
    borderRadius: BorderRadius.md,
  },
  emptyTitle: {
    fontSize: FontSizes.lg,
    fontWeight: '600',
    marginTop: Spacing.md,
  },
  emptyDescription: {
    fontSize: FontSizes.sm,
    marginTop: Spacing.xs,
  },
  // Marks and difficulty editing styles
  editRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: Spacing.sm,
  },
  editLabel: {
    fontSize: FontSizes.sm,
    fontWeight: '500',
    flex: 0.4,
  },
  marksInputWrapper: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
    flex: 0.6,
    justifyContent: 'flex-end',
  },
  marksButton: {
    width: 32,
    height: 32,
    borderRadius: BorderRadius.sm,
    alignItems: 'center',
    justifyContent: 'center',
  },
  marksInput: {
    width: 50,
    height: 36,
    borderWidth: 1,
    borderRadius: BorderRadius.sm,
    textAlign: 'center',
    fontSize: FontSizes.md,
    fontWeight: '600',
  },
  difficultyButtons: {
    flexDirection: 'row',
    gap: Spacing.xs,
    flex: 0.6,
    justifyContent: 'flex-end',
  },
  difficultyButton: {
    paddingVertical: Spacing.xs,
    paddingHorizontal: Spacing.sm,
    borderRadius: BorderRadius.sm,
    borderWidth: 2,
  },
  difficultyButtonText: {
    fontSize: FontSizes.xs,
    fontWeight: '600',
  },
  pickerButton: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: Spacing.sm,
    borderRadius: BorderRadius.sm,
    borderWidth: 1,
    flex: 0.6,
    gap: Spacing.xs,
  },
  pickerText: {
    flex: 1,
    fontSize: FontSizes.sm,
  },
  saveAllButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    padding: Spacing.md,
    borderRadius: BorderRadius.sm,
    marginTop: Spacing.md,
    gap: Spacing.sm,
  },
  saveAllButtonText: {
    fontSize: FontSizes.sm,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  // Modal styles
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    borderTopLeftRadius: BorderRadius.xl,
    borderTopRightRadius: BorderRadius.xl,
    maxHeight: '70%',
    paddingBottom: 34,
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: Spacing.lg,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(0, 0, 0, 0.1)',
  },
  modalTitle: {
    fontSize: FontSizes.lg,
    fontWeight: '600',
  },
  modalList: {
    paddingHorizontal: Spacing.lg,
  },
  modalItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: Spacing.md,
    borderBottomWidth: 1,
  },
  modalItemContent: {
    flex: 1,
  },
  modalItemTitle: {
    fontSize: FontSizes.md,
    fontWeight: '500',
  },
  modalItemSubtitle: {
    fontSize: FontSizes.sm,
    marginTop: 2,
  },
  emptyList: {
    padding: Spacing.xl,
    alignItems: 'center',
  },
  emptyListText: {
    fontSize: FontSizes.sm,
    textAlign: 'center',
  },
  loadingMore: {
    paddingVertical: Spacing.md,
    alignItems: 'center',
  },
  // Rejection modal styles
  rejectModalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: Spacing.lg,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(0, 0, 0, 0.1)',
  },
  rejectModalSubtitle: {
    fontSize: FontSizes.sm,
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.md,
    paddingBottom: Spacing.sm,
  },
  rejectReasonsList: {
    paddingHorizontal: Spacing.lg,
    maxHeight: 300,
  },
  rejectReasonItem: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    padding: Spacing.md,
    borderWidth: 1,
    borderRadius: BorderRadius.md,
    marginBottom: Spacing.sm,
  },
  rejectReasonCheckbox: {
    width: 22,
    height: 22,
    borderRadius: BorderRadius.sm,
    borderWidth: 2,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: Spacing.sm,
    marginTop: 2,
  },
  rejectReasonText: {
    flex: 1,
  },
  rejectReasonLabel: {
    fontSize: FontSizes.md,
    fontWeight: '500',
  },
  rejectReasonDesc: {
    fontSize: FontSizes.sm,
    marginTop: 2,
  },
  customFeedbackSection: {
    paddingHorizontal: Spacing.lg,
    paddingBottom: Spacing.sm,
  },
  feedbackHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: Spacing.sm,
  },
  customFeedbackLabel: {
    fontSize: FontSizes.sm,
    fontWeight: '500',
  },
  inputModeTabs: {
    flexDirection: 'row',
    borderRadius: BorderRadius.sm,
    padding: 2,
    gap: 2,
  },
  inputModeTab: {
    width: 32,
    height: 28,
    borderRadius: BorderRadius.sm - 2,
    alignItems: 'center',
    justifyContent: 'center',
  },
  customFeedbackInput: {
    borderWidth: 1,
    borderRadius: BorderRadius.md,
    padding: Spacing.sm,
    fontSize: FontSizes.sm,
    minHeight: 80,
  },
  rejectModalButtons: {
    flexDirection: 'row',
    padding: Spacing.lg,
    paddingTop: Spacing.md,
    gap: Spacing.sm,
  },
  rejectModalButton: {
    flex: 1,
    paddingVertical: Spacing.md,
    borderRadius: BorderRadius.md,
    alignItems: 'center',
  },
  rejectConfirmButton: {
    backgroundColor: '#FF3B30',
  },
  rejectModalButtonText: {
    fontSize: FontSizes.md,
    fontWeight: '600',
  },
});
