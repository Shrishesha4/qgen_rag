// Fallback for using MaterialIcons on Android and web.

import MaterialIcons from '@expo/vector-icons/MaterialIcons';
import { SymbolWeight, SymbolViewProps } from 'expo-symbols';
import { ComponentProps, useEffect } from 'react';
import { OpaqueColorValue, type StyleProp, type TextStyle } from 'react-native';
import Animated, {
  useAnimatedStyle,
  useSharedValue,
  withSpring,
  withSequence,
  withTiming,
} from 'react-native-reanimated';

type IconMapping = Record<SymbolViewProps['name'], ComponentProps<typeof MaterialIcons>['name']>;
type IconSymbolName = keyof typeof MAPPING;
type SymbolAnimationEffect = 'bounce' | 'pulse' | 'variableColor' | undefined;

/**
 * Add your SF Symbols to Material Icons mappings here.
 * - see Material Icons in the [Icons Directory](https://icons.expo.fyi).
 * - see SF Symbols in the [SF Symbols](https://developer.apple.com/sf-symbols/) app.
 */
const MAPPING = {
  'house.fill': 'home',
  'paperplane.fill': 'send',
  'chevron.left.forwardslash.chevron.right': 'code',
  'chevron.right': 'chevron-right',
  'books.vertical.fill': 'library-books',
  'sparkles': 'auto-awesome',
  'checkmark.shield.fill': 'verified-user',
  'chart.bar.fill': 'bar-chart',
} as IconMapping;

/**
 * An icon component that uses native SF Symbols on iOS, and Material Icons on Android and web.
 * This ensures a consistent look across platforms, and optimal resource usage.
 * Icon `name`s are based on SF Symbols and require manual mapping to Material Icons.
 * Includes animation effects matching iOS 26 behavior.
 */
export function IconSymbol({
  name,
  size = 24,
  color,
  style,
  weight,
  animationEffect,
}: {
  name: IconSymbolName;
  size?: number;
  color: string | OpaqueColorValue;
  style?: StyleProp<TextStyle>;
  weight?: SymbolWeight;
  animationEffect?: SymbolAnimationEffect;
}) {
  const scale = useSharedValue(1);
  const opacity = useSharedValue(1);

  useEffect(() => {
    if (animationEffect === 'bounce') {
      scale.value = withSequence(
        withSpring(1.15, { damping: 10, stiffness: 400 }),
        withSpring(1, { damping: 12, stiffness: 400 })
      );
    } else if (animationEffect === 'pulse') {
      opacity.value = withSequence(
        withTiming(0.6, { duration: 150 }),
        withTiming(1, { duration: 150 })
      );
      scale.value = withSequence(
        withSpring(1.1, { damping: 10, stiffness: 400 }),
        withSpring(1, { damping: 12, stiffness: 400 })
      );
    }
  }, [animationEffect]);

  const animatedStyle = useAnimatedStyle(() => ({
    transform: [{ scale: scale.value }],
    opacity: opacity.value,
  }));

  return (
    <Animated.View style={animatedStyle}>
      <MaterialIcons color={color} size={size} name={MAPPING[name]} style={style} />
    </Animated.View>
  );
}
