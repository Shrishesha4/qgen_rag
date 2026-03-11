/**
 * Responsive layout hook
 * Returns breakpoint info and desktop-centering styles for screens.
 */

import { Platform, useWindowDimensions } from 'react-native';

const DESKTOP_BREAKPOINT = 768;
const CONTENT_MAX_WIDTH = 1100;
const WIDE_MAX_WIDTH = 1300;
const MODAL_MAX_WIDTH = 600;

export function useResponsive() {
  const { width } = useWindowDimensions();
  const isDesktop = Platform.OS === 'web' && width >= DESKTOP_BREAKPOINT;

  return {
    isDesktop,
    windowWidth: width,
    /** Apply to a ScrollView's contentContainerStyle for max-width centering */
    desktopContentStyle: isDesktop
      ? ({ maxWidth: CONTENT_MAX_WIDTH, alignSelf: 'center' as const, width: '100%' as const })
      : {},
    /** Wider container for list-heavy pages */
    wideContentStyle: isDesktop
      ? ({ maxWidth: WIDE_MAX_WIDTH, alignSelf: 'center' as const, width: '100%' as const })
      : {},
    /** Constrain modal inner content on desktop */
    modalContentStyle: isDesktop
      ? ({ maxWidth: MODAL_MAX_WIDTH, alignSelf: 'center' as const, width: '100%' as const })
      : {},
  };
}
