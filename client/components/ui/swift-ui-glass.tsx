import React from 'react';
import { Platform, View, StyleProp, ViewStyle } from 'react-native';
import { isLiquidGlassAvailable, isGlassEffectAPIAvailable } from 'expo-glass-effect';

// SwiftUI components - only imported on iOS
let SwiftUI: any = null;
let SwiftUIModifiers: any = null;

if (Platform.OS === 'ios') {
  try {
    SwiftUI = require('@expo/ui/swift-ui');
    SwiftUIModifiers = require('@expo/ui/swift-ui/modifiers');
  } catch (e) {
    // SwiftUI not available
  }
}

interface SwiftUIGlassTextProps {
  children: string;
  size?: number;
  glassVariant?: 'regular' | 'clear';
  padding?: number;
}

/**
 * SwiftUI Text with native Liquid Glass effect
 * Only works on iOS 26+ with Xcode 26+
 */
export function SwiftUIGlassText({
  children,
  size = 17,
  glassVariant = 'regular',
  padding = 16,
}: SwiftUIGlassTextProps) {
  const canUseSwiftUI = Platform.OS === 'ios' && SwiftUI && SwiftUIModifiers;

  if (!canUseSwiftUI) {
    return null;
  }

  const { Host, Text } = SwiftUI;
  const { glassEffect, padding: paddingModifier } = SwiftUIModifiers;

  return (
    <Host matchContents>
      <Text
        size={size}
        modifiers={[
          paddingModifier({ all: padding }),
          glassEffect({
            glass: {
              variant: glassVariant,
            },
          }),
        ]}
      >
        {children}
      </Text>
    </Host>
  );
}

interface SwiftUICardProps {
  children: React.ReactNode;
  style?: StyleProp<ViewStyle>;
  glassVariant?: 'regular' | 'clear';
  padding?: number;
}

/**
 * SwiftUI VStack with Liquid Glass effect
 */
export function SwiftUIGlassCard({
  children,
  style,
  glassVariant = 'regular',
  padding = 16,
}: SwiftUICardProps) {
  const canUseSwiftUI = Platform.OS === 'ios' && SwiftUI && SwiftUIModifiers;

  if (!canUseSwiftUI) {
    return <View style={style}>{children}</View>;
  }

  const { Host, VStack } = SwiftUI;
  const { glassEffect, padding: paddingModifier } = SwiftUIModifiers;

  return (
    <Host style={style}>
      <VStack
        spacing={8}
        modifiers={[
          paddingModifier({ all: padding }),
          glassEffect({
            glass: {
              variant: glassVariant,
            },
          }),
        ]}
      >
        {children}
      </VStack>
    </Host>
  );
}

interface SwiftUIFormProps {
  children: React.ReactNode;
  style?: StyleProp<ViewStyle>;
}

/**
 * SwiftUI Form component - iOS Settings-like UI
 */
export function SwiftUIForm({ children, style }: SwiftUIFormProps) {
  const canUseSwiftUI = Platform.OS === 'ios' && SwiftUI;

  if (!canUseSwiftUI) {
    return <View style={style}>{children}</View>;
  }

  const { Host, Form } = SwiftUI;

  return (
    <Host style={[{ flex: 1 }, style]}>
      <Form>{children}</Form>
    </Host>
  );
}

interface SwiftUISectionProps {
  title?: string;
  children: React.ReactNode;
}

/**
 * SwiftUI Section for Form
 */
export function SwiftUISection({ title, children }: SwiftUISectionProps) {
  const canUseSwiftUI = Platform.OS === 'ios' && SwiftUI;

  if (!canUseSwiftUI) {
    return <View>{children}</View>;
  }

  const { Section } = SwiftUI;

  return <Section title={title}>{children}</Section>;
}

// Check if SwiftUI components are available
export function isSwiftUIAvailable(): boolean {
  return Platform.OS === 'ios' && SwiftUI !== null;
}

// Check if Liquid Glass modifiers are available
export function isGlassModifierAvailable(): boolean {
  return Platform.OS === 'ios' && SwiftUIModifiers !== null;
}

// Export SwiftUI primitives for direct use
export function getSwiftUIPrimitives() {
  if (!isSwiftUIAvailable()) return null;
  return SwiftUI;
}

export function getSwiftUIModifiers() {
  if (!isGlassModifierAvailable()) return null;
  return SwiftUIModifiers;
}
