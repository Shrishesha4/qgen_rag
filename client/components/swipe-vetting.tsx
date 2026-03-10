/**
 * SwipeVetting - Tinder-like swipe UI for vetting questions
 * 
 * Gestures:
 * - Left swipe: Reject & Regenerate
 * - Right swipe: Approve
 * - Up swipe: Edit (inline)
 * - Down swipe: Skip
 */

import React, { useState, useCallback, useRef, useEffect } from 'react';
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
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { BlurView } from 'expo-blur';

import { GlassCard } from '@/components/ui/glass-card';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { QuestionSources } from '@/components/question-sources';
import { Colors, Spacing, BorderRadius, FontSizes } from '@/constants/theme';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { useToast } from '@/components/toast';
import { lightImpact, mediumImpact, heavyImpact, successNotification, selectionImpact } from '@/utils/haptics';
import {
  vetterService,
  QuestionForVetting,
  VetterUpdateQuestionRequest,
} from '@/services/vetter.service';

const { width: SCREEN_WIDTH, height: SCREEN_HEIGHT } = Dimensions.get('window');
const SWIPE_THRESHOLD = 120;
const VERTICAL_SWIPE_THRESHOLD = 60;
const SWIPE_OUT_DURATION = 250;

// Course Outcome levels
const CO_LEVELS = [
  { level: 1, label: 'Basic', color: '#34C759' },
  { level: 2, label: 'Intermediate', color: '#FF9500' },
  { level: 3, label: 'Advanced', color: '#FF3B30' },
];
const COURSE_OUTCOMES = ['CO1', 'CO2', 'CO3', 'CO4', 'CO5'];

// Robust MCQ correct-answer matching (handles "B", "B.", "B. Paris" formats)
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

// Rejection reasons
const REJECTION_REASONS = [
  { id: 'duplicate', label: 'Duplicate', desc: 'Already exists' },
  { id: 'off_topic', label: 'Off topic', desc: 'Not relevant' },
  { id: 'too_easy', label: 'Too easy', desc: 'Below level' },
  { id: 'too_hard', label: 'Too hard', desc: 'Above level' },
  { id: 'unclear', label: 'Unclear', desc: 'Confusing' },
  { id: 'incorrect_answer', label: 'Wrong answer', desc: 'Key is wrong' },
  { id: 'poor_options', label: 'Bad options', desc: 'MCQ issues' },
  { id: 'needs_improvement', label: 'Improve', desc: 'General fix' },
];

interface SwipeVettingProps {
  visible: boolean;
  onClose: () => void;
  questions: QuestionForVetting[];
  onQuestionVetted: (questionId: string, status: 'approved' | 'rejected' | 'skipped') => void;
  onQuestionUpdated: (questionId: string, updates: Partial<QuestionForVetting>) => void;
  onQuestionReplaced?: (oldId: string, newQuestion: QuestionForVetting) => void;
  onLoadMore?: () => void;
  hasMore?: boolean;
  total?: number;
}

type ViewMode = 'question' | 'edit' | 'reject';

export function SwipeVetting({
  visible,
  onClose,
  questions,
  onQuestionVetted,
  onQuestionUpdated,
  onQuestionReplaced,
  onLoadMore,
  hasMore = false,
  total,
}: SwipeVettingProps) {
  const colorScheme = useColorScheme();
  const colors = Colors[colorScheme ?? 'light'];
  const isDark = colorScheme === 'dark';
  const insets = useSafeAreaInsets();
  const { showSuccess, showError } = useToast();

  const [currentIndex, setCurrentIndex] = useState(0);
  const [isProcessing, setIsProcessing] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>('question');

  // Local override so a regenerated replacement shows immediately without waiting
  // for the parent prop cycle. Cleared when navigating to the next card.
  const [questionOverride, setQuestionOverride] = useState<QuestionForVetting | null>(null);

  // Edit mode state
  const [editData, setEditData] = useState<VetterUpdateQuestionRequest>({});
  const [coMappings, setCoMappings] = useState<Record<string, number>>({});
  const [editingOptionIndex, setEditingOptionIndex] = useState<number | null>(null);
  const [editingOptionText, setEditingOptionText] = useState<string>('');
  const [mcqOptions, setMcqOptions] = useState<string[]>([]);

  // Rejection state
  const [selectedReasons, setSelectedReasons] = useState<string[]>([]);
  const [rejectNotes, setRejectNotes] = useState('');

  // Source references modal
  const [showSourcesModal, setShowSourcesModal] = useState(false);

  // Swipe animation
  const position = useRef(new Animated.ValueXY()).current;
  // Jean button press animation (0 = idle, 1 = fully pressed)
  const buttonPressAnim = useRef(new Animated.Value(0)).current;
  // Tracks the inner dot offset so it follows the user's finger direction
  const handleDragPosition = useRef(new Animated.ValueXY()).current;
  const scrollViewRef = useRef<ScrollView>(null);
  const questionScrollRef = useRef<ScrollView>(null);

  // Track scroll position so we know when the card is at its top/bottom bounds
  const scrollOffsetRef = useRef(0);
  const scrollContentHeightRef = useRef(0);
  const scrollContainerHeightRef = useRef(0);

  // Refs for gesture callbacks — always points to latest functions (fixes stale closures in panResponder)
  const viewModeRef = useRef<ViewMode>('question');
  const gestureCallbacksRef = useRef<{
    handleUpSwipe: () => void;
    handleDownSwipe: () => void;
    swipeOut: (d: 'left' | 'right') => void;
    resetPosition: () => void;
  }>({
    handleUpSwipe: () => {},
    handleDownSwipe: () => {},
    swipeOut: () => {},
    resetPosition: () => {},
  });

  const currentQuestion = questionOverride ?? questions[currentIndex];
  const totalQuestions = total ?? questions.length;

  // Load more when approaching end
  useEffect(() => {
    if (currentIndex >= questions.length - 5 && hasMore && onLoadMore) {
      onLoadMore();
    }
  }, [currentIndex, questions.length, hasMore, onLoadMore]);

  // Reset state when question changes
  const resetState = useCallback(() => {
    setViewMode('question');
    setSelectedReasons([]);
    setRejectNotes('');
    setEditingOptionIndex(null);
    setEditingOptionText('');
    if (currentQuestion) {
      setEditData({
        marks: currentQuestion.marks ?? undefined,
        difficulty_level: currentQuestion.difficulty_level ?? undefined,
        correct_answer: currentQuestion.correct_answer ?? undefined,
        question_text: currentQuestion.question_text,
        course_outcome_mapping: currentQuestion.course_outcome_mapping ?? undefined,
      });
      setCoMappings(currentQuestion.course_outcome_mapping || {});
      // Initialize MCQ options if it's an MCQ
      if (currentQuestion.question_type === 'mcq' && currentQuestion.options) {
        setMcqOptions([...currentQuestion.options]);
      } else {
        setMcqOptions([]);
      }
    }
    scrollOffsetRef.current = 0;
    scrollContentHeightRef.current = 0;
    scrollContainerHeightRef.current = 0;
    questionScrollRef.current?.scrollTo({ y: 0, animated: false });
  }, [currentQuestion]);

  useEffect(() => {
    resetState();
  }, [currentIndex, resetState]);

  // Dedicated drag handle PanResponder — lives outside the ScrollView so it always wins.
  // Supports all 4 directions: left/right = reject/approve, up = edit, down = skip.
  const dragHandlePanResponder = useRef(
    PanResponder.create({
      onStartShouldSetPanResponder: () => true,
      onStartShouldSetPanResponderCapture: () => true,
      onPanResponderGrant: () => {
        swipeHapticFiredRef.current = { left: false, right: false, up: false, down: false };
        // Animate jean button to pressed state
        Animated.spring(buttonPressAnim, {
          toValue: 1,
          useNativeDriver: false,
          speed: 40,
          bounciness: 8,
        }).start();
        lightImpact();
      },
      onPanResponderMove: (_, gesture) => {
        position.setValue({ x: gesture.dx, y: 0 });
        if (gesture.dx > SWIPE_THRESHOLD && !swipeHapticFiredRef.current.right) {
          swipeHapticFiredRef.current.right = true;
          mediumImpact();
        } else if (gesture.dx < -SWIPE_THRESHOLD && !swipeHapticFiredRef.current.left) {
          swipeHapticFiredRef.current.left = true;
          mediumImpact();
        } else if (gesture.dy < -VERTICAL_SWIPE_THRESHOLD && !swipeHapticFiredRef.current.up) {
          swipeHapticFiredRef.current.up = true;
          lightImpact();
        } else if (gesture.dy > VERTICAL_SWIPE_THRESHOLD && !swipeHapticFiredRef.current.down) {
          swipeHapticFiredRef.current.down = true;
          lightImpact();
        }
      },
      onPanResponderRelease: (_, { dx, dy, vx, vy }) => {
        // Spring inner dot back to centre
        Animated.spring(handleDragPosition, {
          toValue: { x: 0, y: 0 },
          useNativeDriver: false,
          speed: 30,
          bounciness: 8,
        }).start();
        // Release jean button animation
        Animated.spring(buttonPressAnim, {
          toValue: 0,
          useNativeDriver: false,
          speed: 30,
          bounciness: 4,
        }).start();
        if (dx > SWIPE_THRESHOLD || vx > 0.8) {
          gestureCallbacksRef.current.swipeOut('right');
        } else if (dx < -SWIPE_THRESHOLD || vx < -0.8) {
          gestureCallbacksRef.current.swipeOut('left');
        } else if (dy < -VERTICAL_SWIPE_THRESHOLD || vy < -0.4) {
          gestureCallbacksRef.current.handleUpSwipe();
        } else if (dy > VERTICAL_SWIPE_THRESHOLD || vy > 0.4) {
          gestureCallbacksRef.current.handleDownSwipe();
        } else {
          gestureCallbacksRef.current.resetPosition();
        }
      },
      onPanResponderTerminate: () => {
        Animated.spring(handleDragPosition, {
          toValue: { x: 0, y: 0 },
          useNativeDriver: false,
          speed: 30,
          bounciness: 8,
        }).start();
        Animated.spring(buttonPressAnim, {
          toValue: 0,
          useNativeDriver: false,
          speed: 30,
          bounciness: 4,
        }).start();
      },
    })
  ).current;

  // Tracks which swipe directions have already fired a threshold haptic this gesture
  const swipeHapticFiredRef = useRef({ left: false, right: false, up: false, down: false });

  const panResponder = useRef(
    PanResponder.create({
      onStartShouldSetPanResponder: () => false,
      onStartShouldSetPanResponderCapture: () => false,
      // Capture phase: parent wins over ScrollView for clearly horizontal moves
      onMoveShouldSetPanResponderCapture: (_, { dx, dy, vx, vy }) => {
        if (viewModeRef.current !== 'question') return false;
        const absDx = Math.abs(dx);
        const absDy = Math.abs(dy);
        const absVx = Math.abs(vx);
        const absVy = Math.abs(vy);
        // Claim when decisively horizontal so ScrollView never steals it
        if (absDx > absDy * 2 && absDx > 6) return true;
        if (absVx > 0.4 && absVx > absVy * 2.5) return true;
        return false;
      },
      // Bubble phase fallback (in case capture didn't fire)
      onMoveShouldSetPanResponder: (_, { dx, dy, vx, vy }) => {
        if (viewModeRef.current !== 'question') return false;
        const absDx = Math.abs(dx);
        const absDy = Math.abs(dy);
        const absVx = Math.abs(vx);
        const absVy = Math.abs(vy);
        if (absDx > absDy * 2 && absDx > 6) return true;
        if (absVx > 0.4 && absVx > absVy * 2.5) return true;
        return false;
      },
      onPanResponderGrant: () => {
        swipeHapticFiredRef.current = { left: false, right: false, up: false, down: false };
        lightImpact();
      },
      onPanResponderMove: (_, gesture) => {
        position.setValue({ x: gesture.dx, y: 0 });
        if (gesture.dx > SWIPE_THRESHOLD && !swipeHapticFiredRef.current.right) {
          swipeHapticFiredRef.current.right = true;
          mediumImpact();
        } else if (gesture.dx < -SWIPE_THRESHOLD && !swipeHapticFiredRef.current.left) {
          swipeHapticFiredRef.current.left = true;
          mediumImpact();
        }
      },
      onPanResponderRelease: (_, gesture) => {
        if (viewModeRef.current !== 'question') {
          gestureCallbacksRef.current.resetPosition();
          return;
        }
        const { dx, vx } = gesture;
        if (dx > SWIPE_THRESHOLD || vx > 0.8) {
          gestureCallbacksRef.current.swipeOut('right');
        } else if (dx < -SWIPE_THRESHOLD || vx < -0.8) {
          gestureCallbacksRef.current.swipeOut('left');
        } else {
          gestureCallbacksRef.current.resetPosition();
        }
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

  const swipeOut = (direction: 'left' | 'right') => {
    heavyImpact();
    const x = direction === 'right' ? SCREEN_WIDTH + 100 : -SCREEN_WIDTH - 100;
    Animated.timing(position, {
      toValue: { x, y: 0 },
      duration: SWIPE_OUT_DURATION,
      useNativeDriver: false,
    }).start(() => {
      if (direction === 'right') {
        handleApprove();
      } else {
        setViewMode('reject');
        resetPosition();
        setTimeout(() => {
          scrollViewRef.current?.scrollTo({ y: 200, animated: true });
        }, 100);
      }
    });
  };

  const handleUpSwipe = () => {
    mediumImpact();
    Animated.timing(position, {
      toValue: { x: 0, y: -50 },
      duration: 150,
      useNativeDriver: false,
    }).start(() => {
      setViewMode('edit');
      resetPosition();
      setTimeout(() => {
        scrollViewRef.current?.scrollTo({ y: 200, animated: true });
      }, 100);
    });
  };

  const handleDownSwipe = () => {
    Animated.timing(position, {
      toValue: { x: 0, y: 50 },
      duration: 150,
      useNativeDriver: false,
    }).start(() => {
      handleSkip();
      resetPosition();
    });
  };

  const handleApprove = async () => {
    if (!currentQuestion || isProcessing) return;
    
    setIsProcessing(true);
    try {
      await vetterService.vetQuestion(currentQuestion.id, {
        status: 'approved',
        course_outcome_mapping: Object.keys(coMappings).length > 0 ? coMappings : undefined,
      });
      successNotification();
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
      const result = await vetterService.rejectAndRegenerate(currentQuestion.id, {
        notes: rejectNotes || undefined,
        rejection_reasons: selectedReasons.length > 0 ? selectedReasons : undefined,
      });
      successNotification();

      if (result.regenerated && result.new_question) {
        // Build replacement question
        const newQ: QuestionForVetting = {
          ...currentQuestion,
          id: result.new_question.id,
          question_text: result.new_question.question_text,
          question_type: result.new_question.question_type,
          options: result.new_question.options,
          correct_answer: result.new_question.correct_answer,
          marks: result.new_question.marks,
          difficulty_level: result.new_question.difficulty_level,
          bloom_taxonomy_level: result.new_question.bloom_taxonomy_level,
          vetting_status: result.new_question.vetting_status,
          vetting_notes: null,
          version_number: result.new_question.version_number,
          replaces_id: currentQuestion.id,
          replaced_by_id: null,
          source_info: result.new_question.source_info ?? null,
        };
        // Set override immediately so card shows without waiting for parent prop cycle
        setQuestionOverride(newQ);
        position.setValue({ x: 0, y: 0 }); // snap card back to centre instantly
        setViewMode('question');
        setSelectedReasons([]);
        setRejectNotes('');
        // Also notify parent to keep the list in sync
        if (onQuestionReplaced) {
          onQuestionReplaced(currentQuestion.id, newQ);
        }
        showSuccess('Rejected — review the replacement');
      } else {
        showSuccess('Question rejected');
        onQuestionVetted(currentQuestion.id, 'rejected');
        moveToNext();
      }
    } catch (err) {
      showError('Failed to reject question');
      console.error(err);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleSkip = () => {
    if (!currentQuestion) return;
    lightImpact();
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
      
      // For MCQs, if options were edited, we need to handle that
      // The backend might need options update - check if the schema supports it
      // For now, just send the correct_answer which should be one of the options
      
      await vetterService.updateQuestion(currentQuestion.id, updates);
      successNotification();
      showSuccess('Question updated!');
      onQuestionUpdated(currentQuestion.id, updates as Partial<QuestionForVetting>);
      resetPosition();
      setViewMode('question');
    } catch (err) {
      showError('Failed to update question');
      console.error(err);
    } finally {
      setIsProcessing(false);
    }
  };

  const moveToNext = () => {
    position.setValue({ x: 0, y: 0 });
    setQuestionOverride(null); // clear any regen override before advancing
    setViewMode('question');
    if (currentIndex < questions.length - 1) {
      setCurrentIndex(currentIndex + 1);
    } else if (!hasMore) {
      showSuccess('All questions reviewed!');
      onClose();
    }
  };

  const toggleRejectReason = (reasonId: string) => {
    selectionImpact();
    setSelectedReasons((prev) =>
      prev.includes(reasonId) ? prev.filter((r) => r !== reasonId) : [...prev, reasonId]
    );
  };

  const updateCoMapping = (co: string, level: number) => {
    setCoMappings((prev) => ({
      ...prev,
      [co]: prev[co] === level ? 0 : level,
    }));
  };

  const handleSelectMcqOption = (option: string) => {
    setEditData((prev) => ({ ...prev, correct_answer: option }));
  };

  // Extract the option letter prefix (e.g., "A)" from "A) Some text")
  const extractOptionPrefix = (option: string): { prefix: string; text: string } => {
    const match = option.match(/^([A-Z]\)|[A-Z]\.\s*|[A-Z]\s+)(.*)$/);
    if (match) {
      return { prefix: match[1], text: match[2] };
    }
    return { prefix: '', text: option };
  };

  const startEditingOption = (index: number) => {
    setEditingOptionIndex(index);
    const { text } = extractOptionPrefix(mcqOptions[index]);
    setEditingOptionText(text);
  };

  const saveEditedOption = () => {
    if (editingOptionIndex !== null && editingOptionText.trim()) {
      const { prefix } = extractOptionPrefix(mcqOptions[editingOptionIndex]);
      const newOptionText = prefix + editingOptionText.trim();
      
      const newOptions = [...mcqOptions];
      const oldOption = newOptions[editingOptionIndex];
      newOptions[editingOptionIndex] = newOptionText;
      setMcqOptions(newOptions);
      
      // If this was the correct answer, update it
      if (oldOption === editData.correct_answer) {
        setEditData((prev) => ({ ...prev, correct_answer: newOptionText }));
      }
      
      setEditingOptionIndex(null);
      setEditingOptionText('');
    }
  };

  const cancelEditingOption = () => {
    setEditingOptionIndex(null);
    setEditingOptionText('');
  };

  // Update refs every render so panResponder always calls the latest handler versions
  viewModeRef.current = viewMode;
  gestureCallbacksRef.current = { handleUpSwipe, handleDownSwipe, swipeOut, resetPosition };

  // Card animation — horizontal only (no vertical swipe gestures)
  const rotate = position.x.interpolate({
    inputRange: [-SCREEN_WIDTH / 2, 0, SCREEN_WIDTH / 2],
    outputRange: ['-8deg', '0deg', '8deg'],
    extrapolate: 'clamp',
  });

  const cardStyle = {
    transform: [
      { translateX: position.x },
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

  if (!visible) return null;

  return (
    <Modal visible={visible} animationType="slide" presentationStyle="fullScreen">
      <View style={[styles.container, { backgroundColor: colors.background, paddingTop: insets.top }]}>
        <KeyboardAvoidingView 
          style={styles.flex} 
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        >
          {/* Header */}
          <View style={[styles.header, { backgroundColor: colors.background }]}>
            <View style={styles.headerRow}>
              <TouchableOpacity onPress={onClose} style={styles.closeButton}>
                <IconSymbol name="xmark.circle.fill" size={28} color={colors.textSecondary} />
              </TouchableOpacity>
              <View style={styles.headerCenter}>
                <Text style={[styles.headerTitle, { color: colors.text }]}>Vetting Mode</Text>
                <Text style={[styles.headerSubtitle, { color: colors.textSecondary }]}>
                  {currentIndex + 1} of {totalQuestions}
                </Text>
              </View>
              <View style={{ width: 28 }} />
            </View>
            <View style={styles.progressContainer}>
              <View style={[styles.progressBar, { backgroundColor: colors.border }]}>
                <View
                  style={[
                    styles.progressFill,
                    {
                      backgroundColor: colors.primary,
                      width: `${((currentIndex + 1) / totalQuestions) * 100}%`,
                    },
                  ]}
                />
              </View>
            </View>
          </View>

          {/* Swipe Instructions (only in question mode) */}
          {viewMode === 'question' && (
            <View style={[styles.instructionsCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
              <Text style={[styles.instructionsTitle, { color: colors.text }]}>Swipe to decide:</Text>
              <View style={styles.instructionsRow}>
                <View style={styles.instructionItem}>
                  <View style={[styles.instructionIcon, { backgroundColor: colors.error + '20' }]}>
                    <IconSymbol name="arrow.left" size={16} color={colors.error} />
                  </View>
                  <Text style={[styles.instructionText, { color: colors.text }]}>Reject</Text>
                </View>
                <View style={styles.instructionItem}>
                  <View style={[styles.instructionIcon, { backgroundColor: colors.primary + '20' }]}>
                    <IconSymbol name="arrow.up" size={16} color={colors.primary} />
                  </View>
                  <Text style={[styles.instructionText, { color: colors.text }]}>Edit¹</Text>
                </View>
                <View style={styles.instructionItem}>
                  <View style={[styles.instructionIcon, { backgroundColor: colors.warning + '20' }]}>
                    <IconSymbol name="arrow.down" size={16} color={colors.warning} />
                  </View>
                  <Text style={[styles.instructionText, { color: colors.text }]}>Skip¹</Text>
                </View>
                <View style={styles.instructionItem}>
                  <View style={[styles.instructionIcon, { backgroundColor: colors.success + '20' }]}>
                    <IconSymbol name="arrow.right" size={16} color={colors.success} />
                  </View>
                  <Text style={[styles.instructionText, { color: colors.text }]}>Approve</Text>
                </View>
              </View>
              <Text style={[styles.instructionsHint, { color: colors.textTertiary }]}>
                ¹ Hold the ● button below to drag in any direction
              </Text>
            </View>
          )}

          {/* Question Card - Outside ScrollView for swipe gestures */}
          {currentQuestion && viewMode === 'question' && (
            <Animated.View
              style={[styles.questionCardContainer, cardStyle]}
              {...panResponder.panHandlers}
            >
              {/* Swipe Indicators */}
              <Animated.View style={[styles.swipeLabel, styles.approveLabel, { opacity: approveOpacity }]}>
                <Text style={styles.swipeLabelText}>APPROVE</Text>
              </Animated.View>
              <Animated.View style={[styles.swipeLabel, styles.rejectLabel, { opacity: rejectOpacity }]}>
                <Text style={styles.swipeLabelText}>REJECT</Text>
              </Animated.View>

              <ScrollView
                ref={questionScrollRef}
                style={styles.questionScrollView}
                contentContainerStyle={styles.questionScrollContent}
                showsVerticalScrollIndicator={false}
                nestedScrollEnabled={true}
                scrollEventThrottle={16}
                onScroll={(e) => {
                  scrollOffsetRef.current = e.nativeEvent.contentOffset.y;
                }}
                onContentSizeChange={(_, h) => {
                  scrollContentHeightRef.current = h;
                }}
                onLayout={(e) => {
                  scrollContainerHeightRef.current = e.nativeEvent.layout.height;
                }}
              >
                <GlassCard style={[styles.questionCard, { backgroundColor: colors.card }]}>
                  {/* Question Header */}
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

                  {/* Subject/Topic */}
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

                  {/* Question Text */}
                  <Text style={[styles.questionText, { color: colors.text }]}>
                    {currentQuestion.question_text}
                  </Text>

                  {/* MCQ Options */}
                  {currentQuestion.question_type === 'mcq' && currentQuestion.options && (
                    <View style={styles.optionsContainer}>
                      {currentQuestion.options.map((option, idx) => {
                        const isCorrect = optionMatchesCorrect(option, currentQuestion.correct_answer, idx);
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
                              <IconSymbol name="checkmark.circle.fill" size={16} color={colors.success} />
                            )}
                          </View>
                        );
                      })}
                    </View>
                  )}

                  {/* Short/Long Answer */}
                  {currentQuestion.question_type !== 'mcq' && currentQuestion.correct_answer && (
                    <View style={[styles.answerBox, { borderColor: colors.success }]}>
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

                  {/* Source References - Tappable button */}
                  {currentQuestion.source_info && currentQuestion.source_info.sources.length > 0 && (
                    <TouchableOpacity
                      style={[styles.sourcesButton, { backgroundColor: colors.primary + '15', borderColor: colors.primary + '40' }]}
                      onPress={() => setShowSourcesModal(true)}
                      activeOpacity={0.7}
                    >
                      <IconSymbol name="doc.text.magnifyingglass" size={14} color={colors.primary} />
                      <Text style={[styles.sourcesButtonText, { color: colors.primary }]}>
                        Source References ({currentQuestion.source_info.sources.length})
                      </Text>
                      <IconSymbol name="chevron.right" size={12} color={colors.primary} />
                    </TouchableOpacity>
                  )}

                  {/* Teacher info + drag handle */}
                  {currentQuestion.teacher_name && (
                    <View style={[styles.teacherRow, { borderTopColor: colors.border }]}>
                      <IconSymbol name="person.fill" size={12} color={colors.textSecondary} />
                      <Text style={[styles.teacherText, { color: colors.textSecondary }]}>
                        {currentQuestion.teacher_name}
                      </Text>
                    </View>
                  )}
                </GlassCard>
              </ScrollView>

              {/* Jean button drag handle — rendered inside absolute bar below */}
            </Animated.View>
          )}

          {/* Edit and Reject Panels - Scrollable */}
          {currentQuestion && viewMode !== 'question' && (
            <ScrollView
              ref={scrollViewRef}
              style={styles.panelScrollView}
              contentContainerStyle={styles.panelScrollContent}
              showsVerticalScrollIndicator={false}
            >
              {/* Dimmed Question Card */}
              <View style={styles.dimmedQuestionContainer}>
                <GlassCard style={[styles.questionCard, { backgroundColor: colors.card, opacity: 0.6 }]}>
                  <View style={styles.cardHeader}>
                    <View style={[styles.typeBadge, { backgroundColor: colors.primary + '20' }]}>
                      <Text style={[styles.typeBadgeText, { color: colors.primary }]}>
                        {currentQuestion.question_type.replace('_', ' ').toUpperCase()}
                      </Text>
                    </View>
                  </View>
                  <Text style={[styles.questionText, { color: colors.text }]} numberOfLines={3}>
                    {currentQuestion.question_text}
                  </Text>
                </GlassCard>
              </View>

            {/* Rejection Panel (Inline Floating Card) */}
            {viewMode === 'reject' && (
              <View style={styles.inlinePanel}>
                <GlassCard style={[styles.rejectCard, { backgroundColor: colors.card }]}>
                  <View style={styles.panelHeader}>
                    <Text style={[styles.panelTitle, { color: colors.error }]}>
                      <IconSymbol name="xmark.circle.fill" size={18} color={colors.error} /> Reject Question
                    </Text>
                    <TouchableOpacity onPress={() => {
                      resetPosition();
                      setViewMode('question');
                    }}>
                      <IconSymbol name="xmark" size={20} color={colors.textSecondary} />
                    </TouchableOpacity>
                  </View>

                  <Text style={[styles.panelSubtitle, { color: colors.textSecondary }]}>
                    Select reason(s) for rejection:
                  </Text>

                  <View style={styles.reasonsGrid}>
                    {REJECTION_REASONS.map((reason) => {
                      const isSelected = selectedReasons.includes(reason.id);
                      return (
                        <TouchableOpacity
                          key={reason.id}
                          style={[
                            styles.reasonChip,
                            {
                              borderColor: isSelected ? colors.error : colors.border,
                              backgroundColor: isSelected ? colors.error + '20' : 'transparent',
                            },
                          ]}
                          onPress={() => toggleRejectReason(reason.id)}
                        >
                          <Text
                            style={[
                              styles.reasonChipText,
                              { color: isSelected ? colors.error : colors.text },
                            ]}
                          >
                            {reason.label}
                          </Text>
                        </TouchableOpacity>
                      );
                    })}
                  </View>

                  <TextInput
                    style={[
                      styles.notesInput,
                      { color: colors.text, borderColor: colors.border, backgroundColor: colors.background },
                    ]}
                    value={rejectNotes}
                    onChangeText={setRejectNotes}
                    placeholder="Additional notes (optional)"
                    placeholderTextColor={colors.textTertiary}
                    multiline
                  />

                  <View style={styles.panelButtons}>
                    <TouchableOpacity
                      style={[styles.panelButton, { backgroundColor: colors.border }]}
                      onPress={() => {
                        resetPosition();
                        setViewMode('question');
                      }}
                    >
                      <Text style={[styles.panelButtonText, { color: colors.text }]}>Cancel</Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                      style={[styles.panelButton, { backgroundColor: colors.error }]}
                      onPress={handleReject}
                      disabled={isProcessing}
                    >
                      {isProcessing ? (
                        <ActivityIndicator size="small" color="#fff" />
                      ) : (
                        <Text style={[styles.panelButtonText, { color: '#fff' }]}>Reject</Text>
                      )}
                    </TouchableOpacity>
                  </View>
                </GlassCard>
              </View>
            )}

            {/* Edit Panel (Inline below question) */}
            {viewMode === 'edit' && (
              <View style={styles.inlinePanel}>
                <GlassCard style={[styles.editCard, { backgroundColor: colors.card }]}>
                  <View style={styles.panelHeader}>
                    <Text style={[styles.panelTitle, { color: colors.primary }]}>
                      <IconSymbol name="pencil" size={18} color={colors.primary} /> Edit Question
                    </Text>
                    <TouchableOpacity onPress={() => {
                      resetPosition();
                      setViewMode('question');
                    }}>
                      <IconSymbol name="xmark" size={20} color={colors.textSecondary} />
                    </TouchableOpacity>
                  </View>

                  {/* Marks */}
                  <View style={styles.editRow}>
                    <Text style={[styles.editLabel, { color: colors.text }]}>Marks</Text>
                    <View style={styles.marksRow}>
                      <TouchableOpacity
                        style={[styles.marksButton, { backgroundColor: colors.border }]}
                        onPress={() => setEditData((prev) => ({ ...prev, marks: Math.max(1, (prev.marks || 1) - 1) }))}
                      >
                        <IconSymbol name="minus" size={14} color={colors.text} />
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
                        <IconSymbol name="plus" size={14} color={colors.text} />
                      </TouchableOpacity>
                    </View>
                  </View>

                  {/* Difficulty */}
                  <View style={styles.editRow}>
                    <Text style={[styles.editLabel, { color: colors.text }]}>Difficulty</Text>
                    <View style={styles.difficultyRow}>
                      {['easy', 'medium', 'hard'].map((diff) => {
                        const diffColor = diff === 'easy' ? '#34C759' : diff === 'medium' ? '#FF9500' : '#FF3B30';
                        return (
                          <TouchableOpacity
                            key={diff}
                            style={[
                              styles.difficultyButton,
                              {
                                borderColor: diffColor,
                                backgroundColor: editData.difficulty_level === diff ? diffColor : 'transparent',
                              },
                            ]}
                            onPress={() => setEditData((prev) => ({ ...prev, difficulty_level: diff }))}
                          >
                            <Text
                              style={[
                                styles.difficultyText,
                                { color: editData.difficulty_level === diff ? '#fff' : diffColor },
                              ]}
                            >
                              {diff.charAt(0).toUpperCase() + diff.slice(1)}
                            </Text>
                          </TouchableOpacity>
                        );
                      })}
                    </View>
                  </View>

                  {/* CO Mapping */}
                  <View style={styles.coSection}>
                    <Text style={[styles.editLabel, { color: colors.text, marginBottom: Spacing.sm }]}>
                      Course Outcome Mapping
                    </Text>
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
                                {level}
                              </Text>
                            </TouchableOpacity>
                          ))}
                        </View>
                      </View>
                    ))}
                  </View>

                  {/* Answer Edit */}
                  <View style={styles.answerSection}>
                    <Text style={[styles.editLabel, { color: colors.text, marginBottom: Spacing.sm }]}>Answer</Text>
                    
                    {currentQuestion.question_type === 'mcq' && mcqOptions.length > 0 ? (
                      // MCQ: Show options to tap and select correct answer
                      <View style={styles.mcqEditContainer}>
                        {mcqOptions.map((option, idx) => {
                          const isCorrect = optionMatchesCorrect(option, editData.correct_answer, idx);
                          const isEditing = editingOptionIndex === idx;
                          const { prefix, text } = extractOptionPrefix(option);
                          
                          return (
                            <View key={idx} style={styles.mcqEditOptionRow}>
                              {isEditing ? (
                                // Edit mode for this option - only edit text after prefix
                                <View style={[styles.mcqEditInput, { backgroundColor: colors.background, borderColor: colors.primary }]}>
                                  <View style={styles.mcqEditInputRow}>
                                    <Text style={[styles.mcqEditPrefix, { color: colors.textSecondary }]}>{prefix}</Text>
                                    <TextInput
                                      style={[styles.mcqEditTextInput, { color: colors.text }]}
                                      value={editingOptionText}
                                      onChangeText={setEditingOptionText}
                                      placeholder="Option text..."
                                      placeholderTextColor={colors.textTertiary}
                                      autoFocus
                                      multiline
                                    />
                                  </View>
                                  <View style={styles.mcqEditActions}>
                                    <TouchableOpacity
                                      style={[styles.mcqEditActionButton, { backgroundColor: colors.border }]}
                                      onPress={cancelEditingOption}
                                    >
                                      <IconSymbol name="xmark" size={14} color={colors.text} />
                                    </TouchableOpacity>
                                    <TouchableOpacity
                                      style={[styles.mcqEditActionButton, { backgroundColor: colors.success }]}
                                      onPress={saveEditedOption}
                                    >
                                      <IconSymbol name="checkmark" size={14} color="#fff" />
                                    </TouchableOpacity>
                                  </View>
                                </View>
                              ) : (
                                // Display mode - tap to select as correct
                                <TouchableOpacity
                                  style={[
                                    styles.mcqEditOption,
                                    {
                                      backgroundColor: isCorrect ? colors.success + '20' : colors.background,
                                      borderColor: isCorrect ? colors.success : colors.border,
                                    },
                                  ]}
                                  onPress={() => handleSelectMcqOption(option)}
                                >
                                  <View style={[
                                    styles.optionLetter,
                                    { backgroundColor: isCorrect ? colors.success : colors.border }
                                  ]}>
                                    <Text style={[
                                      styles.optionLetterText,
                                      { color: isCorrect ? '#fff' : colors.textSecondary }
                                    ]}>
                                      {String.fromCharCode(65 + idx)}
                                    </Text>
                                  </View>
                                  <Text style={[
                                    styles.mcqEditOptionText,
                                    { color: isCorrect ? colors.success : colors.text }
                                  ]}>
                                    {text}
                                  </Text>
                                  {isCorrect && (
                                    <IconSymbol name="checkmark.circle.fill" size={18} color={colors.success} />
                                  )}
                                  <TouchableOpacity
                                    style={[styles.mcqEditButton, { backgroundColor: colors.primary + '15' }]}
                                    onPress={(e) => {
                                      e.stopPropagation();
                                      startEditingOption(idx);
                                    }}
                                  >
                                    <IconSymbol name="pencil" size={14} color={colors.primary} />
                                  </TouchableOpacity>
                                </TouchableOpacity>
                              )}
                            </View>
                          );
                        })}
                        <Text style={[styles.mcqEditHint, { color: colors.textSecondary }]}>
                          Tap an option to mark it as correct. Tap the pencil icon to edit only the option text.
                        </Text>
                      </View>
                    ) : (
                      // Short/Long Answer: Show text input
                      <TextInput
                        style={[
                          styles.answerInput,
                          { color: colors.text, borderColor: colors.border, backgroundColor: colors.background },
                        ]}
                        value={editData.correct_answer || ''}
                        onChangeText={(v) => setEditData((prev) => ({ ...prev, correct_answer: v }))}
                        placeholder="Expected answer..."
                        placeholderTextColor={colors.textTertiary}
                        multiline
                      />
                    )}
                  </View>

                  <View style={styles.panelButtons}>
                    <TouchableOpacity
                      style={[styles.panelButton, { backgroundColor: colors.border }]}
                      onPress={() => {
                        resetPosition();
                        setViewMode('question');
                      }}
                    >
                      <Text style={[styles.panelButtonText, { color: colors.text }]}>Cancel</Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                      style={[styles.panelButton, { backgroundColor: colors.primary }]}
                      onPress={handleSaveEdits}
                      disabled={isProcessing}
                    >
                      {isProcessing ? (
                        <ActivityIndicator size="small" color="#fff" />
                      ) : (
                        <Text style={[styles.panelButtonText, { color: '#fff' }]}>Save</Text>
                      )}
                    </TouchableOpacity>
                  </View>
                </GlassCard>
              </View>
            )}
          </ScrollView>
          )}

          {/* Floating action bar — BlurView backdrop so card shows through */}
          {viewMode === 'question' && (() => {
            const btnScale = buttonPressAnim.interpolate({
              inputRange: [0, 2],
              outputRange: [2, 2.22],
            });
            const ringOpacity = buttonPressAnim.interpolate({
              inputRange: [0, 0.4, 1],
              outputRange: [0, 0.6, 1],
            });
            const ringScale = buttonPressAnim.interpolate({
              inputRange: [0, 1],
              outputRange: [1, 1.55],
            });
            const innerBg = buttonPressAnim.interpolate({
              inputRange: [0, 1],
              outputRange: [
                'transparent',
                isDark ? 'rgba(10,132,255,0.85)' : 'rgba(0,122,255,0.85)',
              ],
            });
            return (
              <View style={[styles.floatingActionBar, { paddingBottom: Math.max(insets.bottom, 12) }]}>
                <BlurView
                  intensity={isDark ? 0 : 0}
                  tint={isDark ? 'dark' : 'light'}
                  style={StyleSheet.absoluteFillObject}
                />

                {/* Jean button row */}
                <View
                  {...dragHandlePanResponder.panHandlers}
                  style={styles.jeanButtonWrapper}
                >
                  {/* Outer ripple ring */}
                  <Animated.View
                    style={[
                      styles.jeanButtonRing,
                      {
                        opacity: ringOpacity,
                        transform: [{ scale: ringScale }],
                        borderColor: isDark ? 'rgba(10,132,255,0.7)' : 'rgba(0,122,255,0.6)',
                      },
                    ]}
                  />
                  {/* Inner rivet circle — translates to follow the finger */}
                  <Animated.View
                    style={[
                      styles.jeanButton,
                      {
                        backgroundColor: innerBg,
                        borderColor: isDark ? 'rgba(255,255,255,0.4)' : 'rgba(80,80,100,0.45)',
                        transform: [
                          { scale: btnScale },
                          { translateX: handleDragPosition.x },
                          { translateY: handleDragPosition.y },
                        ],
                      },
                    ]}
                  >
                    <View style={styles.jeanButtonHighlight} />
                  </Animated.View>
                </View>

                {/* Action buttons */}
                <View style={styles.actionButtonsRow}>
                  <TouchableOpacity
                    style={[styles.actionButton, { backgroundColor: colors.error + '20' }]}
                    onPress={() => setViewMode('reject')}
                    disabled={isProcessing}
                  >
                    <IconSymbol name="xmark" size={24} color={colors.error} />
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[styles.actionButton, { backgroundColor: colors.warning + '20' }]}
                    onPress={handleSkip}
                    disabled={isProcessing}
                  >
                    <IconSymbol name="arrow.uturn.right" size={24} color={colors.warning} />
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[styles.actionButton, { backgroundColor: colors.primary + '20' }]}
                    onPress={() => setViewMode('edit')}
                    disabled={isProcessing}
                  >
                    <IconSymbol name="pencil" size={24} color={colors.primary} />
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[styles.actionButton, { backgroundColor: colors.success + '20' }]}
                    onPress={handleApprove}
                    disabled={isProcessing}
                  >
                    <IconSymbol name="checkmark" size={24} color={colors.success} />
                  </TouchableOpacity>
                </View>
              </View>
            );
          })()}

          {/* Processing Overlay */}
          {isProcessing && (
            <View style={styles.processingOverlay}>
              <BlurView intensity={60} tint={isDark ? 'dark' : 'light'} style={styles.processingBlur}>
                <ActivityIndicator size="large" color={colors.primary} />
              </BlurView>
            </View>
          )}
        </KeyboardAvoidingView>
      </View>

      {/* Source References Floating Card */}
      {showSourcesModal && currentQuestion?.source_info && (
        <View style={styles.sourcesOverlay}>
          <TouchableOpacity
            style={StyleSheet.absoluteFillObject}
            activeOpacity={1}
            onPress={() => setShowSourcesModal(false)}
          />
          <View style={[styles.sourcesFloatingCard, { backgroundColor: colors.card }]}>
            {/* Header */}
            <View style={[styles.sourcesModalHeader, { borderBottomColor: colors.border }]}>
              <View style={styles.sourcesModalHeaderLeft}>
                <IconSymbol name="doc.text.magnifyingglass" size={18} color={colors.primary} />
                <Text style={[styles.sourcesModalTitle, { color: colors.text }]}>Source References</Text>
                {currentQuestion.source_info.sources && (
                  <Text style={[styles.sourcesModalCount, { color: colors.textSecondary }]}>
                    {currentQuestion.source_info.sources.length} source{currentQuestion.source_info.sources.length !== 1 ? 's' : ''}
                  </Text>
                )}
              </View>
              <TouchableOpacity
                onPress={() => setShowSourcesModal(false)}
                style={[styles.sourcesModalClose, { backgroundColor: colors.border }]}
              >
                <IconSymbol name="xmark" size={14} color={colors.textSecondary} />
              </TouchableOpacity>
            </View>
            {/* Scrollable content */}
            <ScrollView
              style={{ maxHeight: SCREEN_HEIGHT * 0.55 }}
              contentContainerStyle={styles.sourcesModalScrollContent}
              showsVerticalScrollIndicator={true}
              nestedScrollEnabled
            >
              <QuestionSources sourceInfo={currentQuestion.source_info} defaultExpanded />
            </ScrollView>
          </View>
        </View>
      )}
    </Modal>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  flex: {
    flex: 1,
  },
  instructionsCard: {
    marginHorizontal: Spacing.md,
    marginTop: Spacing.sm,
    marginBottom: Spacing.md,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.md,
    borderWidth: 1,
  },
  instructionsTitle: {
    fontSize: FontSizes.xs,
    fontWeight: '600',
    marginBottom: Spacing.xs,
  },
  instructionsRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
  },
  instructionItem: {
    alignItems: 'center',
    gap: Spacing.xs,
  },
  instructionIcon: {
    width: 32,
    height: 32,
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
  },
  instructionText: {
    fontSize: FontSizes.xs,
    fontWeight: '500',
  },
  questionCardContainer: {
    flex: 1,
    marginHorizontal: Spacing.md,
    marginBottom: 0,
  },
  questionScrollView: {
    flex: 1,
  },
  questionScrollContent: {
    flexGrow: 1,
    paddingBottom: 140,
  },
  panelScrollView: {
    flex: 1,
  },
  panelScrollContent: {
    paddingHorizontal: Spacing.md,
    paddingBottom: 140,
  },
  dimmedQuestionContainer: {
    marginBottom: Spacing.md,
  },
  header: {
    paddingHorizontal: Spacing.md,
    paddingBottom: Spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(0,0,0,0.05)',
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: Spacing.sm,
  },
  closeButton: {
    padding: Spacing.xs,
  },
  headerCenter: {
    alignItems: 'center',
    flex: 1,
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
    paddingHorizontal: Spacing.sm,
  },
  progressBar: {
    height: 3,
    borderRadius: 2,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    borderRadius: 2,
  },
  questionCard: {
    padding: Spacing.md,
    borderRadius: BorderRadius.lg,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: Spacing.sm,
  },
  typeBadge: {
    paddingHorizontal: Spacing.sm,
    paddingVertical: 4,
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
    paddingVertical: 4,
    borderRadius: BorderRadius.sm,
  },
  metaBadgeText: {
    fontSize: FontSizes.xs,
  },
  subjectRow: {
    flexDirection: 'row',
    marginBottom: Spacing.xs,
  },
  subjectText: {
    fontSize: FontSizes.sm,
    fontWeight: '500',
  },
  topicText: {
    fontSize: FontSizes.sm,
    marginLeft: Spacing.xs,
  },
  questionText: {
    fontSize: FontSizes.md,
    lineHeight: 22,
    marginBottom: Spacing.md,
  },
  optionsContainer: {
    marginBottom: Spacing.md,
  },
  optionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: Spacing.xs,
    paddingHorizontal: Spacing.sm,
    borderRadius: BorderRadius.sm,
    marginBottom: 4,
  },
  optionLetter: {
    width: 24,
    height: 24,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: Spacing.sm,
  },
  optionLetterText: {
    fontSize: FontSizes.xs,
    fontWeight: '600',
  },
  optionText: {
    flex: 1,
    fontSize: FontSizes.sm,
  },
  answerBox: {
    padding: Spacing.sm,
    borderRadius: BorderRadius.sm,
    borderWidth: 1,
    marginBottom: Spacing.sm,
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
  explanationBox: {
    padding: Spacing.sm,
    borderRadius: BorderRadius.sm,
    marginBottom: Spacing.sm,
  },
  explanationLabel: {
    fontSize: FontSizes.xs,
    fontWeight: '600',
    marginBottom: 4,
  },
  explanationText: {
    fontSize: FontSizes.sm,
    lineHeight: 18,
  },
  sourcesSection: {
    marginTop: Spacing.md,
    paddingTop: Spacing.md,
    borderTopWidth: 1,
    borderTopColor: 'rgba(0,0,0,0.05)',
  },
  sourcesButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
    marginTop: Spacing.md,
    paddingHorizontal: Spacing.sm,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.md,
    borderWidth: 1,
  },
  sourcesButtonText: {
    flex: 1,
    fontSize: FontSizes.sm,
    fontWeight: '600',
  },
  // Sources floating card
  sourcesOverlay: {
    ...StyleSheet.absoluteFillObject,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: 'rgba(0,0,0,0.50)',
    zIndex: 100,
    paddingHorizontal: Spacing.lg,
  },
  sourcesFloatingCard: {
    width: '100%',
    borderRadius: BorderRadius.lg,
    overflow: 'hidden',
    boxShadow: '0px 8px 16px rgba(0,0,0,0.25)',
    elevation: 20,
  },
  sourcesModalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderBottomWidth: 1,
  },
  sourcesModalHeaderLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
    flex: 1,
  },
  sourcesModalTitle: {
    fontSize: FontSizes.md,
    fontWeight: '700',
  },
  sourcesModalCount: {
    fontSize: FontSizes.sm,
    marginLeft: 4,
  },
  sourcesModalClose: {
    width: 28,
    height: 28,
    borderRadius: 14,
    justifyContent: 'center',
    alignItems: 'center',
  },
  sourcesModalScroll: {
    flex: 1,
  },
  sourcesModalScrollContent: {
    padding: Spacing.md,
  },
  instructionsHint: {
    fontSize: 10,
    marginTop: 4,
    textAlign: 'center',
    opacity: 0.7,
  },
  teacherRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginTop: Spacing.sm,
    paddingTop: Spacing.sm,
    borderTopWidth: 1,
  },
  teacherText: {
    fontSize: FontSizes.xs,
  },
  dragHandle: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 5,
    paddingVertical: 10,
    paddingHorizontal: 20,
    alignSelf: 'center',
  },
  dragHandleDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  jeanButtonWrapper: {
    alignSelf: 'center',
    alignItems: 'center',
    justifyContent: 'center',
    width: 56,
    height: 56,
    borderRadius: 28,
    marginVertical: 4,
  },
  jeanButtonRing: {
    position: 'absolute',
    width: 40,
    height: 40,
    borderRadius: 20,
    borderWidth: 2,
  },
  jeanButton: {
    width: 28,
    height: 28,
    borderRadius: 14,
    borderWidth: 1.5,
    alignItems: 'center',
    justifyContent: 'flex-start',
    overflow: 'hidden',
  },
  jeanButtonHighlight: {
    width: '70%',
    height: '38%',
    borderRadius: 4,
    backgroundColor: 'rgba(255,255,255,0.45)',
    marginTop: 3,
  },
  swipeLabel: {
    position: 'absolute',
    top: 10,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.xs,
    borderRadius: BorderRadius.sm,
    borderWidth: 2,
    zIndex: 10,
  },
  approveLabel: {
    left: 10,
    borderColor: '#34C759',
    backgroundColor: 'rgba(52, 199, 89, 0.88)',
  },
  rejectLabel: {
    right: 10,
    borderColor: '#FF3B30',
    backgroundColor: 'rgba(255, 59, 48, 0.88)',
  },
  swipeLabelText: {
    fontSize: FontSizes.md,
    fontWeight: '800',
    color: '#fff',
  },
  // Inline Panels
  inlinePanel: {
    marginTop: Spacing.sm,
    marginBottom: Spacing.lg,
  },
  rejectCard: {
    padding: Spacing.md,
    borderRadius: BorderRadius.lg,
    borderWidth: 2,
    borderColor: '#FF3B30',
  },
  editCard: {
    padding: Spacing.md,
    borderRadius: BorderRadius.lg,
    borderWidth: 2,
    borderColor: '#5856D6',
  },
  panelHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: Spacing.sm,
  },
  panelTitle: {
    fontSize: FontSizes.md,
    fontWeight: '700',
  },
  panelSubtitle: {
    fontSize: FontSizes.sm,
    marginBottom: Spacing.sm,
  },
  reasonsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.xs,
    marginBottom: Spacing.sm,
  },
  reasonChip: {
    paddingHorizontal: Spacing.sm,
    paddingVertical: Spacing.xs,
    borderRadius: BorderRadius.full,
    borderWidth: 1,
  },
  reasonChipText: {
    fontSize: FontSizes.xs,
    fontWeight: '500',
  },
  notesInput: {
    borderWidth: 1,
    borderRadius: BorderRadius.md,
    padding: Spacing.sm,
    minHeight: 60,
    fontSize: FontSizes.sm,
    textAlignVertical: 'top',
    marginBottom: Spacing.sm,
  },
  panelButtons: {
    flexDirection: 'row',
    gap: Spacing.sm,
  },
  panelButton: {
    flex: 1,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.md,
    alignItems: 'center',
  },
  panelButtonText: {
    fontSize: FontSizes.sm,
    fontWeight: '600',
  },
  // Edit Panel
  editRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: Spacing.sm,
  },
  editLabel: {
    fontSize: FontSizes.sm,
    fontWeight: '500',
  },
  marksRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
  },
  marksButton: {
    width: 32,
    height: 32,
    borderRadius: BorderRadius.sm,
    justifyContent: 'center',
    alignItems: 'center',
  },
  marksInput: {
    width: 50,
    height: 32,
    borderWidth: 1,
    borderRadius: BorderRadius.sm,
    textAlign: 'center',
    fontSize: FontSizes.sm,
    fontWeight: '600',
  },
  difficultyRow: {
    flexDirection: 'row',
    gap: Spacing.xs,
  },
  difficultyButton: {
    paddingVertical: 4,
    paddingHorizontal: Spacing.sm,
    borderRadius: BorderRadius.sm,
    borderWidth: 2,
  },
  difficultyText: {
    fontSize: FontSizes.xs,
    fontWeight: '600',
  },
  coSection: {
    marginBottom: Spacing.sm,
  },
  coRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: Spacing.xs,
  },
  coLabel: {
    fontSize: FontSizes.sm,
    fontWeight: '600',
    width: 40,
  },
  coLevels: {
    flexDirection: 'row',
    gap: Spacing.xs,
  },
  coLevelButton: {
    width: 28,
    height: 28,
    borderRadius: 14,
    borderWidth: 2,
    justifyContent: 'center',
    alignItems: 'center',
  },
  coLevelText: {
    fontSize: FontSizes.xs,
    fontWeight: '700',
  },
  answerSection: {
    marginBottom: Spacing.sm,
  },
  mcqEditContainer: {
    gap: Spacing.sm,
  },
  mcqEditOptionRow: {
    marginBottom: Spacing.xs,
  },
  mcqEditOption: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: Spacing.sm,
    borderRadius: BorderRadius.md,
    borderWidth: 2,
    gap: Spacing.sm,
  },
  mcqEditOptionText: {
    flex: 1,
    fontSize: FontSizes.sm,
  },
  mcqEditButton: {
    padding: Spacing.xs,
    borderRadius: BorderRadius.sm,
  },
  mcqEditInput: {
    padding: Spacing.sm,
    borderRadius: BorderRadius.md,
    borderWidth: 2,
  },
  mcqEditInputRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: Spacing.xs,
  },
  mcqEditPrefix: {
    fontSize: FontSizes.sm,
    fontWeight: '600',
    paddingTop: 2,
  },
  mcqEditTextInput: {
    flex: 1,
    fontSize: FontSizes.sm,
    minHeight: 40,
    textAlignVertical: 'top',
  },
  mcqEditActions: {
    flexDirection: 'row',
    gap: Spacing.sm,
    marginTop: Spacing.sm,
    justifyContent: 'flex-end',
  },
  mcqEditActionButton: {
    padding: Spacing.sm,
    borderRadius: BorderRadius.sm,
    width: 32,
    height: 32,
    justifyContent: 'center',
    alignItems: 'center',
  },
  mcqEditHint: {
    fontSize: FontSizes.xs,
    fontStyle: 'italic',
    marginTop: Spacing.xs,
  },
  answerInput: {
    borderWidth: 1,
    borderRadius: BorderRadius.md,
    padding: Spacing.sm,
    minHeight: 80,
    fontSize: FontSizes.sm,
    textAlignVertical: 'top',
    marginBottom: Spacing.sm,
  },
  // Action Buttons
  actionButtonsRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: Spacing.lg,
    paddingHorizontal: Spacing.lg,
    paddingBottom: Spacing.sm,
    marginTop: Spacing.lg,
  },
  floatingActionBar: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    alignItems: 'center',
    overflow: 'hidden',
  },
  floatingBarBorder: {
    height: StyleSheet.hairlineWidth,
    alignSelf: 'stretch',
    marginBottom: Spacing.sm,
  },
  actionButton: {
    width: 52,
    height: 52,
    borderRadius: 26,
    justifyContent: 'center',
    alignItems: 'center',
  },
  processingOverlay: {
    ...StyleSheet.absoluteFillObject,
    justifyContent: 'center',
    alignItems: 'center',
  },
  processingBlur: {
    padding: Spacing.xl,
    borderRadius: BorderRadius.lg,
  },
});

export default SwipeVetting;
