import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  Alert,
  ActivityIndicator,
  Modal,
  TextInput,
  Animated,
  Platform,
  SafeAreaView,
  FlatList,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import Slider from '@react-native-community/slider';
import { router } from 'expo-router';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { GlassCard } from '@/components/ui/glass-card';
import { NativeButton } from '@/components/ui/native-button';
import { Colors, Spacing, BorderRadius, FontSizes } from '@/constants/theme';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { rubricsService, Rubric, RubricCreateData, QuestionTypeDistribution, GenerationProgress } from '@/services/rubrics';
import { subjectsService, Subject } from '@/services/subjects';
import { useToast } from '@/components/toast';
import { extractErrorMessage } from '@/utils/errors';

const EXAM_TYPES = [
  { value: 'final_exam', label: 'Final Exam', icon: 'doc.fill' },
  { value: 'mid_term', label: 'Mid-term', icon: 'doc.text.fill' },
  { value: 'quiz', label: 'Quiz', icon: 'clock.fill' },
  { value: 'assignment', label: 'Assignment', icon: 'paperplane.fill' },
];

const QUESTION_TYPES = [
  { value: 'mcq', label: 'MCQ', icon: 'list.bullet', color: '#007AFF' },
  { value: 'short_notes', label: 'Short Notes', icon: 'pencil', color: '#34C759' },
  { value: 'essay', label: 'Essay', icon: 'doc.richtext', color: '#FF9500' },
];

const DEFAULT_LOS = [
  { id: 'LO1', name: 'Understand fundamental concepts', description: 'Recall and comprehend basic principles' },
  { id: 'LO2', name: 'Apply theoretical knowledge', description: 'Use concepts in practical scenarios' },
  { id: 'LO3', name: 'Analyze and solve problems', description: 'Break down complex problems' },
  { id: 'LO4', name: 'Design and implement solutions', description: 'Create new approaches' },
  { id: 'LO5', name: 'Evaluate and optimize', description: 'Assess and improve solutions' },
];

export default function GenerateScreen() {
  const colorScheme = useColorScheme();
  const colors = Colors[colorScheme ?? 'light'];
  const { showError, showSuccess, showWarning } = useToast();
  
  const [rubrics, setRubrics] = useState<Rubric[]>([]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  
  // Generation state
  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [selectedRubric, setSelectedRubric] = useState<Rubric | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationProgress, setGenerationProgress] = useState<GenerationProgress | null>(null);
  const [generatedQuestions, setGeneratedQuestions] = useState<Array<{id: string; question_text: string; question_type: string; marks: number}>>([]);
  const cancelGenerationRef = useRef<(() => void) | null>(null);
  const progressAnim = useRef(new Animated.Value(0)).current;
  
  // Create rubric form state
  const [rubricName, setRubricName] = useState('');
  const [selectedSubject, setSelectedSubject] = useState<Subject | null>(null);
  const [selectedExamType, setSelectedExamType] = useState('final_exam');
  const [duration, setDuration] = useState('180');
  const [questionDistribution, setQuestionDistribution] = useState<Record<string, QuestionTypeDistribution>>({
    mcq: { count: 20, marks_each: 2 },
    short_notes: { count: 5, marks_each: 6 },
    essay: { count: 0, marks_each: 10 },
  });
  const [loDistribution, setLoDistribution] = useState<Record<string, number>>({
    LO1: 25, LO2: 25, LO3: 20, LO4: 15, LO5: 15,
  });
  const [showSubjectPicker, setShowSubjectPicker] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [rubricsResponse, subjectsResponse] = await Promise.all([
        rubricsService.listRubrics(1, 50),
        subjectsService.listSubjects(1, 100),
      ]);
      console.log('[Generate] Loaded subjects:', subjectsResponse.subjects.length);
      setRubrics(rubricsResponse.rubrics);
      setSubjects(subjectsResponse.subjects);
      if (subjectsResponse.subjects.length > 0 && !selectedSubject) {
        setSelectedSubject(subjectsResponse.subjects[0]);
        console.log('[Generate] Auto-selected first subject:', subjectsResponse.subjects[0].name);
      }
    } catch (error) {
      console.error('Failed to load data:', error);
      showError(error, 'Failed to Load Data');
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [showError]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleRefresh = () => {
    setIsRefreshing(true);
    loadData();
  };

  const calculateTotals = () => {
    let totalQuestions = 0;
    let totalMarks = 0;
    Object.values(questionDistribution).forEach((dist) => {
      totalQuestions += dist.count;
      totalMarks += dist.count * dist.marks_each;
    });
    return { totalQuestions, totalMarks };
  };

  const handleCreateRubric = async () => {
    if (!rubricName.trim()) {
      showWarning('Please enter a rubric name', 'Missing Information');
      return;
    }
    if (!selectedSubject) {
      showWarning('Please select a subject', 'Missing Information');
      return;
    }
    
    // Filter out question types with count of 0
    const filteredDistribution = Object.fromEntries(
      Object.entries(questionDistribution).filter(([_, value]) => value.count > 0)
    );
    
    if (Object.keys(filteredDistribution).length === 0) {
      showWarning('Please add at least one question type', 'Missing Information');
      return;
    }
    
    setIsCreating(true);
    try {
      const data: RubricCreateData = {
        subject_id: selectedSubject.id,
        name: rubricName,
        exam_type: selectedExamType,
        duration_minutes: parseInt(duration) || 180,
        question_type_distribution: filteredDistribution,
        learning_outcomes_distribution: loDistribution,
      };
      
      await rubricsService.createRubric(data);
      setShowCreateModal(false);
      resetForm();
      loadData();
      showSuccess('Rubric created successfully');
    } catch (error) {
      console.error('[Rubric Creation Error]', error);
      showError(error, 'Failed to Create Rubric');
    } finally {
      setIsCreating(false);
    }
  };

  const resetForm = () => {
    setRubricName('');
    setSelectedExamType('final_exam');
    setDuration('180');
    setQuestionDistribution({
      mcq: { count: 20, marks_each: 2 },
      short_notes: { count: 5, marks_each: 6 },
      essay: { count: 0, marks_each: 10 },
    });
    setLoDistribution({
      LO1: 25, LO2: 25, LO3: 20, LO4: 15, LO5: 15,
    });
  };

  const handleStartGeneration = (rubric: Rubric) => {
    setSelectedRubric(rubric);
    setGeneratedQuestions([]);
    setGenerationProgress(null);
    setShowGenerateModal(true);
  };

  const handleGenerate = () => {
    if (!selectedRubric) return;
    
    setIsGenerating(true);
    setGeneratedQuestions([]);
    progressAnim.setValue(0);
    
    const cancel = rubricsService.generateFromRubric(
      selectedRubric.id,
      (progress) => {
        setGenerationProgress(progress);
        
        if (progress.progress) {
          Animated.timing(progressAnim, {
            toValue: progress.progress,
            duration: 300,
            useNativeDriver: false,
          }).start();
        }
        
        if (progress.question) {
          setGeneratedQuestions(prev => [...prev, progress.question!]);
        }
        
        if (progress.status === 'error') {
          showError(new Error(progress.message || 'Failed to generate questions'), 'Generation Failed');
          setIsGenerating(false);
        }
      },
      () => {
        setIsGenerating(false);
        loadData();
      },
      (error) => {
        showError(error, 'Generation Failed');
        setIsGenerating(false);
      }
    );
    
    cancelGenerationRef.current = cancel;
  };

  const handleCancelGeneration = () => {
    if (cancelGenerationRef.current) {
      cancelGenerationRef.current();
    }
    setIsGenerating(false);
    setShowGenerateModal(false);
  };

  const handleDeleteRubric = async (rubric: Rubric) => {
    Alert.alert(
      'Delete Rubric',
      `Are you sure you want to delete "${rubric.name}"?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              await rubricsService.deleteRubric(rubric.id);
              loadData();
              showSuccess('Rubric deleted');
            } catch (error) {
              showError(error, 'Failed to Delete');
            }
          },
        },
      ]
    );
  };

  const updateQuestionCount = (type: string, count: number) => {
    setQuestionDistribution((prev) => {
      const existing = prev[type] || { count: 0, marks_each: type === 'essay' ? 10 : type === 'short_notes' ? 6 : 2 };
      return {
        ...prev,
        [type]: { ...existing, count: Math.round(count) },
      };
    });
  };

  const updateMarksEach = (type: string, marks: number) => {
    setQuestionDistribution((prev) => {
      const existing = prev[type] || { count: 0, marks_each: 1 };
      return {
        ...prev,
        [type]: { ...existing, marks_each: Math.max(1, Math.round(marks)) },
      };
    });
  };

  const updateLoPercentage = (loId: string, percentage: number) => {
    setLoDistribution((prev) => ({
      ...prev,
      [loId]: Math.round(percentage),
    }));
  };

  const getLoTotal = () => Object.values(loDistribution).reduce((a, b) => a + b, 0);

  const { totalQuestions, totalMarks } = calculateTotals();

  const renderRubricCard = (rubric: Rubric) => (
    <View
      key={rubric.id}
      style={[styles.rubricCard, { backgroundColor: colors.card }]}
    >
      <TouchableOpacity 
        style={styles.rubricCardContent}
        onLongPress={() => handleDeleteRubric(rubric)}
        activeOpacity={0.7}
      >
        <View style={[styles.rubricIcon, { backgroundColor: colors.secondary + '20' }]}>
          <IconSymbol name="doc.fill" size={24} color={colors.secondary} />
        </View>
        <View style={styles.rubricInfo}>
          <Text style={[styles.rubricName, { color: colors.text }]}>{rubric.name}</Text>
          <Text style={[styles.rubricSubject, { color: colors.textSecondary }]}>
            {rubric.total_questions} Questions • {rubric.total_marks} Marks • {rubric.duration_minutes} min
          </Text>
        </View>
      </TouchableOpacity>
      <TouchableOpacity
        style={[styles.generateIconButton, { backgroundColor: colors.primary }]}
        onPress={() => handleStartGeneration(rubric)}
      >
        <IconSymbol name="sparkles" size={16} color="#FFFFFF" />
      </TouchableOpacity>
    </View>
  );

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
        {/* Header Info Card */}
        <LinearGradient
          colors={['#4A90D9', '#357ABD'] as const}
          style={styles.infoCard}
        >
          <IconSymbol name="sparkles" size={24} color="#FFFFFF" />
          <View style={styles.infoCardContent}>
            <Text style={styles.infoCardTitle}>Subject-Wide Exam Generation</Text>
            <Text style={styles.infoCardDescription}>
              Questions are pulled from all topics across the entire subject based on your rubric's Learning Outcome distribution.
            </Text>
          </View>
        </LinearGradient>

        {/* Create New Rubric Button */}
        <TouchableOpacity
          style={[styles.createButton, { backgroundColor: colors.secondary }]}
          onPress={() => setShowCreateModal(true)}
        >
          <IconSymbol name="plus" size={20} color="#FFFFFF" />
          <Text style={styles.createButtonText}>Create New Rubric</Text>
        </TouchableOpacity>

        {/* Saved Rubrics */}
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: colors.textSecondary }]}>
            SAVED RUBRICS ({rubrics.length})
          </Text>
          <View style={[styles.rubricsList, { backgroundColor: colors.card }]}>
            {rubrics.length === 0 ? (
              <Text style={[styles.emptyText, { color: colors.textSecondary }]}>
                No rubrics created yet
              </Text>
            ) : (
              rubrics.map(renderRubricCard)
            )}
          </View>
        </View>

        {/* Generate Button */}
        <TouchableOpacity
          style={[styles.generateButton, { backgroundColor: colors.textTertiary }]}
          disabled={rubrics.length === 0}
        >
          <IconSymbol name="sparkles" size={20} color="#FFFFFF" />
          <Text style={styles.generateButtonText}>Generate Final Exam</Text>
        </TouchableOpacity>
      </ScrollView>

      {/* Create Rubric Modal */}
      <Modal
        visible={showCreateModal}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => setShowCreateModal(false)}
      >
        <View style={[styles.modalContainer, { backgroundColor: colors.background }]}>
          <LinearGradient
            colors={['#4A90D9', '#357ABD'] as const}
            style={styles.modalHeader}
          >
            <TouchableOpacity onPress={() => setShowCreateModal(false)}>
              <Text style={styles.modalCancel}>Cancel</Text>
            </TouchableOpacity>
            <Text style={styles.modalTitle}>Create Exam Rubric</Text>
            <View style={{ width: 50 }} />
          </LinearGradient>

          <ScrollView style={styles.modalContent}>
            {/* Subject Picker Inline View */}
            {showSubjectPicker ? (
              <View style={[styles.inlinePickerContainer, { backgroundColor: colors.background }]}>
                <View style={[styles.inlinePickerHeader, { backgroundColor: colors.card, borderBottomColor: colors.border }]}>
                  <TouchableOpacity onPress={() => setShowSubjectPicker(false)}>
                    <IconSymbol name="chevron.left" size={24} color={colors.primary} />
                  </TouchableOpacity>
                  <Text style={[styles.inlinePickerTitle, { color: colors.text }]}>Select Subject</Text>
                  <View style={{ width: 24 }} />
                </View>
                <ScrollView style={styles.inlinePickerList}>
                  {subjects.length === 0 ? (
                    <View style={styles.emptySubjectsList}>
                      <IconSymbol name="book.closed" size={48} color={colors.textTertiary} />
                      <Text style={[styles.emptySubjectsText, { color: colors.textSecondary }]}>
                        No subjects available
                      </Text>
                      <Text style={[styles.emptySubjectsHint, { color: colors.textTertiary }]}>
                        Create a subject first in the Subjects tab
                      </Text>
                    </View>
                  ) : (
                    subjects.map((subject) => {
                      const isSelected = selectedSubject?.id === subject.id;
                      return (
                        <TouchableOpacity
                          key={subject.id}
                          activeOpacity={0.6}
                          style={[
                            styles.inlinePickerItem,
                            { backgroundColor: colors.card, borderBottomColor: colors.border },
                            isSelected && { backgroundColor: colors.primary + '15' }
                          ]}
                          onPress={() => {
                            console.log('[Generate] Subject selected:', subject.name);
                            setSelectedSubject(subject);
                            setShowSubjectPicker(false);
                          }}
                        >
                          <View style={styles.inlinePickerItemContent}>
                            <View style={[styles.inlinePickerItemIcon, { backgroundColor: colors.primary + '20' }]}>
                              <IconSymbol name="book.fill" size={20} color={colors.primary} />
                            </View>
                            <View style={styles.inlinePickerItemText}>
                              <Text style={[styles.inlinePickerItemTitle, { color: colors.text }]}>
                                {subject.name}
                              </Text>
                              <Text style={[styles.inlinePickerItemSubtitle, { color: colors.textSecondary }]}>
                                {subject.code}
                              </Text>
                            </View>
                          </View>
                          {isSelected && (
                            <IconSymbol name="checkmark.circle.fill" size={22} color={colors.primary} />
                          )}
                        </TouchableOpacity>
                      );
                    })
                  )}
                </ScrollView>
              </View>
            ) : (
              <>
            {/* Basic Info */}
            <View style={[styles.formSection, { backgroundColor: colors.card }]}>
              <Text style={[styles.formLabel, { color: colors.textSecondary }]}>RUBRIC NAME</Text>
              <TextInput
                style={[styles.textInput, { color: colors.text, borderColor: colors.border }]}
                placeholder="e.g., CS301 Final Exam 2024"
                placeholderTextColor={colors.textTertiary}
                value={rubricName}
                onChangeText={setRubricName}
              />
              
              <Text style={[styles.formLabel, { color: colors.textSecondary, marginTop: Spacing.md }]}>
                SUBJECT (ENTIRE COURSE)
              </Text>
              <TouchableOpacity
                style={[styles.selectContainer, { borderColor: colors.border }]}
                onPress={() => {
                  console.log('[Generate] Opening subject picker. Subjects count:', subjects.length);
                  setShowSubjectPicker(true);
                }}
              >
                <Text style={[styles.selectText, { color: selectedSubject ? colors.text : colors.textTertiary }]}>
                  {selectedSubject ? `${selectedSubject.name} (${selectedSubject.code})` : 'Select a subject'}
                </Text>
                <IconSymbol name="chevron.down" size={16} color={colors.textSecondary} />
              </TouchableOpacity>
              <Text style={[styles.formHint, { color: colors.textTertiary }]}>
                Questions will be pulled from all topics in this subject
              </Text>
              
              <Text style={[styles.formLabel, { color: colors.textSecondary, marginTop: Spacing.md }]}>
                EXAM TYPE
              </Text>
              <View style={styles.examTypesGrid}>
                {EXAM_TYPES.map((type) => (
                  <TouchableOpacity
                    key={type.value}
                    style={[
                      styles.examTypeButton,
                      { borderColor: colors.border },
                      selectedExamType === type.value && { borderColor: colors.primary, backgroundColor: colors.primary + '10' },
                    ]}
                    onPress={() => setSelectedExamType(type.value)}
                  >
                    <IconSymbol
                      name={type.icon as never}
                      size={18}
                      color={selectedExamType === type.value ? colors.primary : colors.textSecondary}
                    />
                    <Text style={[
                      styles.examTypeLabel,
                      { color: selectedExamType === type.value ? colors.primary : colors.text },
                    ]}>
                      {type.label}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
              
              <Text style={[styles.formLabel, { color: colors.textSecondary, marginTop: Spacing.md }]}>
                DURATION (MINUTES)
              </Text>
              <TextInput
                style={[styles.textInput, { color: colors.text, borderColor: colors.border }]}
                placeholder="180"
                placeholderTextColor={colors.textTertiary}
                value={duration}
                onChangeText={setDuration}
                keyboardType="numeric"
              />
            </View>

            {/* Question Types Distribution */}
            <LinearGradient
              colors={['#007AFF', '#0056B3'] as const}
              style={styles.mapHeader}
            >
              <IconSymbol name="list.bullet" size={18} color="#FFFFFF" />
              <Text style={styles.mapTitle}>MAP 1: Question Types Distribution</Text>
            </LinearGradient>
            <View style={[styles.formSection, { backgroundColor: colors.card }]}>
              {QUESTION_TYPES.map((type) => {
                const dist = questionDistribution[type.value] || { count: 0, marks_each: 1 };
                const marks = dist.count * dist.marks_each;
                return (
                  <View key={type.value} style={styles.questionTypeRow}>
                    <View style={styles.questionTypeHeader}>
                      <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                        <IconSymbol name={type.icon as never} size={18} color={type.color} />
                        <Text style={[styles.questionTypeLabel, { color: type.color, marginLeft: Spacing.sm }]}>
                          {type.label}
                        </Text>
                      </View>
                      <Text style={[styles.marksLabel, { color: colors.text }]}>{marks} marks</Text>
                    </View>
                    <View style={styles.sliderRow}>
                      <Text style={[styles.sliderLabel, { color: colors.textSecondary }]}>Count</Text>
                      <Slider
                        style={styles.slider}
                        minimumValue={0}
                        maximumValue={50}
                        value={dist.count}
                        onValueChange={(val: number) => updateQuestionCount(type.value, val)}
                        minimumTrackTintColor={type.color}
                        maximumTrackTintColor={colors.border}
                      />
                      <Text style={[styles.sliderValue, { color: type.color }]}>{dist.count}</Text>
                    </View>
                    <View style={styles.sliderRow}>
                      <Text style={[styles.sliderLabel, { color: colors.textSecondary }]}>Marks</Text>
                      <TouchableOpacity 
                        style={[styles.marksButton, { backgroundColor: colors.card, borderColor: colors.border }]}
                        onPress={() => updateMarksEach(type.value, dist.marks_each - 1)}
                      >
                        <Text style={[styles.marksButtonText, { color: type.color }]}>−</Text>
                      </TouchableOpacity>
                      <TextInput
                        style={[styles.marksInput, { backgroundColor: colors.background, color: colors.text, borderColor: colors.border }]}
                        value={String(dist.marks_each)}
                        onChangeText={(text) => {
                          const num = parseInt(text) || 1;
                          updateMarksEach(type.value, num);
                        }}
                        keyboardType="number-pad"
                      />
                      <TouchableOpacity 
                        style={[styles.marksButton, { backgroundColor: colors.card, borderColor: colors.border }]}
                        onPress={() => updateMarksEach(type.value, dist.marks_each + 1)}
                      >
                        <Text style={[styles.marksButtonText, { color: type.color }]}>+</Text>
                      </TouchableOpacity>
                      <Text style={[styles.sliderValue, { color: type.color }]}>{dist.marks_each}</Text>
                    </View>
                  </View>
                );
              })}
            </View>

            {/* Learning Outcomes Distribution */}
            <LinearGradient
              colors={['#34C759', '#28A745'] as const}
              style={styles.mapHeader}
            >
              <IconSymbol name="target" size={18} color="#FFFFFF" />
              <Text style={styles.mapTitle}>MAP 2: Learning Outcomes Distribution</Text>
              <View style={styles.loTotalBadge}>
                <Text style={styles.loTotalText}>{getLoTotal()}%</Text>
              </View>
            </LinearGradient>
            <View style={[styles.formSection, { backgroundColor: colors.card }]}>
              <Text style={[styles.formHint, { color: colors.textTertiary, marginBottom: Spacing.md }]}>
                Define what percentage of questions should assess each Learning Outcome
              </Text>
              {DEFAULT_LOS.map((lo, index) => {
                const colors_lo = ['#007AFF', '#5856D6', '#FF9500', '#34C759', '#FF3B30'];
                const color = colors_lo[index % colors_lo.length];
                return (
                  <View key={lo.id} style={styles.loRow}>
                    <View style={styles.loHeader}>
                      <View style={[styles.loBadge, { backgroundColor: color }]}>
                        <Text style={styles.loBadgeText}>{lo.id}</Text>
                      </View>
                      <Text style={[styles.loName, { color: colors.text }]}>{lo.name}</Text>
                      <Text style={[styles.loPercentage, { color }]}>{loDistribution[lo.id]}%</Text>
                    </View>
                    <Slider
                      style={styles.slider}
                      minimumValue={0}
                      maximumValue={100}
                      value={loDistribution[lo.id]}
                      onValueChange={(val: number) => updateLoPercentage(lo.id, val)}
                      minimumTrackTintColor={color}
                      maximumTrackTintColor={colors.border}
                    />
                    <Text style={[styles.loDescription, { color: colors.textTertiary }]}>{lo.description}</Text>
                  </View>
                );
              })}
            </View>

            {/* Rubric Summary */}
            <View style={[styles.summarySection, { backgroundColor: colors.card }]}>
              <Text style={[styles.summaryTitle, { color: colors.text }]}>RUBRIC SUMMARY</Text>
              <View style={styles.summaryGrid}>
                <View style={styles.summaryItem}>
                  <Text style={[styles.summaryLabel, { color: colors.textSecondary }]}>Total Questions:</Text>
                  <Text style={[styles.summaryValue, { color: colors.text }]}>{totalQuestions}</Text>
                </View>
                <View style={styles.summaryItem}>
                  <Text style={[styles.summaryLabel, { color: colors.textSecondary }]}>Total Marks:</Text>
                  <Text style={[styles.summaryValue, { color: colors.text }]}>{totalMarks}</Text>
                </View>
                <View style={styles.summaryItem}>
                  <Text style={[styles.summaryLabel, { color: colors.textSecondary }]}>Duration:</Text>
                  <Text style={[styles.summaryValue, { color: colors.text }]}>{duration} min</Text>
                </View>
                <View style={styles.summaryItem}>
                  <Text style={[styles.summaryLabel, { color: colors.textSecondary }]}>Subject:</Text>
                  <Text style={[styles.summaryValue, { color: colors.text }]}>
                    {selectedSubject?.code || 'None'}
                  </Text>
                </View>
              </View>
            </View>

            {/* Action Buttons */}
            <TouchableOpacity
              style={[styles.saveButton, { backgroundColor: colors.success }]}
              onPress={handleCreateRubric}
              disabled={isCreating}
            >
              {isCreating ? (
                <ActivityIndicator size="small" color="#FFFFFF" />
              ) : (
                <Text style={styles.saveButtonText}>Save Rubric</Text>
              )}
            </TouchableOpacity>
            
            <TouchableOpacity
              style={[styles.cancelButton, { borderColor: colors.border }]}
              onPress={() => setShowCreateModal(false)}
            >
              <Text style={[styles.cancelButtonText, { color: colors.text }]}>Cancel</Text>
            </TouchableOpacity>
            
            <View style={{ height: 50 }} />
              </>
            )}
          </ScrollView>
        </View>
      </Modal>

      {/* Generation Progress Modal */}
      <Modal
        visible={showGenerateModal}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={handleCancelGeneration}
      >
        <View style={[styles.modalContainer, { backgroundColor: colors.background }]}>
          <LinearGradient
            colors={['#4A90D9', '#357ABD'] as const}
            style={styles.modalHeader}
          >
            <TouchableOpacity onPress={handleCancelGeneration}>
              <Text style={styles.modalCancel}>
                {isGenerating ? 'Cancel' : 'Close'}
              </Text>
            </TouchableOpacity>
            <Text style={styles.modalTitle}>Generate Questions</Text>
            <View style={{ width: 50 }} />
          </LinearGradient>

          <ScrollView style={styles.modalContent}>
            {/* Rubric Info */}
            {selectedRubric && (
              <View style={[styles.formSection, { backgroundColor: colors.card }]}>
                <Text style={[styles.formLabel, { color: colors.textSecondary }]}>RUBRIC</Text>
                <Text style={[styles.rubricName, { color: colors.text }]}>{selectedRubric.name}</Text>
                <Text style={[styles.rubricSubject, { color: colors.textSecondary }]}>
                  {selectedRubric.total_questions} Questions • {selectedRubric.total_marks} Marks
                </Text>
              </View>
            )}

            {/* Progress Section */}
            {isGenerating && generationProgress && (
              <View style={[styles.formSection, { backgroundColor: colors.card }]}>
                <Text style={[styles.formLabel, { color: colors.textSecondary }]}>PROGRESS</Text>
                <View style={styles.progressBarContainer}>
                  <Animated.View
                    style={[
                      styles.progressBar,
                      {
                        backgroundColor: colors.primary,
                        width: progressAnim.interpolate({
                          inputRange: [0, 100],
                          outputRange: ['0%', '100%'],
                        }),
                      },
                    ]}
                  />
                </View>
                <Text style={[styles.progressText, { color: colors.text }]}>
                  {generationProgress.message}
                </Text>
                {generationProgress.current_question && generationProgress.total_questions && (
                  <Text style={[styles.progressCount, { color: colors.textSecondary }]}>
                    {generationProgress.current_question} / {generationProgress.total_questions} questions
                  </Text>
                )}
              </View>
            )}

            {/* Generated Questions Preview */}
            {generatedQuestions.length > 0 && (
              <View style={[styles.formSection, { backgroundColor: colors.card }]}>
                <Text style={[styles.formLabel, { color: colors.textSecondary }]}>
                  GENERATED QUESTIONS ({generatedQuestions.length})
                </Text>
                {generatedQuestions.slice(-5).map((q, idx) => (
                  <View key={q.id} style={[styles.questionPreview, idx > 0 && { borderTopWidth: 1, borderTopColor: colors.border }]}>
                    <View style={[styles.questionTypeBadge, { backgroundColor: colors.primary + '20' }]}>
                      <Text style={[styles.questionTypeText, { color: colors.primary }]}>
                        {q.question_type.toUpperCase()}
                      </Text>
                    </View>
                    <Text style={[styles.questionPreviewText, { color: colors.text }]} numberOfLines={2}>
                      {q.question_text}
                    </Text>
                    <Text style={[styles.questionMarks, { color: colors.textSecondary }]}>
                      {q.marks} marks
                    </Text>
                  </View>
                ))}
              </View>
            )}

            {/* Completion Message */}
            {generationProgress?.status === 'complete' && (
              <View style={[styles.completionCard, { backgroundColor: '#E8F5E9' }]}>
                <IconSymbol name="checkmark.circle.fill" size={32} color="#34C759" />
                <Text style={styles.completionTitle}>Generation Complete!</Text>
                <Text style={styles.completionSubtitle}>
                  {generatedQuestions.length} questions are now ready for vetting.
                </Text>
                <TouchableOpacity
                  style={[styles.viewQuestionsButton, { backgroundColor: colors.primary }]}
                  onPress={() => {
                    setShowGenerateModal(false);
                    router.push('/(tabs)/home/vetting');
                  }}
                >
                  <Text style={styles.viewQuestionsButtonText}>View & Vet Questions</Text>
                </TouchableOpacity>
              </View>
            )}

            {/* Start Generation Button */}
            {!isGenerating && generationProgress?.status !== 'complete' && (
              <TouchableOpacity
                style={[styles.startGenerateButton, { backgroundColor: colors.primary }]}
                onPress={handleGenerate}
              >
                <IconSymbol name="sparkles" size={20} color="#FFFFFF" />
                <Text style={styles.startGenerateButtonText}>Start Generation</Text>
              </TouchableOpacity>
            )}

            {/* Loading Indicator while generating */}
            {isGenerating && (
              <View style={styles.generatingIndicator}>
                <ActivityIndicator size="large" color={colors.primary} />
                <Text style={[styles.generatingText, { color: colors.textSecondary }]}>
                  Generating questions using AI...
                </Text>
              </View>
            )}

            <View style={{ height: 50 }} />
          </ScrollView>
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
  infoCard: {
    flexDirection: 'row',
    padding: Spacing.lg,
    borderRadius: BorderRadius.md,
    marginBottom: Spacing.lg,
  },
  infoCardContent: {
    flex: 1,
    marginLeft: Spacing.md,
  },
  infoCardTitle: {
    fontSize: FontSizes.md,
    fontWeight: '600',
    color: '#FFFFFF',
    marginBottom: Spacing.xs,
  },
  infoCardDescription: {
    fontSize: FontSizes.sm,
    color: 'rgba(255, 255, 255, 0.9)',
  },
  createButton: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    padding: Spacing.md,
    borderRadius: BorderRadius.md,
    gap: Spacing.sm,
    marginBottom: Spacing.lg,
  },
  createButtonText: {
    fontSize: FontSizes.md,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  section: {
    marginBottom: Spacing.lg,
  },
  sectionTitle: {
    fontSize: FontSizes.xs,
    fontWeight: '600',
    marginBottom: Spacing.sm,
  },
  rubricsList: {
    borderRadius: BorderRadius.md,
    overflow: 'hidden',
  },
  rubricCard: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: Spacing.md,
    borderBottomWidth: 0.5,
    borderBottomColor: '#E5E5EA',
  },
  rubricCardContent: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
  },
  generateIconButton: {
    width: 36,
    height: 36,
    borderRadius: 18,
    justifyContent: 'center',
    alignItems: 'center',
    marginLeft: Spacing.sm,
  },
  rubricIcon: {
    width: 44,
    height: 44,
    borderRadius: BorderRadius.sm,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: Spacing.md,
  },
  rubricInfo: {
    flex: 1,
  },
  rubricName: {
    fontSize: FontSizes.md,
    fontWeight: '600',
    marginBottom: Spacing.xs,
  },
  rubricSubject: {
    fontSize: FontSizes.sm,
  },
  emptyText: {
    padding: Spacing.lg,
    textAlign: 'center',
    fontSize: FontSizes.md,
  },
  generateButton: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    padding: Spacing.md,
    borderRadius: BorderRadius.md,
    gap: Spacing.sm,
  },
  generateButtonText: {
    fontSize: FontSizes.md,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  modalContainer: {
    flex: 1,
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingTop: 20,
    paddingBottom: Spacing.lg,
    paddingHorizontal: Spacing.lg,
  },
  modalTitle: {
    fontSize: FontSizes.lg,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  modalCancel: {
    fontSize: FontSizes.lg,
    color: '#FFFFFF',
  },
  modalContent: {
    flex: 1,
  },
  formSection: {
    padding: Spacing.lg,
    marginHorizontal: Spacing.lg,
    marginBottom: Spacing.md,
    borderRadius: BorderRadius.md,
  },
  formLabel: {
    fontSize: FontSizes.xs,
    fontWeight: '600',
    marginBottom: Spacing.sm,
  },
  formHint: {
    fontSize: FontSizes.xs,
    marginTop: Spacing.xs,
  },
  textInput: {
    fontSize: FontSizes.md,
    paddingVertical: Spacing.sm,
    paddingHorizontal: Spacing.md,
    borderWidth: 1,
    borderRadius: BorderRadius.sm,
  },
  selectContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: Spacing.sm,
    paddingHorizontal: Spacing.md,
    borderWidth: 1,
    borderRadius: BorderRadius.sm,
  },
  selectText: {
    fontSize: FontSizes.md,
  },
  examTypesGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.sm,
  },
  examTypeButton: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: Spacing.sm,
    paddingHorizontal: Spacing.md,
    borderWidth: 1,
    borderRadius: BorderRadius.sm,
    gap: Spacing.xs,
  },
  examTypeLabel: {
    fontSize: FontSizes.sm,
    fontWeight: '500',
  },
  mapHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: Spacing.md,
    paddingHorizontal: Spacing.lg,
    marginHorizontal: Spacing.lg,
    marginTop: Spacing.md,
    borderTopLeftRadius: BorderRadius.md,
    borderTopRightRadius: BorderRadius.md,
    gap: Spacing.sm,
  },
  mapTitle: {
    flex: 1,
    fontSize: FontSizes.md,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  loTotalBadge: {
    backgroundColor: 'rgba(255, 255, 255, 0.2)',
    paddingHorizontal: Spacing.sm,
    paddingVertical: Spacing.xs,
    borderRadius: BorderRadius.sm,
  },
  loTotalText: {
    fontSize: FontSizes.sm,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  questionTypeRow: {
    marginBottom: Spacing.lg,
  },
  questionTypeHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: Spacing.sm,
  },
  questionTypeLabel: {
    fontSize: FontSizes.md,
    fontWeight: '600',
  },
  marksLabel: {
    fontSize: FontSizes.md,
    fontWeight: '600',
  },
  sliderRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  sliderLabel: {
    fontSize: FontSizes.sm,
    width: 50,
  },
  slider: {
    flex: 1,
    height: 40,
  },
  sliderValue: {
    fontSize: FontSizes.md,
    fontWeight: '600',
    width: 40,
    textAlign: 'right',
  },
  marksButton: {
    width: 36,
    height: 36,
    borderRadius: BorderRadius.sm,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1,
    marginHorizontal: Spacing.xs,
  },
  marksButtonText: {
    fontSize: 20,
    fontWeight: '600',
  },
  marksInput: {
    width: 50,
    height: 36,
    borderRadius: BorderRadius.sm,
    borderWidth: 1,
    textAlign: 'center',
    fontSize: FontSizes.md,
    fontWeight: '600',
  },
  loRow: {
    marginBottom: Spacing.lg,
  },
  loHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: Spacing.xs,
  },
  loBadge: {
    paddingHorizontal: Spacing.sm,
    paddingVertical: Spacing.xs,
    borderRadius: BorderRadius.sm,
    marginRight: Spacing.sm,
  },
  loBadgeText: {
    fontSize: FontSizes.xs,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  loName: {
    flex: 1,
    fontSize: FontSizes.md,
    fontWeight: '500',
  },
  loPercentage: {
    fontSize: FontSizes.md,
    fontWeight: '700',
  },
  loDescription: {
    fontSize: FontSizes.xs,
    marginTop: Spacing.xs,
  },
  summarySection: {
    padding: Spacing.lg,
    marginHorizontal: Spacing.lg,
    marginTop: Spacing.md,
    borderRadius: BorderRadius.md,
  },
  summaryTitle: {
    fontSize: FontSizes.sm,
    fontWeight: '700',
    marginBottom: Spacing.md,
  },
  summaryGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
  },
  summaryItem: {
    width: '50%',
    marginBottom: Spacing.sm,
  },
  summaryLabel: {
    fontSize: FontSizes.sm,
  },
  summaryValue: {
    fontSize: FontSizes.md,
    fontWeight: '700',
  },
  saveButton: {
    marginHorizontal: Spacing.lg,
    marginTop: Spacing.lg,
    padding: Spacing.md,
    borderRadius: BorderRadius.md,
    alignItems: 'center',
  },
  saveButtonText: {
    fontSize: FontSizes.md,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  cancelButton: {
    marginHorizontal: Spacing.lg,
    marginTop: Spacing.md,
    padding: Spacing.md,
    borderRadius: BorderRadius.md,
    alignItems: 'center',
    borderWidth: 1,
  },
  cancelButtonText: {
    fontSize: FontSizes.md,
    fontWeight: '500',
  },
  // Generation Modal Styles
  progressBarContainer: {
    height: 8,
    backgroundColor: '#E5E5EA',
    borderRadius: 4,
    overflow: 'hidden',
    marginBottom: Spacing.sm,
  },
  progressBar: {
    height: '100%',
    borderRadius: 4,
  },
  progressText: {
    fontSize: FontSizes.sm,
    marginTop: Spacing.xs,
  },
  progressCount: {
    fontSize: FontSizes.xs,
    marginTop: Spacing.xs,
  },
  questionPreview: {
    paddingVertical: Spacing.sm,
  },
  questionTypeBadge: {
    alignSelf: 'flex-start',
    paddingHorizontal: Spacing.sm,
    paddingVertical: 2,
    borderRadius: BorderRadius.sm,
    marginBottom: Spacing.xs,
  },
  questionTypeText: {
    fontSize: FontSizes.xs,
    fontWeight: '600',
  },
  questionPreviewText: {
    fontSize: FontSizes.sm,
    lineHeight: 20,
  },
  questionMarks: {
    fontSize: FontSizes.xs,
    marginTop: 4,
  },
  completionCard: {
    padding: Spacing.xl,
    marginHorizontal: Spacing.lg,
    borderRadius: BorderRadius.lg,
    alignItems: 'center',
    marginTop: Spacing.md,
  },
  completionTitle: {
    fontSize: FontSizes.lg,
    fontWeight: '700',
    color: '#1B5E20',
    marginTop: Spacing.sm,
  },
  completionSubtitle: {
    fontSize: FontSizes.sm,
    color: '#388E3C',
    marginTop: Spacing.xs,
    textAlign: 'center',
  },
  viewQuestionsButton: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.md,
    marginTop: Spacing.md,
  },
  viewQuestionsButtonText: {
    color: '#FFFFFF',
    fontWeight: '600',
    fontSize: FontSizes.md,
  },
  startGenerateButton: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    marginHorizontal: Spacing.lg,
    marginTop: Spacing.lg,
    padding: Spacing.md,
    borderRadius: BorderRadius.md,
    gap: Spacing.sm,
  },
  startGenerateButtonText: {
    color: '#FFFFFF',
    fontWeight: '600',
    fontSize: FontSizes.md,
  },
  generatingIndicator: {
    alignItems: 'center',
    padding: Spacing.xl,
  },
  generatingText: {
    fontSize: FontSizes.sm,
    marginTop: Spacing.md,
  },
  // Inline Subject Picker Styles
  inlinePickerContainer: {
    flex: 1,
    minHeight: '100%',
  },
  inlinePickerHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: Spacing.lg,
    borderBottomWidth: 1,
  },
  inlinePickerTitle: {
    fontSize: FontSizes.lg,
    fontWeight: '600',
  },
  inlinePickerList: {
    flex: 1,
  },
  emptySubjectsList: {
    padding: Spacing.xl,
    alignItems: 'center',
    marginTop: Spacing.xl,
  },
  emptySubjectsText: {
    fontSize: FontSizes.md,
    textAlign: 'center',
    marginTop: Spacing.md,
    fontWeight: '600',
  },
  emptySubjectsHint: {
    fontSize: FontSizes.sm,
    textAlign: 'center',
    marginTop: Spacing.xs,
  },
  inlinePickerItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: Spacing.lg,
    borderBottomWidth: 1,
  },
  inlinePickerItemContent: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  inlinePickerItemIcon: {
    width: 44,
    height: 44,
    borderRadius: BorderRadius.sm,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: Spacing.md,
  },
  inlinePickerItemText: {
    flex: 1,
  },
  inlinePickerItemTitle: {
    fontSize: FontSizes.md,
    fontWeight: '600',
    marginBottom: 2,
  },
  inlinePickerItemSubtitle: {
    fontSize: FontSizes.sm,
  },
});
