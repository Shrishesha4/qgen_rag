/**
 * Export Modal Component
 * Reusable modal for exporting questions in various formats
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
} from 'react-native';
import { BlurView } from 'expo-blur';
import { IconSymbol } from './ui/icon-symbol';
import { Colors, FontSizes, Spacing, BorderRadius } from '@/constants/theme';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { ExportFormat, ExportOptions, exportQuestions } from '@/services/export';
import { Question } from '@/services/questions';

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

  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={onClose}
    >
      <BlurView intensity={isDark ? 50 : 30} tint={isDark ? 'dark' : 'light'} style={styles.backdrop}>
        <TouchableOpacity style={styles.backdrop} activeOpacity={1} onPress={onClose}>
          <View />
        </TouchableOpacity>
      </BlurView>

      <View style={styles.modalContainer}>
        <View style={[styles.modal, { backgroundColor: isDark ? '#1c1c1e' : '#fff' }]}>
          {/* Header */}
          <View style={[styles.header, { borderBottomColor: borderColor }]}>
            <TouchableOpacity onPress={onClose} style={styles.closeButton}>
              <IconSymbol name="xmark.circle.fill" size={28} color={secondaryText} />
            </TouchableOpacity>
            <Text style={[styles.title, { color: textColor }]}>Export Questions</Text>
            <View style={styles.placeholder} />
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
                  onPress={() => setSelectedFormat(f.format)}
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
                      onPress={() => setGroupBy(opt.value)}
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
                      onPress={() => setVettingFilter(opt.value)}
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
                onValueChange={setIncludeReplacedQuestions}
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

          {/* Export Button */}
          <View style={styles.footer}>
            <TouchableOpacity
              style={[styles.exportButton, isExporting && styles.exportButtonDisabled]}
              onPress={handleExport}
              disabled={isExporting || questions.length === 0}
            >
              {isExporting ? (
                <ActivityIndicator color="#fff" />
              ) : (
                <>
                  <IconSymbol name="square.and.arrow.up" size={20} color="#fff" />
                  <Text style={styles.exportButtonText}>Export</Text>
                </>
              )}
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    ...StyleSheet.absoluteFillObject,
  },
  modalContainer: {
    flex: 1,
    justifyContent: 'flex-end',
  },
  modal: {
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    maxHeight: '85%',
    paddingBottom: 34, // Safe area
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  closeButton: {
    padding: 4,
  },
  title: {
    fontSize: FontSizes.lg,
    fontWeight: '600',
  },
  placeholder: {
    width: 36,
  },
  content: {
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
  footer: {
    paddingHorizontal: Spacing.md,
    paddingTop: Spacing.md,
  },
  exportButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#007AFF',
    paddingVertical: Spacing.md,
    borderRadius: BorderRadius.md,
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
