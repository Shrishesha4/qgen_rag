import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  ActivityIndicator,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { Colors, Spacing, BorderRadius, FontSizes } from '@/constants/theme';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { subjectsService, Subject } from '@/services/subjects';
import { vettingService, VettingStats, SubjectAnalytics } from '@/services/vetting';
import { exportReport, ReportData, ExportFormat } from '@/services/export';
import { useToast } from '@/components/toast';

interface AnalyticsData {
  total_questions: number;
  subjects_count: number;
  unique_los: number;
  unique_blooms: number;
  by_subject: SubjectAnalytics[];
  by_learning_outcome: Array<{ learning_outcome: string; count: number }>;
  by_bloom: Array<{ bloom_level: string; count: number }>;
}

const BLOOM_COLORS: Record<string, string> = {
  remember: '#007AFF',
  understand: '#5856D6',
  apply: '#34C759',
  analyze: '#FF9500',
  evaluate: '#FF3B30',
  create: '#AF52DE',
  unspecified: '#8E8E93',
};

const LO_COLORS = ['#007AFF', '#5856D6', '#FF9500', '#34C759', '#FF3B30', '#AF52DE', '#FF2D55', '#00C7BE'];

export default function ReportsScreen() {
  const colorScheme = useColorScheme();
  const colors = Colors[colorScheme ?? 'light'];
  const { showSuccess, showError } = useToast();
  
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [selectedSubject, setSelectedSubject] = useState<string | null>(null);
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [vettingStats, setVettingStats] = useState<VettingStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    overview: true,
    learning_outcomes: true,
    bloom: true,
    syllabus: false,
  });
  const [isExporting, setIsExporting] = useState(false);

  const loadData = useCallback(async () => {
    try {
      // Fetch all data from API in parallel
      const [subjectsResponse, vettingStatsResponse, subjectAnalytics, loAnalytics, bloomAnalytics] = await Promise.all([
        subjectsService.listSubjects(1, 100),
        vettingService.getVettingStats(selectedSubject || undefined),
        vettingService.getAnalyticsBySubject(),
        vettingService.getAnalyticsByLO(selectedSubject || undefined),
        vettingService.getAnalyticsByBloom(selectedSubject || undefined),
      ]);
      
      setSubjects(subjectsResponse.subjects);
      setVettingStats(vettingStatsResponse);
      
      // Transform LO data
      const loData = Object.entries(loAnalytics.learning_outcomes || {}).map(([lo, count]) => ({
        learning_outcome: lo,
        count: count,
      }));
      
      // Transform Bloom data  
      const bloomData = Object.entries(bloomAnalytics.bloom_levels || {}).map(([level, count]) => ({
        bloom_level: level,
        count: count,
      }));
      
      const analyticsData: AnalyticsData = {
        total_questions: vettingStatsResponse.total_generated,
        subjects_count: subjectsResponse.subjects.length,
        unique_los: loData.length,
        unique_blooms: bloomData.filter(b => b.bloom_level !== 'unspecified').length,
        by_subject: subjectAnalytics.subjects,
        by_learning_outcome: loData,
        by_bloom: bloomData,
      };
      
      setAnalytics(analyticsData);
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [selectedSubject]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleRefresh = () => {
    setIsRefreshing(true);
    loadData();
  };
  
  const handleSubjectChange = (subjectId: string | null) => {
    setSelectedSubject(subjectId);
    setIsLoading(true);
  };

  const handleExport = async (format: ExportFormat = 'xlsx') => {
    if (!analytics || !vettingStats) return;
    
    setIsExporting(true);
    try {
      const selectedSubjectData = subjects.find(s => s.id === selectedSubject);
      const reportData: ReportData = {
        title: selectedSubjectData ? `${selectedSubjectData.code} Analytics Report` : 'Question Bank Analytics Report',
        generatedAt: new Date().toISOString(),
        summary: {
          totalQuestions: analytics.total_questions,
          approvedQuestions: vettingStats.total_approved,
          pendingQuestions: vettingStats.pending_review,
          rejectedQuestions: vettingStats.total_rejected,
        },
        byType: {}, // Not available in current analytics
        byDifficulty: {}, // Not available in current analytics
        byBloomLevel: analytics.by_bloom.reduce((acc, item) => {
          acc[item.bloom_level] = item.count;
          return acc;
        }, {} as Record<string, number>),
        bySubject: analytics.by_subject.reduce((acc, item) => {
          acc[item.code] = item.total_questions;
          return acc;
        }, {} as Record<string, number>),
      };
      
      const filename = selectedSubjectData ? `${selectedSubjectData.code}_report` : 'analytics_report';
      const result = await exportReport(reportData, format, filename);
      
      if (result.success) {
        showSuccess('Report exported successfully');
      } else {
        showError(result.error || 'Export failed', 'Export Failed');
      }
    } catch (error) {
      showError(error, 'Export Failed');
    } finally {
      setIsExporting(false);
    }
  };

  const toggleSection = (section: string) => {
    setExpandedSections((prev) => ({
      ...prev,
      [section]: !prev[section],
    }));
  };

  const getMaxCount = (items: Array<{ count: number }>) => {
    return Math.max(...items.map((i) => i.count), 1);
  };

  const renderProgressBar = (value: number, max: number, color: string) => {
    const percentage = (value / max) * 100;
    return (
      <View style={[styles.progressBarContainer, { backgroundColor: colors.border }]}>
        <View style={[styles.progressBarFill, { width: `${percentage}%`, backgroundColor: color }]} />
      </View>
    );
  };

  const renderCollapsibleSection = (
    title: string,
    icon: string,
    sectionKey: string,
    gradientColors: string[],
    content: React.ReactNode
  ) => {
    const isExpanded = expandedSections[sectionKey];
    return (
      <View style={styles.section}>
        <TouchableOpacity onPress={() => toggleSection(sectionKey)}>
          <LinearGradient
            colors={gradientColors as [string, string]}
            style={styles.sectionHeader}
          >
            <IconSymbol name={icon as never} size={18} color="#FFFFFF" />
            <Text style={styles.sectionTitle}>{title}</Text>
            <IconSymbol
              name={isExpanded ? 'chevron.up' : 'chevron.down'}
              size={16}
              color="#FFFFFF"
            />
          </LinearGradient>
        </TouchableOpacity>
        {isExpanded && (
          <View style={[styles.sectionContent, { backgroundColor: colors.card }]}>
            {content}
          </View>
        )}
      </View>
    );
  };

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
        {/* Header */}
        {/* <LinearGradient
          colors={['#34C759', '#28A745'] as const}
          style={styles.headerCard}
        >
          <IconSymbol name="chart.bar.fill" size={28} color="#FFFFFF" />
          <View style={styles.headerContent}>
            <Text style={styles.headerTitle}>Reports & Analytics</Text>
            <Text style={styles.headerDescription}>
              Comprehensive analysis of question bank coverage and distribution
            </Text>
          </View>
        </LinearGradient> */}

        {/* Subject Filter */}
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={styles.filterContainer}
          contentContainerStyle={styles.filterContent}
        >
          <TouchableOpacity
            style={[
              styles.filterChip,
              { backgroundColor: !selectedSubject ? colors.primary : colors.card },
            ]}
            onPress={() => handleSubjectChange(null)}
          >
            <Text style={[
              styles.filterChipText,
              { color: !selectedSubject ? '#FFFFFF' : colors.text },
            ]}>
              All Subjects
            </Text>
          </TouchableOpacity>
          {subjects.slice(0, 5).map((subject) => (
            <TouchableOpacity
              key={subject.id}
              style={[
                styles.filterChip,
                { backgroundColor: selectedSubject === subject.id ? colors.primary : colors.card },
              ]}
              onPress={() => handleSubjectChange(subject.id)}
            >
              <Text style={[
                styles.filterChipText,
                { color: selectedSubject === subject.id ? '#FFFFFF' : colors.text },
              ]}>
                {subject.code}
              </Text>
            </TouchableOpacity>
          ))}
        </ScrollView>

        {/* Overview Stats */}
        {renderCollapsibleSection(
          'Overview',
          'square.grid.2x2.fill',
          'overview',
          ['#007AFF', '#0056B3'],
          <View style={styles.overviewGrid}>
            <View style={[styles.overviewCard, { backgroundColor: colors.primary + '10' }]}>
              <Text style={[styles.overviewValue, { color: colors.primary }]}>
                {analytics?.total_questions || 0}
              </Text>
              <Text style={[styles.overviewLabel, { color: colors.textSecondary }]}>
                Total Questions
              </Text>
            </View>
            <View style={[styles.overviewCard, { backgroundColor: colors.success + '10' }]}>
              <Text style={[styles.overviewValue, { color: colors.success }]}>
                {analytics?.subjects_count || 0}
              </Text>
              <Text style={[styles.overviewLabel, { color: colors.textSecondary }]}>
                Subjects
              </Text>
            </View>
            <View style={[styles.overviewCard, { backgroundColor: colors.warning + '10' }]}>
              <Text style={[styles.overviewValue, { color: colors.warning }]}>
                {analytics?.unique_los || 0}
              </Text>
              <Text style={[styles.overviewLabel, { color: colors.textSecondary }]}>
                Learning Outcomes
              </Text>
            </View>
            <View style={[styles.overviewCard, { backgroundColor: colors.secondary + '10' }]}>
              <Text style={[styles.overviewValue, { color: colors.secondary }]}>
                {analytics?.unique_blooms || 0}
              </Text>
              <Text style={[styles.overviewLabel, { color: colors.textSecondary }]}>
                Bloom Levels
              </Text>
            </View>
          </View>
        )}

        {/* Learning Outcomes Analysis */}
        {analytics && renderCollapsibleSection(
          'By Learning Outcome',
          'target',
          'learning_outcomes',
          ['#5856D6', '#4A4ADE'],
          <View style={styles.analysisContent}>
            {analytics.by_learning_outcome.map((item, index) => {
              const maxCount = getMaxCount(analytics.by_learning_outcome);
              const color = LO_COLORS[index % LO_COLORS.length];
              return (
                <View key={item.learning_outcome} style={styles.analysisRow}>
                  <View style={styles.analysisLabelContainer}>
                    <View style={[styles.loBadge, { backgroundColor: color }]}>
                      <Text style={styles.loBadgeText}>{item.learning_outcome}</Text>
                    </View>
                  </View>
                  <View style={styles.analysisBarContainer}>
                    {renderProgressBar(item.count, maxCount, color)}
                  </View>
                  <Text style={[styles.analysisCount, { color }]}>{item.count}</Text>
                </View>
              );
            })}
          </View>
        )}

        {/* Bloom's Taxonomy Analysis */}
        {analytics && renderCollapsibleSection(
          "By Bloom's Taxonomy",
          'brain',
          'bloom',
          ['#FF9500', '#FF7F00'],
          <View style={styles.analysisContent}>
            {analytics.by_bloom.map((item) => {
              const maxCount = getMaxCount(analytics.by_bloom);
              const color = BLOOM_COLORS[item.bloom_level] || colors.primary;
              return (
                <View key={item.bloom_level} style={styles.analysisRow}>
                  <Text style={[styles.bloomLabel, { color: colors.text }]}>
                    {item.bloom_level.charAt(0).toUpperCase() + item.bloom_level.slice(1)}
                  </Text>
                  <View style={styles.analysisBarContainer}>
                    {renderProgressBar(item.count, maxCount, color)}
                  </View>
                  <Text style={[styles.analysisCount, { color }]}>{item.count}</Text>
                </View>
              );
            })}
          </View>
        )}

        {/* Syllabus Coverage */}
        {vettingStats && renderCollapsibleSection(
          'Vetting Overview',
          'checkmark.shield.fill',
          'syllabus',
          ['#34C759', '#28A745'],
          <View style={styles.syllabusContent}>
            <View style={styles.coverageHeader}>
              <Text style={[styles.coverageLabel, { color: colors.textSecondary }]}>
                Approval Rate
              </Text>
              <Text style={[styles.coverageValue, { color: colors.success }]}>{vettingStats.approval_rate.toFixed(0)}%</Text>
            </View>
            {renderProgressBar(vettingStats.approval_rate, 100, colors.success)}
            
            <View style={[styles.vettingStatsGrid, { borderTopColor: colors.border }]}> 
              <View style={styles.vettingStatItem}>
                <Text style={[styles.vettingStatValue, { color: colors.success }]}>{vettingStats.total_approved}</Text>
                <Text style={[styles.vettingStatLabel, { color: colors.textSecondary }]}>Approved</Text>
              </View>
              <View style={styles.vettingStatItem}>
                <Text style={[styles.vettingStatValue, { color: colors.warning }]}>{vettingStats.pending_review}</Text>
                <Text style={[styles.vettingStatLabel, { color: colors.textSecondary }]}>Pending</Text>
              </View>
              <View style={styles.vettingStatItem}>
                <Text style={[styles.vettingStatValue, { color: colors.error }]}>{vettingStats.total_rejected}</Text>
                <Text style={[styles.vettingStatLabel, { color: colors.textSecondary }]}>Rejected</Text>
              </View>
            </View>
          </View>
        )}

        {/* Export Button */}
        <TouchableOpacity 
          style={[styles.exportButton, { backgroundColor: colors.primary }, isExporting && { opacity: 0.6 }]}
          onPress={() => handleExport('xlsx')}
          disabled={isExporting}
        >
          <View style={styles.exportIconContainer}>
            {isExporting ? (
              <ActivityIndicator size="small" color="#FFFFFF" />
            ) : (
              <IconSymbol name="square.and.arrow.up" size={18} color="#FFFFFF" />
            )}
          </View>
          <Text style={styles.exportButtonText}>{isExporting ? 'Exporting...' : 'Export Report'}</Text>
        </TouchableOpacity>
      </ScrollView>
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
    paddingTop: Spacing.headerInset,
    paddingHorizontal: Spacing.lg,
    paddingBottom: 100,
  },
  headerCard: {
    flexDirection: 'row',
    padding: Spacing.lg,
    borderRadius: BorderRadius.md,
    marginBottom: Spacing.lg,
  },
  headerContent: {
    flex: 1,
    marginLeft: Spacing.md,
  },
  headerTitle: {
    fontSize: FontSizes.lg,
    fontWeight: '700',
    color: '#FFFFFF',
    marginBottom: Spacing.xs,
  },
  headerDescription: {
    fontSize: FontSizes.sm,
    color: 'rgba(255, 255, 255, 0.9)',
  },
  filterContainer: {
    marginBottom: Spacing.lg,
  },
  filterContent: {
    paddingRight: Spacing.lg,
    gap: Spacing.sm,
  },
  filterChip: {
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.full,
    marginRight: Spacing.sm,
  },
  filterChipText: {
    fontSize: FontSizes.sm,
    fontWeight: '500',
  },
  section: {
    marginBottom: Spacing.md,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: Spacing.sm,
    paddingHorizontal: Spacing.md,
    borderRadius: BorderRadius.md,
    gap: Spacing.sm,
    zIndex: 3,
    elevation: 3, // Android
    boxShadow: '0px 3px 8px rgba(0,0,0,0.06)',
  },
  sectionTitle: {
    flex: 1,
    fontSize: FontSizes.md,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  sectionContent: {
    padding: Spacing.lg,
    borderTopLeftRadius: BorderRadius.md,
    borderTopRightRadius: BorderRadius.md,
    borderBottomLeftRadius: BorderRadius.md,
    borderBottomRightRadius: BorderRadius.md,
    marginTop: Spacing.sm,
    paddingTop: Spacing.md,
    zIndex: 1,
    overflow: 'hidden',
  },
  overviewGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
  },
  overviewCard: {
    flexBasis: '48%',
    padding: Spacing.md,
    borderRadius: BorderRadius.sm,
    alignItems: 'center',
    marginBottom: Spacing.md,
  },
  overviewValue: {
    fontSize: FontSizes.xxl,
    fontWeight: '700',
  },
  overviewLabel: {
    fontSize: FontSizes.xs,
    marginTop: Spacing.xs,
  },
  analysisContent: {
    marginBottom: Spacing.md,
  },
  analysisRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    paddingVertical: Spacing.sm,
  },
  analysisLabelContainer: {
    width: 120,
  },
  loBadge: {
    paddingHorizontal: Spacing.sm,
    paddingVertical: Spacing.xs,
    borderRadius: BorderRadius.sm,
  },
  loBadgeText: {
    fontSize: FontSizes.xs,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  bloomLabel: {
    width: 80,
    fontSize: FontSizes.sm,
    fontWeight: '500',
  },
  analysisBarContainer: {
    flex: 1,
  },
  progressBarContainer: {
    height: 8,
    borderRadius: 4,
    overflow: 'hidden',
  },
  progressBarFill: {
    height: '100%',
    borderRadius: 4,
  },
  analysisCount: {
    width: 40,
    fontSize: FontSizes.sm,
    fontWeight: '700',
    textAlign: 'right',
  },
  syllabusContent: {
    gap: Spacing.md,
  },
  coverageHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  coverageLabel: {
    fontSize: FontSizes.sm,
  },
  coverageValue: {
    fontSize: FontSizes.lg,
    fontWeight: '700',
  },
  vettingStatsGrid: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    marginTop: Spacing.md,
    paddingTop: Spacing.md,
    borderTopWidth: 1,
  },
  vettingStatItem: {
    alignItems: 'center',
  },
  vettingStatValue: {
    fontSize: FontSizes.xl,
    fontWeight: '700',
  },
  vettingStatLabel: {
    fontSize: FontSizes.xs,
    marginTop: Spacing.xs,
  },
  coverageGaps: {
    marginTop: Spacing.md,
    paddingTop: Spacing.md,
    borderTopWidth: 1,
  },
  gapsTitle: {
    fontSize: FontSizes.sm,
    fontWeight: '600',
    marginBottom: Spacing.sm,
  },
  gapItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    marginBottom: Spacing.xs,
  },
  gapText: {
    fontSize: FontSizes.sm,
  },
  exportButton: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    padding: Spacing.md,
    borderRadius: BorderRadius.md,
    marginTop: Spacing.lg,
    gap: Spacing.sm,
  },
  exportIconContainer: {
    width: 18,
    height: 18,
    justifyContent: 'center',
    alignItems: 'center',
  },
  exportButtonText: {
    fontSize: FontSizes.md,
    fontWeight: '600',
    color: '#FFFFFF',
  },
});
