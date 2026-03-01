/**
 * Take Test Screen - Gamified one-question-at-a-time test experience
 * Features: animated transitions, progress bar, timer, streak counter, score reveal
 */
import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
    View,
    Text,
    StyleSheet,
    TouchableOpacity,
    ActivityIndicator,
    Alert,
    Animated,
    Dimensions,
} from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { Colors, Spacing, FontSizes, BorderRadius } from '@/constants/theme';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { testsService } from '@/services/tests';

const { width: SCREEN_WIDTH } = Dimensions.get('window');

export default function TakeTestScreen() {
    const colorScheme = useColorScheme() ?? 'light';
    const colors = Colors[colorScheme];
    const router = useRouter();
    const { testId } = useLocalSearchParams<{ testId: string }>();

    const [test, setTest] = useState<any>(null);
    const [questions, setQuestions] = useState<any[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [currentIndex, setCurrentIndex] = useState(0);
    const [answers, setAnswers] = useState<Record<string, string>>({});
    const [submitting, setSubmitting] = useState(false);
    const [showResult, setShowResult] = useState(false);
    const [result, setResult] = useState<any>(null);
    const [elapsedSeconds, setElapsedSeconds] = useState(0);

    // Animations
    const slideAnim = useRef(new Animated.Value(0)).current;
    const fadeAnim = useRef(new Animated.Value(1)).current;
    const scaleAnim = useRef(new Animated.Value(1)).current;
    const progressAnim = useRef(new Animated.Value(0)).current;
    const optionAnims = useRef<Animated.Value[]>([]).current;
    const resultScaleAnim = useRef(new Animated.Value(0)).current;
    const resultFadeAnim = useRef(new Animated.Value(0)).current;

    // Timer
    useEffect(() => {
        if (isLoading || showResult) return;
        const timer = setInterval(() => setElapsedSeconds((s) => s + 1), 1000);
        return () => clearInterval(timer);
    }, [isLoading, showResult]);

    const formatTime = (s: number) => {
        const m = Math.floor(s / 60);
        const sec = s % 60;
        return `${m}:${sec.toString().padStart(2, '0')}`;
    };

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
                // Init option animations
                const opts = data.questions?.[0]?.options || [];
                for (let i = 0; i < 6; i++) {
                    if (!optionAnims[i]) optionAnims.push(new Animated.Value(0));
                }
                // Animate first question entry
                setTimeout(() => animateQuestionEntry(opts.length), 300);
            } catch (error: any) {
                Alert.alert('Error', error?.response?.data?.detail || 'Failed to load test');
                router.back();
            } finally {
                setIsLoading(false);
            }
        })();
    }, [testId]);

    const animateQuestionEntry = (optCount: number) => {
        slideAnim.setValue(SCREEN_WIDTH);
        fadeAnim.setValue(0);
        scaleAnim.setValue(0.9);

        // Reset option anims
        for (let i = 0; i < 6; i++) {
            if (optionAnims[i]) optionAnims[i].setValue(0);
        }

        Animated.parallel([
            Animated.spring(slideAnim, { toValue: 0, useNativeDriver: true, tension: 50, friction: 9 }),
            Animated.timing(fadeAnim, { toValue: 1, duration: 300, useNativeDriver: true }),
            Animated.spring(scaleAnim, { toValue: 1, useNativeDriver: true, tension: 50, friction: 9 }),
        ]).start();

        // Stagger option animations
        for (let i = 0; i < optCount; i++) {
            if (optionAnims[i]) {
                Animated.timing(optionAnims[i], {
                    toValue: 1,
                    duration: 250,
                    delay: 200 + i * 80,
                    useNativeDriver: true,
                }).start();
            }
        }

        // Progress bar
        Animated.timing(progressAnim, {
            toValue: (currentIndex + 1) / Math.max(questions.length, 1),
            duration: 400,
            useNativeDriver: false,
        }).start();
    };

    const animateQuestionExit = (direction: 'left' | 'right', cb: () => void) => {
        const toX = direction === 'left' ? -SCREEN_WIDTH : SCREEN_WIDTH;
        Animated.parallel([
            Animated.timing(slideAnim, { toValue: toX, duration: 200, useNativeDriver: true }),
            Animated.timing(fadeAnim, { toValue: 0, duration: 200, useNativeDriver: true }),
        ]).start(cb);
    };

    const goToQuestion = (newIndex: number) => {
        if (newIndex < 0 || newIndex >= questions.length) return;
        const direction = newIndex > currentIndex ? 'left' : 'right';
        animateQuestionExit(direction, () => {
            setCurrentIndex(newIndex);
            const opts = questions[newIndex]?.options || [];
            // Update progress
            Animated.timing(progressAnim, {
                toValue: (newIndex + 1) / questions.length,
                duration: 400,
                useNativeDriver: false,
            }).start();
            animateQuestionEntry(opts.length);
        });
    };

    const selectAnswer = (questionId: string, optLetter: string) => {
        setAnswers((prev) => ({ ...prev, [questionId]: optLetter }));

        // Bounce animation on selection
        Animated.sequence([
            Animated.timing(scaleAnim, { toValue: 1.02, duration: 100, useNativeDriver: true }),
            Animated.spring(scaleAnim, { toValue: 1, useNativeDriver: true, tension: 100, friction: 6 }),
        ]).start();
    };

    const handleSubmit = () => {
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

            // Animate result
            Animated.parallel([
                Animated.spring(resultScaleAnim, { toValue: 1, useNativeDriver: true, tension: 40, friction: 5 }),
                Animated.timing(resultFadeAnim, { toValue: 1, duration: 600, useNativeDriver: true }),
            ]).start();
        } catch (error: any) {
            Alert.alert('Error', error?.response?.data?.detail || 'Failed to submit');
        } finally {
            setSubmitting(false);
        }
    };

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
                <View style={styles.resultContainer}>
                    <Animated.View style={{
                        transform: [{ scale: resultScaleAnim }],
                        opacity: resultFadeAnim,
                        alignItems: 'center',
                    }}>
                        <Text style={{ fontSize: 80 }}>{grade.emoji}</Text>
                        <Text style={{ fontSize: 32, fontWeight: '900', color: colors.text, marginTop: 16 }}>
                            {grade.label}
                        </Text>

                        {/* Score Circle */}
                        <View style={[styles.scoreCircle, { borderColor: grade.color }]}>
                            <Text style={{ fontSize: 48, fontWeight: '900', color: grade.color }}>{pct}%</Text>
                            <Text style={{ fontSize: FontSizes.sm, color: colors.textSecondary }}>
                                {result.score}/{result.total_marks}
                            </Text>
                        </View>

                        {/* Stats Row */}
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

                        <TouchableOpacity
                            style={[styles.doneButton, { backgroundColor: colors.primary }]}
                            onPress={() => router.back()}
                        >
                            <Text style={{ color: '#FFF', fontSize: FontSizes.md, fontWeight: '700' }}>
                                Done 🎉
                            </Text>
                        </TouchableOpacity>
                    </Animated.View>
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
                    Alert.alert('Exit Test', 'Your progress will be lost. Are you sure?', [
                        { text: 'Continue Test', style: 'cancel' },
                        { text: 'Exit', style: 'destructive', onPress: () => router.back() },
                    ]);
                }}>
                    <IconSymbol name="xmark" size={24} color={colors.textSecondary} />
                </TouchableOpacity>

                {/* Progress Bar */}
                <View style={[styles.progressBarBg, { backgroundColor: colors.border }]}>
                    <Animated.View style={[
                        styles.progressBarFill,
                        {
                            backgroundColor: colors.primary,
                            width: progressAnim.interpolate({
                                inputRange: [0, 1],
                                outputRange: ['0%', '100%'],
                            }),
                        },
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
            <Animated.View style={[
                styles.questionContainer,
                {
                    transform: [
                        { translateX: slideAnim },
                        { scale: scaleAnim },
                    ],
                    opacity: fadeAnim,
                },
            ]}>
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
                        const anim = optionAnims[i] || new Animated.Value(1);

                        return (
                            <Animated.View
                                key={i}
                                style={{
                                    opacity: anim,
                                    transform: [{
                                        translateY: anim.interpolate({
                                            inputRange: [0, 1],
                                            outputRange: [30, 0],
                                        }),
                                    }],
                                }}
                            >
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
                            </Animated.View>
                        );
                    })}
                </View>
            </Animated.View>

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

                {/* Question dots */}
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
                        {submitting ? (
                            <ActivityIndicator size="small" color="#FFF" />
                        ) : (
                            <Text style={{ color: '#FFF', fontWeight: '700', fontSize: FontSizes.sm }}>
                                Submit ✨
                            </Text>
                        )}
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
    // Result styles
    resultContainer: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
        padding: Spacing.xl,
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
    },
});
