/**
 * Take Test Screen - Gamified one-question-at-a-time test experience
 * Features: 3...2...1...GO! countdown, react-native-reanimated 120fps animations,
 * haptic feedback, AI Tutor feedback, celebration effects
 */
import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
    View,
    Text,
    StyleSheet,
    TouchableOpacity,
    ActivityIndicator,
    Alert,
    Dimensions,
    ScrollView,
} from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import * as Haptics from 'expo-haptics';
import ReAnimated, {
    useSharedValue,
    useAnimatedStyle,
    withSpring,
    withTiming,
    withDelay,
    withSequence,
    runOnJS,
    Easing,
    FadeIn,
    FadeOut,
    SlideInRight,
    SlideOutLeft,
} from 'react-native-reanimated';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { Colors, Spacing, FontSizes, BorderRadius } from '@/constants/theme';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { testsService } from '@/services/tests';

const { width: SCREEN_WIDTH } = Dimensions.get('window');

// Spring configs for high-refresh-rate smoothness
const SPRING_SNAPPY = { damping: 20, stiffness: 200, mass: 0.8 };
const SPRING_BOUNCY = { damping: 12, stiffness: 150, mass: 0.6 };
const SPRING_GENTLE = { damping: 15, stiffness: 100, mass: 1 };

export default function TakeTestScreen() {
    const colorScheme = useColorScheme() ?? 'light';
    const colors = Colors[colorScheme];
    const router = useRouter();
    const { testId } = useLocalSearchParams<{ testId: string }>();

    const [test, setTest] = useState<any>(null);
    const [questions, setQuestions] = useState<any[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [showCountdown, setShowCountdown] = useState(false);
    const [countdownValue, setCountdownValue] = useState('3');
    const [currentIndex, setCurrentIndex] = useState(0);
    const [answers, setAnswers] = useState<Record<string, string>>({});
    const [submitting, setSubmitting] = useState(false);
    const [showResult, setShowResult] = useState(false);
    const [result, setResult] = useState<any>(null);
    const [elapsedSeconds, setElapsedSeconds] = useState(0);
    const [testStarted, setTestStarted] = useState(false);

    // Reanimated shared values
    const countdownScale = useSharedValue(0);
    const countdownOpacity = useSharedValue(0);
    const overlayOpacity = useSharedValue(1);

    const questionSlideX = useSharedValue(0);
    const questionFade = useSharedValue(1);
    const questionScale = useSharedValue(1);
    const progressWidth = useSharedValue(0);

    const optionValues = useRef(
        Array.from({ length: 6 }, () => ({ opacity: useSharedValue(0), translateY: useSharedValue(30) }))
    ).current;

    const resultScale = useSharedValue(0);
    const resultOpacity = useSharedValue(0);
    const tutorFade = useSharedValue(0);
    const tutorSlide = useSharedValue(20);
    const confettiOp = useSharedValue(0);
    const pulseScale = useSharedValue(1);
    const selectedPop = useSharedValue(1);

    // Timer - only counts when test has started and not showing result
    useEffect(() => {
        if (!testStarted || showResult) return;
        const timer = setInterval(() => setElapsedSeconds((s) => s + 1), 1000);
        return () => clearInterval(timer);
    }, [testStarted, showResult]);

    // Pulse animation for submitting state
    useEffect(() => {
        if (submitting) {
            const interval = setInterval(() => {
                pulseScale.value = withSequence(
                    withTiming(1.06, { duration: 700, easing: Easing.inOut(Easing.ease) }),
                    withTiming(1, { duration: 700, easing: Easing.inOut(Easing.ease) })
                );
            }, 1400);
            return () => clearInterval(interval);
        }
    }, [submitting]);

    const formatTime = (s: number) => {
        const m = Math.floor(s / 60);
        const sec = s % 60;
        return `${m}:${sec.toString().padStart(2, '0')}`;
    };

    // ====== Countdown ======
    const startCountdown = useCallback(() => {
        setShowCountdown(true);
        const steps = ['3', '2', '1', 'GO!'];
        let i = 0;

        const showNext = () => {
            if (i >= steps.length) {
                // End countdown
                overlayOpacity.value = withTiming(0, { duration: 300 }, () => {
                    runOnJS(setShowCountdown)(false);
                    runOnJS(setTestStarted)(true);
                });
                return;
            }
            runOnJS(setCountdownValue)(steps[i]);
            runOnJS(Haptics.impactAsync)(Haptics.ImpactFeedbackStyle.Heavy);

            countdownScale.value = 0;
            countdownOpacity.value = 1;
            countdownScale.value = withSequence(
                withSpring(1.3, { damping: 8, stiffness: 300 }),
                withSpring(1, { damping: 14, stiffness: 200 })
            );

            // Fade out after showing
            setTimeout(() => {
                countdownOpacity.value = withTiming(0, { duration: 250 });
                i++;
                setTimeout(showNext, 300);
            }, 600);
        };

        setTimeout(showNext, 200);
    }, []);

    // Load test
    useEffect(() => {
        if (!testId) return;
        (async () => {
            try {
                const data = await testsService.getStudentTest(testId);
                if (data.already_submitted) {
                    Alert.alert('Already Submitted', 'You have already completed this test.', [
                        { text: 'OK', onPress: () => router.back() },
                    ]);
                    return;
                }
                setTest(data);
                setQuestions(data.questions || []);
                setIsLoading(false);
                // Start countdown after load
                setTimeout(() => startCountdown(), 300);
            } catch (error: any) {
                Alert.alert('Error', error?.response?.data?.detail || 'Failed to load test');
                router.back();
            }
        })();
    }, [testId]);

    // Animate first question after countdown
    useEffect(() => {
        if (testStarted && questions.length > 0) {
            animateQuestionEntry(questions[0]?.options?.length || 0);
        }
    }, [testStarted]);

    const animateQuestionEntry = (optCount: number) => {
        questionSlideX.value = SCREEN_WIDTH;
        questionFade.value = 0;
        questionScale.value = 0.92;

        // Reset option anims
        for (let i = 0; i < 6; i++) {
            optionValues[i].opacity.value = 0;
            optionValues[i].translateY.value = 30;
        }

        questionSlideX.value = withSpring(0, SPRING_SNAPPY);
        questionFade.value = withTiming(1, { duration: 300 });
        questionScale.value = withSpring(1, SPRING_SNAPPY);

        // Stagger options
        for (let i = 0; i < optCount; i++) {
            optionValues[i].opacity.value = withDelay(200 + i * 70, withTiming(1, { duration: 250 }));
            optionValues[i].translateY.value = withDelay(200 + i * 70, withSpring(0, SPRING_BOUNCY));
        }

        // Progress bar
        progressWidth.value = withTiming(
            ((currentIndex + 1) / Math.max(questions.length, 1)) * 100,
            { duration: 400, easing: Easing.out(Easing.cubic) }
        );
    };

    const animateQuestionExit = (direction: 'left' | 'right', cb: () => void) => {
        const toX = direction === 'left' ? -SCREEN_WIDTH : SCREEN_WIDTH;
        questionSlideX.value = withTiming(toX, { duration: 200, easing: Easing.in(Easing.cubic) });
        questionFade.value = withTiming(0, { duration: 200 }, () => {
            runOnJS(cb)();
        });
    };

    const goToQuestion = (newIndex: number) => {
        if (newIndex < 0 || newIndex >= questions.length) return;
        Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
        const direction = newIndex > currentIndex ? 'left' : 'right';
        animateQuestionExit(direction, () => {
            setCurrentIndex(newIndex);
            const opts = questions[newIndex]?.options || [];
            progressWidth.value = withTiming(
                ((newIndex + 1) / questions.length) * 100,
                { duration: 400 }
            );
            animateQuestionEntry(opts.length);
        });
    };

    const selectAnswer = (questionId: string, optLetter: string) => {
        Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
        setAnswers((prev) => ({ ...prev, [questionId]: optLetter }));
        selectedPop.value = withSequence(
            withTiming(1.03, { duration: 80 }),
            withSpring(1, { damping: 10, stiffness: 300 })
        );
    };

    const handleSubmit = () => {
        Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
        const unanswered = questions.length - Object.keys(answers).length;
        const msg = unanswered > 0
            ? `You have ${unanswered} unanswered question(s). Submit anyway?`
            : 'Ready to submit your test?';
        Alert.alert('Submit Test', msg, [
            { text: 'Cancel', style: 'cancel' },
            { text: 'Submit', onPress: doSubmit },
        ]);
    };

    const doSubmit = async () => {
        if (!testId) return;
        setSubmitting(true);
        try {
            const answerList = Object.entries(answers).map(([qId, sel]) => ({
                question_id: qId,
                selected_answer: sel,
                time_taken_seconds: Math.round(elapsedSeconds / questions.length),
            }));
            const res = await testsService.submitTest(testId, answerList, elapsedSeconds);
            setResult(res);
            setShowResult(true);

            const pct = Math.round(res.percentage || 0);
            if (pct >= 80) {
                Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
                confettiOp.value = withSequence(
                    withTiming(1, { duration: 300 }),
                    withDelay(1500, withTiming(0, { duration: 2000 }))
                );
            } else {
                Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
            }

            resultScale.value = withSpring(1, SPRING_GENTLE);
            resultOpacity.value = withTiming(1, { duration: 600 });

            if (res.tutor_feedback) {
                tutorFade.value = withDelay(1000, withTiming(1, { duration: 600 }));
                tutorSlide.value = withDelay(1000, withSpring(0, SPRING_GENTLE));
            }
        } catch (error: any) {
            Alert.alert('Error', error?.response?.data?.detail || 'Failed to submit');
        } finally {
            setSubmitting(false);
        }
    };

    // ====== Animated Styles ======
    const countdownStyle = useAnimatedStyle(() => ({
        transform: [{ scale: countdownScale.value }],
        opacity: countdownOpacity.value,
    }));
    const overlayStyle = useAnimatedStyle(() => ({
        opacity: overlayOpacity.value,
    }));
    const questionStyle = useAnimatedStyle(() => ({
        transform: [
            { translateX: questionSlideX.value },
            { scale: questionScale.value },
        ],
        opacity: questionFade.value,
    }));
    const progressStyle = useAnimatedStyle(() => ({
        width: `${progressWidth.value}%` as any,
    }));
    const resultAnimStyle = useAnimatedStyle(() => ({
        transform: [{ scale: resultScale.value }],
        opacity: resultOpacity.value,
    }));
    const tutorStyle = useAnimatedStyle(() => ({
        opacity: tutorFade.value,
        transform: [{ translateY: tutorSlide.value }],
    }));
    const confettiStyle = useAnimatedStyle(() => ({
        opacity: confettiOp.value,
    }));
    const pulseStyle = useAnimatedStyle(() => ({
        transform: [{ scale: pulseScale.value }],
    }));

    const makeOptionStyle = (i: number) =>
        useAnimatedStyle(() => ({
            opacity: optionValues[i].opacity.value,
            transform: [{ translateY: optionValues[i].translateY.value }],
        }));

    const optionAnimStyles = [
        makeOptionStyle(0), makeOptionStyle(1), makeOptionStyle(2),
        makeOptionStyle(3), makeOptionStyle(4), makeOptionStyle(5),
    ];

    // ====== Loading ======
    if (isLoading) {
        return (
            <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]}>
                <View style={styles.centered}>
                    <ActivityIndicator size="large" color={colors.primary} />
                    <Text style={{ color: colors.textSecondary, marginTop: 12 }}>Loading test...</Text>
                </View>
            </SafeAreaView>
        );
    }

    // ====== Countdown Overlay ======
    if (showCountdown) {
        return (
            <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]}>
                <ReAnimated.View style={[styles.countdownOverlay, overlayStyle, { backgroundColor: colors.background }]}>
                    <ReAnimated.View style={countdownStyle}>
                        <Text style={[
                            styles.countdownText,
                            {
                                color: countdownValue === 'GO!' ? colors.success : colors.primary,
                                fontSize: countdownValue === 'GO!' ? 72 : 120,
                            },
                        ]}>
                            {countdownValue}
                        </Text>
                    </ReAnimated.View>
                    <Text style={[styles.countdownSubtext, { color: colors.textSecondary }]}>
                        {test?.title || 'Get Ready!'}
                    </Text>
                    <Text style={[styles.countdownMeta, { color: colors.textTertiary }]}>
                        {questions.length} questions
                    </Text>
                </ReAnimated.View>
            </SafeAreaView>
        );
    }

    // ====== Submitting State ======
    if (submitting) {
        return (
            <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]}>
                <View style={styles.centered}>
                    <ReAnimated.View style={[{ alignItems: 'center' }, pulseStyle]}>
                        <Text style={{ fontSize: 48, marginBottom: 16 }}>🤖</Text>
                        <ActivityIndicator size="large" color={colors.primary} />
                        <Text style={{ color: colors.text, marginTop: 16, fontSize: FontSizes.lg, fontWeight: '600', textAlign: 'center' }}>
                            The Tutor is evaluating{'\n'}your answers...
                        </Text>
                        <Text style={{ color: colors.textSecondary, marginTop: 8, fontSize: FontSizes.sm }}>
                            This may take a moment
                        </Text>
                    </ReAnimated.View>
                </View>
            </SafeAreaView>
        );
    }

    // ====== Result Screen ======
    if (showResult && result) {
        const pct = Math.round(result.percentage || 0);
        const getGrade = () => {
            if (pct >= 90) return { emoji: '🏆', label: 'Outstanding!', color: '#FFD700' };
            if (pct >= 75) return { emoji: '🌟', label: 'Great Job!', color: '#34C759' };
            if (pct >= 60) return { emoji: '👍', label: 'Good Work!', color: '#007AFF' };
            if (pct >= 40) return { emoji: '💪', label: 'Keep Trying!', color: '#FF9500' };
            return { emoji: '📚', label: 'Study More!', color: '#FF3B30' };
        };
        const grade = getGrade();

        return (
            <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]}>
                <ScrollView contentContainerStyle={styles.resultScrollContent}>
                    {pct >= 80 && (
                        <ReAnimated.View style={[styles.confettiOverlay, confettiStyle]} pointerEvents="none">
                            <Text style={styles.confettiText}>🎉🎊✨🎉🎊✨🎉</Text>
                        </ReAnimated.View>
                    )}

                    <ReAnimated.View style={[{ alignItems: 'center' }, resultAnimStyle]}>
                        <Text style={{ fontSize: 80 }}>{grade.emoji}</Text>
                        <Text style={{ fontSize: 32, fontWeight: '900', color: colors.text, marginTop: 16 }}>
                            {grade.label}
                        </Text>

                        <View style={[styles.scoreCircle, { borderColor: grade.color }]}>
                            <Text style={{ fontSize: 48, fontWeight: '900', color: grade.color }}>{pct}%</Text>
                            <Text style={{ fontSize: FontSizes.sm, color: colors.textSecondary }}>
                                {result.score}/{result.total_marks}
                            </Text>
                        </View>

                        <View style={styles.resultStats}>
                            <View style={styles.resultStatItem}>
                                <Text style={{ fontSize: FontSizes.xxl, fontWeight: '800', color: colors.primary }}>
                                    {questions.length}
                                </Text>
                                <Text style={{ fontSize: FontSizes.xs, color: colors.textSecondary }}>Questions</Text>
                            </View>
                            <View style={styles.resultStatItem}>
                                <Text style={{ fontSize: FontSizes.xxl, fontWeight: '800', color: colors.success }}>
                                    {formatTime(elapsedSeconds)}
                                </Text>
                                <Text style={{ fontSize: FontSizes.xs, color: colors.textSecondary }}>Time</Text>
                            </View>
                            <View style={styles.resultStatItem}>
                                <Text style={{ fontSize: FontSizes.xxl, fontWeight: '800', color: '#FF9500' }}>
                                    {Object.keys(answers).length}
                                </Text>
                                <Text style={{ fontSize: FontSizes.xs, color: colors.textSecondary }}>Answered</Text>
                            </View>
                        </View>
                    </ReAnimated.View>

                    {result.tutor_feedback ? (
                        <ReAnimated.View style={[
                            styles.tutorCard,
                            { backgroundColor: colors.card, borderColor: colors.border },
                            tutorStyle,
                        ]}>
                            <View style={styles.tutorHeader}>
                                <View style={[styles.tutorAvatar, { backgroundColor: colors.primary + '20' }]}>
                                    <Text style={styles.tutorAvatarEmoji}>🤖</Text>
                                </View>
                                <View>
                                    <Text style={[styles.tutorName, { color: colors.text }]}>AI Tutor</Text>
                                    <Text style={[styles.tutorSubtitle, { color: colors.textTertiary }]}>Personalized feedback</Text>
                                </View>
                            </View>
                            <View style={[styles.tutorBubble, { backgroundColor: colors.primary + '10' }]}>
                                <Text style={[styles.tutorFeedbackText, { color: colors.text }]}>
                                    {result.tutor_feedback}
                                </Text>
                            </View>
                        </ReAnimated.View>
                    ) : null}

                    <TouchableOpacity
                        style={[styles.doneButton, { backgroundColor: colors.primary }]}
                        onPress={() => {
                            Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
                            router.back();
                        }}
                    >
                        <Text style={{ color: '#FFF', fontSize: FontSizes.md, fontWeight: '700' }}>
                            Done 🎉
                        </Text>
                    </TouchableOpacity>
                </ScrollView>
            </SafeAreaView>
        );
    }

    // ====== Waiting for countdown to finish ======
    if (!testStarted) {
        return (
            <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]}>
                <View style={styles.centered}>
                    <ActivityIndicator size="large" color={colors.primary} />
                </View>
            </SafeAreaView>
        );
    }

    // ====== Test-Taking Screen ======
    if (!questions.length) {
        return (
            <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]}>
                <View style={styles.centered}>
                    <Text style={{ color: colors.textSecondary }}>No questions in this test</Text>
                </View>
            </SafeAreaView>
        );
    }

    const currentQ = questions[currentIndex];
    const qId = currentQ?.question_id || currentQ?.id;
    const options = currentQ?.options || [];
    const selectedAnswer = answers[qId];
    const answeredCount = Object.keys(answers).length;
    const isLast = currentIndex === questions.length - 1;

    return (
        <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]}>
            {/* Top Bar */}
            <View style={styles.topBar}>
                <TouchableOpacity onPress={() => {
                    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
                    Alert.alert('Exit Test', 'Your progress will be lost. Are you sure?', [
                        { text: 'Continue Test', style: 'cancel' },
                        { text: 'Exit', style: 'destructive', onPress: () => router.back() },
                    ]);
                }}>
                    <IconSymbol name="xmark" size={24} color={colors.textSecondary} />
                </TouchableOpacity>

                {/* Progress Bar */}
                <View style={[styles.progressBarBg, { backgroundColor: colors.border }]}>
                    <ReAnimated.View style={[
                        styles.progressBarFill,
                        { backgroundColor: colors.primary },
                        progressStyle,
                    ]} />
                </View>

                {/* Timer */}
                <View style={styles.timerBadge}>
                    <IconSymbol name="clock" size={14} color={colors.textSecondary} />
                    <Text style={{ fontSize: FontSizes.sm, fontWeight: '600', color: colors.text }}>
                        {formatTime(elapsedSeconds)}
                    </Text>
                </View>
            </View>

            {/* Question Counter */}
            <View style={styles.counterRow}>
                <Text style={{ fontSize: FontSizes.sm, color: colors.textSecondary }}>
                    Question {currentIndex + 1} of {questions.length}
                </Text>
                <View style={[styles.answeredBadge, { backgroundColor: colors.primary + '15' }]}>
                    <Text style={{ fontSize: FontSizes.xs, fontWeight: '600', color: colors.primary }}>
                        {answeredCount}/{questions.length} answered
                    </Text>
                </View>
            </View>

            {/* Difficulty Badge */}
            {currentQ.difficulty_level && (
                <View style={{ paddingHorizontal: Spacing.lg, marginBottom: 4 }}>
                    <View style={[styles.diffBadge, {
                        backgroundColor: (currentQ.difficulty_level === 'easy' ? '#34C759' : currentQ.difficulty_level === 'medium' ? '#FF9500' : '#FF3B30') + '15',
                        alignSelf: 'flex-start',
                    }]}>
                        <Text style={{
                            fontSize: FontSizes.xs, fontWeight: '600', textTransform: 'capitalize',
                            color: currentQ.difficulty_level === 'easy' ? '#34C759' : currentQ.difficulty_level === 'medium' ? '#FF9500' : '#FF3B30',
                        }}>
                            {currentQ.difficulty_level} · {currentQ.marks} mark{currentQ.marks !== 1 ? 's' : ''}
                        </Text>
                    </View>
                </View>
            )}

            {/* Question Card */}
            <ReAnimated.View style={[styles.questionContainer, questionStyle]}>
                <View style={[styles.questionCard, { backgroundColor: colors.card, borderColor: colors.border }]}>
                    <Text style={[styles.questionText, { color: colors.text }]}>
                        {currentQ.question_text}
                    </Text>
                </View>

                {/* Options */}
                <View style={styles.optionsContainer}>
                    {options.map((opt: string, i: number) => {
                        const optLetter = opt.charAt(0).toUpperCase();
                        const isSelected = selectedAnswer === optLetter;
                        const animStyle = optionAnimStyles[i] || {};

                        return (
                            <ReAnimated.View key={i} style={animStyle}>
                                <TouchableOpacity
                                    style={[
                                        styles.optionButton,
                                        {
                                            backgroundColor: isSelected ? colors.primary + '12' : colors.card,
                                            borderColor: isSelected ? colors.primary : colors.border,
                                            borderWidth: isSelected ? 2 : 1,
                                        },
                                    ]}
                                    onPress={() => selectAnswer(qId, optLetter)}
                                    activeOpacity={0.7}
                                >
                                    <View style={[
                                        styles.optionCircle,
                                        {
                                            backgroundColor: isSelected ? colors.primary : 'transparent',
                                            borderColor: isSelected ? colors.primary : colors.textTertiary,
                                        },
                                    ]}>
                                        {isSelected ? (
                                            <Text style={{ color: '#FFF', fontSize: 12, fontWeight: '800' }}>✓</Text>
                                        ) : (
                                            <Text style={{ color: colors.textTertiary, fontSize: 12, fontWeight: '600' }}>
                                                {String.fromCharCode(65 + i)}
                                            </Text>
                                        )}
                                    </View>
                                    <Text style={[
                                        styles.optionText,
                                        {
                                            color: isSelected ? colors.primary : colors.text,
                                            fontWeight: isSelected ? '600' : '400',
                                        },
                                    ]} numberOfLines={3}>
                                        {opt.substring(opt.indexOf(')') + 1).trim() || opt}
                                    </Text>
                                </TouchableOpacity>
                            </ReAnimated.View>
                        );
                    })}
                </View>
            </ReAnimated.View>

            {/* Navigation */}
            <View style={styles.navBar}>
                <TouchableOpacity
                    style={[styles.navButton, { opacity: currentIndex === 0 ? 0.3 : 1 }]}
                    onPress={() => goToQuestion(currentIndex - 1)}
                    disabled={currentIndex === 0}
                >
                    <IconSymbol name="chevron.left" size={20} color={colors.primary} />
                    <Text style={{ color: colors.primary, fontWeight: '600' }}>Prev</Text>
                </TouchableOpacity>

                <View style={styles.dotsRow}>
                    {questions.map((_, i) => {
                        const qid = questions[i]?.question_id || questions[i]?.id;
                        const isAnswered = !!answers[qid];
                        const isCurrent = i === currentIndex;
                        return (
                            <TouchableOpacity
                                key={i}
                                onPress={() => goToQuestion(i)}
                                style={[
                                    styles.dot,
                                    {
                                        backgroundColor: isCurrent ? colors.primary
                                            : isAnswered ? colors.success
                                                : colors.border,
                                        width: isCurrent ? 12 : 8,
                                        height: isCurrent ? 12 : 8,
                                    },
                                ]}
                            />
                        );
                    })}
                </View>

                {isLast ? (
                    <TouchableOpacity
                        style={[styles.submitButton, { backgroundColor: colors.primary }]}
                        onPress={handleSubmit}
                        disabled={submitting}
                    >
                        <Text style={{ color: '#FFF', fontWeight: '700', fontSize: FontSizes.sm }}>
                            Submit ✨
                        </Text>
                    </TouchableOpacity>
                ) : (
                    <TouchableOpacity
                        style={styles.navButton}
                        onPress={() => goToQuestion(currentIndex + 1)}
                    >
                        <Text style={{ color: colors.primary, fontWeight: '600' }}>Next</Text>
                        <IconSymbol name="chevron.right" size={20} color={colors.primary} />
                    </TouchableOpacity>
                )}
            </View>
        </SafeAreaView>
    );
}

const styles = StyleSheet.create({
    container: { flex: 1 },
    centered: { flex: 1, justifyContent: 'center', alignItems: 'center' },
    // Countdown
    countdownOverlay: {
        ...StyleSheet.absoluteFillObject,
        justifyContent: 'center',
        alignItems: 'center',
        zIndex: 100,
    },
    countdownText: {
        fontWeight: '900',
        textAlign: 'center',
    },
    countdownSubtext: {
        fontSize: FontSizes.lg,
        fontWeight: '600',
        marginTop: 24,
    },
    countdownMeta: {
        fontSize: FontSizes.sm,
        marginTop: 8,
    },
    // Top bar
    topBar: {
        flexDirection: 'row',
        alignItems: 'center',
        paddingHorizontal: Spacing.lg,
        paddingVertical: Spacing.sm,
        gap: Spacing.sm,
    },
    progressBarBg: {
        flex: 1,
        height: 8,
        borderRadius: 4,
        overflow: 'hidden',
    },
    progressBarFill: {
        height: '100%',
        borderRadius: 4,
    },
    timerBadge: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: 4,
    },
    counterRow: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        paddingHorizontal: Spacing.lg,
        marginBottom: Spacing.sm,
    },
    answeredBadge: {
        paddingHorizontal: 10,
        paddingVertical: 4,
        borderRadius: BorderRadius.full,
    },
    diffBadge: {
        paddingHorizontal: 10,
        paddingVertical: 4,
        borderRadius: BorderRadius.full,
    },
    questionContainer: {
        flex: 1,
        paddingHorizontal: Spacing.lg,
    },
    questionCard: {
        borderRadius: BorderRadius.xl,
        padding: Spacing.lg,
        borderWidth: 1,
        marginBottom: Spacing.md,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.05,
        shadowRadius: 8,
        elevation: 2,
    },
    questionText: {
        fontSize: FontSizes.md + 1,
        fontWeight: '500',
        lineHeight: 26,
    },
    optionsContainer: {
        gap: 10,
    },
    optionButton: {
        flexDirection: 'row',
        alignItems: 'center',
        padding: Spacing.md,
        borderRadius: BorderRadius.lg,
        gap: 12,
    },
    optionCircle: {
        width: 28,
        height: 28,
        borderRadius: 14,
        borderWidth: 2,
        justifyContent: 'center',
        alignItems: 'center',
    },
    optionText: {
        fontSize: FontSizes.sm + 1,
        flex: 1,
        lineHeight: 20,
    },
    navBar: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        paddingHorizontal: Spacing.lg,
        paddingVertical: Spacing.md,
        paddingBottom: 70,
        borderTopWidth: 1,
        borderTopColor: 'rgba(0,0,0,0.06)',
    },
    navButton: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: 4,
        paddingVertical: 8,
        paddingHorizontal: 12,
    },
    dotsRow: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: 4,
        flexWrap: 'wrap',
        maxWidth: SCREEN_WIDTH * 0.4,
        justifyContent: 'center',
    },
    dot: {
        borderRadius: 6,
    },
    submitButton: {
        paddingVertical: 10,
        paddingHorizontal: 20,
        borderRadius: BorderRadius.lg,
    },
    // Result
    confettiOverlay: {
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        alignItems: 'center',
        zIndex: 10,
    },
    confettiText: { fontSize: 40, letterSpacing: 8 },
    resultScrollContent: {
        flexGrow: 1,
        justifyContent: 'center',
        alignItems: 'center',
        padding: Spacing.xl,
        paddingBottom: 100,
    },
    scoreCircle: {
        width: 160,
        height: 160,
        borderRadius: 80,
        borderWidth: 6,
        justifyContent: 'center',
        alignItems: 'center',
        marginTop: 24,
        marginBottom: 24,
    },
    resultStats: {
        flexDirection: 'row',
        gap: Spacing.xl,
        marginBottom: 32,
    },
    resultStatItem: {
        alignItems: 'center',
    },
    doneButton: {
        paddingVertical: 14,
        paddingHorizontal: 48,
        borderRadius: BorderRadius.xl,
        marginTop: Spacing.lg,
    },
    // AI Tutor
    tutorCard: {
        width: '100%',
        marginTop: Spacing.lg,
        marginBottom: Spacing.md,
        borderRadius: BorderRadius.xl,
        padding: Spacing.lg,
        borderWidth: 1,
    },
    tutorHeader: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: Spacing.sm,
        marginBottom: Spacing.md,
    },
    tutorAvatar: {
        width: 40,
        height: 40,
        borderRadius: 20,
        justifyContent: 'center',
        alignItems: 'center',
    },
    tutorAvatarEmoji: { fontSize: 22 },
    tutorName: { fontSize: FontSizes.md, fontWeight: '700' },
    tutorSubtitle: { fontSize: FontSizes.xs },
    tutorBubble: {
        borderRadius: BorderRadius.lg,
        padding: Spacing.md,
    },
    tutorFeedbackText: {
        fontSize: FontSizes.sm + 1,
        lineHeight: 22,
    },
});
