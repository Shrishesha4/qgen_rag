/**
 * iOS 26 Liquid Glass Design System
 * Inspired by Apple's new translucent, depth-aware interface
 */

import { Platform } from 'react-native';

const tintColorLight = '#007AFF';
const tintColorDark = '#0A84FF';

export const Colors = {
  light: {
    text: '#000000',
    textSecondary: '#3C3C43',
    textTertiary: '#8A8A8E',
    background: '#F2F2F7',
    backgroundSecondary: '#FFFFFF',
    card: '#FFFFFF',
    // iOS 26 Liquid Glass surfaces
    glass: 'rgba(255, 255, 255, 0.72)',
    glassSecondary: 'rgba(255, 255, 255, 0.6)',
    glassTertiary: 'rgba(255, 255, 255, 0.4)',
    glassStroke: 'rgba(255, 255, 255, 0.5)',
    tint: tintColorLight,
    icon: '#8E8E93',
    tabIconDefault: '#8E8E93',
    tabIconSelected: tintColorLight,
    border: 'rgba(60, 60, 67, 0.12)',
    // Accent colors - iOS 26 vibrant
    primary: '#007AFF',
    secondary: '#5856D6',
    success: '#34C759',
    warning: '#FF9500',
    error: '#FF3B30',
    info: '#5AC8FA',
    // iOS 26 Gradient colors
    gradientBlue: ['#007AFF', '#00C7FF'],
    gradientPurple: ['#AF52DE', '#5856D6'],
    gradientGreen: ['#30D158', '#34C759'],
    gradientOrange: ['#FF9F0A', '#FF6B00'],
    gradientPink: ['#FF2D92', '#FF375F'],
    // iOS 26 Liquid Glass specific
    liquidGlass: {
      background: 'rgba(255, 255, 255, 0.7)',
      blur: 40,
      borderColor: 'rgba(255, 255, 255, 0.4)',
      shadowColor: 'rgba(0, 0, 0, 0.08)',
    },
  },
  dark: {
    text: '#FFFFFF',
    textSecondary: '#EBEBF5',
    textTertiary: '#8E8E93',
    background: '#000000',
    backgroundSecondary: '#1C1C1E',
    card: '#1C1C1E',
    // iOS 26 Liquid Glass surfaces (dark)
    glass: 'rgba(44, 44, 46, 0.72)',
    glassSecondary: 'rgba(44, 44, 46, 0.6)',
    glassTertiary: 'rgba(44, 44, 46, 0.4)',
    glassStroke: 'rgba(255, 255, 255, 0.16)',
    tint: tintColorDark,
    icon: '#8E8E93',
    tabIconDefault: '#8E8E93',
    tabIconSelected: tintColorDark,
    border: 'rgba(84, 84, 88, 0.65)',
    // Accent colors - iOS 26 vibrant dark
    primary: '#0A84FF',
    secondary: '#5E5CE6',
    success: '#30D158',
    warning: '#FF9F0A',
    error: '#FF453A',
    info: '#64D2FF',
    // iOS 26 Gradient colors
    gradientBlue: ['#0A84FF', '#00D4FF'],
    gradientPurple: ['#BF5AF2', '#5E5CE6'],
    gradientGreen: ['#30D158', '#32D74B'],
    gradientOrange: ['#FF9F0A', '#FF6B00'],
    gradientPink: ['#FF375F', '#FF2D55'],
    // iOS 26 Liquid Glass specific
    liquidGlass: {
      background: 'rgba(44, 44, 46, 0.75)',
      blur: 50,
      borderColor: 'rgba(255, 255, 255, 0.1)',
      shadowColor: 'rgba(0, 0, 0, 0.3)',
    },
  },
};

export const Spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  xxl: 24,
  xxxl: 32,
  headerInset: 100, // Space for transparent header on iOS
};

// iOS 26 uses more rounded corners
export const BorderRadius = {
  sm: 10,
  md: 14,
  lg: 20,
  xl: 26,
  xxl: 32,
  full: 9999,
};

export const FontSizes = {
  xs: 11,
  sm: 13,
  md: 15,
  lg: 17,
  xl: 20,
  xxl: 24,
  xxxl: 28,
  title: 34,
  largeTitle: 40,
};

// Shadow styles (cross-platform: boxShadow for iOS/web on RN 0.76+, elevation for Android)
export const Shadows = {
  small: {
    boxShadow: '0px 2px 8px rgba(0,0,0,0.08)',
    elevation: 2,
  },
  medium: {
    boxShadow: '0px 4px 16px rgba(0,0,0,0.12)',
    elevation: 4,
  },
  large: {
    boxShadow: '0px 8px 24px rgba(0,0,0,0.16)',
    elevation: 8,
  },
  glow: (color: string) => ({
    boxShadow: `0px 4px 12px ${color}66`,
    elevation: 6,
  }),
};

export const Fonts = Platform.select({
  ios: {
    sans: 'system-ui',
    serif: 'ui-serif',
    rounded: 'ui-rounded',
    mono: 'ui-monospace',
  },
  default: {
    sans: 'normal',
    serif: 'serif',
    rounded: 'normal',
    mono: 'monospace',
  },
  web: {
    sans: "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
    serif: "Georgia, 'Times New Roman', serif",
    rounded: "'SF Pro Rounded', 'Hiragino Maru Gothic ProN', Meiryo, 'MS PGothic', sans-serif",
    mono: "SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace",
  },
});

// ── macOS Aqua design tokens (used by home & vetter screens) ─────────────────
export const AquaTokens = {
  // Blues
  deepBlue: '#1565C0',
  royalBlue: '#1976D2',
  aquaBlue: '#0288D1',
  skyBlue: '#29B6F6',
  iceBlue: '#81D4FA',
  // Status gel colors
  gelGreen: '#2E7D32',
  gelGreenLight: '#43A047',
  gelOrange: '#E65100',
  gelOrangeLight: '#FB8C00',
  gelRed: '#B71C1C',
  gelRedLight: '#E53935',
  gelPurple: '#4527A0',
  gelPurpleLight: '#7B1FA2',
  // Surfaces
  bgLight: '#EBF4FD',
  bgDark: '#0D1B2A',
  cardLight: '#FFFFFF',
  cardDark: '#132F4C',
  // Gloss / chrome
  shine: 'rgba(255,255,255,0.55)',
  metalBorderLight: '#A8C8E8',
  metalBorderDark: '#1E4A72',
} as const;
