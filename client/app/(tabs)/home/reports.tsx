import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  ActivityIndicator,
  Platform,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { GlassCard } from '@/components/ui/glass-card';
import { NativeButton } from '@/components/ui/native-button';
import { Colors, Spacing, BorderRadius, FontSizes } from '@/constants/theme';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { subjectsService, Subject } from '@/services/subjects';
import { questionsService } from '@/services/questions';

interface AnalyticsData {
  total_questions: number;
  by_subject: Array<{ subject_id: string; subject_name: string; count: number }>;
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
};

const LO_COLORS = ['#007AFF', '#5856D6', '#FF9500', '#34C759', '#FF3B30'];

export default function ReportsScreen() {
  const colorScheme = useColorScheme();
  const colors = Colors[colorScheme ?? 'light'];
  
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [selectedSubject, setSelectedSubject] = useState<string | null>(null);
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    overview: true,
    learning_outcomes: true,
    bloom: true,
    syllabus: false,
  });

  const loadData = useCallback(async () => {
    try {
      const subjectsResponse = await subjectsService.listSubjects(1, 100);
      setSubjects(subjectsResponse.subjects);
      
      // Mock analytics data - in production, fetch from API
      const mockAnalytics: AnalyticsData = {
        total_questions: 156,
        by_subject: subjectsResponse.subjects.slice(0, 5).map((s, i) => ({
          subject_id: s.id,
          subject_name: s.name,
          count: Math.floor(Math.random() * 50) + 10,
        })),
        by_learning_outcome: [
          { learning_outcome: 'LO1', count: 35 },
          { learning_outcome: 'LO2', count: 42 },
          { learning_outcome: 'LO3', count: 28 },
          { learning_outcome: 'LO4', count: 31 },
          { learning_outcome: 'LO5', count: 20 },
        ],
        by_bloom: [
          { bloom_level: 'remember', count: 25 },
          { bloom_level: 'understand', count: 38 },
          { bloom_level: 'apply', count: 45 },
          { bloom_level: 'analyze', count: 28 },
          { bloom_level: 'evaluate', count: 15 },
          { bloom_level: 'create', count: 5 },
        ],
      };
      setAnalytics(mockAnalytics);
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, []);

  const handleRefresh = () => {
    setIsRefreshing(true);
    loadData();
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
        <LinearGradient
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
        </LinearGradient>

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
            onPress={() => setSelectedSubject(null)}
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
              onPress={() => setSelectedSubject(subject.id)}
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
                {subjects.length}
              </Text>
              <Text style={[styles.overviewLabel, { color: colors.textSecondary }]}>
                Subjects
              </Text>
            </View>
            <View style={[styles.overviewCard, { backgroundColor: colors.warning + '10' }]}>
              <Text style={[styles.overviewValue, { color: colors.warning }]}>
                5
              </Text>
              <Text style={[styles.overviewLabel, { color: colors.textSecondary }]}>
                Learning Outcomes
              </Text>
            </View>
            <View style={[styles.overviewCard, { backgroundColor: colors.secondary + '10' }]}>
              <Text style={[styles.overviewValue, { color: colors.secondary }]}>
                6
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
        {renderCollapsibleSection(
          'Syllabus Coverage',
          'doc.text.fill',
          'syllabus',
          ['#34C759', '#28A745'],
          <View style={styles.syllabusContent}>
            <View style={styles.coverageHeader}>
              <Text style={[styles.coverageLabel, { color: colors.textSecondary }]}>
                Overall Coverage
              </Text>
              <Text style={[styles.coverageValue, { color: colors.success }]}>78%</Text>
            </View>
            {renderProgressBar(78, 100, colors.success)}
            
            <View style={styles.coverageGaps}>
              <Text style={[styles.gapsTitle, { color: colors.text }]}>Coverage Gaps</Text>
              {['Unit 3: Advanced Topics', 'Unit 5: Case Studies'].map((gap, index) => (
                <View key={index} style={styles.gapItem}>
                  <IconSymbol name="exclamationmark.triangle.fill" size={14} color={colors.warning} />
                  <Text style={[styles.gapText, { color: colors.textSecondary }]}>{gap}</Text>
                </View>
              ))}
            </View>
          </View>
        )}

        {/* Export Button */}
        <TouchableOpacity style={[styles.exportButton, { backgroundColor: colors.primary }]}>
          <IconSymbol name="square.and.arrow.up" size={18} color="#FFFFFF" />
          <Text style={styles.exportButtonText}>Export Report</Text>
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
    padding: Spacing.lg,
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
    padding: Spacing.md,
    borderRadius: BorderRadius.md,
    gap: Spacing.sm,
  },
  sectionTitle: {
    flex: 1,
    fontSize: FontSizes.md,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  sectionContent: {
    padding: Spacing.lg,
    borderBottomLeftRadius: BorderRadius.md,
    borderBottomRightRadius: BorderRadius.md,
    marginTop: -BorderRadius.md,
    paddingTop: Spacing.lg + BorderRadius.md,
  },
  overviewGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.md,
  },
  overviewCard: {
    flex: 1,
    minWidth: '45%',
    padding: Spacing.md,
    borderRadius: BorderRadius.sm,
    alignItems: 'center',
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
    gap: Spacing.md,
  },
  analysisRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  analysisLabelContainer: {
    width: 50,
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
    width: 35,
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
  coverageGaps: {
    marginTop: Spacing.md,
    paddingTop: Spacing.md,
    borderTopWidth: 1,
    borderTopColor: '#E5E5EA',
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
  exportButtonText: {
    fontSize: FontSizes.md,
    fontWeight: '600',
    color: '#FFFFFF',
  },
});
