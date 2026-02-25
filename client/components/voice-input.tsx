import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Platform,
} from 'react-native';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { Spacing, BorderRadius, FontSizes } from '@/constants/theme';

// Conditionally import expo-speech-recognition if available
let ExpoSpeechRecognitionModule: any = null;
let useSpeechRecognitionEvent: any = null;
let isSpeechRecognitionAvailable = false;

try {
  const speechRecognition = require('expo-speech-recognition');
  ExpoSpeechRecognitionModule = speechRecognition.ExpoSpeechRecognitionModule;
  useSpeechRecognitionEvent = speechRecognition.useSpeechRecognitionEvent;
  isSpeechRecognitionAvailable = true;
} catch (e) {
  console.log('expo-speech-recognition not available - voice input disabled');
}

// Export for checking availability
export { isSpeechRecognitionAvailable };

interface VoiceInputProps {
  value: string;
  onChangeText: (text: string) => void;
  placeholder?: string;
  colors: {
    text: string;
    textSecondary: string;
    primary: string;
    background: string;
    border: string;
    error: string;
  };
  disabled?: boolean;
}

export function VoiceInput({
  value,
  onChangeText,
  placeholder = 'Tap mic to speak...',
  colors,
  disabled = false,
}: VoiceInputProps) {
  const [isListening, setIsListening] = useState(false);
  const [hasPermission, setHasPermission] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [interimText, setInterimText] = useState('');

  // Check if speech recognition is available
  const isAvailable = ExpoSpeechRecognitionModule !== null;

  // Check permission on mount
  useEffect(() => {
    if (!isAvailable) return;
    
    const checkPermission = async () => {
      const result = await ExpoSpeechRecognitionModule.getPermissionsAsync();
      setHasPermission(result.granted);
    };
    checkPermission();
  }, [isAvailable]);

  // Handle speech recognition results
  if (isAvailable && useSpeechRecognitionEvent) {
    useSpeechRecognitionEvent('result', (event: any) => {
      if (event.isFinal) {
        // Final result - append to the value
        const finalText = event.results[0]?.transcript || '';
        if (finalText) {
          const newValue = value ? `${value} ${finalText}` : finalText;
          onChangeText(newValue.trim());
        }
        setInterimText('');
      } else {
        // Interim result - show preview
        const interim = event.results[0]?.transcript || '';
        setInterimText(interim);
      }
    });

    useSpeechRecognitionEvent('error', (event: any) => {
      console.error('Speech recognition error:', event.error, event.message);
      setError(event.message || 'Speech recognition error');
      setIsListening(false);
    });

    useSpeechRecognitionEvent('end', () => {
      setIsListening(false);
      setInterimText('');
    });
  }

  const requestPermission = async () => {
    if (!isAvailable) return false;
    const result = await ExpoSpeechRecognitionModule.requestPermissionsAsync();
    setHasPermission(result.granted);
    return result.granted;
  };

  const startListening = useCallback(async () => {
    if (!isAvailable) {
      setError('Voice input requires rebuilding the app. Please use text input.');
      return;
    }
    
    setError(null);
    
    // Check and request permission if needed
    if (!hasPermission) {
      const granted = await requestPermission();
      if (!granted) {
        setError('Microphone permission required');
        return;
      }
    }

    try {
      setIsListening(true);
      setInterimText('');
      
      // Start speech recognition
      ExpoSpeechRecognitionModule.start({
        lang: 'en-US',
        interimResults: true,
        maxAlternatives: 1,
        continuous: false,
        requiresOnDeviceRecognition: false,
        addsPunctuation: true,
      });
    } catch (err) {
      console.error('Failed to start speech recognition:', err);
      setError('Failed to start speech recognition');
      setIsListening(false);
    }
  }, [hasPermission, isAvailable]);

  const stopListening = useCallback(() => {
    if (!isAvailable) return;
    
    try {
      ExpoSpeechRecognitionModule.stop();
    } catch (err) {
      console.error('Failed to stop speech recognition:', err);
    }
    setIsListening(false);
    setInterimText('');
  }, [isAvailable]);

  const toggleListening = useCallback(() => {
    if (isListening) {
      stopListening();
    } else {
      startListening();
    }
  }, [isListening, startListening, stopListening]);

  // Display text - show interim while listening, otherwise show final value
  const displayText = isListening && interimText 
    ? (value ? `${value} ${interimText}...` : `${interimText}...`)
    : value;

  return (
    <View style={styles.container}>
      <View style={styles.row}>
        <TouchableOpacity
          style={[
            styles.micButton,
            {
              backgroundColor: isListening ? colors.error : colors.primary,
              opacity: disabled ? 0.5 : 1,
            },
          ]}
          onPress={toggleListening}
          disabled={disabled}
          activeOpacity={0.7}
        >
          {isListening ? (
            <View style={styles.recordingIndicator}>
              <ActivityIndicator size="small" color="#fff" />
            </View>
          ) : (
            <IconSymbol name="mic.fill" size={20} color="#fff" />
          )}
        </TouchableOpacity>
        
        <View 
          style={[
            styles.textPreview, 
            { 
              backgroundColor: colors.background,
              borderColor: isListening ? colors.primary : colors.border,
            }
          ]}
        >
          <Text
            style={[
              styles.previewText,
              { 
                color: displayText ? colors.text : colors.textSecondary,
                fontStyle: isListening && interimText ? 'italic' : 'normal',
              },
            ]}
            numberOfLines={3}
          >
            {displayText || placeholder}
          </Text>
        </View>
      </View>

      {error && (
        <Text style={[styles.errorText, { color: colors.error }]}>
          {error}
        </Text>
      )}

      {!isAvailable && (
        <Text style={[styles.infoText, { color: colors.textSecondary }]}>
          Voice input requires a development build. Running in Expo Go? Use text input above.
        </Text>
      )}

      {isListening && (
        <View style={styles.listeningIndicator}>
          <View style={[styles.pulsingDot, { backgroundColor: colors.error }]} />
          <Text style={[styles.listeningText, { color: colors.textSecondary }]}>
            Listening... Tap mic to stop
          </Text>
        </View>
      )}

      {hasPermission === false && (
        <TouchableOpacity onPress={requestPermission}>
          <Text style={[styles.permissionText, { color: colors.primary }]}>
            Tap to grant microphone permission
          </Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    width: '100%',
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  micButton: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: 'center',
    justifyContent: 'center',
    // iOS shadow
    ...Platform.select({
      ios: {
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.2,
        shadowRadius: 4,
      },
      android: {
        elevation: 4,
      },
    }),
  },
  recordingIndicator: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  textPreview: {
    flex: 1,
    borderWidth: 1,
    borderRadius: BorderRadius.md,
    padding: Spacing.sm,
    minHeight: 44,
    justifyContent: 'center',
  },
  previewText: {
    fontSize: FontSizes.sm,
    lineHeight: 18,
  },
  errorText: {
    fontSize: FontSizes.xs,
    marginTop: Spacing.xs,
  },
  infoText: {
    fontSize: FontSizes.xs,
    marginTop: Spacing.xs,
    fontStyle: 'italic',
  },
  listeningIndicator: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: Spacing.sm,
    gap: Spacing.xs,
  },
  pulsingDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  listeningText: {
    fontSize: FontSizes.xs,
  },
  permissionText: {
    fontSize: FontSizes.sm,
    marginTop: Spacing.sm,
    textDecorationLine: 'underline',
  },
});

export default VoiceInput;
