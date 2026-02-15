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
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { GlassCard } from '@/components/ui/glass-card';
import { NativeButton } from '@/components/ui/native-button';
import { Colors, Spacing, BorderRadius, FontSizes } from '@/constants/theme';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { vettingService, PendingQuestion, VettingStats, CourseOutcomeMapping } from '@/services/vetting';
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
  const { showError, showSuccess } = useToast();
  
  const [questions, setQuestions] = useState<PendingQuestion[]>([]);
  const [stats, setStats] = useState<VettingStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [expandedQuestion, setExpandedQuestion] = useState<string | null>(null);
  const [coMappings, setCoMappings] = useState<Record<string, CourseOutcomeMapping>>({});

  const loadData = useCallback(async () => {
    try {
      const [questionsResponse, statsResponse] = await Promise.all([
        vettingService.getPendingQuestions(1, 20),
        vettingService.getVettingStats(),
      ]);
      setQuestions(questionsResponse.questions);
      setStats(statsResponse);
      
      // Initialize CO mappings
      const initialMappings: Record<string, CourseOutcomeMapping> = {};
      questionsResponse.questions.forEach((q) => {
        initialMappings[q.id] = q.course_outcome_mapping || {};
      });
      setCoMappings(initialMappings);
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, []);

  const handleRefresh = () => {
    setIsRefreshing(true);
    loadData();
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

        {/* Expanded Content - CO Mapping */}
        {isExpanded && (
          <View style={styles.expandedContent}>
            <LinearGradient
              colors={['#5856D6', '#4A4ADE'] as const}
              style={styles.coHeader}
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
              style={[styles.saveCoButton, { backgroundColor: colors.secondary }]}
              onPress={() => saveCoMapping(question.id)}
            >
              <Text style={styles.saveCoButtonText}>Save CO Mapping</Text>
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
});
