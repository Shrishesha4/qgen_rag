import { BottomTabBarButtonProps } from '@react-navigation/bottom-tabs';
import { PlatformPressable } from '@react-navigation/elements';
import * as Haptics from 'expo-haptics';
import { Platform, StyleSheet } from 'react-native';
import Animated, { 
  useAnimatedStyle, 
  useSharedValue, 
  withSpring,
  withTiming,
} from 'react-native-reanimated';

/**
 * iOS 26 native-style haptic tab button with:
 * - Refined haptic feedback matching iOS 26 system behavior
 * - Subtle scale animation on press
 * - Spring physics for natural feel
 */
export function HapticTab(props: BottomTabBarButtonProps) {
  const scale = useSharedValue(1);
  const opacity = useSharedValue(1);

  const animatedStyle = useAnimatedStyle(() => ({
    transform: [{ scale: scale.value }],
    opacity: opacity.value,
  }));

  return (
    <Animated.View style={[styles.container, animatedStyle]}>
      <PlatformPressable
        {...props}
        style={[props.style, styles.pressable]}
        onPressIn={(ev) => {
          if (Platform.OS === 'ios') {
            // iOS 26 uses refined haptic feedback
            Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Soft);
            // Subtle scale down animation
            scale.value = withSpring(0.92, {
              damping: 15,
              stiffness: 400,
            });
            opacity.value = withTiming(0.7, { duration: 100 });
          }
          props.onPressIn?.(ev);
        }}
        onPressOut={(ev) => {
          if (Platform.OS === 'ios') {
            // Spring back to original scale
            scale.value = withSpring(1, {
              damping: 15,
              stiffness: 400,
            });
            opacity.value = withTiming(1, { duration: 150 });
          }
          props.onPressOut?.(ev);
        }}
      />
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  pressable: {
    flex: 1,
    width: '100%',
    justifyContent: 'center',
    alignItems: 'center',
  },
});
