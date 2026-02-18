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

type IconMapping = Record<string, string>;
type SymbolAnimationEffect = 'bounce' | 'pulse' | 'variableColor' | undefined;

/**
 * Mapping from SF Symbol names (used across the app) to Material Icons names for Android/web.
 * - Extend this map when new SF Symbols are used.
 * - If a mapping is missing we fall back to `help-outline` and log a warning so missing icons are easy to find.
 */
const MAPPING: IconMapping = {
  // existing mappings
  'house.fill': 'home',
  'paperplane.fill': 'send',
  'chevron.left.forwardslash.chevron.right': 'code',
  'chevron.right': 'chevron-right',
  'chevron.left': 'chevron-left',
  'chevron.down': 'expand-more',
  'books.vertical.fill': 'library-books',

  // common app icons
  'sparkles': 'auto-awesome',
  'magnifyingglass': 'search',
  'questionmark.circle': 'help-outline',
  'questionmark.circle.fill': 'help-outline',
  'xmark': 'close',
  'xmark.circle.fill': 'remove-circle',
  'plus': 'add',
  'plus.circle.fill': 'add-circle',
  'minus': 'remove',
  'person.circle.fill': 'account-circle',
  'person.fill': 'person',

  // document / book related
  'book': 'book',
  'book.fill': 'book',
  'book.closed': 'book',
  'doc.fill': 'description',
  'doc.text': 'description',
  'doc.text.fill': 'description',
  'doc.text.magnifyingglass': 'search',
  'doc.badge.plus': 'post-add',
  'doc.badge.gearshape.fill': 'settings',
  'text.alignleft': 'format-align-left',

  // state / badges
  'checkmark.circle.fill': 'check-circle',
  'checkmark.circle': 'check-circle',
  'checkmark.shield.fill': 'verified-user',
  'checkmark': 'check',
  'star.fill': 'star',

  // layout / lists
  'list.bullet': 'format-list-bulleted',
  'list.number': 'format-list-numbered',
  'archivebox': 'archive',

  // misc
  'chart.bar.fill': 'bar-chart',
  'chart.bar': 'bar-chart',
  'clock.fill': 'schedule',
  'calendar': 'calendar-today',
  'slider.horizontal.3': 'tune',
  'link': 'link',
  'pencil': 'edit',
  'arrow.uturn.backward': 'undo',
  'target': 'adjust',
  'square.and.arrow.up': 'share',
  'square.grid.2x2.fill': 'grid-view',
  'chevron.up': 'expand-less',
  'brain': 'psychology',
  'doc.richtext': 'description',
  'rectangle.portrait.and.arrow.right.fill': 'logout',
  'exclamationmark.triangle': 'warning',
  'exclamationmark.triangle.fill': 'warning',

  // profile / settings
  'lock.fill': 'lock',
  'bell.fill': 'notifications',
  'info.circle.fill': 'info',
};

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
  name: SymbolViewProps['name'];
  size?: number;
  color: string | OpaqueColorValue;
  style?: StyleProp<TextStyle>;
  weight?: SymbolWeight;
  animationEffect?: SymbolAnimationEffect;
}) {
  const scale = useSharedValue(1);
  const opacity = useSharedValue(1);

  const mappedName = MAPPING[name] ?? 'help-outline';
  if (!MAPPING[name]) {
    if (typeof __DEV__ !== 'undefined' && __DEV__) {
      // eslint-disable-next-line no-console
      console.warn(`[IconSymbol] missing mapping for "${name}" — falling back to "${mappedName}"`);
    }
  }

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
      <MaterialIcons color={color} size={size} name={mappedName as any} style={style} />
    </Animated.View>
  );
}
