/**
 * Export Modal Component
 * Reusable modal for exporting questions in various formats
 * Uses native iOS page-sheet presentation for authentic feel
 */

import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Modal,
  TouchableOpacity,
  Switch,
  ScrollView,
  ActivityIndicator,
  Platform,
} from 'react-native';
import { IconSymbol } from './ui/icon-symbol';
import { Colors, FontSizes, Spacing, BorderRadius } from '@/constants/theme';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { ExportFormat, ExportOptions, exportQuestions } from '@/services/export';
import { Question } from '@/services/questions';
import { mediumImpact, selectionImpact } from '@/utils/haptics';

interface ExportModalProps {
  visible: boolean;
  onClose: () => void;
  questions: Question[];
  defaultFilename?: string;
  showGroupOptions?: boolean;
  showVettingFilter?: boolean;
}

export function ExportModal({
  visible,
  onClose,
  questions,
  defaultFilename = 'questions',
  showGroupOptions = true,
  showVettingFilter = true,
}: ExportModalProps) {
  const colorScheme = useColorScheme();
  const isDark = colorScheme === 'dark';
  const colors = Colors[colorScheme ?? 'light'];

  const [selectedFormat, setSelectedFormat] = useState<ExportFormat>('xlsx');
  const [includeReplacedQuestions, setIncludeReplacedQuestions] = useState(false);
  const [groupBy, setGroupBy] = useState<ExportOptions['groupBy']>('none');
  const [vettingFilter, setVettingFilter] = useState<ExportOptions['filterVettingStatus']>('all');
  const [isExporting, setIsExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const formats: { format: ExportFormat; label: string; icon: string }[] = [
    { format: 'xlsx', label: 'Excel (.xlsx)', icon: 'doc.text' },
    { format: 'csv', label: 'CSV', icon: 'tablecells' },
    { format: 'docx', label: 'Word (.doc)', icon: 'doc.richtext' },
  ];

  const groupOptions: { value: ExportOptions['groupBy']; label: string }[] = [
    { value: 'none', label: 'No Grouping' },
    { value: 'chapter', label: 'By Chapter' },
    { value: 'subject', label: 'By Subject' },
    { value: 'type', label: 'By Question Type' },
    { value: 'difficulty', label: 'By Difficulty' },
  ];

  const vettingOptions: { value: ExportOptions['filterVettingStatus']; label: string }[] = [
    { value: 'all', label: 'All Questions' },
    { value: 'approved', label: 'Approved Only' },
    { value: 'pending', label: 'Pending Review' },
    { value: 'rejected', label: 'Rejected' },
  ];

  const handleExport = async () => {
    mediumImpact();
    setIsExporting(true);
    setError(null);

    const result = await exportQuestions(questions, {
      format: selectedFormat,
      includeReplacedQuestions,
      groupBy,
      filterVettingStatus: vettingFilter,
    }, defaultFilename);

    setIsExporting(false);

    if (result.success) {
      onClose();
    } else {
      setError(result.error || 'Export failed');
    }
  };

  const textColor = isDark ? '#fff' : '#000';
  const secondaryText = isDark ? 'rgba(255,255,255,0.6)' : 'rgba(0,0,0,0.6)';
  const cardBg = isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.05)';
  const selectedBg = isDark ? 'rgba(0,122,255,0.3)' : 'rgba(0,122,255,0.15)';
  const borderColor = isDark ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.1)';

  // Filter questions based on current settings
  const getFilteredQuestions = () => {
    let filtered = [...questions];

    // Filter by vetting status
    if (vettingFilter !== 'all') {
      filtered = filtered.filter(q => {
        if (vettingFilter === 'approved') return q.vetting_status === 'approved';
        if (vettingFilter === 'pending') return q.vetting_status === 'pending' || !q.vetting_status;
        if (vettingFilter === 'rejected') return q.vetting_status === 'rejected';
        return true;
      });
    }

    return filtered;
  };

  const filteredQuestions = getFilteredQuestions();
  const previewQuestions = filteredQuestions.slice(0, 3); // Show first 3 as preview

  return (
    <Modal
      visible={visible}
      animationType="slide"
      presentationStyle={Platform.OS === 'ios' ? 'pageSheet' : 'fullScreen'}
      onRequestClose={onClose}
    >
      <View style={{ flex: 1, backgroundColor: colors.background }}>
      <View style={[styles.container, { backgroundColor: colors.background }]}>
        {/* Header */}
        <View style={[styles.header, { borderBottomColor: borderColor }]}>
          <TouchableOpacity onPress={() => {
            mediumImpact();
            onClose();
          }} style={styles.headerButton}>
            <Text style={[styles.headerButtonText, { color: colors.primary }]}>Cancel</Text>
          </TouchableOpacity>
          <Text style={[styles.title, { color: textColor }]}>Export Questions</Text>
          <View style={styles.headerButton} />
        </View>

        <ScrollView style={styles.content} showsVerticalScrollIndicator={false}>
          {/* Question Count */}
          <Text style={[styles.subtitle, { color: secondaryText }]}>
            {questions.length} question{questions.length !== 1 ? 's' : ''} available
          </Text>

          {/* Format Selection */}
          <Text style={[styles.sectionTitle, { color: textColor }]}>Export Format</Text>
          <View style={styles.optionGroup}>
            {formats.map((f) => (
              <TouchableOpacity
                key={f.format}
                style={[
                  styles.formatOption,
                  { backgroundColor: selectedFormat === f.format ? selectedBg : cardBg },
                  { borderColor: selectedFormat === f.format ? colors.primary : borderColor },
                ]}
                onPress={() => {
                  selectionImpact();
                  setSelectedFormat(f.format);
                }}
              >
                <IconSymbol
                  name={f.icon as any}
                  size={24}
                  color={selectedFormat === f.format ? colors.primary : secondaryText}
                />
                <Text
                  style={[
                    styles.formatLabel,
                    { color: selectedFormat === f.format ? colors.primary : textColor },
                  ]}
                >
                  {f.label}
                </Text>
              </TouchableOpacity>
            ))}
          </View>

          {/* Preview */}
          <Text style={[styles.sectionTitle, { color: textColor }]}>Preview</Text>
          <View style={[styles.previewContainer, {
            backgroundColor: isDark ? 'rgba(255,255,255,0.06)' : '#f8f9fa',
            borderColor: isDark ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.15)',
          }]}>
            <View style={styles.previewHeader}>
              <IconSymbol name="eye" size={14} color={colors.primary} />
              <Text style={[styles.previewHeaderText, { color: secondaryText }]}>
                {filteredQuestions.length} question{filteredQuestions.length !== 1 ? 's' : ''} · {selectedFormat.toUpperCase()} format
              </Text>
            </View>

            {previewQuestions.length > 0 ? (
              selectedFormat === 'docx' ? (
                /* Word-style preview */
                <View style={styles.previewDocx}>
                  {previewQuestions.map((q, idx) => (
                    <View key={q.id} style={styles.previewDocxItem}>
                      <Text style={[styles.previewDocxNumber, { color: textColor }]}>
                        Q{idx + 1}. {q.marks ? `[${q.marks} marks]` : ''}
                      </Text>
                      <Text style={[styles.previewDocxText, { color: textColor }]} numberOfLines={2}>
                        {q.question_text}
                      </Text>
                      {q.question_type === 'mcq' && q.options && q.options.length > 0 && (
                        <View style={styles.previewDocxOptions}>
                          {q.options.slice(0, 4).map((opt, oi) => (
                            <Text key={oi} style={[styles.previewDocxOption, { color: secondaryText }]}>
                              {String.fromCharCode(65 + oi)}) {opt}
                            </Text>
                          ))}
                        </View>
                      )}
                      {q.correct_answer && (
                        <Text style={[styles.previewDocxAnswer, { color: colors.primary }]} numberOfLines={1}>
                          Answer: {q.correct_answer}
                        </Text>
                      )}
                      {q.explanation && (
                        <Text style={[styles.previewDocxAnswer, { color: colors.textSecondary }]} numberOfLines={2}>
                          Explanation: {q.explanation}
                        </Text>
                      )}
                    </View>
                  ))}
                </View>
              ) : (
                /* Table-style preview for Excel/CSV */
                <View style={styles.previewTable}>
                  {/* Table header */}
                  <View style={[styles.previewTableRow, styles.previewTableHeaderRow, {
                    backgroundColor: isDark ? 'rgba(0,122,255,0.15)' : 'rgba(0,122,255,0.08)',
                    borderBottomColor: isDark ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.12)',
                  }]}>
                    <Text style={[styles.previewTableCell, styles.previewTableCellNum, styles.previewTableHeaderCell, { color: textColor }]}>#</Text>
                    <Text style={[styles.previewTableCell, styles.previewTableCellQ, styles.previewTableHeaderCell, { color: textColor }]}>Question</Text>
                    <Text style={[styles.previewTableCell, styles.previewTableCellType, styles.previewTableHeaderCell, { color: textColor }]}>Type</Text>
                    <Text style={[styles.previewTableCell, styles.previewTableCellMarks, styles.previewTableHeaderCell, { color: textColor }]}>Marks</Text>
                  </View>
                  {/* Table rows */}
                  {previewQuestions.map((q, idx) => (
                    <View key={q.id} style={[styles.previewTableRow, {
                      borderBottomColor: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)',
                      backgroundColor: idx % 2 === 0
                        ? 'transparent'
                        : isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.02)',
                    }]}>
                      <Text style={[styles.previewTableCell, styles.previewTableCellNum, { color: secondaryText }]}>{idx + 1}</Text>
                      <Text style={[styles.previewTableCell, styles.previewTableCellQ, { color: textColor }]} numberOfLines={1}>{q.question_text}</Text>
                      <Text style={[styles.previewTableCell, styles.previewTableCellType, { color: secondaryText }]}>
                        {q.question_type === 'mcq' ? 'MCQ' : q.question_type === 'short_answer' ? 'Short' : 'Long'}
                      </Text>
                      <Text style={[styles.previewTableCell, styles.previewTableCellMarks, { color: secondaryText }]}>{q.marks ?? '-'}</Text>
                    </View>
                  ))}
                </View>
              )
            ) : (
              <Text style={[styles.previewEmpty, { color: secondaryText }]}>
                No questions match the current filters
              </Text>
            )}

            {filteredQuestions.length > 3 && previewQuestions.length > 0 && (
              <Text style={[styles.previewMore, { color: secondaryText }]}>
                + {filteredQuestions.length - 3} more question{filteredQuestions.length - 3 !== 1 ? 's' : ''}
              </Text>
            )}
          </View>

          {/* Group By Selection */}
            {showGroupOptions && (
              <>
                <Text style={[styles.sectionTitle, { color: textColor }]}>Group By</Text>
                <View style={styles.chipGroup}>
                  {groupOptions.map((opt) => (
                    <TouchableOpacity
                      key={opt.value}
                      style={[
                        styles.chip,
                        { backgroundColor: groupBy === opt.value ? selectedBg : cardBg },
                        { borderColor: groupBy === opt.value ? colors.primary : borderColor },
                      ]}
                      onPress={() => {
                        selectionImpact();
                        setGroupBy(opt.value);
                      }}
                    >
                      <Text
                        style={[
                          styles.chipText,
                          { color: groupBy === opt.value ? colors.primary : textColor },
                        ]}
                      >
                        {opt.label}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </>
            )}

            {/* Vetting Status Filter */}
            {showVettingFilter && (
              <>
                <Text style={[styles.sectionTitle, { color: textColor }]}>Vetting Status</Text>
                <View style={styles.chipGroup}>
                  {vettingOptions.map((opt) => (
                    <TouchableOpacity
                      key={opt.value}
                      style={[
                        styles.chip,
                        { backgroundColor: vettingFilter === opt.value ? selectedBg : cardBg },
                        { borderColor: vettingFilter === opt.value ? colors.primary : borderColor },
                      ]}
                      onPress={() => {
                        selectionImpact();
                        setVettingFilter(opt.value);
                      }}
                    >
                      <Text
                        style={[
                          styles.chipText,
                          { color: vettingFilter === opt.value ? colors.primary : textColor },
                        ]}
                      >
                        {opt.label}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </>
            )}

            {/* Include Replaced Questions Toggle */}
            <View style={[styles.toggleRow, { borderTopColor: borderColor }]}>
              <View>
                <Text style={[styles.toggleLabel, { color: textColor }]}>Include Replaced Questions</Text>
                <Text style={[styles.toggleHint, { color: secondaryText }]}>
                  Export questions that were replaced during vetting
                </Text>
              </View>
              <Switch
                value={includeReplacedQuestions}
                onValueChange={(value) => {
                  selectionImpact();
                  setIncludeReplacedQuestions(value);
                }}
                trackColor={{ false: cardBg, true: colors.primary }}
                thumbColor="#fff"
              />
            </View>

            {/* Error Message */}
            {error && (
              <View style={styles.errorContainer}>
                <IconSymbol name="exclamationmark.triangle.fill" size={16} color={colors.error} />
                <Text style={[styles.errorText, { color: colors.error }]}>{error}</Text>
              </View>
            )}
          </ScrollView>

          {/* Export Button Footer */}
          <View style={[styles.footer, { borderTopColor: borderColor }]}>
            <TouchableOpacity
              style={[styles.exportButton, isExporting && styles.exportButtonDisabled]}
              onPress={handleExport}
              disabled={isExporting || questions.length === 0}
            >
              <View style={styles.exportButtonContent}>
                {isExporting ? (
                  <ActivityIndicator color="#fff" size="small" />
                ) : (
                  <>
                    <IconSymbol name="square.and.arrow.up" size={20} color="#fff" />
                    <Text style={styles.exportButtonText}>Export</Text>
                  </>
                )}
              </View>
            </TouchableOpacity>
          </View>
      </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    maxWidth: 600,
    width: '100%',
    alignSelf: 'center',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  headerButton: {
    minWidth: 60,
    alignItems: 'center',
    paddingVertical: 4,
  },
  headerButtonText: {
    fontSize: FontSizes.md,
  },
  title: {
    fontSize: FontSizes.lg,
    fontWeight: '600',
    flex: 1,
    textAlign: 'center',
  },
  content: {
    flex: 1,
    paddingHorizontal: Spacing.md,
    paddingTop: Spacing.sm,
  },
  subtitle: {
    fontSize: FontSizes.sm,
    marginBottom: Spacing.md,
  },
  sectionTitle: {
    fontSize: FontSizes.md,
    fontWeight: '600',
    marginTop: Spacing.md,
    marginBottom: Spacing.sm,
  },
  optionGroup: {
    flexDirection: 'row',
    gap: Spacing.sm,
  },
  formatOption: {
    flex: 1,
    alignItems: 'center',
    padding: Spacing.md,
    borderRadius: BorderRadius.md,
    borderWidth: 1.5,
    gap: 6,
  },
  formatLabel: {
    fontSize: FontSizes.sm,
    fontWeight: '500',
  },
  chipGroup: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.xs,
  },
  chip: {
    paddingHorizontal: Spacing.sm,
    paddingVertical: 6,
    borderRadius: BorderRadius.full,
    borderWidth: 1,
  },
  chipText: {
    fontSize: FontSizes.sm,
    fontWeight: '500',
  },
  toggleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: Spacing.lg,
    paddingTop: Spacing.md,
    borderTopWidth: StyleSheet.hairlineWidth,
  },
  toggleLabel: {
    fontSize: FontSizes.md,
    fontWeight: '500',
  },
  toggleHint: {
    fontSize: FontSizes.xs,
    marginTop: 2,
  },
  errorContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: Spacing.md,
    padding: Spacing.sm,
    backgroundColor: 'rgba(255,59,48,0.1)',
    borderRadius: BorderRadius.sm,
  },
  errorText: {
    fontSize: FontSizes.sm,
    flex: 1,
  },
  previewContainer: {
    padding: Spacing.md,
    borderRadius: BorderRadius.md,
    borderWidth: 1.5,
    overflow: 'hidden',
  },
  previewHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: Spacing.sm,
  },
  previewHeaderText: {
    fontSize: FontSizes.xs,
    fontWeight: '500',
  },
  // Word-style preview
  previewDocx: {
    gap: Spacing.sm,
  },
  previewDocxItem: {
    gap: 3,
  },
  previewDocxNumber: {
    fontSize: FontSizes.sm,
    fontWeight: '600',
  },
  previewDocxText: {
    fontSize: FontSizes.sm,
    lineHeight: 19,
    paddingLeft: Spacing.md,
  },
  previewDocxOptions: {
    paddingLeft: Spacing.xl,
    gap: 2,
  },
  previewDocxOption: {
    fontSize: FontSizes.xs,
    lineHeight: 16,
  },
  previewDocxAnswer: {
    fontSize: FontSizes.xs,
    fontWeight: '600',
    paddingLeft: Spacing.md,
    marginTop: 2,
  },
  // Table-style preview (Excel/CSV)
  previewTable: {
    borderRadius: BorderRadius.sm,
    overflow: 'hidden',
  },
  previewTableRow: {
    flexDirection: 'row',
    alignItems: 'center',
    borderBottomWidth: StyleSheet.hairlineWidth,
    paddingVertical: 6,
    paddingHorizontal: 6,
  },
  previewTableHeaderRow: {
    borderBottomWidth: 1,
    paddingVertical: 8,
  },
  previewTableHeaderCell: {
    fontWeight: '600',
  },
  previewTableCell: {
    fontSize: FontSizes.xs,
  },
  previewTableCellNum: {
    width: 24,
    textAlign: 'center',
  },
  previewTableCellQ: {
    flex: 1,
    paddingHorizontal: 4,
  },
  previewTableCellType: {
    width: 42,
    textAlign: 'center',
  },
  previewTableCellMarks: {
    width: 38,
    textAlign: 'center',
  },
  previewMore: {
    fontSize: FontSizes.xs,
    textAlign: 'center',
    marginTop: Spacing.sm,
    fontWeight: '500',
    fontStyle: 'italic',
  },
  previewEmpty: {
    fontSize: FontSizes.sm,
    textAlign: 'center',
    paddingVertical: Spacing.lg,
    fontStyle: 'italic',
  },
  footer: {
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.md,
    borderTopWidth: StyleSheet.hairlineWidth,
  },
  exportButton: {
    backgroundColor: '#007AFF',
    paddingVertical: Spacing.md,
    borderRadius: BorderRadius.md,
  },
  exportButtonContent: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  exportButtonDisabled: {
    opacity: 0.6,
  },
  exportButtonText: {
    color: '#fff',
    fontSize: FontSizes.md,
    fontWeight: '600',
  },
});
