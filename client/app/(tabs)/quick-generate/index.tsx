import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
  Animated,
  Modal,
  RefreshControl,
  Platform,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { BlurView } from 'expo-blur';
import * as DocumentPicker from 'expo-document-picker';
import { router } from 'expo-router';
import Slider from '@react-native-community/slider';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { GlassCard } from '@/components/ui/glass-card';
import { Colors, Spacing, BorderRadius, FontSizes, Shadows } from '@/constants/theme';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { questionsService, QuickGenerateProgress, Question } from '@/services/questions';
import { subjectsService, Subject, Topic } from '@/services/subjects';
import { useToast } from '@/components/toast';
import { extractErrorDetails } from '@/utils/errors';
import { selectionImpact, mediumImpact, lightImpact } from '@/utils/haptics';
import { QuestionSources } from '@/components/question-sources';
import { useResponsive } from '@/hooks/use-responsive';

type QuestionType = 'mcq' | 'short_answer' | 'long_answer';
type Difficulty = 'easy' | 'medium' | 'hard';
type InputMode = 'pdf' | 'subject';

export default function QuickGenerateScreen() {
  const colorScheme = useColorScheme();
  const colors = Colors[colorScheme ?? 'light'];
  const isDark = colorScheme === 'dark';
  const { showError, showSuccess, showWarning } = useToast();
  const { desktopContentStyle } = useResponsive();
  const insets = useSafeAreaInsets();

  // Input mode (PDF tab vs Subject tab)
  const [inputMode, setInputMode] = useState<InputMode>('pdf');

  // Form state
  const [selectedFile, setSelectedFile] = useState<{ uri: string; name: string; type: string; webFile?: File } | null>(null);
  const [context, setContext] = useState('');
  const [count, setCount] = useState(10);
  const [customCount, setCustomCount] = useState('');
  const [showCustomInput, setShowCustomInput] = useState(false);
  const [selectedTypes, setSelectedTypes] = useState<QuestionType[]>(['mcq']);
  const [difficulty, setDifficulty] = useState<Difficulty>('medium');

  // Marks per question type
  const [marksMcq, setMarksMcq] = useState(1);
  const [marksShort, setMarksShort] = useState(2);
  const [marksLong, setMarksLong] = useState(5);

  // Subject/Topic (now inline in Subject tab)
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [selectedSubjectId, setSelectedSubjectId] = useState<string | null>(null);
  const [selectedTopicId, setSelectedTopicId] = useState<string | null>(null);
  const [showSubjectPicker, setShowSubjectPicker] = useState(false);
  const [showTopicPicker, setShowTopicPicker] = useState(false);
  const [loadingSubjects, setLoadingSubjects] = useState(false);
  const [loadingTopics, setLoadingTopics] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Generation state
  const [isGenerating, setIsGenerating] = useState(false);
  const [progress, setProgress] = useState<QuickGenerateProgress | null>(null);
  const [generatedQuestions, setGeneratedQuestions] = useState<Question[]>([]);
  const [failedCount, setFailedCount] = useState(0);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const cancelRef = useRef<(() => void) | null>(null);
  const progressAnim = useRef(new Animated.Value(0)).current;

  // Track if document picker is currently open
  const [isPickingDocument, setIsPickingDocument] = useState(false);

  // Web Speech API voice input for Focus On field (web only)
  const [isFocusRecording, setIsFocusRecording] = useState(false);
  const [webSpeechAvailable, setWebSpeechAvailable] = useState(false);
  const focusSpeechRef = useRef<any>(null);

  useEffect(() => {
    if (Platform.OS === 'web') {
      const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      const isSecure = window.location.protocol === 'https:' ||
        window.location.hostname === 'localhost' ||
        window.location.hostname === '127.0.0.1';
      setWebSpeechAvailable(!!SR && isSecure);
    }
  }, []);

  const toggleFocusSpeech = useCallback(() => {
    if (isFocusRecording) {
      focusSpeechRef.current?.stop();
      setIsFocusRecording(false);
      return;
    }
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) return;
    const recognition = new SR();
    recognition.lang = 'en-US';
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    recognition.continuous = true;
    recognition.onresult = (event: any) => {
      for (let i = event.resultIndex; i < event.results.length; i++) {
        if (event.results[i].isFinal) {
          const transcript = event.results[i][0].transcript.trim();
          if (transcript) setContext((prev) => (prev ? `${prev} ${transcript}` : transcript));
        }
      }
    };
    recognition.onerror = (event: any) => {
      setIsFocusRecording(false);
      if (event.error === 'not-allowed' || event.error === 'permission-denied') {
        showError('Microphone access denied. Please allow it in your browser settings.');
      } else if (event.error === 'network') {
        showError('Speech recognition unavailable. Your browser may be blocking access to Google\'s speech servers.');
      }
    };
    recognition.onend = () => setIsFocusRecording(false);
    focusSpeechRef.current = recognition;
    recognition.start();
    setIsFocusRecording(true);
  }, [isFocusRecording, showError]);

  // Load subjects on mount
  useEffect(() => {
    loadSubjects();
  }, []);

  // Load topics when subject changes
  useEffect(() => {
    if (selectedSubjectId) {
      loadTopics(selectedSubjectId);
    } else {
      setTopics([]);
      setSelectedTopicId(null);
    }
  }, [selectedSubjectId]);

  const loadSubjects = async () => {
    setLoadingSubjects(true);
    try {
      const response = await subjectsService.listSubjects(1, 100);
      setSubjects(response.subjects);
    } catch (error) {
      const details = extractErrorDetails(error);
      if (details.isAuthError) return;
      console.error('Failed to load subjects:', error);
      showError(error, 'Failed to load subjects');
    } finally {
      setLoadingSubjects(false);
      setIsRefreshing(false);
    }
  };

  const loadTopics = async (subjectId: string) => {
    setLoadingTopics(true);
    try {
      const response = await subjectsService.listTopics(subjectId, 1, 100);
      setTopics(response.topics);
    } catch (error) {
      console.error('Failed to load topics:', error);
    } finally {
      setLoadingTopics(false);
    }
  };

  const getSelectedSubject = () => subjects.find(s => s.id === selectedSubjectId);
  const getSelectedTopic = () => topics.find(t => t.id === selectedTopicId);

  const handleRefresh = () => {
    setIsRefreshing(true);
    loadSubjects();
  };

  const handlePickDocument = async () => {
    if (isPickingDocument) {
      showWarning('Please wait for the current file selection to complete', 'File Picker Busy');
      return;
    }
    setIsPickingDocument(true);
    try {
      mediumImpact();
      const result = await DocumentPicker.getDocumentAsync({
        type: 'application/pdf',
        copyToCacheDirectory: true,
      });
      if (!result.canceled && result.assets[0]) {
        setSelectedFile({
          uri: result.assets[0].uri,
          name: result.assets[0].name,
          type: result.assets[0].mimeType || 'application/pdf',
          webFile: typeof File !== 'undefined' && (result.assets[0] as any).file instanceof File
            ? (result.assets[0] as any).file
            : undefined,
        });
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      if (errorMessage.includes('document picking in progress') || errorMessage.includes('Different document picking')) {
        showWarning('Please wait for the current file selection to complete', 'File Picker Busy');
      } else {
        showError(error, 'Document Error');
      }
    } finally {
      setIsPickingDocument(false);
    }
  };

  const handleGenerate = () => {
    try {
      mediumImpact();

      if (inputMode === 'pdf') {
        if (!selectedFile) {
          showWarning('Please upload a PDF document first', 'Missing File');
          return;
        }
      } else {
        if (!selectedSubjectId) {
          showWarning('Please select a subject first', 'Missing Subject');
          return;
        }
      }

      if (!context.trim()) {
        showWarning('Please provide a focus topic or description', 'Missing Focus');
        return;
      }
      if (selectedTypes.length === 0) {
        showWarning('Please select at least one question type', 'Missing Types');
        return;
      }

      setIsGenerating(true);
      setGeneratedQuestions([]);
      setProgress(null);
      setFailedCount(0);
      setCurrentSessionId(null);
      progressAnim.setValue(0);

      const marks_by_type = {
        marks_mcq: selectedTypes.includes('mcq') ? marksMcq : undefined,
        marks_short: selectedTypes.includes('short_answer') ? marksShort : undefined,
        marks_long: selectedTypes.includes('long_answer') ? marksLong : undefined,
      };

      const onProgress = (progressUpdate: QuickGenerateProgress) => {
        try {
          setProgress(progressUpdate);
          if (progressUpdate.session_id) {
            setCurrentSessionId(progressUpdate.session_id);
          }
          if (progressUpdate.questions_failed !== undefined) {
            setFailedCount(progressUpdate.questions_failed);
          }
          Animated.timing(progressAnim, {
            toValue: progressUpdate.progress / 100,
            duration: 300,
            useNativeDriver: false,
          }).start();
          if (progressUpdate.question) {
            setGeneratedQuestions(prev => [...prev, progressUpdate.question!]);
          }
        } catch (callbackError) {
          console.error('[QuickGenerate UI] Error in progress callback:', callbackError);
        }
      };

      const onComplete = (_documentId: string | null) => {
        try {
          setIsGenerating(false);
        } catch (completeError) {
          console.error('[QuickGenerate UI] Error in complete callback:', completeError);
        }
      };

      const onError = (error: Error) => {
        try {
          setIsGenerating(false);
          showError(error, 'Generation Failed');
        } catch (errorCallbackError) {
          console.error('[QuickGenerate UI] Error in error callback:', errorCallbackError);
        }
      };

      if (inputMode === 'pdf') {
        cancelRef.current = questionsService.quickGenerate(
          {
            file: selectedFile!,
            context: context.trim(),
            count,
            types: selectedTypes,
            difficulty,
            ...marks_by_type,
            subject_id: selectedSubjectId || undefined,
            topic_id: selectedTopicId || undefined,
          },
          onProgress,
          onComplete,
          onError,
        );
      } else {
        cancelRef.current = questionsService.quickGenerateFromSubject(
          {
            subject_id: selectedSubjectId!,
            topic_id: selectedTopicId || undefined,
            context: context.trim(),
            count,
            types: selectedTypes,
            difficulty,
            ...marks_by_type,
          },
          onProgress,
          onComplete,
          onError,
        );
      }
    } catch (error) {
      console.error('[QuickGenerate UI] Unexpected error in handleGenerate:', error);
      setIsGenerating(false);
      showError(error, 'Generation Failed');
    }
  };

  const handleCancel = () => {
    cancelRef.current?.();
    setIsGenerating(false);
  };

  const handleRetryFailed = () => {
    if (failedCount <= 0 || isGenerating) return;
    mediumImpact();

    const marks_by_type = {
      marks_mcq: selectedTypes.includes('mcq') ? marksMcq : undefined,
      marks_short: selectedTypes.includes('short_answer') ? marksShort : undefined,
      marks_long: selectedTypes.includes('long_answer') ? marksLong : undefined,
    };

    setIsGenerating(true);
    setFailedCount(0);
    progressAnim.setValue(0);

    const onProgress = (progressUpdate: QuickGenerateProgress) => {
      try {
        setProgress(progressUpdate);
        if (progressUpdate.session_id) {
          setCurrentSessionId(progressUpdate.session_id);
        }
        if (progressUpdate.questions_failed !== undefined) {
          setFailedCount(progressUpdate.questions_failed);
        }
        Animated.timing(progressAnim, {
          toValue: progressUpdate.progress / 100,
          duration: 300,
          useNativeDriver: false,
        }).start();
        if (progressUpdate.question) {
          setGeneratedQuestions(prev => [...prev, progressUpdate.question!]);
        }
      } catch (e) { /* ignore */ }
    };
    const onComplete = (_documentId: string | null) => setIsGenerating(false);
    const onError = (error: Error) => { setIsGenerating(false); showError(error, 'Retry Failed'); };

    if (inputMode === 'pdf') {
      cancelRef.current = questionsService.quickGenerate(
        {
          file: selectedFile!,
          context: context.trim(),
          count: failedCount,
          types: selectedTypes,
          difficulty,
          ...marks_by_type,
          subject_id: selectedSubjectId || undefined,
          topic_id: selectedTopicId || undefined,
          existing_session_id: currentSessionId || undefined,
        },
        onProgress, onComplete, onError,
      );
    } else {
      cancelRef.current = questionsService.quickGenerateFromSubject(
        {
          subject_id: selectedSubjectId!,
          topic_id: selectedTopicId || undefined,
          context: context.trim(),
          count: failedCount,
          types: selectedTypes,
          difficulty,
          ...marks_by_type,
          existing_session_id: currentSessionId || undefined,
        },
        onProgress, onComplete, onError,
      );
    }
  };

  const toggleType = (type: QuestionType) => {
    selectionImpact();
    setSelectedTypes(prev =>
      prev.includes(type) ? prev.filter(t => t !== type) : [...prev, type]
    );
  };

  const switchTab = (mode: InputMode) => {
    selectionImpact();
    setInputMode(mode);
  };

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      <ScrollView
        style={styles.scrollContent}
        contentContainerStyle={[styles.contentContainer, desktopContentStyle]}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={isRefreshing}
            onRefresh={handleRefresh}
            tintColor={colors.primary}
            colors={[colors.primary]}
          />
        }
      >
      {/* ── Header ──────────────────────────────────────────────────── */}
      <BlurView intensity={95} style={styles.headerBlur}>
        <LinearGradient
          colors={['#4A90D9', '#357ABD'] as [string, string]}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
          style={styles.header}
        >
          <IconSymbol name="sparkles" size={48} color="#FFFFFF" weight="semibold" />
          <Text style={styles.headerTitle}>Quick Generate</Text>
          <Text style={styles.headerSubtitle}>
            Upload a PDF or pick a subject
          </Text>
        </LinearGradient>
      </BlurView>

      {/* ── Input Source Card (tabbed) ───────────────────────────────── */}
      <GlassCard style={styles.section}>
        {/* Tab bar */}
        <View style={[styles.tabBar, { backgroundColor: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)', borderColor: colors.border }]}>
          <TouchableOpacity
            style={[
              styles.tab,
              inputMode === 'pdf' && [styles.tabActive, { backgroundColor: colors.primary }],
            ]}
            onPress={() => switchTab('pdf')}
            disabled={isGenerating}
          >
            <IconSymbol
              name="doc.fill"
              size={14}
              color={inputMode === 'pdf' ? '#FFFFFF' : colors.textSecondary}
            />
            <Text style={[styles.tabText, { color: inputMode === 'pdf' ? '#FFFFFF' : colors.textSecondary }]}>
              Upload PDF
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[
              styles.tab,
              inputMode === 'subject' && [styles.tabActive, { backgroundColor: colors.primary }],
            ]}
            onPress={() => switchTab('subject')}
            disabled={isGenerating}
          >
            <IconSymbol
              name="book.fill"
              size={14}
              color={inputMode === 'subject' ? '#FFFFFF' : colors.textSecondary}
            />
            <Text style={[styles.tabText, { color: inputMode === 'subject' ? '#FFFFFF' : colors.textSecondary }]}>
              From Subject
            </Text>
          </TouchableOpacity>
        </View>

        {/* PDF Tab */}
        {inputMode === 'pdf' && (
          <TouchableOpacity
            style={[
              styles.uploadButton,
              selectedFile && styles.uploadButtonSelected,
              { borderColor: selectedFile ? colors.success : colors.border },
            ]}
            onPress={handlePickDocument}
            disabled={isGenerating}
          >
            <IconSymbol
              name={selectedFile ? 'checkmark.circle.fill' : 'doc.badge.plus'}
              size={32}
              color={selectedFile ? colors.success : colors.primary}
            />
            <View style={styles.uploadTextContainer}>
              <Text style={[styles.uploadTitle, { color: colors.text }]}>
                {selectedFile ? selectedFile.name : 'Upload PDF'}
              </Text>
              <Text style={[styles.uploadSubtitle, { color: colors.textSecondary }]}>
                {selectedFile ? 'Tap to change' : 'Tap to select a file'}
              </Text>
            </View>
          </TouchableOpacity>
        )}

        {/* Subject Tab */}
        {inputMode === 'subject' && (
          <View style={styles.subjectTabContent}>
            {/* Subject picker button */}
            <TouchableOpacity
              style={[styles.pickerButton, {
                backgroundColor: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.04)',
                borderColor: selectedSubjectId ? colors.primary : colors.border,
              }]}
              onPress={() => { selectionImpact(); setShowSubjectPicker(true); }}
              disabled={isGenerating || loadingSubjects}
            >
              {loadingSubjects ? (
                <ActivityIndicator size="small" color={colors.primary} />
              ) : (
                <>
                  <IconSymbol name="book.fill" size={18} color={selectedSubjectId ? colors.primary : colors.textSecondary} />
                  <Text style={[styles.pickerText, { color: selectedSubjectId ? colors.text : colors.textTertiary }]}>
                    {getSelectedSubject()?.name || 'Select subject…'}
                  </Text>
                  <IconSymbol name="chevron.right" size={14} color={colors.textSecondary} />
                </>
              )}
            </TouchableOpacity>

            {/* Topic picker (shows after subject selected) */}
            {selectedSubjectId && (
              <TouchableOpacity
                style={[styles.pickerButton, {
                  backgroundColor: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.04)',
                  borderColor: selectedTopicId ? colors.primary : colors.border,
                  marginTop: 8,
                }]}
                onPress={() => { selectionImpact(); setShowTopicPicker(true); }}
                disabled={isGenerating || loadingTopics}
              >
                {loadingTopics ? (
                  <ActivityIndicator size="small" color={colors.primary} />
                ) : (
                  <>
                    <IconSymbol name="doc.text.fill" size={18} color={selectedTopicId ? colors.primary : colors.textSecondary} />
                    <Text style={[styles.pickerText, { color: selectedTopicId ? colors.text : colors.textTertiary }]}>
                      {getSelectedTopic()?.name || 'Select chapter / topic (optional)'}
                    </Text>
                    <IconSymbol name="chevron.right" size={14} color={colors.textSecondary} />
                  </>
                )}
              </TouchableOpacity>
            )}

            {/* Clear link */}
            {selectedSubjectId && (
              <TouchableOpacity
                onPress={() => { setSelectedSubjectId(null); setSelectedTopicId(null); }}
                style={styles.clearBtn}
              >
                <Text style={[styles.clearBtnText, { color: colors.error }]}>Clear selection</Text>
              </TouchableOpacity>
            )}
          </View>
        )}
      </GlassCard>

      {/* ── Focus On (context input) ─────────────────────────────────── */}
      <GlassCard style={styles.section}>
        <Text style={[styles.sectionTitle, { color: colors.text }]}>Focus On</Text>
        <View style={styles.focusRow}>
          <TextInput
            style={[
              styles.contextInput,
              { flex: 1,
                backgroundColor: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.04)',
                color: colors.text,
                borderColor: isFocusRecording ? colors.error : colors.border,
              },
            ]}
            placeholder={isFocusRecording ? 'Listening...' : 'e.g., Chapter 5: Binary Trees and Tree Traversal'}
            placeholderTextColor={isFocusRecording ? colors.error : colors.textTertiary}
            value={context}
            onChangeText={setContext}
            multiline
            numberOfLines={3}
            editable={!isGenerating}
          />
          {Platform.OS === 'web' && webSpeechAvailable && (
            <TouchableOpacity
              style={[
                styles.focusMicButton,
                { backgroundColor: isFocusRecording ? colors.error : colors.primary },
              ]}
              onPress={toggleFocusSpeech}
              disabled={isGenerating}
              activeOpacity={0.8}
            >
              {isFocusRecording ? (
                <ActivityIndicator size="small" color="#fff" />
              ) : (
                <IconSymbol name="mic.fill" size={18} color="#fff" />
              )}
            </TouchableOpacity>
          )}
        </View>
      </GlassCard>

      {/* ── Options ─────────────────────────────────────────────────── */}
      <GlassCard style={styles.section}>
        {/* Question Types */}
        <View style={styles.typesContainer}>
          {[
            { type: 'mcq' as QuestionType, label: 'MCQ', icon: 'list.bullet' },
            { type: 'short_answer' as QuestionType, label: 'Short Answer', icon: 'text.alignleft' },
            { type: 'long_answer' as QuestionType, label: 'Long Answer', icon: 'doc.text' },
          ].map(({ type, label, icon }) => (
            <TouchableOpacity
              key={type}
              style={[
                styles.typeButton,
                selectedTypes.includes(type) && { backgroundColor: colors.primary },
                { borderColor: selectedTypes.includes(type) ? colors.primary : colors.border },
              ]}
              onPress={() => toggleType(type)}
              disabled={isGenerating}
            >
              <IconSymbol
                name={icon as any}
                size={18}
                color={selectedTypes.includes(type) ? '#FFFFFF' : colors.textSecondary}
              />
              <Text style={[styles.typeButtonText, { color: selectedTypes.includes(type) ? '#FFFFFF' : colors.text }]}>
                {label}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Question Count */}
        <Text style={[styles.optionLabel, { color: colors.textSecondary, marginTop: Spacing.lg }]}>
          Number of Questions: {count}
        </Text>
        <View style={styles.sliderRow}>
          <Text style={[styles.sliderLabel, { color: colors.textSecondary }]}>1</Text>
          <Slider
            style={styles.slider}
            minimumValue={1}
            maximumValue={50}
            step={1}
            value={count}
            onValueChange={(val: number) => { lightImpact(); setCount(Math.round(val)); }}
            onSlidingComplete={() => mediumImpact()}
            minimumTrackTintColor={colors.primary}
            maximumTrackTintColor={colors.border}
            thumbTintColor={colors.primary}
            disabled={isGenerating}
          />
          <Text style={[styles.sliderValue, { color: colors.primary }]}>{count}</Text>
        </View>
        <TouchableOpacity
          style={[styles.customButton, { borderColor: colors.border, backgroundColor: colors.card }]}
          onPress={() => { selectionImpact(); setShowCustomInput(true); }}
          disabled={isGenerating}
        >
          <IconSymbol name="pencil" size={16} color={colors.primary} />
          <Text style={[styles.customButtonText, { color: colors.text }]}>Custom Amount</Text>
        </TouchableOpacity>

        {/* Difficulty */}
        <Text style={[styles.optionLabel, { color: colors.textSecondary, marginTop: Spacing.lg }]}>
          Difficulty
        </Text>
        <View style={styles.difficultyContainer}>
          {[
            { value: 'easy' as Difficulty, label: 'Easy', color: colors.success },
            { value: 'medium' as Difficulty, label: 'Medium', color: colors.warning },
            { value: 'hard' as Difficulty, label: 'Hard', color: colors.error },
          ].map(({ value, label, color }) => (
            <TouchableOpacity
              key={value}
              style={[
                styles.difficultyButton,
                difficulty === value && { backgroundColor: color, borderColor: color },
                { borderColor: difficulty === value ? color : colors.border },
              ]}
              onPress={() => { selectionImpact(); setDifficulty(value); }}
              disabled={isGenerating}
            >
              <Text style={[styles.difficultyButtonText, { color: difficulty === value ? '#FFFFFF' : colors.text }]}>
                {label}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Marks per Question Type */}
        <Text style={[styles.optionLabel, { color: colors.textSecondary, marginTop: Spacing.lg }]}>
          Marks per Question Type
        </Text>
        <View style={styles.marksContainer}>
          {selectedTypes.includes('mcq') && (
            <View style={styles.marksInputRow}>
              <Text style={[styles.marksLabel, { color: colors.text }]}>MCQ</Text>
              <View style={styles.marksInputWrapper}>
                <TouchableOpacity style={[styles.marksButton, { backgroundColor: colors.border }]} onPress={() => { mediumImpact(); setMarksMcq(Math.max(1, marksMcq - 1)); }} disabled={isGenerating}>
                  <IconSymbol name="minus" size={14} color={colors.text} />
                </TouchableOpacity>
                <TextInput style={[styles.marksInput, { backgroundColor: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.04)', color: colors.text, borderColor: colors.border }]} value={marksMcq.toString()} onChangeText={(v) => setMarksMcq(parseInt(v) || 1)} keyboardType="numeric" editable={!isGenerating} />
                <TouchableOpacity style={[styles.marksButton, { backgroundColor: colors.border }]} onPress={() => { mediumImpact(); setMarksMcq(marksMcq + 1); }} disabled={isGenerating}>
                  <IconSymbol name="plus" size={14} color={colors.text} />
                </TouchableOpacity>
              </View>
            </View>
          )}
          {selectedTypes.includes('short_answer') && (
            <View style={styles.marksInputRow}>
              <Text style={[styles.marksLabel, { color: colors.text }]}>Short Answer</Text>
              <View style={styles.marksInputWrapper}>
                <TouchableOpacity style={[styles.marksButton, { backgroundColor: colors.border }]} onPress={() => { mediumImpact(); setMarksShort(Math.max(1, marksShort - 1)); }} disabled={isGenerating}>
                  <IconSymbol name="minus" size={14} color={colors.text} />
                </TouchableOpacity>
                <TextInput style={[styles.marksInput, { backgroundColor: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.04)', color: colors.text, borderColor: colors.border }]} value={marksShort.toString()} onChangeText={(v) => setMarksShort(parseInt(v) || 1)} keyboardType="numeric" editable={!isGenerating} />
                <TouchableOpacity style={[styles.marksButton, { backgroundColor: colors.border }]} onPress={() => setMarksShort(marksShort + 1)} disabled={isGenerating}>
                  <IconSymbol name="plus" size={14} color={colors.text} />
                </TouchableOpacity>
              </View>
            </View>
          )}
          {selectedTypes.includes('long_answer') && (
            <View style={styles.marksInputRow}>
              <Text style={[styles.marksLabel, { color: colors.text }]}>Long Answer</Text>
              <View style={styles.marksInputWrapper}>
                <TouchableOpacity style={[styles.marksButton, { backgroundColor: colors.border }]} onPress={() => { mediumImpact(); setMarksLong(Math.max(1, marksLong - 1)); }} disabled={isGenerating}>
                  <IconSymbol name="minus" size={14} color={colors.text} />
                </TouchableOpacity>
                <TextInput style={[styles.marksInput, { backgroundColor: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.04)', color: colors.text, borderColor: colors.border }]} value={marksLong.toString()} onChangeText={(v) => setMarksLong(parseInt(v) || 1)} keyboardType="numeric" editable={!isGenerating} />
                <TouchableOpacity style={[styles.marksButton, { backgroundColor: colors.border }]} onPress={() => { mediumImpact(); setMarksLong(marksLong + 1); }} disabled={isGenerating}>
                  <IconSymbol name="plus" size={14} color={colors.text} />
                </TouchableOpacity>
              </View>
            </View>
          )}
        </View>
      </GlassCard>

      {/* Subject/Topic Picker Modals */}
      <Modal visible={showSubjectPicker} animationType="slide" presentationStyle="pageSheet" onRequestClose={() => setShowSubjectPicker(false)}>
        <View style={[styles.modalContainer, { backgroundColor: colors.background }]}>
          <View style={styles.modalHeaderBar}><View style={[styles.modalHandle, { backgroundColor: colors.border }]} /></View>
          <View style={styles.modalTop}>
            <Text style={[styles.modalTitle, { color: colors.text }]}>Select Subject</Text>
            <TouchableOpacity onPress={() => setShowSubjectPicker(false)}><IconSymbol name="xmark.circle.fill" size={28} color={colors.textSecondary} /></TouchableOpacity>
          </View>
          <View style={styles.modalDivider} />
          <ScrollView style={styles.modalScrollContent}>
            {subjects.length === 0 ? (
              <View style={styles.emptyList}><Text style={[styles.emptyListText, { color: colors.textSecondary }]}>No subjects available. Create a subject first.</Text></View>
            ) : subjects.map((subject) => (
              <TouchableOpacity key={subject.id} style={[styles.modalItem, { borderBottomColor: colors.border }, selectedSubjectId === subject.id && { backgroundColor: colors.primary + '15' }]} onPress={() => { setSelectedSubjectId(subject.id); setSelectedTopicId(null); setShowSubjectPicker(false); }}>
                <View style={styles.modalItemContent}>
                  <Text style={[styles.modalItemTitle, { color: colors.text }]}>{subject.name}</Text>
                  <Text style={[styles.modalItemSubtitle, { color: colors.textSecondary }]}>{subject.code} • {subject.total_topics} topics</Text>
                </View>
                {selectedSubjectId === subject.id && <IconSymbol name="checkmark.circle.fill" size={22} color={colors.primary} />}
              </TouchableOpacity>
            ))}
          </ScrollView>
        </View>
      </Modal>

      <Modal visible={showTopicPicker} animationType="slide" presentationStyle="pageSheet" onRequestClose={() => setShowTopicPicker(false)}>
        <View style={[styles.modalContainer, { backgroundColor: colors.background }]}>
          <View style={styles.modalHeaderBar}><View style={[styles.modalHandle, { backgroundColor: colors.border }]} /></View>
          <View style={styles.modalTop}>
            <Text style={[styles.modalTitle, { color: colors.text }]}>Select Chapter</Text>
            <TouchableOpacity onPress={() => setShowTopicPicker(false)}><IconSymbol name="xmark.circle.fill" size={28} color={colors.textSecondary} /></TouchableOpacity>
          </View>
          <View style={styles.modalDivider} />
          <ScrollView style={styles.modalScrollContent}>
            {topics.length === 0 ? (
              <View style={styles.emptyList}><Text style={[styles.emptyListText, { color: colors.textSecondary }]}>No topics available for this subject.</Text></View>
            ) : topics.map((topic) => (
              <TouchableOpacity key={topic.id} style={[styles.modalItem, { borderBottomColor: colors.border }, selectedTopicId === topic.id && { backgroundColor: colors.primary + '15' }]} onPress={() => { setSelectedTopicId(topic.id); setShowTopicPicker(false); }}>
                <View style={styles.modalItemContent}>
                  <Text style={[styles.modalItemTitle, { color: colors.text }]}>{topic.name}</Text>
                  {topic.description && <Text style={[styles.modalItemSubtitle, { color: colors.textSecondary }]} numberOfLines={1}>{topic.description}</Text>}
                </View>
                {selectedTopicId === topic.id && <IconSymbol name="checkmark.circle.fill" size={22} color={colors.primary} />}
              </TouchableOpacity>
            ))}
          </ScrollView>
        </View>
      </Modal>

      {/* ── Progress ─────────────────────────────────────────────────── */}
      {isGenerating && progress && (
        <GlassCard style={styles.section}>
          <Text style={[styles.sectionTitle, { color: colors.text }]}>Generating...</Text>
          <View style={styles.progressContainer}>
            <View style={[styles.progressBar, { backgroundColor: colors.border }]}>
              <Animated.View style={[styles.progressFill, { backgroundColor: colors.primary, width: progressAnim.interpolate({ inputRange: [0, 1], outputRange: ['0%', '100%'] }) }]} />
            </View>
            <Text style={[styles.progressText, { color: colors.textSecondary }]}>{progress.message || `${progress.progress}%`}</Text>
          </View>
          {progress.current_question && progress.total_questions && (
            <Text style={[styles.progressCount, { color: colors.primary }]}>
              {progress.current_question} / {progress.total_questions} questions
            </Text>
          )}
        </GlassCard>
      )}

      {/* ── Generated Questions Preview ──────────────────────────────── */}
      {generatedQuestions.length > 0 && (
        <GlassCard style={styles.section}>
          <Text style={[styles.sectionTitle, { color: colors.text }]}>
            Generated Questions ({generatedQuestions.length})
          </Text>
          {generatedQuestions.map((q) => (
            <View key={q.id} style={[styles.questionPreview, { borderColor: colors.border }]}>
              <View style={styles.questionHeader}>
                <View style={[styles.questionBadge, { backgroundColor: colors.primary }]}>
                  <Text style={styles.questionBadgeText}>{q.question_type?.toUpperCase()}</Text>
                </View>
                {q.difficulty_level && (
                  <View style={[styles.difficultyBadge, { backgroundColor: q.difficulty_level === 'easy' ? '#34C759' : q.difficulty_level === 'medium' ? '#FF9500' : '#FF3B30' }]}>
                    <Text style={styles.questionBadgeText}>{q.difficulty_level.toUpperCase()}</Text>
                  </View>
                )}
              </View>
              <Text style={[styles.questionText, { color: colors.text }]}>{q.question_text}</Text>
              {q.source_info && <QuestionSources sourceInfo={q.source_info} compact />}
              <View style={styles.generatedMetaRow}>
                {(q as any).learning_outcome_id ? <Text style={[styles.generatedMetaText, { color: colors.textSecondary }]}>{(q as any).learning_outcome_id}</Text> : null}
                {(q as any).course_outcome_mapping && Object.keys((q as any).course_outcome_mapping).length ? <Text style={[styles.generatedMetaText, { color: colors.textSecondary }]}>{Object.keys((q as any).course_outcome_mapping).join(', ')}</Text> : null}
                {q.topic_tags && q.topic_tags.length ? <Text style={[styles.generatedMetaText, { color: colors.textSecondary }]}>{q.topic_tags[0]}</Text> : null}
              </View>
              {q.options && q.options.length > 0 && (
                <View style={styles.optionsContainer}>
                  {q.options.map((opt, optIdx) => {
                    const isCorrect = q.correct_answer && opt.startsWith(q.correct_answer);
                    return (
                      <View key={optIdx} style={[styles.optionRow, isCorrect && { backgroundColor: colors.success + '20', borderRadius: BorderRadius.sm, padding: 4 }]}>
                        <Text style={[styles.optionText, { color: isCorrect ? colors.success : colors.textSecondary }]}>{opt}</Text>
                        {isCorrect && <IconSymbol name="checkmark.circle.fill" size={16} color={colors.success} />}
                      </View>
                    );
                  })}
                </View>
              )}
              {q.explanation && (
                <View style={[styles.explanationContainer, { backgroundColor: colors.primary + '10', borderColor: colors.primary + '30' }]}>
                  <Text style={[styles.answerLabel, { color: colors.primary }]}>Explanation:</Text>
                  <Text style={[styles.answerText, { color: colors.text }]}>{q.explanation}</Text>
                </View>
              )}
            </View>
          ))}
          {progress?.status === 'complete' && (
            <View style={styles.actionButtons}>
              {failedCount > 0 && (
                <TouchableOpacity style={[styles.actionButton, { backgroundColor: '#FF9500' }]} onPress={handleRetryFailed}>
                  <IconSymbol name="arrow.clockwise.circle.fill" size={20} color="#FFFFFF" />
                  <Text style={styles.actionButtonText}>Generate {failedCount} More</Text>
                </TouchableOpacity>
              )}
              <TouchableOpacity style={[styles.actionButton, { backgroundColor: colors.primary }]} onPress={() => router.push('/(tabs)/home/vetting')}>
                <IconSymbol name="checkmark.shield.fill" size={20} color="#FFFFFF" />
                <Text style={styles.actionButtonText}>Review & Validate</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[styles.actionButton, { backgroundColor: colors.success }]} onPress={() => { setGeneratedQuestions([]); setProgress(null); setSelectedFile(null); setContext(''); setFailedCount(0); }}>
                <IconSymbol name="plus.circle.fill" size={20} color="#FFFFFF" />
                <Text style={styles.actionButtonText}>Generate More</Text>
              </TouchableOpacity>
            </View>
          )}
        </GlassCard>
      )}

      <View style={{ height: 120 }} />

      {/* Custom Count Input Modal */}
      <Modal visible={showCustomInput} transparent animationType="fade" onRequestClose={() => setShowCustomInput(false)}>
        <View style={styles.customInputModal}>
          <View style={[styles.customInputContainer, { backgroundColor: colors.card }]}>
            <Text style={[styles.customInputTitle, { color: colors.text }]}>Enter Number of Questions</Text>
            <TextInput
              style={[styles.customInput, { borderColor: colors.border, color: colors.text, backgroundColor: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.02)' }]}
              value={customCount}
              onChangeText={setCustomCount}
              keyboardType="number-pad"
              placeholder="e.g., 25"
              placeholderTextColor={colors.textSecondary}
              autoFocus
              selectTextOnFocus
            />
            <View style={styles.customInputButtons}>
              <TouchableOpacity style={[styles.customInputButton, { backgroundColor: colors.border }]} onPress={() => { selectionImpact(); setShowCustomInput(false); setCustomCount(''); }}>
                <Text style={[styles.customInputButtonText, { color: colors.text }]}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[styles.customInputButton, { backgroundColor: colors.primary }]} onPress={() => {
                mediumImpact();
                const num = parseInt(customCount, 10);
                if (!isNaN(num) && num >= 1 && num <= 150) {
                  setCount(num);
                  setShowCustomInput(false);
                  setCustomCount('');
                } else {
                  showError(new Error('Please enter a number between 1 and 150'), 'Invalid input');
                }
              }}>
                <Text style={[styles.customInputButtonText, { color: '#FFFFFF' }]}>Apply</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
      </ScrollView>

      {/* ── Floating Generate Button ──────────────────────────────── */}
      <TouchableOpacity
        style={[styles.floatingGenerateButton, isGenerating && styles.floatingGenerateButtonDisabled, Platform.OS === 'ios' && { bottom: Spacing.lg + insets.bottom + 30}]}
        onPress={isGenerating ? handleCancel : handleGenerate}
        activeOpacity={0.8}
      >
        <LinearGradient
          colors={isGenerating ? ['#FF3B30', '#FF453A'] : ['#4A90D9', '#357ABD'] as [string, string]}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 0 }}
          style={styles.generateButtonGradient}
        >
          {isGenerating ? (
            <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: Spacing.sm }}>
              <ActivityIndicator color="#FFFFFF" />
              <Text style={styles.generateButtonText}>Cancel</Text>
            </View>
          ) : (
            <>
              <Text style={styles.generateButtonText}>Generate Questions</Text>
            </>
          )}
        </LinearGradient>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, position: 'relative' },
  scrollContent: { flex: 1, },
  contentContainer: { paddingTop: Spacing.xxxl + 15, paddingBottom: Spacing.xxl },

  // Header
  headerBlur: { overflow: 'hidden', borderRadius: BorderRadius.xxl, marginTop: Spacing.sm, marginBottom: Spacing.lg, marginHorizontal: Spacing.md, ...Shadows.medium },
  header: { paddingTop: Spacing.lg, paddingBottom: Spacing.xxxl, paddingHorizontal: Spacing.lg, alignItems: 'center' },
  headerTitle: { fontSize: FontSizes.xxxl, fontWeight: '700', color: '#FFFFFF', marginTop: Spacing.md },
  headerSubtitle: { fontSize: FontSizes.md, color: 'rgba(255,255,255,0.85)', marginTop: Spacing.xs, textAlign: 'center' },

  section: { marginBottom: Spacing.lg, marginRight: Spacing.lg, marginLeft: Spacing.lg },
  sectionTitle: { fontSize: FontSizes.lg, fontWeight: '600', marginBottom: Spacing.md },

  // Tab bar
  tabBar: { flexDirection: 'row', borderRadius: BorderRadius.md, borderWidth: 1, marginBottom: Spacing.md, overflow: 'hidden' },
  tab: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 10, paddingHorizontal: 12 },
  tabActive: { borderRadius: BorderRadius.md - 1 },
  tabText: { fontSize: FontSizes.sm, fontWeight: '600' },

  // Upload
  uploadButton: { flexDirection: 'row', alignItems: 'center', padding: Spacing.lg, borderRadius: BorderRadius.md, borderWidth: 2, borderStyle: 'dashed' },
  uploadButtonSelected: { borderStyle: 'solid' },
  uploadTextContainer: { marginLeft: Spacing.md, flex: 1 },
  uploadTitle: { fontSize: FontSizes.md, fontWeight: '600' },
  uploadSubtitle: { fontSize: FontSizes.sm, marginTop: 2 },

  // Subject tab
  subjectTabContent: {},
  pickerButton: { flexDirection: 'row', alignItems: 'center', padding: Spacing.md, borderRadius: BorderRadius.md, borderWidth: 1, gap: Spacing.sm },
  pickerText: { flex: 1, fontSize: FontSizes.md },
  clearBtn: { marginTop: 6, paddingVertical: 4 },
  clearBtnText: { fontSize: FontSizes.sm, fontWeight: '500' },

  // Context input
  contextInput: { borderWidth: 1, borderRadius: BorderRadius.md, padding: Spacing.md, fontSize: FontSizes.md, minHeight: 100, textAlignVertical: 'top' },
  focusRow: { flexDirection: 'row', alignItems: 'flex-start', gap: Spacing.xs },
  focusMicButton: { width: 40, height: 40, borderRadius: 20, alignItems: 'center', justifyContent: 'center', marginTop: 2, flexShrink: 0 },
  helperText: { fontSize: FontSizes.xs, marginTop: Spacing.sm },

  // Options
  optionLabel: { fontSize: FontSizes.sm, fontWeight: '500', marginBottom: Spacing.sm },
  typesContainer: { flexDirection: 'row', gap: Spacing.sm },
  typeButton: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', paddingVertical: Spacing.md, paddingHorizontal: Spacing.sm, borderRadius: BorderRadius.md, borderWidth: 1, gap: Spacing.xs },
  typeButtonText: { fontSize: FontSizes.sm, fontWeight: '500' },
  sliderRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm },
  sliderLabel: { fontSize: FontSizes.sm, minWidth: 20 },
  slider: { flex: 1, height: 40 },
  sliderValue: { fontSize: FontSizes.lg, fontWeight: '700', minWidth: 40, textAlign: 'right' },
  customButton: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: Spacing.xs, paddingVertical: Spacing.sm, paddingHorizontal: Spacing.md, borderRadius: BorderRadius.md, borderWidth: 1, marginTop: Spacing.sm },
  customButtonText: { fontSize: FontSizes.sm, fontWeight: '500' },
  difficultyContainer: { flexDirection: 'row', gap: Spacing.sm },
  difficultyButton: { flex: 1, alignItems: 'center', paddingVertical: Spacing.md, borderRadius: BorderRadius.md, borderWidth: 1 },
  difficultyButtonText: { fontSize: FontSizes.sm, fontWeight: '600' },
  marksContainer: { gap: Spacing.sm },
  marksInputRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  marksLabel: { fontSize: FontSizes.sm, fontWeight: '500', flex: 1 },
  marksInputWrapper: { flexDirection: 'row', alignItems: 'center', gap: Spacing.xs },
  marksButton: { width: 32, height: 32, borderRadius: BorderRadius.sm, alignItems: 'center', justifyContent: 'center' },
  marksInput: { width: 50, height: 36, borderWidth: 1, borderRadius: BorderRadius.sm, textAlign: 'center', fontSize: FontSizes.md, fontWeight: '600' },

  // Modals
  modalContainer: { flex: 1, maxWidth: 600, width: '100%', alignSelf: 'center' },
  modalHeaderBar: { paddingVertical: Spacing.sm, alignItems: 'center' },
  modalHandle: { width: 40, height: 4, borderRadius: 2 },
  modalTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: Spacing.lg, paddingVertical: Spacing.md },
  modalTitle: { fontSize: FontSizes.xl, fontWeight: '700' },
  modalDivider: { height: 1, backgroundColor: 'rgba(128,128,128,0.2)', marginHorizontal: Spacing.lg },
  modalScrollContent: { flex: 1, paddingHorizontal: Spacing.lg, paddingTop: Spacing.md },
  modalItem: { flexDirection: 'row', alignItems: 'center', paddingVertical: Spacing.md, borderBottomWidth: 1 },
  modalItemContent: { flex: 1 },
  modalItemTitle: { fontSize: FontSizes.md, fontWeight: '500' },
  modalItemSubtitle: { fontSize: FontSizes.sm, marginTop: 2 },
  emptyList: { padding: Spacing.xl, alignItems: 'center' },
  emptyListText: { fontSize: FontSizes.sm, textAlign: 'center' },

  // Progress
  progressContainer: { marginTop: Spacing.sm },
  progressBar: { height: 8, borderRadius: 4, overflow: 'hidden' },
  progressFill: { height: '100%', borderRadius: 4 },
  progressText: { fontSize: FontSizes.sm, marginTop: Spacing.sm, textAlign: 'center' },
  progressCount: { fontSize: FontSizes.lg, fontWeight: '600', textAlign: 'center', marginTop: Spacing.sm },

  // Question cards
  questionPreview: { padding: Spacing.md, borderRadius: BorderRadius.sm, borderWidth: 1, marginBottom: Spacing.sm },
  questionBadge: { alignSelf: 'flex-start', paddingHorizontal: Spacing.sm, paddingVertical: 2, borderRadius: BorderRadius.sm, marginBottom: Spacing.xs },
  questionBadgeText: { color: '#FFFFFF', fontSize: FontSizes.xs, fontWeight: '600' },
  questionText: { fontSize: FontSizes.sm, lineHeight: 20 },
  questionHeader: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm, marginBottom: Spacing.xs },
  generatedMetaRow: { flexDirection: 'row', flexWrap: 'wrap', gap: Spacing.sm, marginTop: Spacing.sm },
  generatedMetaText: { fontSize: FontSizes.xs, paddingHorizontal: Spacing.sm, paddingVertical: 2, borderRadius: BorderRadius.sm, backgroundColor: 'rgba(128,128,128,0.15)', overflow: 'hidden' },
  difficultyBadge: { paddingHorizontal: Spacing.sm, paddingVertical: 2, borderRadius: BorderRadius.sm },
  optionsContainer: { marginTop: Spacing.sm, paddingLeft: Spacing.sm },
  optionRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 },
  optionText: { fontSize: FontSizes.xs, lineHeight: 18, marginBottom: 4 },
  answerContainer: { marginTop: Spacing.md, padding: Spacing.sm, borderRadius: BorderRadius.sm, borderWidth: 1 },
  answerLabel: { fontSize: FontSizes.xs, fontWeight: '600', marginBottom: 4 },
  answerText: { fontSize: FontSizes.sm, lineHeight: 18 },
  explanationContainer: { marginTop: Spacing.sm, padding: Spacing.sm, borderRadius: BorderRadius.sm, borderWidth: 1 },
  actionButtons: { flexDirection: 'row', gap: Spacing.md, marginTop: Spacing.lg },
  actionButton: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', paddingVertical: Spacing.md, borderRadius: BorderRadius.md, gap: Spacing.xs },
  actionButtonText: { color: '#FFFFFF', fontSize: FontSizes.sm, fontWeight: '600' },

  // Generate button
  generateButton: { marginHorizontal: Spacing.xxxl + 60, marginTop: Spacing.xl, borderRadius: BorderRadius.lg, overflow: 'hidden', ...Shadows.large },
  generateButtonDisabled: {},
  generateButtonGradient: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', paddingVertical: Spacing.lg, gap: Spacing.sm },
  generateButtonText: { color: '#FFFFFF', fontSize: FontSizes.lg, fontWeight: '600' },

  // Floating generate button
  floatingGenerateButton: { position: 'absolute', bottom: Spacing.lg, left: Spacing.lg, right: Spacing.lg, marginBottom: 10, borderRadius: BorderRadius.xxl, overflow: 'hidden', zIndex: 100, ...Shadows.large, alignSelf: 'center', maxHeight: 50 },
  floatingGenerateButtonDisabled: {},

  // Custom count modal
  customInputModal: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: 'rgba(0,0,0,0.5)' },
  customInputContainer: { width: '80%', padding: Spacing.xl, borderRadius: BorderRadius.lg, gap: Spacing.md },
  customInputTitle: { fontSize: FontSizes.lg, fontWeight: '600', textAlign: 'center' },
  customInput: { borderWidth: 1, borderRadius: BorderRadius.md, paddingVertical: Spacing.md, paddingHorizontal: Spacing.md, fontSize: FontSizes.lg, fontWeight: '600', textAlign: 'center' },
  customInputButtons: { flexDirection: 'row', gap: Spacing.sm },
  customInputButton: { flex: 1, paddingVertical: Spacing.md, borderRadius: BorderRadius.md, alignItems: 'center' },
  customInputButtonText: { fontSize: FontSizes.md, fontWeight: '600' },
});

