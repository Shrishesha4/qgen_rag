/**
 * QuestionSources Component
 * Collapsible UI showing where question content came from
 */

import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Animated,
  LayoutAnimation,
  Platform,
  UIManager,
  ScrollView,
} from 'react-native';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { Colors, Spacing, BorderRadius, FontSizes } from '@/constants/theme';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { QuestionSourceInfo, SourceReference } from '@/services/questions';

// Enable LayoutAnimation for Android
if (Platform.OS === 'android' && UIManager.setLayoutAnimationEnabledExperimental) {
  UIManager.setLayoutAnimationEnabledExperimental(true);
}

interface QuestionSourcesProps {
  sourceInfo: QuestionSourceInfo | null | undefined;
  compact?: boolean; // For inline usage
}

export function QuestionSources({ sourceInfo, compact = false }: QuestionSourcesProps) {
  const colorScheme = useColorScheme();
  const colors = Colors[colorScheme ?? 'light'];
  const isDark = colorScheme === 'dark';
  const [isExpanded, setIsExpanded] = useState(false);
  const [expandedSnippets, setExpandedSnippets] = useState<Record<number, boolean>>({});

  // Debug logging
  console.log('QuestionSources - sourceInfo:', sourceInfo);

  if (!sourceInfo || !sourceInfo.sources || sourceInfo.sources.length === 0) {
    console.log('QuestionSources - No sources to display');
    return null;
  }

  console.log('QuestionSources - Displaying', sourceInfo.sources.length, 'sources');

  const toggleExpand = () => {
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setIsExpanded(!isExpanded);
  };

  const getPositionIcon = (position: string | null): string => {
    switch (position) {
      case 'top':
        return 'arrow.up.doc';
      case 'bottom':
        return 'arrow.down.doc';
      default:
        return 'doc.text';
    }
  };

  const formatPageRange = (source: SourceReference): string => {
    if (source.page_range && source.page_range[0] !== source.page_range[1]) {
      return `Pages ${source.page_range[0]}-${source.page_range[1]}`;
    }
    if (source.page_number) {
      return `Page ${source.page_number}`;
    }
    return 'Unknown page';
  };

  const formatPosition = (source: SourceReference): string => {
    if (source.position_percentage !== null) {
      if (source.position_percentage < 33) return 'Top of page';
      if (source.position_percentage < 66) return 'Middle of page';
      return 'Bottom of page';
    }
    if (source.position_in_page) {
      return `${source.position_in_page.charAt(0).toUpperCase()}${source.position_in_page.slice(1)} of page`;
    }
    return '';
  };

  const styles = StyleSheet.create({
    container: {
      marginTop: compact ? Spacing.xs : Spacing.sm,
      borderRadius: BorderRadius.md,
      backgroundColor: isDark 
        ? 'rgba(100, 100, 100, 0.15)' 
        : 'rgba(0, 0, 0, 0.03)',
      overflow: 'hidden',
    },
    header: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      paddingHorizontal: Spacing.sm,
      paddingVertical: compact ? Spacing.xs : Spacing.sm,
    },
    headerLeft: {
      flexDirection: 'row',
      alignItems: 'center',
      flex: 1,
    },
    headerIcon: {
      marginRight: Spacing.xs,
    },
    headerText: {
      fontSize: compact ? FontSizes.xs : FontSizes.sm,
      fontWeight: '600',
      color: colors.primary,
    },
    headerCount: {
      fontSize: FontSizes.xs,
      color: colors.textSecondary,
      marginLeft: Spacing.xs,
    },
    expandIcon: {
      padding: Spacing.xs,
    },
    content: {
      paddingHorizontal: Spacing.sm,
      paddingBottom: Spacing.sm,
    },
    reasoning: {
      fontSize: FontSizes.sm,
      color: colors.textSecondary,
      fontStyle: 'italic',
      marginBottom: Spacing.sm,
      paddingHorizontal: Spacing.xs,
    },
    coverage: {
      fontSize: FontSizes.xs,
      color: colors.primary,
      backgroundColor: isDark 
        ? 'rgba(0, 122, 255, 0.15)' 
        : 'rgba(0, 122, 255, 0.08)',
      paddingHorizontal: Spacing.sm,
      paddingVertical: Spacing.xs,
      borderRadius: BorderRadius.sm,
      marginBottom: Spacing.sm,
      alignSelf: 'flex-start',
    },
    sourceCard: {
      backgroundColor: isDark 
        ? 'rgba(255, 255, 255, 0.05)' 
        : 'rgba(255, 255, 255, 0.8)',
      borderRadius: BorderRadius.sm,
      padding: Spacing.sm,
      marginBottom: Spacing.xs,
      borderLeftWidth: 3,
      borderLeftColor: colors.primary,
    },
    sourceHeader: {
      flexDirection: 'row',
      alignItems: 'flex-start',
      marginBottom: Spacing.xs,
      flexWrap: 'wrap',
    },
    sourceIcon: {
      marginRight: Spacing.xs,
    },
    documentName: {
      fontSize: FontSizes.sm,
      fontWeight: '600',
      color: colors.text,
      flex: 1,
      flexWrap: 'wrap',
    },
    sourceDetails: {
      flexDirection: 'row',
      flexWrap: 'wrap',
      gap: Spacing.xs,
      marginBottom: Spacing.xs,
    },
    detailBadge: {
      flexDirection: 'row',
      alignItems: 'center',
      backgroundColor: isDark 
        ? 'rgba(150, 150, 150, 0.2)' 
        : 'rgba(0, 0, 0, 0.05)',
      paddingHorizontal: Spacing.xs,
      paddingVertical: 2,
      borderRadius: 6,
    },
    detailText: {
      fontSize: FontSizes.xs,
      color: colors.textSecondary,
      marginLeft: 2,
    },
    sectionHeading: {
      fontSize: FontSizes.xs,
      color: colors.primary,
      fontWeight: '500',
      marginBottom: Spacing.xs,
    },
    snippet: {
      fontSize: FontSizes.xs,
      color: colors.textSecondary,
      lineHeight: 16,
      fontStyle: 'italic',
    },
    relevanceReason: {
      marginTop: Spacing.xs,
      paddingTop: Spacing.xs,
      borderTopWidth: 1,
      borderTopColor: isDark 
        ? 'rgba(255, 255, 255, 0.1)' 
        : 'rgba(0, 0, 0, 0.05)',
    },
    relevanceLabel: {
      fontSize: FontSizes.xs,
      color: colors.textSecondary,
      fontWeight: '500',
    },
    relevanceText: {
      fontSize: FontSizes.xs,
      color: colors.text,
      marginTop: 2,
    },
    showMoreButton: {
      flexDirection: 'row',
      alignItems: 'center',
      marginTop: Spacing.xs,
      alignSelf: 'flex-start',
    },
    showMoreText: {
      fontSize: FontSizes.xs,
      color: colors.primary,
      fontWeight: '600',
      marginRight: 4,
    },
  });

  return (
    <View style={styles.container}>
      <TouchableOpacity 
        style={styles.header} 
        onPress={toggleExpand}
        activeOpacity={0.7}
      >
        <View style={styles.headerLeft}>
          <IconSymbol 
            name="doc.text.magnifyingglass" 
            size={compact ? 14 : 16} 
            color={colors.primary}
            style={styles.headerIcon}
          />
          <Text style={styles.headerText}>Source References</Text>
          <Text style={styles.headerCount}>
            ({sourceInfo.sources.length} source{sourceInfo.sources.length !== 1 ? 's' : ''})
          </Text>
        </View>
        <View style={styles.expandIcon}>
          <IconSymbol 
            name={isExpanded ? 'chevron.up' : 'chevron.down'} 
            size={14} 
            color={colors.textSecondary}
          />
        </View>
      </TouchableOpacity>

      {isExpanded && (
        <View style={styles.content}>
          {/* Generation Reasoning */}
          {sourceInfo.generation_reasoning && (
            <Text style={styles.reasoning}>
              "{sourceInfo.generation_reasoning}"
            </Text>
          )}

          {/* Content Coverage */}
          {sourceInfo.content_coverage && (
            <Text style={styles.coverage}>
              {sourceInfo.content_coverage}
            </Text>
          )}

          {/* Source Cards */}
          {sourceInfo.sources.map((source, index) => (
            <View key={index} style={styles.sourceCard}>
              {/* Document Name */}
              <View style={styles.sourceHeader}>
                <IconSymbol 
                  name="book.closed" 
                  size={14} 
                  color={colors.primary}
                  style={styles.sourceIcon}
                />
                <Text style={styles.documentName}>
                  {source.document_name || 'Unknown Document'}
                </Text>
              </View>

              {/* Page & Position Details */}
              <View style={styles.sourceDetails}>
                {source.page_number && (
                  <View style={styles.detailBadge}>
                    <IconSymbol name="doc.text" size={10} color={colors.textSecondary} />
                    <Text style={styles.detailText}>{formatPageRange(source)}</Text>
                  </View>
                )}
                {source.position_in_page && (
                  <View style={styles.detailBadge}>
                    <IconSymbol 
                      name={getPositionIcon(source.position_in_page) as any} 
                      size={10} 
                      color={colors.textSecondary} 
                    />
                    <Text style={styles.detailText}>{formatPosition(source)}</Text>
                  </View>
                )}
              </View>

              {/* Section Heading */}
              {source.section_heading && (
                <Text style={styles.sectionHeading}>
                  Section: {source.section_heading}
                </Text>
              )}

              {/* Content Snippet */}
              {source.content_snippet && (
                <View>
                  <Text 
                    style={styles.snippet} 
                    numberOfLines={expandedSnippets[index] ? undefined : 3}
                  >
                    "{source.content_snippet}"
                  </Text>
                  {source.content_snippet.length > 150 && (
                    <TouchableOpacity
                      onPress={() => {
                        setExpandedSnippets(prev => ({
                          ...prev,
                          [index]: !prev[index]
                        }));
                      }}
                      style={styles.showMoreButton}
                    >
                      <Text style={styles.showMoreText}>
                        {expandedSnippets[index] ? 'Show Less' : 'Show More'}
                      </Text>
                      <IconSymbol 
                        name={expandedSnippets[index] ? 'chevron.up' : 'chevron.down'} 
                        size={12} 
                        color={colors.primary}
                      />
                    </TouchableOpacity>
                  )}
                </View>
              )}

              {/* Relevance Reason */}
              {source.relevance_reason && (
                <View style={styles.relevanceReason}>
                  <Text style={styles.relevanceLabel}>Why this was used:</Text>
                  <Text style={styles.relevanceText}>{source.relevance_reason}</Text>
                </View>
              )}
            </View>
          ))}
        </View>
      )}
    </View>
  );
}

export default QuestionSources;
