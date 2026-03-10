import React from 'react';
import { 
  View, 
  StyleSheet, 
  ViewStyle, 
  Platform,
  StyleProp,
} from 'react-native';
import { 
  GlassView, 
  GlassContainer,
  isLiquidGlassAvailable,
  isGlassEffectAPIAvailable,
} from 'expo-glass-effect';
import { BorderRadius } from '@/constants/theme';
import { useColorScheme } from '@/hooks/use-color-scheme';
import { Colors } from '@/constants/theme';

// Check if native glass effect is available (iOS 26+)
const checkCanUseGlass = () => {
  try {
    return Platform.OS === 'ios' && 
      isLiquidGlassAvailable?.() && 
      isGlassEffectAPIAvailable?.();
  } catch {
    return false;
  }
};

interface GlassCardProps {
  children: React.ReactNode;
  style?: StyleProp<ViewStyle>;
  glassStyle?: 'regular' | 'clear';
  tintColor?: string;
  isInteractive?: boolean;
  borderRadius?: number;
  pointerEvents?: 'auto' | 'none' | 'box-none' | 'box-only';
}

/**
 * iOS 26 Native Liquid Glass Card Component
 * Uses expo-glass-effect's GlassView for native iOS glass effect
 * Falls back to themed view on unsupported platforms
 */
export function GlassCard({ 
  children, 
  style,
  glassStyle = 'regular',
  tintColor,
  isInteractive = false,
  borderRadius = BorderRadius.lg,
  pointerEvents,
}: GlassCardProps) {
  const colorScheme = useColorScheme();
  const colors = Colors[colorScheme ?? 'light'];
  const isDark = colorScheme === 'dark';
  const canUseGlass = checkCanUseGlass();

  if (canUseGlass) {
    return (
      <GlassView
        style={[
          styles.glassCard,
          { borderRadius },
          style,
        ]}
        glassEffectStyle={glassStyle}
        tintColor={tintColor}
        isInteractive={isInteractive}
        pointerEvents={pointerEvents}
      >
        {children}
      </GlassView>
    );
  }

  // Fallback for non-iOS or unsupported iOS versions
  return (
    <View 
      style={[
        styles.fallbackCard,
        { 
          borderRadius,
          backgroundColor: isDark ? colors.card : 'rgba(255, 255, 255, 0.95)',
          borderColor: isDark ? colors.border : 'rgba(0, 0, 0, 0.06)',
          pointerEvents,
        },
        style,
      ]}
    >
      {children}
    </View>
  );
}

interface GlassCardContainerProps {
  children: React.ReactNode;
  style?: StyleProp<ViewStyle>;
  spacing?: number;
}

/**
 * Container for multiple GlassCards with combined glass effect
 */
export function GlassCardContainer({ 
  children, 
  style,
  spacing = 10,
}: GlassCardContainerProps) {
  const canUseGlass = checkCanUseGlass();

  if (canUseGlass) {
    return (
      <GlassContainer spacing={spacing} style={style}>
        {children}
      </GlassContainer>
    );
  }

  return (
    <View style={style}>
      {children}
    </View>
  );
}

/**
 * Simple glass button component
 */
interface GlassButtonProps {
  children: React.ReactNode;
  style?: StyleProp<ViewStyle>;
  tintColor?: string;
}

export function GlassButton({
  children,
  style,
  tintColor,
}: GlassButtonProps) {
  const colorScheme = useColorScheme();
  const isDark = colorScheme === 'dark';
  const canUseGlass = checkCanUseGlass();

  if (canUseGlass) {
    return (
      <GlassView
        style={[styles.glassButton, style]}
        glassEffectStyle="regular"
        tintColor={tintColor}
        isInteractive
      >
        {children}
      </GlassView>
    );
  }

  return (
    <View style={[
      styles.fallbackButton, 
      { backgroundColor: isDark ? 'rgba(255, 255, 255, 0.15)' : 'rgba(255, 255, 255, 0.9)' },
      style,
    ]}>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  glassCard: {
    padding: 16,
    overflow: 'hidden',
  },
  fallbackCard: {
    padding: 16,
    borderWidth: StyleSheet.hairlineWidth,
    boxShadow: '0px 1px 4px rgba(0,0,0,0.05)',
    elevation: 2,
  },
  glassButton: {
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: BorderRadius.md,
    alignItems: 'center',
    justifyContent: 'center',
  },
  fallbackButton: {
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: BorderRadius.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: 'rgba(0, 0, 0, 0.1)',
    alignItems: 'center',
    justifyContent: 'center',
    boxShadow: '0px 1px 2px rgba(0,0,0,0.04)',
    elevation: 1,
  },
});

// Export availability check function
export { isLiquidGlassAvailable, isGlassEffectAPIAvailable };
