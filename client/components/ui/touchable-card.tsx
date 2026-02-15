import React, { useState } from 'react';
import {
  Pressable,
  View,
  Text,
  StyleSheet,
  ViewStyle,
  StyleProp,
  Platform,
} from 'react-native';
import { 
  GlassView, 
  isLiquidGlassAvailable, 
  isGlassEffectAPIAvailable 
} from 'expo-glass-effect';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { BorderRadius, FontSizes, Spacing } from '@/constants/theme';

// Check if native glass effect is available (iOS 26+)
const canUseGlass = Platform.OS === 'ios' && 
  isLiquidGlassAvailable?.() && 
  isGlassEffectAPIAvailable?.();

interface TouchableCardProps {
  children: React.ReactNode;
  onPress?: () => void;
  style?: StyleProp<ViewStyle>;
  disabled?: boolean;
  showArrow?: boolean;
  icon?: string;
  iconColor?: string;
  additionalText?: string;
  grouped?: boolean;
  groupFirst?: boolean;
  groupLast?: boolean;
  variant?: 'default' | 'primary' | 'danger';
}

/**
 * iOS 26 Native Touchable Card Component
 * Inspired by bw-mobile-app TouchableBox
 * Uses native GlassView on iOS 26+, fallback styling on other platforms
 */
export function TouchableCard({
  children,
  onPress,
  style,
  disabled = false,
  showArrow = false,
  icon,
  iconColor,
  additionalText,
  grouped = false,
  groupFirst = false,
  groupLast = false,
  variant = 'default',
}: TouchableCardProps) {
  const [isPressed, setIsPressed] = useState(false);

  // Grouped card border radius adjustments
  const groupedBorderRadius = {
    borderTopLeftRadius: grouped && !groupFirst ? 0 : BorderRadius.md,
    borderTopRightRadius: grouped && !groupFirst ? 0 : BorderRadius.md,
    borderBottomLeftRadius: grouped && !groupLast ? 0 : BorderRadius.md,
    borderBottomRightRadius: grouped && !groupLast ? 0 : BorderRadius.md,
  };

  const getBackgroundColor = () => {
    if (variant === 'primary') {
      return isPressed ? '#0061CA' : '#007AFF';
    }
    if (variant === 'danger') {
      return isPressed ? 'rgba(255, 59, 48, 0.8)' : 'rgba(255, 59, 48, 0.6)';
    }
    return isPressed 
      ? Platform.select({ ios: 'rgba(120, 120, 128, 0.12)', default: 'rgba(0, 0, 0, 0.05)' })
      : Platform.select({ ios: 'rgba(255, 255, 255, 0.9)', default: '#FFFFFF' });
  };

  const getTextColor = () => {
    if (variant === 'primary' || variant === 'danger') {
      return '#FFFFFF';
    }
    return '#000000';
  };

  const content = (
    <>
      {icon && (
        <View style={styles.iconContainer}>
          <IconSymbol 
            name={icon as any} 
            size={22} 
            color={iconColor || (variant !== 'default' ? '#FFFFFF' : '#8E8E93')} 
          />
        </View>
      )}
      <View style={styles.contentContainer}>
        {typeof children === 'string' ? (
          <Text style={[styles.text, { color: getTextColor() }]} numberOfLines={1}>
            {children}
          </Text>
        ) : (
          children
        )}
      </View>
      {additionalText && (
        <Text style={[styles.additionalText, { color: variant !== 'default' ? '#FFFFFF' : '#8E8E93' }]}>
          {additionalText}
        </Text>
      )}
      {showArrow && (
        <IconSymbol 
          name="chevron.right" 
          size={16} 
          color={variant !== 'default' ? '#FFFFFF' : '#C7C7CC'} 
        />
      )}
      {grouped && !groupLast && (
        <View style={styles.separator} />
      )}
    </>
  );

  // Use native GlassView for iOS 26+
  if (canUseGlass && variant === 'default') {
    return (
      <Pressable
        onPressIn={() => setIsPressed(true)}
        onPressOut={() => setIsPressed(false)}
        onPress={onPress}
        disabled={disabled}
        style={({ pressed }) => [{ opacity: pressed ? 0.9 : 1 }]}
      >
        <GlassView
          style={[
            styles.card,
            groupedBorderRadius,
            { opacity: disabled ? 0.5 : 1 },
            style,
          ]}
          glassEffectStyle="regular"
          isInteractive
        >
          {content}
        </GlassView>
      </Pressable>
    );
  }

  // Fallback for non-iOS or colored variants
  return (
    <Pressable
      onPressIn={() => setIsPressed(true)}
      onPressOut={() => setIsPressed(false)}
      onPress={onPress}
      disabled={disabled}
      style={[
        styles.card,
        styles.fallbackCard,
        groupedBorderRadius,
        { backgroundColor: getBackgroundColor(), opacity: disabled ? 0.5 : 1 },
        style,
      ]}
    >
      {content}
    </Pressable>
  );
}

/**
 * Grouped container for TouchableCards
 */
interface CardGroupProps {
  children: React.ReactNode;
  style?: StyleProp<ViewStyle>;
}

export function CardGroup({ children, style }: CardGroupProps) {
  const childArray = React.Children.toArray(children);
  
  return (
    <View style={[styles.cardGroup, style]}>
      {childArray.map((child, index) => {
        if (React.isValidElement(child)) {
          return React.cloneElement(child as React.ReactElement<TouchableCardProps>, {
            grouped: true,
            groupFirst: index === 0,
            groupLast: index === childArray.length - 1,
          });
        }
        return child;
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    minHeight: 50,
    paddingVertical: 12,
    paddingHorizontal: 16,
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: BorderRadius.md,
  },
  fallbackCard: {
    backgroundColor: '#FFFFFF',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04,
    shadowRadius: 3,
    elevation: 1,
  },
  iconContainer: {
    marginRight: 12,
  },
  contentContainer: {
    flex: 1,
    flexShrink: 1,
  },
  text: {
    fontSize: FontSizes.md,
    fontWeight: '400',
  },
  additionalText: {
    fontSize: FontSizes.md,
    marginLeft: 'auto',
    marginRight: Spacing.xs,
  },
  separator: {
    position: 'absolute',
    bottom: 0,
    left: 16,
    right: 0,
    height: StyleSheet.hairlineWidth,
    backgroundColor: 'rgba(60, 60, 67, 0.12)',
  },
  cardGroup: {
    borderRadius: BorderRadius.md,
    overflow: 'hidden',
  },
});

export default TouchableCard;
