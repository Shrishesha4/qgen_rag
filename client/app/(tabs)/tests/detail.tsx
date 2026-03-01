/**
 * Test Detail Screen - View/edit test, questions, publish/unpublish
 */
import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
  RefreshControl,
  TextInput,
} from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { Colors, Spacing, FontSizes, BorderRadius } from '@/constants/theme';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { GlassCard } from '@/components/ui/glass-card';
import { NativeButton } from '@/components/ui/native-button';
import {
  testsService,
  TestDetailResponse,
  TestQuestion,
} from '@/services/tests';

export default function TestDetailScreen() {
  const colorScheme = useColorScheme() ?? 'light';
  const colors = Colors[colorScheme];
  const router = useRouter();
  const { testId } = useLocalSearchParams<{ testId: string }>();

  const [test, setTest] = useState<TestDetailResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [actionLoading, setActionLoading] = useState('');

  // Inline editing state
  const [editingTitle, setEditingTitle] = useState(false);
  const [editTitle, setEditTitle] = useState('');
  const [editingDesc, setEditingDesc] = useState(false);
  const [editDesc, setEditDesc] = useState('');
  const [editingInstructions, setEditingInstructions] = useState(false);
  const [editInstructions, setEditInstructions] = useState('');

  const loadTest = useCallback(async () => {
    if (!testId) return;
    try {
      const data = await testsService.getTest(testId);
      setTest(data);
      setEditTitle(data.title);
      setEditDesc(data.description || '');
      setEditInstructions(data.instructions || '');
    } catch (error: any) {
      console.error('Failed to load test:', error);
      Alert.alert('Error', 'Failed to load test details');
    } finally {
      setIsLoading(false);
      setRefreshing(false);
    }
  }, [testId]);

  useEffect(() => {
    loadTest();
  }, [loadTest]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadTest();
  }, [loadTest]);

  const handleSaveTitle = async () => {
    if (!testId || !editTitle.trim()) return;
    try {
      await testsService.updateTest(testId, { title: editTitle.trim() });
      setTest((prev) => prev ? { ...prev, title: editTitle.trim() } : prev);
      setEditingTitle(false);
    } catch (error) {
      Alert.alert('Error', 'Failed to update title');
    }
  };

  const handleSaveDesc = async () => {
    if (!testId) return;
    try {
      await testsService.updateTest(testId, { description: editDesc.trim() });
      setTest((prev) => prev ? { ...prev, description: editDesc.trim() } : prev);
      setEditingDesc(false);
    } catch (error) {
      Alert.alert('Error', 'Failed to update description');
    }
  };

  const handleSaveInstructions = async () => {
    if (!testId) return;
    try {
      await testsService.updateTest(testId, { instructions: editInstructions.trim() });
      setTest((prev) => prev ? { ...prev, instructions: editInstructions.trim() } : prev);
      setEditingInstructions(false);
    } catch (error) {
      Alert.alert('Error', 'Failed to update instructions');
    }
  };

  const handlePublish = async () => {
    if (!testId) return;
    Alert.alert('Publish Test', 'This will make the test available to enrolled students.', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Publish',
        onPress: async () => {
          setActionLoading('publish');
          try {
            await testsService.publishTest(testId);
            await loadTest();
          } catch (error: any) {
            Alert.alert('Error', error?.response?.data?.detail || 'Failed to publish');
          } finally {
            setActionLoading('');
          }
        },
      },
    ]);
  };

  const handleUnpublish = async () => {
    if (!testId) return;
    Alert.alert('Unpublish Test', 'Students will no longer be able to take this test.', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Unpublish',
        style: 'destructive',
        onPress: async () => {
          setActionLoading('unpublish');
          try {
            await testsService.unpublishTest(testId);
            await loadTest();
          } catch (error: any) {
            Alert.alert('Error', error?.response?.data?.detail || 'Failed to unpublish');
          } finally {
            setActionLoading('');
          }
        },
      },
    ]);
  };

  const handleRegenerate = async () => {
    if (!testId) return;
    Alert.alert(
      'Regenerate Questions',
      'This will replace all current questions with new selections from the approved pool.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Regenerate',
          onPress: async () => {
            setActionLoading('regenerate');
            try {
              const result = await testsService.generateQuestions(testId);
              Alert.alert(
                'Done',
                `${result.questions_added} questions selected (${result.total_marks} marks)`
              );
              await loadTest();
            } catch (error: any) {
              Alert.alert('Error', error?.response?.data?.detail || 'Failed to regenerate');
            } finally {
              setActionLoading('');
            }
          },
        },
      ]
    );
  };

  const handleRemoveQuestion = async (testQuestionId: string) => {
    if (!testId) return;
    Alert.alert('Remove Question', 'Remove this question from the test?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Remove',
        style: 'destructive',
        onPress: async () => {
          try {
            await testsService.removeTestQuestion(testId, testQuestionId);
            await loadTest();
          } catch (error) {
            Alert.alert('Error', 'Failed to remove question');
          }
        },
      },
    ]);
  };

  const getDifficultyColor = (level?: string | null) => {
    switch (level) {
      case 'easy': return colors.success;
      case 'medium': return colors.warning;
      case 'hard': return colors.error;
      default: return colors.textTertiary;
    }
  };

  if (isLoading) {
    return (
      <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]} edges={['bottom']}>
        <View style={styles.centered}>
          <ActivityIndicator size="large" color={colors.primary} />
        </View>
      </SafeAreaView>
    );
  }

  if (!test) {
    return (
      <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]} edges={['bottom']}>
        <View style={styles.centered}>
          <Text style={{ color: colors.error }}>Test not found</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]} edges={['bottom']}>
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
      >
        {/* Status Banner */}
        <View
          style={[
            styles.statusBanner,
            {
              backgroundColor:
                test.status === 'published'
                  ? colors.success + '15'
                  : test.status === 'draft'
                  ? colors.warning + '15'
                  : colors.textTertiary + '15',
              borderColor:
                test.status === 'published'
                  ? colors.success + '30'
                  : test.status === 'draft'
                  ? colors.warning + '30'
                  : colors.textTertiary + '30',
            },
          ]}
        >
          <IconSymbol
            name={
              test.status === 'published'
                ? 'checkmark.circle.fill'
                : test.status === 'draft'
                ? 'pencil.circle.fill'
                : 'xmark.circle.fill'
            }
            size={20}
            color={
              test.status === 'published'
                ? colors.success
                : test.status === 'draft'
                ? colors.warning
                : colors.textTertiary
            }
          />
          <Text
            style={[
              styles.statusBannerText,
              {
                color:
                  test.status === 'published'
                    ? colors.success
                    : test.status === 'draft'
                    ? colors.warning
                    : colors.textTertiary,
              },
            ]}
          >
            {test.status === 'published'
              ? 'Published — students can take this test'
              : test.status === 'draft'
              ? 'Draft — not yet visible to students'
              : 'Unpublished — no longer visible'}
          </Text>
        </View>

        {/* Title (editable) */}
        <GlassCard style={styles.infoCard}>
          <View style={styles.editableRow}>
            {editingTitle ? (
              <View style={styles.editRow}>
                <TextInput
                  style={[styles.editInput, { color: colors.text, borderColor: colors.border }]}
                  value={editTitle}
                  onChangeText={setEditTitle}
                  autoFocus
                />
                <TouchableOpacity onPress={handleSaveTitle}>
                  <IconSymbol name="checkmark.circle.fill" size={28} color={colors.primary} />
                </TouchableOpacity>
                <TouchableOpacity onPress={() => { setEditingTitle(false); setEditTitle(test.title); }}>
                  <IconSymbol name="xmark.circle.fill" size={28} color={colors.textTertiary} />
                </TouchableOpacity>
              </View>
            ) : (
              <TouchableOpacity style={styles.editTrigger} onPress={() => setEditingTitle(true)}>
                <Text style={[styles.testTitle, { color: colors.text }]}>{test.title}</Text>
                <IconSymbol name="pencil" size={16} color={colors.textTertiary} />
              </TouchableOpacity>
            )}
          </View>

          {/* Description (editable) */}
          <View style={styles.editableRow}>
            {editingDesc ? (
              <View style={[styles.editRow, { flex: 1 }]}>
                <TextInput
                  style={[styles.editInput, styles.multilineEdit, { color: colors.text, borderColor: colors.border }]}
                  value={editDesc}
                  onChangeText={setEditDesc}
                  multiline
                  autoFocus
                />
                <View style={styles.editActions}>
                  <TouchableOpacity onPress={handleSaveDesc}>
                    <IconSymbol name="checkmark.circle.fill" size={28} color={colors.primary} />
                  </TouchableOpacity>
                  <TouchableOpacity onPress={() => { setEditingDesc(false); setEditDesc(test.description || ''); }}>
                    <IconSymbol name="xmark.circle.fill" size={28} color={colors.textTertiary} />
                  </TouchableOpacity>
                </View>
              </View>
            ) : (
              <TouchableOpacity style={styles.editTrigger} onPress={() => setEditingDesc(true)}>
                <Text style={[styles.descText, { color: colors.textSecondary }]}>
                  {test.description || 'Add description...'}
                </Text>
                <IconSymbol name="pencil" size={14} color={colors.textTertiary} />
              </TouchableOpacity>
            )}
          </View>

          {/* Instructions (editable) */}
          <View style={styles.editableRow}>
            <Text style={[styles.sectionLabel, { color: colors.textTertiary }]}>Instructions</Text>
            {editingInstructions ? (
              <View style={[styles.editRow, { flex: 1 }]}>
                <TextInput
                  style={[styles.editInput, styles.multilineEdit, { color: colors.text, borderColor: colors.border }]}
                  value={editInstructions}
                  onChangeText={setEditInstructions}
                  multiline
                  autoFocus
                />
                <View style={styles.editActions}>
                  <TouchableOpacity onPress={handleSaveInstructions}>
                    <IconSymbol name="checkmark.circle.fill" size={28} color={colors.primary} />
                  </TouchableOpacity>
                  <TouchableOpacity onPress={() => { setEditingInstructions(false); setEditInstructions(test.instructions || ''); }}>
                    <IconSymbol name="xmark.circle.fill" size={28} color={colors.textTertiary} />
                  </TouchableOpacity>
                </View>
              </View>
            ) : (
              <TouchableOpacity style={styles.editTrigger} onPress={() => setEditingInstructions(true)}>
                <Text style={[styles.descText, { color: colors.textSecondary }]}>
                  {test.instructions || 'Add instructions...'}
                </Text>
                <IconSymbol name="pencil" size={14} color={colors.textTertiary} />
              </TouchableOpacity>
            )}
          </View>

          {/* Stats */}
          <View style={styles.statsRow}>
            <View style={styles.statItem}>
              <Text style={[styles.statValue, { color: colors.primary }]}>{test.total_questions}</Text>
              <Text style={[styles.statLabel, { color: colors.textTertiary }]}>Questions</Text>
            </View>
            <View style={styles.statItem}>
              <Text style={[styles.statValue, { color: colors.primary }]}>{test.total_marks}</Text>
              <Text style={[styles.statLabel, { color: colors.textTertiary }]}>Marks</Text>
            </View>
            {test.duration_minutes && (
              <View style={styles.statItem}>
                <Text style={[styles.statValue, { color: colors.primary }]}>{test.duration_minutes}</Text>
                <Text style={[styles.statLabel, { color: colors.textTertiary }]}>Minutes</Text>
              </View>
            )}
            {test.submissions_count > 0 && (
              <View style={styles.statItem}>
                <Text style={[styles.statValue, { color: colors.success }]}>{test.submissions_count}</Text>
                <Text style={[styles.statLabel, { color: colors.textTertiary }]}>Submissions</Text>
              </View>
            )}
          </View>
        </GlassCard>

        {/* Actions */}
        <View style={styles.actionsRow}>
          {test.status === 'draft' && (
            <TouchableOpacity
              style={[styles.actionButton, { backgroundColor: colors.success }]}
              onPress={handlePublish}
              disabled={actionLoading === 'publish'}
            >
              {actionLoading === 'publish' ? (
                <ActivityIndicator size="small" color="#FFF" />
              ) : (
                <>
                  <IconSymbol name="paperplane.fill" size={16} color="#FFF" />
                  <Text style={styles.actionText}>Publish</Text>
                </>
              )}
            </TouchableOpacity>
          )}
          {test.status === 'published' && (
            <TouchableOpacity
              style={[styles.actionButton, { backgroundColor: colors.error }]}
              onPress={handleUnpublish}
              disabled={actionLoading === 'unpublish'}
            >
              {actionLoading === 'unpublish' ? (
                <ActivityIndicator size="small" color="#FFF" />
              ) : (
                <>
                  <IconSymbol name="xmark.circle.fill" size={16} color="#FFF" />
                  <Text style={styles.actionText}>Unpublish</Text>
                </>
              )}
            </TouchableOpacity>
          )}
          {test.status !== 'published' && (
            <TouchableOpacity
              style={[styles.actionButton, { backgroundColor: colors.secondary }]}
              onPress={handleRegenerate}
              disabled={actionLoading === 'regenerate'}
            >
              {actionLoading === 'regenerate' ? (
                <ActivityIndicator size="small" color="#FFF" />
              ) : (
                <>
                  <IconSymbol name="arrow.triangle.2.circlepath" size={16} color="#FFF" />
                  <Text style={styles.actionText}>Regenerate</Text>
                </>
              )}
            </TouchableOpacity>
          )}
          {test.status === 'published' && test.submissions_count > 0 && (
            <TouchableOpacity
              style={[styles.actionButton, { backgroundColor: colors.primary }]}
              onPress={() =>
                router.push({
                  pathname: '/(tabs)/tests/performance',
                  params: { testId: test.id },
                })
              }
            >
              <IconSymbol name="chart.bar.fill" size={16} color="#FFF" />
              <Text style={styles.actionText}>Performance</Text>
            </TouchableOpacity>
          )}
        </View>

        {/* Questions List */}
        <Text style={[styles.questionsHeader, { color: colors.text }]}>
          Questions ({test.questions?.length || 0})
        </Text>

        {(!test.questions || test.questions.length === 0) ? (
          <GlassCard style={styles.emptyQuestions}>
            <IconSymbol name="doc.text" size={32} color={colors.textTertiary} />
            <Text style={[styles.emptyText, { color: colors.textSecondary }]}>
              No questions yet. Use "Regenerate" to select questions.
            </Text>
          </GlassCard>
        ) : (
          test.questions.map((q: TestQuestion, idx: number) => (
            <GlassCard key={q.id} style={styles.questionCard}>
              <View style={styles.questionHeader}>
                <View style={styles.questionIndex}>
                  <Text style={[styles.indexText, { color: colors.primary }]}>Q{idx + 1}</Text>
                </View>
                <View style={styles.questionBadges}>
                  <View
                    style={[
                      styles.diffBadge,
                      { backgroundColor: getDifficultyColor(q.difficulty_level) + '20' },
                    ]}
                  >
                    <Text
                      style={[styles.diffBadgeText, { color: getDifficultyColor(q.difficulty_level) }]}
                    >
                      {q.difficulty_level || 'N/A'}
                    </Text>
                  </View>
                  <Text style={[styles.marksText, { color: colors.textTertiary }]}>
                    {q.marks} mark{q.marks !== 1 ? 's' : ''}
                  </Text>
                </View>
              </View>

              <Text style={[styles.questionText, { color: colors.text }]} numberOfLines={3}>
                {q.question_text}
              </Text>

              {q.topic_name && (
                <Text style={[styles.topicTag, { color: colors.textTertiary }]}>
                  Topic: {q.topic_name}
                </Text>
              )}

              {q.options && q.options.length > 0 && (
                <View style={styles.optionsList}>
                  {q.options.map((opt, i) => (
                    <Text
                      key={i}
                      style={[
                        styles.optionText,
                        {
                          color:
                            q.correct_answer &&
                            opt.charAt(0).toUpperCase() === q.correct_answer.charAt(0).toUpperCase()
                              ? colors.success
                              : colors.textSecondary,
                        },
                      ]}
                      numberOfLines={2}
                    >
                      {opt}
                    </Text>
                  ))}
                </View>
              )}

              <View style={styles.questionActions}>
                <TouchableOpacity
                  style={[styles.qAction, { borderColor: colors.border }]}
                  onPress={() =>
                    router.push({
                      pathname: '/(tabs)/tests/edit-question',
                      params: {
                        testId: test.id,
                        testQuestionId: q.id,
                        questionText: q.question_text,
                        options: JSON.stringify(q.options || []),
                        correctAnswer: q.correct_answer || '',
                        marks: String(q.marks),
                      },
                    })
                  }
                >
                  <IconSymbol name="pencil" size={14} color={colors.primary} />
                  <Text style={[styles.qActionText, { color: colors.primary }]}>Edit</Text>
                </TouchableOpacity>
                {test.status !== 'published' && (
                  <TouchableOpacity
                    style={[styles.qAction, { borderColor: colors.error + '40' }]}
                    onPress={() => handleRemoveQuestion(q.id)}
                  >
                    <IconSymbol name="trash" size={14} color={colors.error} />
                    <Text style={[styles.qActionText, { color: colors.error }]}>Remove</Text>
                  </TouchableOpacity>
                )}
              </View>
            </GlassCard>
          ))
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  content: { padding: Spacing.md, paddingBottom: 100 },
  statusBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    padding: Spacing.md,
    borderRadius: BorderRadius.md,
    borderWidth: 1,
    marginBottom: Spacing.md,
  },
  statusBannerText: {
    fontSize: FontSizes.sm,
    fontWeight: '500',
    flex: 1,
  },
  infoCard: {
    padding: Spacing.md,
    marginBottom: Spacing.md,
    gap: Spacing.sm,
  },
  editableRow: {
    gap: 4,
  },
  editTrigger: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  editRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    flex: 1,
  },
  editInput: {
    borderWidth: 1,
    borderRadius: BorderRadius.md,
    paddingHorizontal: Spacing.sm,
    paddingVertical: 8,
    fontSize: FontSizes.md,
    flex: 1,
  },
  multilineEdit: {
    minHeight: 60,
    textAlignVertical: 'top',
  },
  editActions: {
    gap: 4,
  },
  testTitle: {
    fontSize: FontSizes.xl,
    fontWeight: '700',
  },
  descText: {
    fontSize: FontSizes.sm,
    flex: 1,
  },
  sectionLabel: {
    fontSize: FontSizes.xs,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  statsRow: {
    flexDirection: 'row',
    gap: Spacing.lg,
    marginTop: Spacing.sm,
    paddingTop: Spacing.sm,
    borderTopWidth: 1,
    borderTopColor: 'rgba(0,0,0,0.06)',
  },
  statItem: {
    alignItems: 'center',
  },
  statValue: {
    fontSize: FontSizes.lg,
    fontWeight: '700',
  },
  statLabel: {
    fontSize: FontSizes.xs,
    marginTop: 2,
  },
  actionsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.sm,
    marginBottom: Spacing.lg,
  },
  actionButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: Spacing.md,
    paddingVertical: 10,
    borderRadius: BorderRadius.md,
  },
  actionText: {
    color: '#FFFFFF',
    fontSize: FontSizes.sm,
    fontWeight: '600',
  },
  questionsHeader: {
    fontSize: FontSizes.lg,
    fontWeight: '700',
    marginBottom: Spacing.sm,
  },
  emptyQuestions: {
    alignItems: 'center',
    padding: Spacing.xl,
    gap: Spacing.sm,
  },
  emptyText: {
    fontSize: FontSizes.sm,
    textAlign: 'center',
  },
  questionCard: {
    padding: Spacing.md,
    marginBottom: Spacing.sm,
  },
  questionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  questionIndex: {
    width: 36,
    height: 36,
    borderRadius: 18,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: 'rgba(0, 122, 255, 0.1)',
  },
  indexText: {
    fontSize: FontSizes.sm,
    fontWeight: '700',
  },
  questionBadges: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  diffBadge: {
    paddingHorizontal: 10,
    paddingVertical: 3,
    borderRadius: BorderRadius.full,
  },
  diffBadgeText: {
    fontSize: FontSizes.xs,
    fontWeight: '600',
    textTransform: 'capitalize',
  },
  marksText: {
    fontSize: FontSizes.xs,
  },
  questionText: {
    fontSize: FontSizes.md,
    lineHeight: 22,
    marginBottom: 6,
  },
  topicTag: {
    fontSize: FontSizes.xs,
    marginBottom: 6,
  },
  optionsList: {
    gap: 4,
    marginBottom: 8,
  },
  optionText: {
    fontSize: FontSizes.sm,
    paddingLeft: 8,
  },
  questionActions: {
    flexDirection: 'row',
    gap: Spacing.sm,
    marginTop: 4,
  },
  qAction: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: BorderRadius.md,
    borderWidth: 1,
  },
  qActionText: {
    fontSize: FontSizes.xs,
    fontWeight: '500',
  },
});
