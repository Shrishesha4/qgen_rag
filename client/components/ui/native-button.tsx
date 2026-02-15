import React, { useState } from 'react';
import {
  Pressable,
  Text,
  StyleSheet,
  ViewStyle,
  TextStyle,
  StyleProp,
  Platform,
  ActivityIndicator,
  View,
} from 'react-native';
import { 
  GlassView, 
  isLiquidGlassAvailable, 
  isGlassEffectAPIAvailable 
} from 'expo-glass-effect';
import { LinearGradient } from 'expo-linear-gradient';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { BorderRadius, FontSizes, Spacing } from '@/constants/theme';

// Check if native glass effect is available (iOS 26+)
const canUseGlass = Platform.OS === 'ios' && 
  isLiquidGlassAvailable?.() && 
  isGlassEffectAPIAvailable?.();

interface NativeButtonProps {
  title: string;
  onPress?: () => void;
  disabled?: boolean;
  loading?: boolean;
  variant?: 'primary' | 'secondary' | 'glass' | 'destructive' | 'outline';
  size?: 'small' | 'medium' | 'large';
  icon?: string;
  iconPosition?: 'left' | 'right';
  gradient?: [string, string];
  style?: StyleProp<ViewStyle>;
  textStyle?: StyleProp<TextStyle>;
  fullWidth?: boolean;
}

/**
 * iOS 26 Native Button Component
 * Supports glass effect on iOS 26+, gradient backgrounds, and multiple variants
 */
export function NativeButton({
  title,
  onPress,
  disabled = false,
  loading = false,
  variant = 'primary',
  size = 'medium',
  icon,
  iconPosition = 'left',
  gradient,
  style,
  textStyle,
  fullWidth = false,
}: NativeButtonProps) {
  const [isPressed, setIsPressed] = useState(false);

  const getSizeStyles = () => {
    switch (size) {
      case 'small':
        return { paddingVertical: 8, paddingHorizontal: 14 };
      case 'large':
        return { paddingVertical: 16, paddingHorizontal: 24 };
      default:
        return { paddingVertical: 12, paddingHorizontal: 20 };
    }
  };

  const getFontSize = () => {
    switch (size) {
      case 'small':
        return FontSizes.sm;
      case 'large':
        return FontSizes.lg;
      default:
        return FontSizes.md;
    }
  };

  const getIconSize = () => {
    switch (size) {
      case 'small':
        return 16;
      case 'large':
        return 24;
      default:
        return 20;
    }
  };

  const getBackgroundColor = () => {
    if (disabled) return '#C7C7CC';
    
    switch (variant) {
      case 'primary':
        return isPressed ? '#0061CA' : '#007AFF';
      case 'secondary':
        return isPressed ? 'rgba(120, 120, 128, 0.16)' : 'rgba(120, 120, 128, 0.08)';
      case 'destructive':
        return isPressed ? '#D70015' : '#FF3B30';
      case 'outline':
        return isPressed ? 'rgba(0, 122, 255, 0.1)' : 'transparent';
      case 'glass':
        return 'transparent'; // Handled by GlassView
      default:
        return '#007AFF';
    }
  };

  const getTextColor = () => {
    if (disabled) return '#8E8E93';
    
    switch (variant) {
      case 'primary':
      case 'destructive':
        return '#FFFFFF';
      case 'secondary':
        return '#007AFF';
      case 'outline':
        return '#007AFF';
      case 'glass':
        return '#FFFFFF';
      default:
        return '#FFFFFF';
    }
  };

  const getBorderStyle = () => {
    if (variant === 'outline') {
      return {
        borderWidth: 1.5,
        borderColor: disabled ? '#C7C7CC' : '#007AFF',
      };
    }
    return {};
  };

  const content = (
    <View style={styles.contentRow}>
      {loading ? (
        <ActivityIndicator size="small" color={getTextColor()} />
      ) : (
        <>
          {icon && iconPosition === 'left' && (
            <IconSymbol 
              name={icon as any} 
              size={getIconSize()} 
              color={getTextColor()} 
              style={styles.iconLeft}
            />
          )}
          <Text style={[
            styles.text,
            { fontSize: getFontSize(), color: getTextColor() },
            textStyle,
          ]}>
            {title}
          </Text>
          {icon && iconPosition === 'right' && (
            <IconSymbol 
              name={icon as any} 
              size={getIconSize()} 
              color={getTextColor()} 
              style={styles.iconRight}
            />
          )}
        </>
      )}
    </View>
  );

  // Render gradient button
  if (gradient && !disabled) {
    return (
      <Pressable
        onPressIn={() => setIsPressed(true)}
        onPressOut={() => setIsPressed(false)}
        onPress={onPress}
        disabled={disabled || loading}
        style={[
          fullWidth && styles.fullWidth,
          { opacity: isPressed ? 0.9 : 1 },
        ]}
      >
        <LinearGradient
          colors={gradient}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 0 }}
          style={[
            styles.button,
            getSizeStyles(),
            fullWidth && styles.fullWidth,
            style,
          ]}
        >
          {content}
        </LinearGradient>
      </Pressable>
    );
  }

  // Render glass button for iOS 26+
  if (variant === 'glass' && canUseGlass) {
    return (
      <Pressable
        onPressIn={() => setIsPressed(true)}
        onPressOut={() => setIsPressed(false)}
        onPress={onPress}
        disabled={disabled || loading}
        style={[
          fullWidth && styles.fullWidth,
          { opacity: isPressed ? 0.8 : 1 },
        ]}
      >
        <GlassView
          style={[
            styles.button,
            getSizeStyles(),
            fullWidth && styles.fullWidth,
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

  // Standard button
  return (
    <Pressable
      onPressIn={() => setIsPressed(true)}
      onPressOut={() => setIsPressed(false)}
      onPress={onPress}
      disabled={disabled || loading}
      style={[
        styles.button,
        getSizeStyles(),
        getBorderStyle(),
        { backgroundColor: getBackgroundColor() },
        fullWidth && styles.fullWidth,
        style,
      ]}
    >
      {content}
    </Pressable>
  );
}

/**
 * Convenience styled button variants
 */
export function PrimaryButton(props: Omit<NativeButtonProps, 'variant'>) {
  return <NativeButton {...props} variant="primary" />;
}

export function SecondaryButton(props: Omit<NativeButtonProps, 'variant'>) {
  return <NativeButton {...props} variant="secondary" />;
}

export function DestructiveButton(props: Omit<NativeButtonProps, 'variant'>) {
  return <NativeButton {...props} variant="destructive" />;
}

export function GlassButton(props: Omit<NativeButtonProps, 'variant'>) {
  return <NativeButton {...props} variant="glass" />;
}

export function OutlineButton(props: Omit<NativeButtonProps, 'variant'>) {
  return <NativeButton {...props} variant="outline" />;
}

const styles = StyleSheet.create({
  button: {
    borderRadius: BorderRadius.md,
    alignItems: 'center',
    justifyContent: 'center',
    flexDirection: 'row',
  },
  contentRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
  },
  text: {
    fontWeight: '600',
    textAlign: 'center',
  },
  iconLeft: {
    marginRight: Spacing.sm,
  },
  iconRight: {
    marginLeft: Spacing.sm,
  },
  fullWidth: {
    width: '100%',
  },
});

export default NativeButton;
