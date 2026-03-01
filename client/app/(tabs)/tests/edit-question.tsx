/**
 * Edit Question Screen - Teacher can override question text, options, marks
 */
import React, { useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  Alert,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { Colors, Spacing, FontSizes, BorderRadius } from '@/constants/theme';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { GlassCard } from '@/components/ui/glass-card';
import { testsService } from '@/services/tests';

export default function EditQuestionScreen() {
  const colorScheme = useColorScheme() ?? 'light';
  const colors = Colors[colorScheme];
  const router = useRouter();
  const {
    testId,
    testQuestionId,
    questionText: initialText,
    options: initialOptionsStr,
    correctAnswer: initialCorrect,
    marks: initialMarks,
  } = useLocalSearchParams<{
    testId: string;
    testQuestionId: string;
    questionText: string;
    options: string;
    correctAnswer: string;
    marks: string;
  }>();

  const initialOptions: string[] = initialOptionsStr ? JSON.parse(initialOptionsStr) : [];

  const [questionText, setQuestionText] = useState(initialText || '');
  const [options, setOptions] = useState<string[]>(initialOptions);
  const [correctAnswer, setCorrectAnswer] = useState(initialCorrect || '');
  const [marks, setMarks] = useState(initialMarks || '1');
  const [isSaving, setIsSaving] = useState(false);

  const updateOption = (index: number, value: string) => {
    setOptions((prev) => prev.map((o, i) => (i === index ? value : o)));
  };

  const handleSave = async () => {
    if (!testId || !testQuestionId) return;
    setIsSaving(true);
    try {
      await testsService.updateTestQuestion(testId, testQuestionId, {
        question_text_override: questionText !== initialText ? questionText : undefined,
        options_override: JSON.stringify(options) !== initialOptionsStr ? options : undefined,
        correct_answer_override: correctAnswer !== initialCorrect ? correctAnswer : undefined,
        marks: parseInt(marks) !== parseInt(initialMarks || '1') ? parseInt(marks) : undefined,
      });
      Alert.alert('Saved', 'Question updated successfully', [
        { text: 'OK', onPress: () => router.back() },
      ]);
    } catch (error: any) {
      Alert.alert('Error', error?.message || 'Failed to update question');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]} edges={['bottom']}>
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
          {/* Question Text */}
          <GlassCard style={styles.card}>
            <Text style={[styles.label, { color: colors.text }]}>Question Text</Text>
            <TextInput
              style={[
                styles.textArea,
                { backgroundColor: colors.backgroundSecondary, color: colors.text, borderColor: colors.border },
              ]}
              value={questionText}
              onChangeText={setQuestionText}
              multiline
              numberOfLines={5}
              placeholder="Enter question text..."
              placeholderTextColor={colors.textTertiary}
            />
          </GlassCard>

          {/* Options */}
          {options.length > 0 && (
            <GlassCard style={styles.card}>
              <Text style={[styles.label, { color: colors.text }]}>Options</Text>
              {options.map((opt, idx) => (
                <View key={idx} style={styles.optionRow}>
                  <View
                    style={[
                      styles.optionLabel,
                      {
                        backgroundColor:
                          correctAnswer.charAt(0).toUpperCase() === String.fromCharCode(65 + idx)
                            ? colors.success
                            : colors.backgroundSecondary,
                      },
                    ]}
                  >
                    <Text
                      style={[
                        styles.optionLabelText,
                        {
                          color:
                            correctAnswer.charAt(0).toUpperCase() === String.fromCharCode(65 + idx)
                              ? '#FFFFFF'
                              : colors.text,
                        },
                      ]}
                    >
                      {String.fromCharCode(65 + idx)}
                    </Text>
                  </View>
                  <TextInput
                    style={[
                      styles.optionInput,
                      { backgroundColor: colors.backgroundSecondary, color: colors.text, borderColor: colors.border },
                    ]}
                    value={opt.replace(/^[A-D]\)\s*/, '')}
                    onChangeText={(v) => updateOption(idx, `${String.fromCharCode(65 + idx)}) ${v}`)}
                    placeholder={`Option ${String.fromCharCode(65 + idx)}`}
                    placeholderTextColor={colors.textTertiary}
                  />
                </View>
              ))}
            </GlassCard>
          )}

          {/* Correct Answer */}
          <GlassCard style={styles.card}>
            <Text style={[styles.label, { color: colors.text }]}>Correct Answer</Text>
            <View style={styles.answerOptions}>
              {['A', 'B', 'C', 'D'].map((letter) => (
                <TouchableOpacity
                  key={letter}
                  style={[
                    styles.answerChip,
                    {
                      backgroundColor:
                        correctAnswer.charAt(0).toUpperCase() === letter
                          ? colors.primary
                          : colors.backgroundSecondary,
                      borderColor:
                        correctAnswer.charAt(0).toUpperCase() === letter
                          ? colors.primary
                          : colors.border,
                    },
                  ]}
                  onPress={() => setCorrectAnswer(letter)}
                >
                  <Text
                    style={[
                      styles.answerChipText,
                      {
                        color:
                          correctAnswer.charAt(0).toUpperCase() === letter
                            ? '#FFFFFF'
                            : colors.text,
                      },
                    ]}
                  >
                    {letter}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
          </GlassCard>

          {/* Marks */}
          <GlassCard style={styles.card}>
            <Text style={[styles.label, { color: colors.text }]}>Marks</Text>
            <TextInput
              style={[
                styles.input,
                { backgroundColor: colors.backgroundSecondary, color: colors.text, borderColor: colors.border },
              ]}
              value={marks}
              onChangeText={setMarks}
              keyboardType="numeric"
              maxLength={3}
            />
          </GlassCard>
        </ScrollView>

        {/* Save Button */}
        <View style={[styles.bottomBar, { backgroundColor: colors.card, borderTopColor: colors.border }]}>
          <TouchableOpacity
            style={[styles.cancelButton, { borderColor: colors.border }]}
            onPress={() => router.back()}
          >
            <Text style={[styles.cancelText, { color: colors.text }]}>Cancel</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.saveButton, { backgroundColor: colors.primary, opacity: isSaving ? 0.6 : 1 }]}
            onPress={handleSave}
            disabled={isSaving}
          >
            <IconSymbol name="checkmark" size={16} color="#FFF" />
            <Text style={styles.saveText}>{isSaving ? 'Saving...' : 'Save Changes'}</Text>
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  flex: { flex: 1 },
  content: { padding: Spacing.md, paddingBottom: 120, gap: Spacing.md },
  card: { padding: Spacing.md, gap: 8 },
  label: { fontSize: FontSizes.sm, fontWeight: '600' },
  textArea: {
    borderWidth: 1,
    borderRadius: BorderRadius.md,
    paddingHorizontal: Spacing.md,
    paddingVertical: 12,
    fontSize: FontSizes.md,
    minHeight: 120,
    textAlignVertical: 'top',
  },
  optionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  optionLabel: {
    width: 32,
    height: 32,
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
  },
  optionLabelText: {
    fontSize: FontSizes.sm,
    fontWeight: '700',
  },
  optionInput: {
    flex: 1,
    borderWidth: 1,
    borderRadius: BorderRadius.md,
    paddingHorizontal: Spacing.sm,
    paddingVertical: 8,
    fontSize: FontSizes.sm,
  },
  answerOptions: {
    flexDirection: 'row',
    gap: Spacing.sm,
  },
  answerChip: {
    width: 44,
    height: 44,
    borderRadius: 22,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1.5,
  },
  answerChipText: {
    fontSize: FontSizes.md,
    fontWeight: '700',
  },
  input: {
    borderWidth: 1,
    borderRadius: BorderRadius.md,
    paddingHorizontal: Spacing.md,
    paddingVertical: 10,
    fontSize: FontSizes.md,
    width: 80,
  },
  bottomBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'flex-end',
    padding: Spacing.md,
    borderTopWidth: 1,
    gap: Spacing.sm,
  },
  cancelButton: {
    paddingHorizontal: Spacing.md,
    paddingVertical: 10,
    borderRadius: BorderRadius.md,
    borderWidth: 1,
  },
  cancelText: {
    fontSize: FontSizes.sm,
    fontWeight: '500',
  },
  saveButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: Spacing.lg,
    paddingVertical: 10,
    borderRadius: BorderRadius.md,
  },
  saveText: {
    color: '#FFF',
    fontSize: FontSizes.sm,
    fontWeight: '600',
  },
});
