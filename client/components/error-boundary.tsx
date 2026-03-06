import React, { Component, ErrorInfo, ReactNode } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView } from 'react-native';
import { Colors, Spacing, BorderRadius, FontSizes } from '@/constants/theme';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

/**
 * ErrorBoundary component to catch JavaScript errors anywhere in the child
 * component tree and display a fallback UI instead of crashing the whole app.
 */
export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    };
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    // Update state so the next render will show the fallback UI
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    // Log error to console in development
    console.error('ErrorBoundary caught an error:', error);
    console.error('Error info:', errorInfo);
    
    this.setState({ errorInfo });
    
    // You could also log to an error reporting service here
    // e.g., Sentry.captureException(error, { extra: errorInfo });
  }

  handleReset = (): void => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      // Custom fallback UI if provided
      if (this.props.fallback) {
        return this.props.fallback;
      }

      // Default error UI
      return (
        <View style={styles.container}>
          <View style={styles.content}>
            <Text style={styles.emoji}>😵</Text>
            <Text style={styles.title}>Something went wrong</Text>
            <Text style={styles.message}>
              The app encountered an unexpected error. Please try again.
            </Text>
            
            {__DEV__ && this.state.error && (
              <ScrollView style={styles.errorDetails} showsVerticalScrollIndicator={false}>
                <Text style={styles.errorTitle}>Error Details:</Text>
                <Text style={styles.errorText}>{this.state.error.toString()}</Text>
                {this.state.errorInfo?.componentStack && (
                  <>
                    <Text style={styles.errorTitle}>Component Stack:</Text>
                    <Text style={styles.errorText}>
                      {this.state.errorInfo.componentStack.slice(0, 500)}...
                    </Text>
                  </>
                )}
              </ScrollView>
            )}

            <TouchableOpacity style={styles.button} onPress={this.handleReset}>
              <Text style={styles.buttonText}>Try Again</Text>
            </TouchableOpacity>
          </View>
        </View>
      );
    }

    return this.props.children;
  }
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.light.background,
    justifyContent: 'center',
    alignItems: 'center',
    padding: Spacing.lg,
  },
  content: {
    alignItems: 'center',
    maxWidth: 400,
  },
  emoji: {
    fontSize: 64,
    marginBottom: Spacing.md,
  },
  title: {
    fontSize: FontSizes.xxl,
    fontWeight: '700',
    color: Colors.light.text,
    marginBottom: Spacing.sm,
    textAlign: 'center',
  },
  message: {
    fontSize: FontSizes.md,
    color: Colors.light.textSecondary,
    textAlign: 'center',
    marginBottom: Spacing.lg,
    lineHeight: 22,
  },
  errorDetails: {
    maxHeight: 200,
    backgroundColor: '#f5f5f5',
    borderRadius: BorderRadius.md,
    padding: Spacing.md,
    marginBottom: Spacing.lg,
    width: '100%',
  },
  errorTitle: {
    fontSize: FontSizes.sm,
    fontWeight: '600',
    color: Colors.light.error,
    marginTop: Spacing.sm,
    marginBottom: Spacing.xs,
  },
  errorText: {
    fontSize: FontSizes.xs,
    color: '#666',
    fontFamily: 'monospace',
  },
  button: {
    backgroundColor: Colors.light.primary,
    paddingVertical: Spacing.md,
    paddingHorizontal: Spacing.xl,
    borderRadius: BorderRadius.md,
  },
  buttonText: {
    color: '#fff',
    fontSize: FontSizes.md,
    fontWeight: '600',
  },
});

export default ErrorBoundary;
