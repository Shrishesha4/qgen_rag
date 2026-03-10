/**
 * Cross-platform alert utility
 * Uses native Alert on iOS/Android, web-compatible confirm/modal on web
 */

import { Alert, Platform } from 'react-native';

export interface AlertButton {
  text: string;
  onPress?: () => void;
  style?: 'default' | 'cancel' | 'destructive';
}

/**
 * Show a confirmation dialog that works on all platforms
 * On web: Uses window.confirm()
 * On native: Uses React Native Alert
 */
export const showConfirmDialog = (
  title: string,
  message: string,
  buttons: AlertButton[]
): void => {
  if (Platform.OS === 'web') {
    // Web: Use window.confirm() for simple two-button dialogs
    const destructiveBtn = buttons.find(b => b.style === 'destructive');
    const cancelBtn = buttons.find(b => b.style === 'cancel');
    
    const confirmed = window.confirm(`${title}\n\n${message}`);
    
    if (confirmed && destructiveBtn?.onPress) {
      destructiveBtn.onPress();
    } else if (!confirmed && cancelBtn?.onPress) {
      cancelBtn.onPress();
    }
  } else {
    // Native: Use React Native Alert
    Alert.alert(title, message, buttons);
  }
};

/**
 * Show a simple alert that works on all platforms
 * On web: Uses window.alert()
 * On native: Uses React Native Alert
 */
export const showAlert = (title: string, message?: string): void => {
  if (Platform.OS === 'web') {
    window.alert(message ? `${title}\n\n${message}` : title);
  } else {
    Alert.alert(title, message);
  }
};
