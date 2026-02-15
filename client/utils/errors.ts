/**
 * Centralized Error Handling Utilities
 * 
 * This module provides consistent error extraction and formatting
 * for API errors throughout the application.
 */

import { AxiosError } from 'axios';

export interface ApiErrorDetail {
  message: string;
  code?: string;
  field?: string;
  statusCode?: number;
  isNetworkError: boolean;
  isTimeout: boolean;
  isServerError: boolean;
  isAuthError: boolean;
}

/**
 * Extract a user-friendly error message from various error types
 */
export function extractErrorMessage(error: unknown): string {
  // Handle null/undefined
  if (!error) {
    return 'An unexpected error occurred';
  }

  // Handle Axios errors
  if (isAxiosError(error)) {
    return extractAxiosErrorMessage(error);
  }

  // Handle Error objects
  if (error instanceof Error) {
    // Check for specific error messages
    if (error.message === 'Network Error') {
      return 'Unable to connect to the server. Please check your internet connection.';
    }
    return error.message;
  }

  // Handle string errors
  if (typeof error === 'string') {
    return error;
  }

  // Handle objects with message property
  if (typeof error === 'object' && 'message' in error) {
    return String((error as { message: unknown }).message);
  }

  return 'An unexpected error occurred';
}

/**
 * Extract detailed error information from an Axios error
 */
export function extractErrorDetails(error: unknown): ApiErrorDetail {
  const details: ApiErrorDetail = {
    message: 'An unexpected error occurred',
    isNetworkError: false,
    isTimeout: false,
    isServerError: false,
    isAuthError: false,
  };

  if (!isAxiosError(error)) {
    details.message = extractErrorMessage(error);
    return details;
  }

  const axiosError = error as AxiosError;

  // Network error (no response)
  if (!axiosError.response) {
    if (axiosError.code === 'ECONNABORTED') {
      details.message = 'Request timed out. Please try again.';
      details.isTimeout = true;
    } else if (axiosError.message === 'Network Error') {
      details.message = 'Unable to connect to the server. Please check your internet connection.';
      details.isNetworkError = true;
    } else {
      details.message = axiosError.message || 'Connection failed';
      details.isNetworkError = true;
    }
    return details;
  }

  const { status, data } = axiosError.response;
  details.statusCode = status;

  // Authentication errors
  if (status === 401 || status === 403) {
    details.isAuthError = true;
    details.message = 'Authentication failed. Please log in again.';
    return details;
  }

  // Server errors (5xx)
  if (status >= 500) {
    details.isServerError = true;
    details.message = 'Server error. Please try again later.';
    return details;
  }

  // Extract message from response data
  details.message = extractMessageFromResponseData(data);

  return details;
}

/**
 * Extract error message from Axios error
 */
function extractAxiosErrorMessage(error: AxiosError): string {
  // No response (network error, timeout, etc.)
  if (!error.response) {
    if (error.code === 'ECONNABORTED') {
      return 'Request timed out. Please try again.';
    }
    if (error.message === 'Network Error') {
      return 'Unable to connect to the server. Please check your internet connection.';
    }
    return error.message || 'Connection failed';
  }

  const { status, data } = error.response;

  // Authentication errors
  if (status === 401) {
    return 'Your session has expired. Please log in again.';
  }
  if (status === 403) {
    return 'You do not have permission to perform this action.';
  }

  // Not found
  if (status === 404) {
    return extractMessageFromResponseData(data) || 'The requested resource was not found.';
  }

  // Validation error
  if (status === 422) {
    return extractValidationErrorMessage(data);
  }

  // Bad request
  if (status === 400) {
    return extractMessageFromResponseData(data) || 'Invalid request. Please check your input.';
  }

  // Rate limiting
  if (status === 429) {
    return 'Too many requests. Please wait a moment and try again.';
  }

  // Server error
  if (status >= 500) {
    return 'Server error. Please try again later.';
  }

  // Generic extraction
  return extractMessageFromResponseData(data) || `Request failed (${status})`;
}

/**
 * Extract message from response data
 */
function extractMessageFromResponseData(data: unknown): string {
  if (!data) return '';

  // String response
  if (typeof data === 'string') {
    // Try to parse as JSON
    try {
      const parsed = JSON.parse(data);
      return extractMessageFromResponseData(parsed);
    } catch {
      return data;
    }
  }

  // Object response
  if (typeof data === 'object') {
    const obj = data as Record<string, unknown>;

    // FastAPI detail string
    if (typeof obj.detail === 'string') {
      return obj.detail;
    }

    // FastAPI validation errors array
    if (Array.isArray(obj.detail)) {
      return extractValidationErrorMessage(obj);
    }

    // Generic message field
    if (typeof obj.message === 'string') {
      return obj.message;
    }

    // Generic error field
    if (typeof obj.error === 'string') {
      return obj.error;
    }
  }

  return '';
}

/**
 * Extract validation error message from FastAPI 422 response
 */
function extractValidationErrorMessage(data: unknown): string {
  if (!data || typeof data !== 'object') {
    return 'Validation error. Please check your input.';
  }

  const obj = data as { detail?: unknown };

  if (!Array.isArray(obj.detail)) {
    if (typeof obj.detail === 'string') {
      return obj.detail;
    }
    return 'Validation error. Please check your input.';
  }

  // Extract first meaningful error
  const errors = obj.detail as Array<{
    loc?: (string | number)[];
    msg?: string;
    type?: string;
  }>;

  if (errors.length === 0) {
    return 'Validation error. Please check your input.';
  }

  const firstError = errors[0];
  const field = firstError.loc?.slice(-1)[0] || 'field';
  const message = firstError.msg || 'is invalid';

  // Make field name human-readable
  const fieldName = String(field)
    .replace(/_/g, ' ')
    .replace(/([A-Z])/g, ' $1')
    .trim()
    .toLowerCase();

  return `${capitalizeFirst(fieldName)} ${message}`;
}

/**
 * Type guard for Axios errors
 */
function isAxiosError(error: unknown): error is AxiosError {
  return (
    typeof error === 'object' &&
    error !== null &&
    'isAxiosError' in error &&
    (error as AxiosError).isAxiosError === true
  );
}

/**
 * Capitalize first letter
 */
function capitalizeFirst(str: string): string {
  return str.charAt(0).toUpperCase() + str.slice(1);
}

/**
 * Format error for logging
 */
export function formatErrorForLogging(error: unknown): string {
  if (isAxiosError(error)) {
    const axiosError = error as AxiosError;
    return JSON.stringify({
      url: axiosError.config?.url,
      method: axiosError.config?.method,
      status: axiosError.response?.status,
      data: axiosError.response?.data,
      message: axiosError.message,
    });
  }
  
  if (error instanceof Error) {
    return `${error.name}: ${error.message}`;
  }
  
  return String(error);
}
