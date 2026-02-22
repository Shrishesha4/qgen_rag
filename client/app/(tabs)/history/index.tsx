import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
    View,
    Text,
    StyleSheet,
    ScrollView,
    TouchableOpacity,
    ActivityIndicator,
    Modal,
    RefreshControl,
    Alert,
    Dimensions,
} from 'react-native';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { GlassCard } from '@/components/ui/glass-card';
import { Colors, Spacing, BorderRadius, FontSizes } from '@/constants/theme';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { questionsService, GenerationSession, SessionQuestion } from '@/services/questions';

// Type for version chain groups
interface VersionChain {
    chainId: string;
    questions: SessionQuestion[]; // Newest first
}

// Helper to group questions into version chains
function groupIntoVersionChains(questions: SessionQuestion[]): VersionChain[] {
    const qById = new Map<string, SessionQuestion>();
    questions.forEach(q => qById.set(q.id, q));
    
    const visited = new Set<string>();
    const chains: VersionChain[] = [];
    
    for (const q of questions) {
        if (visited.has(q.id)) continue;
        
        // Walk backwards to find the root (oldest version)
        let root = q;
        while (root.replaces_id && qById.has(root.replaces_id)) {
            root = qById.get(root.replaces_id)!;
        }
        
        // Walk forwards from root to build chain
        const chain: SessionQuestion[] = [];
        let current: SessionQuestion | undefined = root;
        while (current) {
            chain.push(current);
            visited.add(current.id);
            // Find next version (the one with replaces_id == current.id)
            current = questions.find(nq => nq.replaces_id === current!.id && !visited.has(nq.id));
        }
        
        // Reverse so newest is first
        chain.reverse();
        chains.push({ chainId: root.id, questions: chain });
    }
    
    // Sort chains by the original question's generated_at
    chains.sort((a, b) => {
        const aOldest = a.questions[a.questions.length - 1];
        const bOldest = b.questions[b.questions.length - 1];
        return new Date(aOldest.generated_at || 0).getTime() - new Date(bOldest.generated_at || 0).getTime();
    });
    
    return chains;
}

export default function HistoryScreen() {
    const colorScheme = useColorScheme();
    const colors = Colors[colorScheme ?? 'light'];

    const [sessions, setSessions] = useState<GenerationSession[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [page, setPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);

    // Session detail modal
    const [selectedSession, setSelectedSession] = useState<GenerationSession | null>(null);
    const [sessionQuestions, setSessionQuestions] = useState<SessionQuestion[]>([]);
    const [isLoadingQuestions, setIsLoadingQuestions] = useState(false);
    
    // Track current visible page for each version chain
    const [chainCurrentPage, setChainCurrentPage] = useState<Record<string, number>>({});

    const loadSessions = useCallback(async (pageNum: number = 1, refresh = false) => {
        try {
            if (refresh) setIsRefreshing(true);
            else setIsLoading(true);

            const response = await questionsService.listSessions(undefined, undefined, pageNum, 50);
            setSessions(response.sessions);
            setTotalPages(response.pagination.pages);
            setPage(pageNum);
        } catch (error) {
            console.error('[History] Failed to load:', error);
        } finally {
            setIsLoading(false);
            setIsRefreshing(false);
        }
    }, []);

    useEffect(() => {
        loadSessions();
    }, [loadSessions]);

    const openSessionDetail = async (session: GenerationSession) => {
        setSelectedSession(session);
        setIsLoadingQuestions(true);
        try {
            const data = await questionsService.getSessionQuestions(session.id);
            setSessionQuestions(data.questions);
        } catch (error) {
            console.error('[History] Failed to load session questions:', error);
            setSessionQuestions([]);
        } finally {
            setIsLoadingQuestions(false);
        }
    };

    const handleDeleteSession = (session: GenerationSession) => {
        const count = session.questions_generated || 0;
        Alert.alert(
            'Delete Session',
            `This will permanently delete this session and ${count} associated question${count !== 1 ? 's' : ''}. This action cannot be undone.`,
            [
                { text: 'Cancel', style: 'cancel' },
                {
                    text: 'Delete',
                    style: 'destructive',
                    onPress: async () => {
                        try {
                            await questionsService.deleteSession(session.id);
                            setSessions(prev => prev.filter(s => s.id !== session.id));
                            if (selectedSession?.id === session.id) {
                                setSelectedSession(null);
                            }
                        } catch (error) {
                            console.error('[History] Failed to delete:', error);
                            Alert.alert('Error', 'Failed to delete session.');
                        }
                    },
                },
            ],
        );
    };

    const getMethodInfo = (method: string | null) => {
        switch (method) {
            case 'quick': return { label: 'Quick Generate', color: '#007AFF', icon: 'bolt.fill' as const };
            case 'rubric': return { label: 'Rubric Generate', color: '#AF52DE', icon: 'doc.badge.gearshape.fill' as const };
            case 'chapter': return { label: 'Chapter-wise', color: '#34C759', icon: 'book.fill' as const };
            case 'import': return { label: 'Excel/CSV Import', color: '#FF9500', icon: 'square.and.arrow.down.fill' as const };
            default: return { label: 'Generated', color: '#8E8E93', icon: 'sparkles' as const };
        }
    };

    const formatDate = (dateStr: string | null) => {
        if (!dateStr) return '';
        const d = new Date(dateStr);
        return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    };

    const formatTime = (dateStr: string | null) => {
        if (!dateStr) return '';
        const d = new Date(dateStr);
        return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    };

    // Group sessions by date
    const groupedSessions: { [date: string]: GenerationSession[] } = {};
    for (const session of sessions) {
        const date = formatDate(session.started_at);
        if (!groupedSessions[date]) groupedSessions[date] = [];
        groupedSessions[date].push(session);
    }

    if (isLoading) {
        return (
            <View style={[styles.centerContainer, { backgroundColor: colors.background }]}>
                <ActivityIndicator size="large" color={colors.primary} />
                <Text style={[styles.loadingText, { color: colors.textSecondary }]}>Loading history...</Text>
            </View>
        );
    }

    return (
        <View style={[styles.container, { backgroundColor: colors.background }]}>
            <ScrollView
                contentContainerStyle={styles.scrollContent}
                showsVerticalScrollIndicator={false}
                refreshControl={
                    <RefreshControl refreshing={isRefreshing} onRefresh={() => loadSessions(1, true)} />
                }
            >
                {sessions.length === 0 ? (
                    <View style={styles.emptyState}>
                        <IconSymbol name="clock.arrow.circlepath" size={64} color={colors.textTertiary} />
                        <Text style={[styles.emptyTitle, { color: colors.text }]}>No Generation History</Text>
                        <Text style={[styles.emptySubtitle, { color: colors.textSecondary }]}>
                            Your question generation sessions will appear here
                        </Text>
                    </View>
                ) : (
                    Object.entries(groupedSessions).map(([date, dateSessions]) => (
                        <View key={date} style={styles.dateGroup}>
                            <Text style={[styles.dateHeader, { color: colors.textSecondary }]}>{date}</Text>
                            {dateSessions.map((session) => {
                                const info = getMethodInfo(session.generation_method);
                                return (
                                    <TouchableOpacity
                                        key={session.id}
                                        activeOpacity={0.7}
                                        onPress={() => openSessionDetail(session)}
                                        onLongPress={() => handleDeleteSession(session)}
                                    >
                                        <GlassCard style={styles.sessionCard}>
                                            {/* Row 1: Method badge + time + delete */}
                                            <View style={styles.sessionRow}>
                                                <View style={[styles.methodBadge, { backgroundColor: info.color + '20' }]}>
                                                    <IconSymbol name={info.icon} size={13} color={info.color} />
                                                    <Text style={[styles.methodLabel, { color: info.color }]}>{info.label}</Text>
                                                </View>
                                                <View style={styles.sessionRowRight}>
                                                    <Text style={[styles.sessionTime, { color: colors.textTertiary }]}>
                                                        {formatTime(session.started_at)}
                                                    </Text>
                                                    {/* <TouchableOpacity onPress={() => handleDeleteSession(session)} hitSlop={8}>
                                                        <IconSymbol name="trash" size={14} color={colors.textTertiary} />
                                                    </TouchableOpacity> */}
                                                </View>
                                            </View>

                                            {/* Row 2: Subject + Topic/Chapter */}
                                            {(session.subject_name || session.topic_name) && (
                                                <View style={styles.subjectRow}>
                                                    {session.subject_name && (
                                                        <View style={styles.subjectChip}>
                                                            <IconSymbol name="book.closed.fill" size={12} color={colors.primary} />
                                                            <Text style={[styles.subjectText, { color: colors.text }]} numberOfLines={1}>
                                                                {session.subject_code ? `${session.subject_code} — ` : ''}{session.subject_name}
                                                            </Text>
                                                        </View>
                                                    )}
                                                    {session.topic_name && (
                                                        <View style={styles.topicChip}>
                                                            <IconSymbol name="bookmark.fill" size={11} color="#FF9500" />
                                                            <Text style={[styles.topicText, { color: colors.textSecondary }]} numberOfLines={1}>
                                                                {session.topic_name}
                                                            </Text>
                                                        </View>
                                                    )}
                                                </View>
                                            )}

                                            {/* Row 3: Stats */}
                                            <View style={styles.statsRow}>
                                                <View style={styles.stat}>
                                                    <Text style={[styles.statValue, { color: colors.primary }]}>
                                                        {session.questions_generated}
                                                    </Text>
                                                    <Text style={[styles.statLabel, { color: colors.textSecondary }]}>Generated</Text>
                                                </View>
                                                {session.questions_failed > 0 && (
                                                    <View style={styles.stat}>
                                                        <Text style={[styles.statValue, { color: '#FF3B30' }]}>
                                                            {session.questions_failed}
                                                        </Text>
                                                        <Text style={[styles.statLabel, { color: colors.textSecondary }]}>Skipped</Text>
                                                    </View>
                                                )}
                                                {session.requested_difficulty && (
                                                    <View style={[styles.infoBadge, { backgroundColor: colors.card }]}>
                                                        <Text style={{ fontSize: 10, color: colors.textSecondary }}>
                                                            {session.requested_difficulty.toUpperCase()}
                                                        </Text>
                                                    </View>
                                                )}
                                                <View style={[styles.statusChip, {
                                                    backgroundColor: session.status === 'completed' ? '#34C75915' : '#FF3B3015',
                                                }]}>
                                                    <Text style={{
                                                        fontSize: 10,
                                                        fontWeight: '600',
                                                        color: session.status === 'completed' ? '#34C759' : '#FF3B30',
                                                    }}>
                                                        {session.status === 'completed' ? '✓ Done' : session.status}
                                                    </Text>
                                                </View>
                                            </View>

                                            {/* Row 4: Focus topics / source file */}
                                            {session.focus_topics && session.focus_topics.length > 0 && (
                                                <View style={styles.focusRow}>
                                                    <Text style={{ fontSize: 10, color: colors.textTertiary }}>Focus: </Text>
                                                    {session.focus_topics.slice(0, 3).map((t, i) => (
                                                        <View key={i} style={[styles.focusChip, { backgroundColor: colors.card }]}>
                                                            <Text style={{ fontSize: 10, color: colors.textSecondary }}>{t}</Text>
                                                        </View>
                                                    ))}
                                                    {session.focus_topics.length > 3 && (
                                                        <Text style={{ fontSize: 10, color: colors.textTertiary }}>+{session.focus_topics.length - 3}</Text>
                                                    )}
                                                </View>
                                            )}
                                            {session.generation_config?.source_file ? (
                                                <Text style={[styles.sourceFile, { color: colors.textTertiary }]} numberOfLines={1}>
                                                    {'📄 ' + String(session.generation_config.source_file)}
                                                </Text>
                                            ) : null}
                                        </GlassCard>
                                    </TouchableOpacity>
                                );
                            })}
                        </View>
                    ))
                )}

                {totalPages > 1 && (
                    <View style={styles.pagination}>
                        <TouchableOpacity
                            style={[styles.pageButton, { opacity: page <= 1 ? 0.4 : 1 }]}
                            disabled={page <= 1}
                            onPress={() => loadSessions(page - 1)}
                        >
                            <Text style={[styles.pageButtonText, { color: colors.primary }]}>← Previous</Text>
                        </TouchableOpacity>
                        <Text style={[styles.pageInfo, { color: colors.textSecondary }]}>
                            Page {page} of {totalPages}
                        </Text>
                        <TouchableOpacity
                            style={[styles.pageButton, { opacity: page >= totalPages ? 0.4 : 1 }]}
                            disabled={page >= totalPages}
                            onPress={() => loadSessions(page + 1)}
                        >
                            <Text style={[styles.pageButtonText, { color: colors.primary }]}>Next →</Text>
                        </TouchableOpacity>
                    </View>
                )}
                <View style={{ height: 100 }} />
            </ScrollView>

            {/* ──────── Session Detail Modal ──────── */}
            <Modal
                visible={selectedSession !== null}
                animationType="slide"
                presentationStyle="pageSheet"
                onRequestClose={() => setSelectedSession(null)}
            >
                <View style={[styles.modalContainer, { backgroundColor: colors.background }]}>
                    {/* Modal Header */}
                    <View style={styles.modalHeader}>
                        <View style={styles.modalTopRow}>
                            <TouchableOpacity onPress={() => setSelectedSession(null)}>
                                <IconSymbol name="xmark.circle.fill" size={28} color={colors.textTertiary} />
                            </TouchableOpacity>
                            {/* {selectedSession && (
                                <TouchableOpacity onPress={() => handleDeleteSession(selectedSession)}>
                                    <IconSymbol name="trash.fill" size={20} color="#FF3B30" />
                                </TouchableOpacity>
                            )} */}
                        </View>
                        {selectedSession && (
                            <View style={styles.modalMeta}>
                                <View style={[styles.methodBadge, { backgroundColor: getMethodInfo(selectedSession.generation_method).color + '20' }]}>
                                    <IconSymbol name={getMethodInfo(selectedSession.generation_method).icon} size={13} color={getMethodInfo(selectedSession.generation_method).color} />
                                    <Text style={[styles.methodLabel, { color: getMethodInfo(selectedSession.generation_method).color }]}>
                                        {getMethodInfo(selectedSession.generation_method).label}
                                    </Text>
                                </View>
                                {selectedSession.subject_name && (
                                    <Text style={[styles.modalSubject, { color: colors.text }]}>
                                        {selectedSession.subject_code ? `${selectedSession.subject_code} — ` : ''}{selectedSession.subject_name}
                                    </Text>
                                )}
                                {selectedSession.topic_name && (
                                    <Text style={{ fontSize: FontSizes.sm, color: colors.textSecondary, marginTop: 2 }}>
                                        Chapter: {selectedSession.topic_name}
                                    </Text>
                                )}
                                <Text style={{ fontSize: FontSizes.xs, color: colors.textTertiary, marginTop: 4 }}>
                                    {formatDate(selectedSession.started_at)} at {formatTime(selectedSession.started_at)}
                                    {' · '}{sessionQuestions.length} question{sessionQuestions.length !== 1 ? 's' : ''}
                                </Text>
                            </View>
                        )}
                    </View>

                    {/* Questions List */}
                    <ScrollView style={styles.modalScroll} showsVerticalScrollIndicator={false}>
                        {isLoadingQuestions ? (
                            <View style={{ paddingTop: 60, alignItems: 'center' }}>
                                <ActivityIndicator size="large" color={colors.primary} />
                            </View>
                        ) : sessionQuestions.length === 0 ? (
                            <Text style={[styles.noQuestionsText, { color: colors.textSecondary }]}>
                                No questions found in this session
                            </Text>
                        ) : (
                            groupIntoVersionChains(sessionQuestions).map((chain, chainIndex) => {
                                const hasVersions = chain.questions.length > 1;
                                const screenWidth = Dimensions.get('window').width;
                                const cardWidth = screenWidth - Spacing.md * 4;
                                
                                return (
                                    <View key={chain.chainId} style={styles.versionChainContainer}>
                                        {/* Chain header with version indicator */}
                                        <View style={styles.chainHeader}>
                                            <View style={[styles.qIndex, { backgroundColor: colors.primary + '20' }]}>
                                                <Text style={[styles.qIndexText, { color: colors.primary }]}>{chainIndex + 1}</Text>
                                            </View>
                                            {hasVersions && (
                                                <View style={styles.versionIndicator}>
                                                    <IconSymbol name="arrow.left.arrow.right" size={12} color={colors.textTertiary} />
                                                    <Text style={{ fontSize: 10, color: colors.textTertiary, marginLeft: 4 }}>
                                                        {chain.questions.length} versions
                                                    </Text>
                                                </View>
                                            )}
                                        </View>
                                        
                                        {/* Horizontal scroll for version chain */}
                                        <ScrollView
                                            horizontal
                                            pagingEnabled
                                            showsHorizontalScrollIndicator={false}
                                            style={{ marginHorizontal: -Spacing.md }}
                                            contentContainerStyle={{ paddingHorizontal: Spacing.md }}
                                            snapToInterval={cardWidth + Spacing.sm}
                                            decelerationRate="fast"
                                            onMomentumScrollEnd={(event) => {
                                                const offset = event.nativeEvent.contentOffset.x;
                                                const currentPage = Math.round(offset / (cardWidth + Spacing.sm));
                                                setChainCurrentPage(prev => ({
                                                    ...prev,
                                                    [chain.chainId]: currentPage
                                                }));
                                            }}
                                            scrollEventThrottle={16}
                                        >
                                            {chain.questions.map((q, versionIndex) => {
                                                const isNewest = versionIndex === 0;
                                                const isOldVersion = !isNewest;
                                                
                                                return (
                                                    <GlassCard 
                                                        key={q.id} 
                                                        style={[
                                                            styles.questionCard,
                                                            { width: cardWidth, marginRight: hasVersions ? Spacing.sm : 0 },
                                                            isOldVersion && { borderLeftWidth: 3, borderLeftColor: '#FF9500' },
                                                            isNewest && hasVersions && { borderLeftWidth: 3, borderLeftColor: '#34C759' },
                                                        ]}
                                                    >
                                                        {/* Version badge */}
                                                        <View style={styles.questionHeaderRow}>
                                                            <View style={styles.qMetaRow}>
                                                                <View style={[styles.qBadge, { 
                                                                    backgroundColor: isNewest ? '#34C75920' : '#FF950020' 
                                                                }]}>
                                                                    <Text style={{ 
                                                                        fontSize: 9, fontWeight: '700', 
                                                                        color: isNewest ? '#34C759' : '#FF9500' 
                                                                    }}>
                                                                        {isNewest ? 'CURRENT' : `v${q.version_number ?? (chain.questions.length - versionIndex)}`}
                                                                    </Text>
                                                                </View>
                                                                <View style={[styles.qBadge, { backgroundColor: q.question_type === 'mcq' ? '#007AFF15' : '#AF52DE15' }]}>
                                                                    <Text style={{ fontSize: 10, fontWeight: '600', color: q.question_type === 'mcq' ? '#007AFF' : '#AF52DE' }}>
                                                                        {q.question_type === 'mcq' ? 'MCQ' : q.question_type === 'short_answer' ? 'SHORT' : 'LONG'}
                                                                    </Text>
                                                                </View>
                                                                {q.difficulty_level && (
                                                                    <View style={[styles.qBadge, {
                                                                        backgroundColor: q.difficulty_level === 'easy' ? '#34C75915' : q.difficulty_level === 'hard' ? '#FF3B3015' : '#FF950015',
                                                                    }]}>
                                                                        <Text style={{
                                                                            fontSize: 10, fontWeight: '600',
                                                                            color: q.difficulty_level === 'easy' ? '#34C759' : q.difficulty_level === 'hard' ? '#FF3B30' : '#FF9500',
                                                                        }}>
                                                                            {q.difficulty_level.toUpperCase()}
                                                                        </Text>
                                                                    </View>
                                                                )}
                                                                {q.marks != null && (
                                                                    <Text style={{ fontSize: 10, color: colors.textTertiary, fontWeight: '600' }}>
                                                                        {q.marks} mark{q.marks !== 1 ? 's' : ''}
                                                                    </Text>
                                                                )}
                                                            </View>
                                                        </View>

                                                        {/* Question text */}
                                                        <Text style={[styles.questionText, { color: colors.text }]}>{q.question_text}</Text>

                                                        {/* MCQ Options with correct answer highlighted */}
                                                        {q.options && q.options.length > 0 && (
                                                            <View style={styles.optionsList}>
                                                                {q.options.map((opt, i) => {
                                                                    const optionMatches = (option: string, correct: string | null | undefined, idx: number): boolean => {
                                                                        if (!correct) return false;
                                                                        const trimmedCorrect = correct.trim();
                                                                        const trimmedOption = option.trim();
                                                                        if (trimmedOption === trimmedCorrect) return true;
                                                                        if (trimmedOption.startsWith(trimmedCorrect)) return true;
                                                                        const letter = String.fromCharCode(65 + idx);
                                                                        if (trimmedCorrect === letter || trimmedCorrect.startsWith(letter + ')') || trimmedCorrect.startsWith(letter + ' ')) return true;
                                                                        if (trimmedCorrect.toLowerCase().startsWith('option ' + letter.toLowerCase())) return true;
                                                                        return false;
                                                                    };
                                                                    const isCorrect = optionMatches(opt, q.correct_answer, i);
                                                                    return (
                                                                        <View
                                                                            key={i}
                                                                            style={[styles.optionRow, {
                                                                                backgroundColor: isCorrect ? '#34C75910' : 'transparent',
                                                                                borderColor: isCorrect ? '#34C759' : colors.border,
                                                                                borderWidth: isCorrect ? 1.5 : 1,
                                                                            }]}
                                                                        >
                                                                            <View style={[styles.optionLetter, {
                                                                                backgroundColor: isCorrect ? '#34C759' : colors.card,
                                                                            }]}>
                                                                                <Text style={{
                                                                                    fontSize: 11, fontWeight: '700',
                                                                                    color: isCorrect ? '#FFFFFF' : colors.textTertiary,
                                                                                }}>
                                                                                    {String.fromCharCode(65 + i)}
                                                                                </Text>
                                                                            </View>
                                                                            <Text style={[styles.optionText, {
                                                                                color: isCorrect ? '#34C759' : colors.text,
                                                                                fontWeight: isCorrect ? '600' : '400',
                                                                            }]}>
                                                                                {opt}
                                                                            </Text>
                                                                            {isCorrect && <IconSymbol name="checkmark.circle.fill" size={16} color="#34C759" />}
                                                                        </View>
                                                                    );
                                                                })}
                                                            </View>
                                                        )}

                                                        {/* Non-MCQ correct answer */}
                                                        {q.correct_answer && (!q.options || q.options.length === 0) && (
                                                            <View style={[styles.answerBox, { backgroundColor: '#34C75910', borderColor: '#34C759' }]}>
                                                                <Text style={{ fontSize: 11, fontWeight: '600', color: '#34C759', marginBottom: 2 }}>
                                                                    ✓ Answer
                                                                </Text>
                                                                <Text style={{ fontSize: FontSizes.sm, color: colors.text }}>{q.correct_answer}</Text>
                                                            </View>
                                                        )}

                                                        {/* LO / CO tags */}
                                                        {(q.learning_outcome_id || (q.course_outcome_mapping && Object.keys(q.course_outcome_mapping).length > 0) || q.bloom_taxonomy_level) && (
                                                            <View style={styles.tagsRow}>
                                                                {q.learning_outcome_id && (
                                                                    <View style={[styles.loTag, { backgroundColor: '#5AC8FA15' }]}>
                                                                        <Text style={{ fontSize: 10, fontWeight: '600', color: '#5AC8FA' }}>
                                                                            LO: {q.learning_outcome_id}
                                                                        </Text>
                                                                    </View>
                                                                )}
                                                                {q.course_outcome_mapping && Object.keys(q.course_outcome_mapping).map(co => (
                                                                    <View key={co} style={[styles.loTag, { backgroundColor: '#AF52DE15' }]}>
                                                                        <Text style={{ fontSize: 10, fontWeight: '600', color: '#AF52DE' }}>
                                                                            {co}
                                                                        </Text>
                                                                    </View>
                                                                ))}
                                                                {q.bloom_taxonomy_level && (
                                                                    <View style={[styles.loTag, { backgroundColor: '#FF950015' }]}>
                                                                        <Text style={{ fontSize: 10, fontWeight: '600', color: '#FF9500' }}>
                                                                            {q.bloom_taxonomy_level.charAt(0).toUpperCase() + q.bloom_taxonomy_level.slice(1)}
                                                                        </Text>
                                                                    </View>
                                                                )}
                                                            </View>
                                                        )}

                                                        {/* Topic tags */}
                                                        {q.topic_tags && q.topic_tags.length > 0 && (
                                                            <View style={[styles.tagsRow, { marginTop: 4 }]}>
                                                                {q.topic_tags.map((tag, i) => (
                                                                    <View key={i} style={[styles.loTag, { backgroundColor: colors.card }]}>
                                                                        <Text style={{ fontSize: 10, color: colors.textSecondary }}>{tag}</Text>
                                                                    </View>
                                                                ))}
                                                            </View>
                                                        )}
                                                    </GlassCard>
                                                );
                                            })}
                                        </ScrollView>
                                        
                                        {/* Page dots for multi-version chains */}
                                        {hasVersions && (
                                            <View style={styles.pageDots}>
                                                {chain.questions.map((_, idx) => {
                                                    const currentPage = chainCurrentPage[chain.chainId] ?? 0;
                                                    return (
                                                        <View 
                                                            key={idx} 
                                                            style={[
                                                                styles.pageDot, 
                                                                { backgroundColor: idx === currentPage ? colors.primary : colors.textTertiary + '40' }
                                                            ]} 
                                                        />
                                                    );
                                                })}
                                            </View>
                                        )}
                                    </View>
                                );
                            })
                        )}
                        <View style={{ height: 40 }} />
                    </ScrollView>
                </View>
            </Modal>
        </View>
    );
}

const styles = StyleSheet.create({
    container: { flex: 1 },
    scrollContent: { padding: Spacing.md },
    centerContainer: { flex: 1, justifyContent: 'center', alignItems: 'center', paddingTop: 100 },
    loadingText: { marginTop: Spacing.md, fontSize: FontSizes.md },
    emptyState: { alignItems: 'center', paddingTop: 120 },
    emptyTitle: { fontSize: FontSizes.xl, fontWeight: '700', marginTop: Spacing.lg },
    emptySubtitle: { fontSize: FontSizes.md, marginTop: Spacing.sm, textAlign: 'center' },

    // Date groups
    dateGroup: { marginBottom: Spacing.lg },
    dateHeader: { fontSize: FontSizes.sm, fontWeight: '600', marginBottom: Spacing.sm, textTransform: 'uppercase', letterSpacing: 0.5 },

    // Session cards
    sessionCard: { marginBottom: Spacing.sm, padding: Spacing.md },
    sessionRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 },
    sessionRowRight: { flexDirection: 'row', alignItems: 'center', gap: 10 },
    methodBadge: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 8, paddingVertical: 3, borderRadius: BorderRadius.sm, gap: 4 },
    methodLabel: { fontSize: 11, fontWeight: '600' },
    sessionTime: { fontSize: 11 },

    subjectRow: { marginBottom: 6, gap: 3 },
    subjectChip: { flexDirection: 'row', alignItems: 'center', gap: 5 },
    subjectText: { fontSize: FontSizes.sm, fontWeight: '600', flex: 1 },
    topicChip: { flexDirection: 'row', alignItems: 'center', gap: 4, marginLeft: 17 },
    topicText: { fontSize: 12 },

    statsRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing.md },
    stat: { alignItems: 'center' },
    statValue: { fontSize: FontSizes.lg, fontWeight: '700' },
    statLabel: { fontSize: 10 },
    infoBadge: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4 },
    statusChip: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4, marginLeft: 'auto' },

    focusRow: { flexDirection: 'row', alignItems: 'center', marginTop: 6, gap: 4, flexWrap: 'wrap' },
    focusChip: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4 },
    sourceFile: { fontSize: 11, marginTop: 4 },

    // Pagination
    pagination: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: Spacing.md },
    pageButton: { padding: Spacing.sm },
    pageButtonText: { fontSize: FontSizes.md, fontWeight: '600' },
    pageInfo: { fontSize: FontSizes.sm },

    // Modal
    modalContainer: { flex: 1 },
    modalHeader: { paddingHorizontal: Spacing.md, paddingTop: Spacing.lg, paddingBottom: Spacing.sm, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: '#8882' },
    modalTopRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
    modalMeta: { marginTop: Spacing.sm },
    modalSubject: { fontSize: FontSizes.md, fontWeight: '700', marginTop: 6 },
    modalScroll: { flex: 1, padding: Spacing.md },
    noQuestionsText: { textAlign: 'center', fontSize: FontSizes.md, marginTop: 40 },

    // Question cards
    questionCard: { marginBottom: Spacing.md, padding: Spacing.md },
    questionHeaderRow: { flexDirection: 'row', alignItems: 'center', marginBottom: 8, gap: 8 },
    qIndex: { width: 26, height: 26, borderRadius: 13, justifyContent: 'center', alignItems: 'center' },
    qIndexText: { fontSize: 12, fontWeight: '700' },
    qMetaRow: { flexDirection: 'row', gap: 6, alignItems: 'center', flex: 1 },
    qBadge: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4 },
    questionText: { fontSize: FontSizes.md, lineHeight: 22, marginBottom: 4 },

    // Options
    optionsList: { marginTop: 8, gap: 6 },
    optionRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 8, paddingHorizontal: 10, borderRadius: BorderRadius.sm, gap: 8 },
    optionLetter: { width: 22, height: 22, borderRadius: 11, justifyContent: 'center', alignItems: 'center' },
    optionText: { fontSize: FontSizes.sm, flex: 1 },

    // Answer box for non-MCQ
    answerBox: { marginTop: 8, padding: Spacing.sm, borderRadius: BorderRadius.sm, borderWidth: 1 },

    // Tags
    tagsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 5, marginTop: 8 },
    loTag: { paddingHorizontal: 7, paddingVertical: 3, borderRadius: 4 },

    // Version chain UI
    versionChainContainer: { marginBottom: Spacing.lg },
    chainHeader: { flexDirection: 'row', alignItems: 'center', marginBottom: Spacing.sm, gap: 8 },
    versionIndicator: { flexDirection: 'row', alignItems: 'center' },
    pageDots: { flexDirection: 'row', justifyContent: 'center', gap: 6, marginTop: 8 },
    pageDot: { width: 6, height: 6, borderRadius: 3 },
});
