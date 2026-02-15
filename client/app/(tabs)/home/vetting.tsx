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
  Platform,
  TextInput,
  Modal,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { GlassCard } from '@/components/ui/glass-card';
import { NativeButton } from '@/components/ui/native-button';
import { Colors, Spacing, BorderRadius, FontSizes } from '@/constants/theme';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { vettingService, PendingQuestion, VettingStats, CourseOutcomeMapping } from '@/services/vetting';
import { questionsService } from '@/services/questions';
import { subjectsService, Subject, Topic } from '@/services/subjects';
import { useToast } from '@/components/toast';

const CO_LEVELS = [
  { level: 1, label: 'Basic', color: '#34C759' },
  { level: 2, label: 'Intermediate', color: '#FF9500' },
  { level: 3, label: 'Advanced', color: '#FF3B30' },
];

const COURSE_OUTCOMES = ['CO1', 'CO2', 'CO3', 'CO4', 'CO5'];

export default function VettingScreen() {
  const colorScheme = useColorScheme();
  const colors = Colors[colorScheme ?? 'light'];
  const isDark = colorScheme === 'dark';
  const { showError, showSuccess } = useToast();
  
  const [questions, setQuestions] = useState<PendingQuestion[]>([]);
  const [stats, setStats] = useState<VettingStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [expandedQuestion, setExpandedQuestion] = useState<string | null>(null);
  const [coMappings, setCoMappings] = useState<Record<string, CourseOutcomeMapping>>({});
  
  // Edit state for marks and subject/topic
  const [editMarks, setEditMarks] = useState<Record<string, number>>({});
  const [editDifficulty, setEditDifficulty] = useState<Record<string, string>>({});
  const [editSubjectId, setEditSubjectId] = useState<Record<string, string | null>>({});
  const [editTopicId, setEditTopicId] = useState<Record<string, string | null>>({});
  
  // Subject/Topic picker state
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [topics, setTopics] = useState<Record<string, Topic[]>>({});
  const [loadingSubjects, setLoadingSubjects] = useState(false);
  const [showSubjectPicker, setShowSubjectPicker] = useState<string | null>(null);
  const [showTopicPicker, setShowTopicPicker] = useState<string | null>(null);
  const [savingQuestion, setSavingQuestion] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      const [questionsResponse, statsResponse] = await Promise.all([
        vettingService.getPendingQuestions(1, 20),
        vettingService.getVettingStats(),
      ]);
      setQuestions(questionsResponse.questions);
      setStats(statsResponse);
      
      // Initialize CO mappings and edit state
      const initialMappings: Record<string, CourseOutcomeMapping> = {};
      const initialMarks: Record<string, number> = {};
      const initialDifficulty: Record<string, string> = {};
      const initialSubjectId: Record<string, string | null> = {};
      const initialTopicId: Record<string, string | null> = {};
      
      questionsResponse.questions.forEach((q) => {
        initialMappings[q.id] = q.course_outcome_mapping || {};
        initialMarks[q.id] = q.marks || 1;
        initialDifficulty[q.id] = q.difficulty_level || 'medium';
        initialSubjectId[q.id] = q.subject_id || null;
        initialTopicId[q.id] = q.topic_id || null;
      });
      setCoMappings(initialMappings);
      setEditMarks(initialMarks);
      setEditDifficulty(initialDifficulty);
      setEditSubjectId(initialSubjectId);
      setEditTopicId(initialTopicId);
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  const loadSubjects = useCallback(async () => {
    if (subjects.length > 0) return;
    setLoadingSubjects(true);
    try {
      const response = await subjectsService.listSubjects(1, 100);
      setSubjects(response.subjects);
    } catch (error) {
      console.error('Failed to load subjects:', error);
    } finally {
      setLoadingSubjects(false);
    }
  }, [subjects.length]);

  const loadTopicsForSubject = useCallback(async (subjectId: string) => {
    if (topics[subjectId]) return;
    try {
      const response = await subjectsService.listTopics(subjectId, 1, 100);
      setTopics(prev => ({ ...prev, [subjectId]: response.topics }));
    } catch (error) {
      console.error('Failed to load topics:', error);
    }
  }, [topics]);

  useEffect(() => {
    loadData();
    loadSubjects();
  }, []);

  const handleRefresh = () => {
    setIsRefreshing(true);
    loadData();
  };

  const handleSaveQuestionEdits = async (questionId: string) => {
    setSavingQuestion(questionId);
    try {
      await questionsService.updateQuestion(questionId, {
        marks: editMarks[questionId],
        difficulty_level: editDifficulty[questionId],
        subject_id: editSubjectId[questionId] || undefined,
        topic_id: editTopicId[questionId] || undefined,
        course_outcome_mapping: coMappings[questionId],
      });
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
      loadData(); // Refresh stats
    } catch (error) {
      showError(error, 'Approval Failed');
    }
  };

  const handleReject = async (questionId: string) => {
    Alert.alert(
      'Reject Question',
      'Are you sure you want to reject this question?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Reject',
          style: 'destructive',
          onPress: async () => {
            try {
              await vettingService.vetQuestion(questionId, 'rejected', 'Rejected by reviewer');
              setQuestions((prev) => prev.filter((q) => q.id !== questionId));
              showSuccess('Question rejected');
              loadData();
            } catch (error) {
              showError(error, 'Rejection Failed');
            }
          },
        },
      ]
    );
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
    
    return (
      <View key={question.id} style={[styles.questionCard, { backgroundColor: colors.card }]}>
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

        {/* MCQ Options */}
        {question.question_type === 'mcq' && question.options && (
          <View style={styles.optionsContainer}>
            {(question.options as string[]).map((option: string, index: number) => {
              const isCorrect = question.correct_answer === option;
              return (
                <View
                  key={index}
                  style={[
                    styles.optionRow,
                    isCorrect && { backgroundColor: colors.success + '15' },
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
                  <Text style={[styles.optionText, { color: colors.text }]}>{option}</Text>
                  {isCorrect && (
                    <IconSymbol name="checkmark.circle.fill" size={18} color={colors.success} />
                  )}
                </View>
              );
            })}
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
                  onPress={() => setEditMarks(prev => ({ ...prev, [question.id]: Math.max(1, (prev[question.id] || 1) - 1) }))}
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
                  onPress={() => setEditMarks(prev => ({ ...prev, [question.id]: (prev[question.id] || 1) + 1 }))}
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
                    onPress={() => setEditDifficulty(prev => ({ ...prev, [question.id]: value }))}
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
                  <Text style={[styles.coLabel, { color: colors.text }]}>{co}</Text>
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
            style={[styles.actionButton, styles.rejectButton]}
            onPress={() => handleReject(question.id)}
          >
            <IconSymbol name="xmark" size={16} color="#FF3B30" />
            <Text style={[styles.actionButtonText, { color: '#FF3B30' }]}>Reject</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.actionButton, { backgroundColor: colors.border }]}
            onPress={() => setExpandedQuestion(isExpanded ? null : question.id)}
          >
            <IconSymbol name="pencil" size={16} color={colors.text} />
            <Text style={[styles.actionButtonText, { color: colors.text }]}>Edit</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.actionButton, styles.approveButton]}
            onPress={() => handleApprove(question.id)}
          >
            <IconSymbol name="checkmark" size={16} color="#FFFFFF" />
            <Text style={[styles.actionButtonText, { color: '#FFFFFF' }]}>Approve</Text>
          </TouchableOpacity>
        </View>
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
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        refreshControl={<RefreshControl refreshing={isRefreshing} onRefresh={handleRefresh} />}
      >
        {/* Header */}
        <LinearGradient
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
        </LinearGradient>

        {/* Stats */}
        {renderStatsCard()}

        {/* Questions List */}
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: colors.textSecondary }]}>
            PENDING REVIEW ({questions.length})
          </Text>
          {questions.length === 0 ? (
            <View style={[styles.emptyCard, { backgroundColor: colors.card }]}>
              <IconSymbol name="checkmark.circle" size={48} color={colors.success} />
              <Text style={[styles.emptyTitle, { color: colors.text }]}>All Caught Up!</Text>
              <Text style={[styles.emptyDescription, { color: colors.textSecondary }]}>
                No questions pending review
              </Text>
            </View>
          ) : (
            questions.map(renderQuestionCard)
          )}
        </View>
      </ScrollView>

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
                          {subject.code} • {subject.total_topics} chapters
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
                    No chapters available.
                  </Text>
                </View>
              )}
            </ScrollView>
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
    padding: Spacing.lg,
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
  coLabel: {
    width: 50,
    fontSize: FontSizes.md,
    fontWeight: '600',
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
});
