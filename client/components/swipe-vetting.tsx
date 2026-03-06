/**
 * SwipeVetting - Tinder-like swipe UI for vetting questions
 * 
 * Gestures:
 * - Left swipe: Reject & Regenerate
 * - Right swipe: Approve
 * - Up swipe: Edit
 * - Down swipe: Skip
 */

import React, { useState, useCallback, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Dimensions,
  Modal,
  TouchableOpacity,
  ScrollView,
  TextInput,
  ActivityIndicator,
  Animated,
  PanResponder,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { BlurView } from 'expo-blur';
import { LinearGradient } from 'expo-linear-gradient';

import { GlassCard } from '@/components/ui/glass-card';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { Colors, Spacing, BorderRadius, FontSizes } from '@/constants/theme';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { useToast } from '@/components/toast';
import {
  vetterService,
  QuestionForVetting,
  VetterUpdateQuestionRequest,
} from '@/services/vetter.service';

const { width: SCREEN_WIDTH, height: SCREEN_HEIGHT } = Dimensions.get('window');
const SWIPE_THRESHOLD = 120;
const SWIPE_OUT_DURATION = 250;

// Course Outcome levels
const CO_LEVELS = [
  { level: 1, label: 'Basic', color: '#34C759' },
  { level: 2, label: 'Intermediate', color: '#FF9500' },
  { level: 3, label: 'Advanced', color: '#FF3B30' },
];
const COURSE_OUTCOMES = ['CO1', 'CO2', 'CO3', 'CO4', 'CO5'];

// Rejection reasons
const REJECTION_REASONS = [
  { id: 'duplicate', label: 'Duplicate question', desc: 'Similar question already exists' },
  { id: 'off_topic', label: 'Off topic', desc: 'Not relevant to the subject' },
  { id: 'too_easy', label: 'Too easy', desc: 'Below expected difficulty' },
  { id: 'too_hard', label: 'Too hard', desc: 'Above expected difficulty' },
  { id: 'unclear', label: 'Unclear wording', desc: 'Question is confusing' },
  { id: 'incorrect_answer', label: 'Incorrect answer', desc: 'The answer key is wrong' },
  { id: 'poor_options', label: 'Poor MCQ options', desc: 'Options need improvement' },
  { id: 'needs_improvement', label: 'Needs improvement', desc: 'General improvements needed' },
];

interface SwipeVettingProps {
  visible: boolean;
  onClose: () => void;
  questions: QuestionForVetting[];
  onQuestionVetted: (questionId: string, status: 'approved' | 'rejected' | 'skipped') => void;
  onQuestionUpdated: (questionId: string, updates: Partial<QuestionForVetting>) => void;
}

type SwipeDirection = 'left' | 'right' | 'up' | 'down' | null;

export function SwipeVetting({
  visible,
  onClose,
  questions,
  onQuestionVetted,
  onQuestionUpdated,
}: SwipeVettingProps) {
  const colorScheme = useColorScheme();
  const colors = Colors[colorScheme ?? 'light'];
  const isDark = colorScheme === 'dark';
  const { showSuccess, showError } = useToast();

  const [currentIndex, setCurrentIndex] = useState(0);
  const [isProcessing, setIsProcessing] = useState(false);
  
  // Edit mode state
  const [showEditPanel, setShowEditPanel] = useState(false);
  const [editData, setEditData] = useState<VetterUpdateQuestionRequest>({});
  const [coMappings, setCoMappings] = useState<Record<string, number>>({});

  // Rejection modal state
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [selectedReasons, setSelectedReasons] = useState<string[]>([]);
  const [rejectNotes, setRejectNotes] = useState('');

  // Swipe animation
  const position = useRef(new Animated.ValueXY()).current;
  const [swipeDirection, setSwipeDirection] = useState<SwipeDirection>(null);

  const currentQuestion = questions[currentIndex];

  // Reset edit state when question changes
  const resetEditState = useCallback(() => {
    if (currentQuestion) {
      setEditData({
        marks: currentQuestion.marks ?? undefined,
        difficulty_level: currentQuestion.difficulty_level ?? undefined,
        correct_answer: currentQuestion.correct_answer ?? undefined,
        question_text: currentQuestion.question_text,
        course_outcome_mapping: currentQuestion.course_outcome_mapping ?? undefined,
      });
      setCoMappings(currentQuestion.course_outcome_mapping || {});
    }
  }, [currentQuestion]);

  React.useEffect(() => {
    resetEditState();
  }, [currentIndex, resetEditState]);

  const panResponder = useRef(
    PanResponder.create({
      onStartShouldSetPanResponder: () => !showEditPanel && !showRejectModal,
      onMoveShouldSetPanResponder: () => !showEditPanel && !showRejectModal,
      onPanResponderMove: (_, gesture) => {
        position.setValue({ x: gesture.dx, y: gesture.dy });
        
        // Determine swipe direction hint
        if (Math.abs(gesture.dx) > Math.abs(gesture.dy)) {
          setSwipeDirection(gesture.dx > 50 ? 'right' : gesture.dx < -50 ? 'left' : null);
        } else {
          setSwipeDirection(gesture.dy < -50 ? 'up' : gesture.dy > 50 ? 'down' : null);
        }
      },
      onPanResponderRelease: (_, gesture) => {
        // Check horizontal swipe
        if (gesture.dx > SWIPE_THRESHOLD) {
          swipeOut('right');
        } else if (gesture.dx < -SWIPE_THRESHOLD) {
          swipeOut('left');
        }
        // Check vertical swipe
        else if (gesture.dy < -SWIPE_THRESHOLD) {
          handleUpSwipe();
        } else if (gesture.dy > SWIPE_THRESHOLD) {
          handleDownSwipe();
        } else {
          resetPosition();
        }
        setSwipeDirection(null);
      },
    })
  ).current;

  const resetPosition = useCallback(() => {
    Animated.spring(position, {
      toValue: { x: 0, y: 0 },
      useNativeDriver: false,
      friction: 5,
    }).start();
  }, [position]);

  const swipeOut = useCallback((direction: 'left' | 'right') => {
    const x = direction === 'right' ? SCREEN_WIDTH + 100 : -SCREEN_WIDTH - 100;
    Animated.timing(position, {
      toValue: { x, y: 0 },
      duration: SWIPE_OUT_DURATION,
      useNativeDriver: false,
    }).start(() => {
      if (direction === 'right') {
        handleApprove();
      } else {
        setShowRejectModal(true);
        resetPosition();
      }
    });
  }, [position]);

  const handleUpSwipe = useCallback(() => {
    Animated.timing(position, {
      toValue: { x: 0, y: -100 },
      duration: 200,
      useNativeDriver: false,
    }).start(() => {
      setShowEditPanel(true);
      resetPosition();
    });
  }, [position, resetPosition]);

  const handleDownSwipe = useCallback(() => {
    Animated.timing(position, {
      toValue: { x: 0, y: 100 },
      duration: 200,
      useNativeDriver: false,
    }).start(() => {
      handleSkip();
      resetPosition();
    });
  }, [position, resetPosition]);

  const handleApprove = async () => {
    if (!currentQuestion || isProcessing) return;
    
    setIsProcessing(true);
    try {
      await vetterService.vetQuestion(currentQuestion.id, {
        status: 'approved',
        course_outcome_mapping: Object.keys(coMappings).length > 0 ? coMappings : undefined,
      });
      showSuccess('Question approved!');
      onQuestionVetted(currentQuestion.id, 'approved');
      moveToNext();
    } catch (err) {
      showError('Failed to approve question');
      console.error(err);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleReject = async () => {
    if (!currentQuestion || isProcessing) return;
    
    setIsProcessing(true);
    try {
      await vetterService.vetQuestion(currentQuestion.id, {
        status: 'rejected',
        notes: rejectNotes || undefined,
        rejection_reasons: selectedReasons.length > 0 ? selectedReasons : undefined,
      });
      showSuccess('Question rejected & regeneration queued');
      onQuestionVetted(currentQuestion.id, 'rejected');
      setShowRejectModal(false);
      setSelectedReasons([]);
      setRejectNotes('');
      moveToNext();
    } catch (err) {
      showError('Failed to reject question');
      console.error(err);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleSkip = () => {
    if (!currentQuestion) return;
    onQuestionVetted(currentQuestion.id, 'skipped');
    moveToNext();
  };

  const handleSaveEdits = async () => {
    if (!currentQuestion || isProcessing) return;
    
    setIsProcessing(true);
    try {
      const updates: VetterUpdateQuestionRequest = {
        ...editData,
        course_outcome_mapping: Object.keys(coMappings).length > 0 ? coMappings : undefined,
      };
      
      await vetterService.updateQuestion(currentQuestion.id, updates);
      showSuccess('Question updated!');
      onQuestionUpdated(currentQuestion.id, updates as Partial<QuestionForVetting>);
      setShowEditPanel(false);
    } catch (err) {
      showError('Failed to update question');
      console.error(err);
    } finally {
      setIsProcessing(false);
    }
  };

  const moveToNext = () => {
    position.setValue({ x: 0, y: 0 });
    if (currentIndex < questions.length - 1) {
      setCurrentIndex(currentIndex + 1);
    } else {
      // All questions done
      showSuccess('All questions reviewed!');
      onClose();
    }
  };

  const toggleRejectReason = (reasonId: string) => {
    setSelectedReasons((prev) =>
      prev.includes(reasonId) ? prev.filter((r) => r !== reasonId) : [...prev, reasonId]
    );
  };

  const updateCoMapping = (co: string, level: number) => {
    setCoMappings((prev) => ({
      ...prev,
      [co]: prev[co] === level ? 0 : level, // Toggle off if same level
    }));
  };

  // Card rotation based on swipe
  const rotate = position.x.interpolate({
    inputRange: [-SCREEN_WIDTH / 2, 0, SCREEN_WIDTH / 2],
    outputRange: ['-10deg', '0deg', '10deg'],
    extrapolate: 'clamp',
  });

  const cardStyle = {
    transform: [
      { translateX: position.x },
      { translateY: position.y },
      { rotate },
    ],
  };

  // Swipe indicator opacity
  const approveOpacity = position.x.interpolate({
    inputRange: [0, SWIPE_THRESHOLD],
    outputRange: [0, 1],
    extrapolate: 'clamp',
  });

  const rejectOpacity = position.x.interpolate({
    inputRange: [-SWIPE_THRESHOLD, 0],
    outputRange: [1, 0],
    extrapolate: 'clamp',
  });

  const editOpacity = position.y.interpolate({
    inputRange: [-SWIPE_THRESHOLD, 0],
    outputRange: [1, 0],
    extrapolate: 'clamp',
  });

  const skipOpacity = position.y.interpolate({
    inputRange: [0, SWIPE_THRESHOLD],
    outputRange: [0, 1],
    extrapolate: 'clamp',
  });

  if (!visible) return null;

  return (
    <Modal visible={visible} animationType="slide" presentationStyle="fullScreen">
      <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]}>
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity onPress={onClose} style={styles.closeButton}>
            <IconSymbol name="xmark" size={24} color={colors.text} />
          </TouchableOpacity>
          <View style={styles.headerCenter}>
            <Text style={[styles.headerTitle, { color: colors.text }]}>Vetting Mode</Text>
            <Text style={[styles.headerSubtitle, { color: colors.textSecondary }]}>
              {currentIndex + 1} of {questions.length}
            </Text>
          </View>
          <View style={styles.progressContainer}>
            <View
              style={[
                styles.progressBar,
                { backgroundColor: colors.border },
              ]}
            >
              <View
                style={[
                  styles.progressFill,
                  {
                    backgroundColor: colors.primary,
                    width: `${((currentIndex + 1) / questions.length) * 100}%`,
                  },
                ]}
              />
            </View>
          </View>
        </View>

        {/* Swipe Instructions */}
        <View style={styles.instructionsRow}>
          <View style={styles.instructionItem}>
            <IconSymbol name="arrow.left" size={16} color={colors.error} />
            <Text style={[styles.instructionText, { color: colors.textSecondary }]}>Reject</Text>
          </View>
          <View style={styles.instructionItem}>
            <IconSymbol name="arrow.up" size={16} color={colors.primary} />
            <Text style={[styles.instructionText, { color: colors.textSecondary }]}>Edit</Text>
          </View>
          <View style={styles.instructionItem}>
            <IconSymbol name="arrow.down" size={16} color={colors.warning} />
            <Text style={[styles.instructionText, { color: colors.textSecondary }]}>Skip</Text>
          </View>
          <View style={styles.instructionItem}>
            <IconSymbol name="arrow.right" size={16} color={colors.success} />
            <Text style={[styles.instructionText, { color: colors.textSecondary }]}>Approve</Text>
          </View>
        </View>

        {/* Card Stack */}
        <View style={styles.cardContainer}>
          {/* Swipe Indicators */}
          <Animated.View style={[styles.swipeIndicator, styles.approveIndicator, { opacity: approveOpacity }]}>
            <LinearGradient colors={['#34C759', '#30B350']} style={styles.indicatorGradient}>
              <IconSymbol name="checkmark" size={48} color="#FFFFFF" />
              <Text style={styles.indicatorText}>APPROVE</Text>
            </LinearGradient>
          </Animated.View>

          <Animated.View style={[styles.swipeIndicator, styles.rejectIndicator, { opacity: rejectOpacity }]}>
            <LinearGradient colors={['#FF3B30', '#D63D2F']} style={styles.indicatorGradient}>
              <IconSymbol name="xmark" size={48} color="#FFFFFF" />
              <Text style={styles.indicatorText}>REJECT</Text>
            </LinearGradient>
          </Animated.View>

          <Animated.View style={[styles.swipeIndicator, styles.editIndicator, { opacity: editOpacity }]}>
            <LinearGradient colors={['#5856D6', '#4A4ADE']} style={styles.indicatorGradient}>
              <IconSymbol name="pencil" size={48} color="#FFFFFF" />
              <Text style={styles.indicatorText}>EDIT</Text>
            </LinearGradient>
          </Animated.View>

          <Animated.View style={[styles.swipeIndicator, styles.skipIndicator, { opacity: skipOpacity }]}>
            <LinearGradient colors={['#FF9500', '#FF8000']} style={styles.indicatorGradient}>
              <IconSymbol name="arrow.uturn.right" size={48} color="#FFFFFF" />
              <Text style={styles.indicatorText}>SKIP</Text>
            </LinearGradient>
          </Animated.View>

          {/* Question Card */}
          {currentQuestion && (
            <Animated.View
              style={[styles.card, cardStyle]}
              {...panResponder.panHandlers}
            >
              <GlassCard style={[styles.cardContent, { backgroundColor: colors.card }]}>
                {/* Question type badge */}
                <View style={styles.cardHeader}>
                  <View style={[styles.typeBadge, { backgroundColor: colors.primary + '20' }]}>
                    <Text style={[styles.typeBadgeText, { color: colors.primary }]}>
                      {currentQuestion.question_type.replace('_', ' ').toUpperCase()}
                    </Text>
                  </View>
                  <View style={styles.metaBadges}>
                    {currentQuestion.difficulty_level && (
                      <View style={[styles.metaBadge, { backgroundColor: colors.border }]}>
                        <Text style={[styles.metaBadgeText, { color: colors.text }]}>
                          {currentQuestion.difficulty_level}
                        </Text>
                      </View>
                    )}
                    {currentQuestion.marks && (
                      <View style={[styles.metaBadge, { backgroundColor: colors.border }]}>
                        <Text style={[styles.metaBadgeText, { color: colors.text }]}>
                          {currentQuestion.marks} marks
                        </Text>
                      </View>
                    )}
                  </View>
                </View>

                {/* Subject/Topic info */}
                {(currentQuestion.subject_name || currentQuestion.topic_name) && (
                  <View style={styles.subjectRow}>
                    {currentQuestion.subject_name && (
                      <Text style={[styles.subjectText, { color: colors.textSecondary }]}>
                        {currentQuestion.subject_code || currentQuestion.subject_name}
                      </Text>
                    )}
                    {currentQuestion.topic_name && (
                      <Text style={[styles.topicText, { color: colors.textSecondary }]}>
                        • {currentQuestion.topic_name}
                      </Text>
                    )}
                  </View>
                )}

                {/* Question text */}
                <ScrollView style={styles.questionScroll} showsVerticalScrollIndicator={false}>
                  <Text style={[styles.questionText, { color: colors.text }]}>
                    {currentQuestion.question_text}
                  </Text>

                  {/* MCQ Options */}
                  {currentQuestion.question_type === 'mcq' && currentQuestion.options && (
                    <View style={styles.optionsContainer}>
                      {currentQuestion.options.map((option, idx) => {
                        const isCorrect = option === currentQuestion.correct_answer ||
                          option.startsWith(currentQuestion.correct_answer || '');
                        return (
                          <View
                            key={idx}
                            style={[
                              styles.optionRow,
                              isCorrect && { backgroundColor: colors.success + '15' },
                            ]}
                          >
                            <View
                              style={[
                                styles.optionLetter,
                                { backgroundColor: isCorrect ? colors.success : colors.border },
                              ]}
                            >
                              <Text
                                style={[
                                  styles.optionLetterText,
                                  { color: isCorrect ? '#fff' : colors.textSecondary },
                                ]}
                              >
                                {String.fromCharCode(65 + idx)}
                              </Text>
                            </View>
                            <Text
                              style={[
                                styles.optionText,
                                { color: isCorrect ? colors.success : colors.text },
                              ]}
                            >
                              {option}
                            </Text>
                            {isCorrect && (
                              <IconSymbol name="checkmark.circle.fill" size={18} color={colors.success} />
                            )}
                          </View>
                        );
                      })}
                    </View>
                  )}

                  {/* Short/Long answer */}
                  {currentQuestion.question_type !== 'mcq' && currentQuestion.correct_answer && (
                    <View style={[styles.answerBox, { backgroundColor: colors.success + '10', borderColor: colors.success }]}>
                      <Text style={[styles.answerLabel, { color: colors.success }]}>Expected Answer:</Text>
                      <Text style={[styles.answerText, { color: colors.text }]}>
                        {currentQuestion.correct_answer}
                      </Text>
                    </View>
                  )}

                  {/* Explanation */}
                  {currentQuestion.explanation && (
                    <View style={[styles.explanationBox, { backgroundColor: colors.primary + '10' }]}>
                      <Text style={[styles.explanationLabel, { color: colors.primary }]}>Explanation:</Text>
                      <Text style={[styles.explanationText, { color: colors.text }]}>
                        {currentQuestion.explanation}
                      </Text>
                    </View>
                  )}
                </ScrollView>

                {/* Teacher info */}
                {currentQuestion.teacher_name && (
                  <View style={styles.teacherRow}>
                    <IconSymbol name="person.fill" size={14} color={colors.textSecondary} />
                    <Text style={[styles.teacherText, { color: colors.textSecondary }]}>
                      {currentQuestion.teacher_name}
                    </Text>
                  </View>
                )}
              </GlassCard>
            </Animated.View>
          )}

          {/* Loading overlay */}
          {isProcessing && (
            <View style={styles.processingOverlay}>
              <BlurView intensity={80} tint={isDark ? 'dark' : 'light'} style={styles.processingBlur}>
                <ActivityIndicator size="large" color={colors.primary} />
                <Text style={[styles.processingText, { color: colors.primary }]}>Processing...</Text>
              </BlurView>
            </View>
          )}
        </View>

        {/* Quick Action Buttons */}
        <View style={styles.actionButtonsRow}>
          <TouchableOpacity
            style={[styles.actionButton, { backgroundColor: colors.error + '20' }]}
            onPress={() => setShowRejectModal(true)}
            disabled={isProcessing}
          >
            <IconSymbol name="xmark" size={28} color={colors.error} />
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.actionButton, { backgroundColor: colors.warning + '20' }]}
            onPress={handleSkip}
            disabled={isProcessing}
          >
            <IconSymbol name="arrow.uturn.right" size={28} color={colors.warning} />
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.actionButton, { backgroundColor: colors.primary + '20' }]}
            onPress={() => setShowEditPanel(true)}
            disabled={isProcessing}
          >
            <IconSymbol name="pencil" size={28} color={colors.primary} />
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.actionButton, { backgroundColor: colors.success + '20' }]}
            onPress={handleApprove}
            disabled={isProcessing}
          >
            <IconSymbol name="checkmark" size={28} color={colors.success} />
          </TouchableOpacity>
        </View>

        {/* Edit Panel Modal */}
        <Modal
          visible={showEditPanel}
          animationType="slide"
          presentationStyle="pageSheet"
          onRequestClose={() => setShowEditPanel(false)}
        >
          <SafeAreaView style={[styles.editContainer, { backgroundColor: colors.background }]}>
            <View style={styles.editHeader}>
              <TouchableOpacity onPress={() => setShowEditPanel(false)}>
                <Text style={[styles.cancelText, { color: colors.textSecondary }]}>Cancel</Text>
              </TouchableOpacity>
              <Text style={[styles.editTitle, { color: colors.text }]}>Edit Question</Text>
              <TouchableOpacity onPress={handleSaveEdits} disabled={isProcessing}>
                {isProcessing ? (
                  <ActivityIndicator size="small" color={colors.primary} />
                ) : (
                  <Text style={[styles.saveText, { color: colors.primary }]}>Save</Text>
                )}
              </TouchableOpacity>
            </View>

            <ScrollView style={styles.editContent} showsVerticalScrollIndicator={false}>
              {/* Marks */}
              <View style={styles.editSection}>
                <Text style={[styles.editLabel, { color: colors.text }]}>Marks</Text>
                <View style={styles.marksRow}>
                  <TouchableOpacity
                    style={[styles.marksButton, { backgroundColor: colors.border }]}
                    onPress={() => setEditData((prev) => ({ ...prev, marks: Math.max(1, (prev.marks || 1) - 1) }))}
                  >
                    <IconSymbol name="minus" size={16} color={colors.text} />
                  </TouchableOpacity>
                  <TextInput
                    style={[styles.marksInput, { color: colors.text, borderColor: colors.border }]}
                    value={String(editData.marks || 1)}
                    onChangeText={(v) => setEditData((prev) => ({ ...prev, marks: parseInt(v) || 1 }))}
                    keyboardType="numeric"
                  />
                  <TouchableOpacity
                    style={[styles.marksButton, { backgroundColor: colors.border }]}
                    onPress={() => setEditData((prev) => ({ ...prev, marks: (prev.marks || 1) + 1 }))}
                  >
                    <IconSymbol name="plus" size={16} color={colors.text} />
                  </TouchableOpacity>
                </View>
              </View>

              {/* Difficulty */}
              <View style={styles.editSection}>
                <Text style={[styles.editLabel, { color: colors.text }]}>Difficulty</Text>
                <View style={styles.difficultyRow}>
                  {['easy', 'medium', 'hard'].map((diff) => (
                    <TouchableOpacity
                      key={diff}
                      style={[
                        styles.difficultyButton,
                        {
                          borderColor:
                            diff === 'easy' ? '#34C759' : diff === 'medium' ? '#FF9500' : '#FF3B30',
                          backgroundColor:
                            editData.difficulty_level === diff
                              ? diff === 'easy'
                                ? '#34C759'
                                : diff === 'medium'
                                ? '#FF9500'
                                : '#FF3B30'
                              : 'transparent',
                        },
                      ]}
                      onPress={() => setEditData((prev) => ({ ...prev, difficulty_level: diff }))}
                    >
                      <Text
                        style={[
                          styles.difficultyText,
                          {
                            color:
                              editData.difficulty_level === diff
                                ? '#fff'
                                : diff === 'easy'
                                ? '#34C759'
                                : diff === 'medium'
                                ? '#FF9500'
                                : '#FF3B30',
                          },
                        ]}
                      >
                        {diff.charAt(0).toUpperCase() + diff.slice(1)}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </View>

              {/* Course Outcome Mapping */}
              <View style={styles.editSection}>
                <LinearGradient
                  colors={['#5856D6', '#4A4ADE']}
                  style={styles.sectionHeader}
                >
                  <IconSymbol name="list.number" size={16} color="#FFFFFF" />
                  <Text style={styles.sectionHeaderText}>Course Outcome Mapping</Text>
                </LinearGradient>
                
                <View style={styles.coGrid}>
                  {COURSE_OUTCOMES.map((co) => (
                    <View key={co} style={styles.coRow}>
                      <Text style={[styles.coLabel, { color: colors.text }]}>{co}</Text>
                      <View style={styles.coLevels}>
                        {CO_LEVELS.map(({ level, label, color }) => (
                          <TouchableOpacity
                            key={level}
                            style={[
                              styles.coLevelButton,
                              {
                                borderColor: color,
                                backgroundColor: coMappings[co] === level ? color : 'transparent',
                              },
                            ]}
                            onPress={() => updateCoMapping(co, level)}
                          >
                            <Text
                              style={[
                                styles.coLevelText,
                                { color: coMappings[co] === level ? '#fff' : color },
                              ]}
                            >
                              {label}
                            </Text>
                          </TouchableOpacity>
                        ))}
                      </View>
                    </View>
                  ))}
                </View>
              </View>

              {/* Answer Edit */}
              <View style={styles.editSection}>
                <Text style={[styles.editLabel, { color: colors.text }]}>Answer</Text>
                <TextInput
                  style={[
                    styles.answerInput,
                    { color: colors.text, borderColor: colors.border, backgroundColor: colors.card },
                  ]}
                  value={editData.correct_answer || ''}
                  onChangeText={(v) => setEditData((prev) => ({ ...prev, correct_answer: v }))}
                  placeholder="Enter expected answer..."
                  placeholderTextColor={colors.textSecondary}
                  multiline
                />
              </View>
            </ScrollView>
          </SafeAreaView>
        </Modal>

        {/* Rejection Modal */}
        <Modal
          visible={showRejectModal}
          animationType="fade"
          transparent
          onRequestClose={() => setShowRejectModal(false)}
        >
          <View style={styles.rejectModalOverlay}>
            <View style={[styles.rejectModalContent, { backgroundColor: colors.card }]}>
              <View style={styles.rejectModalHeader}>
                <Text style={[styles.rejectModalTitle, { color: colors.text }]}>Reject Question</Text>
                <TouchableOpacity onPress={() => setShowRejectModal(false)}>
                  <IconSymbol name="xmark.circle.fill" size={24} color={colors.textSecondary} />
                </TouchableOpacity>
              </View>

              <Text style={[styles.rejectModalSubtitle, { color: colors.textSecondary }]}>
                Select rejection reasons (optional)
              </Text>

              <ScrollView style={styles.reasonsList}>
                {REJECTION_REASONS.map((reason) => {
                  const isSelected = selectedReasons.includes(reason.id);
                  return (
                    <TouchableOpacity
                      key={reason.id}
                      style={[
                        styles.reasonItem,
                        {
                          borderColor: isSelected ? colors.error : colors.border,
                          backgroundColor: isSelected ? colors.error + '10' : 'transparent',
                        },
                      ]}
                      onPress={() => toggleRejectReason(reason.id)}
                    >
                      <View
                        style={[
                          styles.reasonCheckbox,
                          {
                            borderColor: isSelected ? colors.error : colors.border,
                            backgroundColor: isSelected ? colors.error : 'transparent',
                          },
                        ]}
                      >
                        {isSelected && <IconSymbol name="checkmark" size={12} color="#fff" />}
                      </View>
                      <View style={styles.reasonContent}>
                        <Text style={[styles.reasonLabel, { color: colors.text }]}>{reason.label}</Text>
                        <Text style={[styles.reasonDesc, { color: colors.textSecondary }]}>
                          {reason.desc}
                        </Text>
                      </View>
                    </TouchableOpacity>
                  );
                })}
              </ScrollView>

              <TextInput
                style={[
                  styles.rejectNotesInput,
                  { color: colors.text, borderColor: colors.border, backgroundColor: colors.background },
                ]}
                value={rejectNotes}
                onChangeText={setRejectNotes}
                placeholder="Additional notes (optional)..."
                placeholderTextColor={colors.textSecondary}
                multiline
              />

              <View style={styles.rejectModalButtons}>
                <TouchableOpacity
                  style={[styles.rejectCancelButton, { backgroundColor: colors.border }]}
                  onPress={() => setShowRejectModal(false)}
                >
                  <Text style={[styles.rejectCancelText, { color: colors.text }]}>Cancel</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[styles.rejectConfirmButton, { backgroundColor: colors.error }]}
                  onPress={handleReject}
                  disabled={isProcessing}
                >
                  {isProcessing ? (
                    <ActivityIndicator size="small" color="#fff" />
                  ) : (
                    <Text style={styles.rejectConfirmText}>Reject & Regenerate</Text>
                  )}
                </TouchableOpacity>
              </View>
            </View>
          </View>
        </Modal>
      </SafeAreaView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  header: {
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
  },
  closeButton: {
    position: 'absolute',
    left: Spacing.lg,
    top: Spacing.md,
    zIndex: 10,
    padding: Spacing.sm,
  },
  headerCenter: {
    alignItems: 'center',
  },
  headerTitle: {
    fontSize: FontSizes.lg,
    fontWeight: '700',
  },
  headerSubtitle: {
    fontSize: FontSizes.sm,
    marginTop: 2,
  },
  progressContainer: {
    marginTop: Spacing.sm,
    paddingHorizontal: Spacing.xl,
  },
  progressBar: {
    height: 4,
    borderRadius: 2,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    borderRadius: 2,
  },
  instructionsRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    paddingHorizontal: Spacing.lg,
    paddingBottom: Spacing.sm,
  },
  instructionItem: {
    alignItems: 'center',
    gap: 4,
  },
  instructionText: {
    fontSize: FontSizes.xs,
  },
  cardContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  card: {
    width: SCREEN_WIDTH - 40,
    maxHeight: SCREEN_HEIGHT * 0.55,
  },
  cardContent: {
    padding: Spacing.lg,
    borderRadius: BorderRadius.lg,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
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
  metaBadges: {
    flexDirection: 'row',
    gap: Spacing.xs,
  },
  metaBadge: {
    paddingHorizontal: Spacing.sm,
    paddingVertical: Spacing.xs,
    borderRadius: BorderRadius.sm,
  },
  metaBadgeText: {
    fontSize: FontSizes.xs,
  },
  subjectRow: {
    flexDirection: 'row',
    marginBottom: Spacing.sm,
  },
  subjectText: {
    fontSize: FontSizes.sm,
    fontWeight: '500',
  },
  topicText: {
    fontSize: FontSizes.sm,
    marginLeft: Spacing.xs,
  },
  questionScroll: {
    maxHeight: SCREEN_HEIGHT * 0.35,
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
  answerBox: {
    padding: Spacing.md,
    borderRadius: BorderRadius.sm,
    borderWidth: 1,
    marginBottom: Spacing.md,
  },
  answerLabel: {
    fontSize: FontSizes.xs,
    fontWeight: '600',
    marginBottom: Spacing.xs,
  },
  answerText: {
    fontSize: FontSizes.sm,
    lineHeight: 20,
  },
  explanationBox: {
    padding: Spacing.md,
    borderRadius: BorderRadius.sm,
    marginBottom: Spacing.md,
  },
  explanationLabel: {
    fontSize: FontSizes.xs,
    fontWeight: '600',
    marginBottom: Spacing.xs,
  },
  explanationText: {
    fontSize: FontSizes.sm,
    lineHeight: 20,
  },
  teacherRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
    marginTop: Spacing.sm,
    paddingTop: Spacing.sm,
    borderTopWidth: 1,
    borderTopColor: 'rgba(0,0,0,0.1)',
  },
  teacherText: {
    fontSize: FontSizes.xs,
  },
  swipeIndicator: {
    position: 'absolute',
    width: 120,
    height: 120,
    borderRadius: 60,
    overflow: 'hidden',
  },
  approveIndicator: {
    right: 20,
    top: '50%',
    marginTop: -60,
  },
  rejectIndicator: {
    left: 20,
    top: '50%',
    marginTop: -60,
  },
  editIndicator: {
    top: 20,
    left: '50%',
    marginLeft: -60,
  },
  skipIndicator: {
    bottom: 20,
    left: '50%',
    marginLeft: -60,
  },
  indicatorGradient: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  indicatorText: {
    color: '#FFFFFF',
    fontSize: FontSizes.xs,
    fontWeight: '700',
    marginTop: 4,
  },
  processingOverlay: {
    ...StyleSheet.absoluteFillObject,
    justifyContent: 'center',
    alignItems: 'center',
  },
  processingBlur: {
    padding: Spacing.xl,
    borderRadius: BorderRadius.lg,
    alignItems: 'center',
  },
  processingText: {
    marginTop: Spacing.md,
    fontSize: FontSizes.md,
    fontWeight: '600',
  },
  actionButtonsRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: Spacing.lg,
    paddingVertical: Spacing.lg,
    paddingBottom: Spacing.xl,
  },
  actionButton: {
    width: 56,
    height: 56,
    borderRadius: 28,
    justifyContent: 'center',
    alignItems: 'center',
  },
  // Edit Modal Styles
  editContainer: {
    flex: 1,
  },
  editHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(0,0,0,0.1)',
  },
  cancelText: {
    fontSize: FontSizes.md,
  },
  editTitle: {
    fontSize: FontSizes.lg,
    fontWeight: '600',
  },
  saveText: {
    fontSize: FontSizes.md,
    fontWeight: '600',
  },
  editContent: {
    flex: 1,
    padding: Spacing.lg,
  },
  editSection: {
    marginBottom: Spacing.lg,
  },
  editLabel: {
    fontSize: FontSizes.sm,
    fontWeight: '500',
    marginBottom: Spacing.sm,
  },
  marksRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  marksButton: {
    width: 40,
    height: 40,
    borderRadius: BorderRadius.sm,
    justifyContent: 'center',
    alignItems: 'center',
  },
  marksInput: {
    width: 60,
    height: 40,
    borderWidth: 1,
    borderRadius: BorderRadius.sm,
    textAlign: 'center',
    fontSize: FontSizes.md,
    fontWeight: '600',
  },
  difficultyRow: {
    flexDirection: 'row',
    gap: Spacing.sm,
  },
  difficultyButton: {
    flex: 1,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.sm,
    borderWidth: 2,
    alignItems: 'center',
  },
  difficultyText: {
    fontSize: FontSizes.sm,
    fontWeight: '600',
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: Spacing.sm,
    borderRadius: BorderRadius.sm,
    marginBottom: Spacing.md,
    gap: Spacing.sm,
  },
  sectionHeaderText: {
    color: '#FFFFFF',
    fontSize: FontSizes.sm,
    fontWeight: '600',
  },
  coGrid: {
    gap: Spacing.sm,
  },
  coRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  coLabel: {
    fontSize: FontSizes.md,
    fontWeight: '600',
    width: 50,
  },
  coLevels: {
    flexDirection: 'row',
    flex: 1,
    gap: Spacing.xs,
    justifyContent: 'flex-end',
  },
  coLevelButton: {
    paddingVertical: Spacing.xs,
    paddingHorizontal: Spacing.sm,
    borderRadius: BorderRadius.sm,
    borderWidth: 2,
  },
  coLevelText: {
    fontSize: FontSizes.xs,
    fontWeight: '600',
  },
  answerInput: {
    minHeight: 100,
    padding: Spacing.md,
    borderWidth: 1,
    borderRadius: BorderRadius.md,
    fontSize: FontSizes.sm,
    textAlignVertical: 'top',
  },
  // Reject Modal Styles
  rejectModalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'flex-end',
  },
  rejectModalContent: {
    borderTopLeftRadius: BorderRadius.xl,
    borderTopRightRadius: BorderRadius.xl,
    maxHeight: '80%',
    paddingBottom: 34,
  },
  rejectModalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: Spacing.lg,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(0,0,0,0.1)',
  },
  rejectModalTitle: {
    fontSize: FontSizes.lg,
    fontWeight: '600',
  },
  rejectModalSubtitle: {
    fontSize: FontSizes.sm,
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.md,
  },
  reasonsList: {
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.sm,
    maxHeight: 300,
  },
  reasonItem: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    padding: Spacing.md,
    borderWidth: 1,
    borderRadius: BorderRadius.md,
    marginBottom: Spacing.sm,
  },
  reasonCheckbox: {
    width: 22,
    height: 22,
    borderRadius: BorderRadius.sm,
    borderWidth: 2,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: Spacing.sm,
  },
  reasonContent: {
    flex: 1,
  },
  reasonLabel: {
    fontSize: FontSizes.md,
    fontWeight: '500',
  },
  reasonDesc: {
    fontSize: FontSizes.sm,
    marginTop: 2,
  },
  rejectNotesInput: {
    marginHorizontal: Spacing.lg,
    marginTop: Spacing.sm,
    minHeight: 80,
    padding: Spacing.md,
    borderWidth: 1,
    borderRadius: BorderRadius.md,
    fontSize: FontSizes.sm,
    textAlignVertical: 'top',
  },
  rejectModalButtons: {
    flexDirection: 'row',
    padding: Spacing.lg,
    gap: Spacing.sm,
  },
  rejectCancelButton: {
    flex: 1,
    paddingVertical: Spacing.md,
    borderRadius: BorderRadius.md,
    alignItems: 'center',
  },
  rejectCancelText: {
    fontSize: FontSizes.md,
    fontWeight: '600',
  },
  rejectConfirmButton: {
    flex: 1,
    paddingVertical: Spacing.md,
    borderRadius: BorderRadius.md,
    alignItems: 'center',
  },
  rejectConfirmText: {
    color: '#FFFFFF',
    fontSize: FontSizes.md,
    fontWeight: '600',
  },
});

export default SwipeVetting;
