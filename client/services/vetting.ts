/**
 * Vetting/Review API Service
 */

import apiClient from './api';
import { Question } from './questions';
import { PaginatedResponse } from './subjects';

export interface VettingRequest {
  status: 'approved' | 'rejected';
  course_outcome_mapping?: Record<string, number>;
  notes?: string;
  rejection_reasons?: string[];
  custom_feedback?: string;  // Custom feedback from voice input or text
  regeneration_mode?: 'modify' | 'new';  // Explicit regeneration mode
}

// Rejection reason categories for intelligent regeneration
export type RejectionCategory = 'modify' | 'new';

// Predefined rejection reasons with regeneration categories
export const REJECTION_REASONS = [
  { id: 'duplicate', label: 'Duplicate Question', description: 'Similar to an existing question', category: 'new' as RejectionCategory },
  { id: 'unclear', label: 'Unclear Wording', description: 'Question is ambiguous or confusing', category: 'modify' as RejectionCategory },
  { id: 'off_topic', label: 'Off Topic', description: 'Not relevant to the subject matter', category: 'new' as RejectionCategory },
  { id: 'incorrect_answer', label: 'Wrong Answer', description: 'The correct answer is inaccurate', category: 'modify' as RejectionCategory },
  { id: 'poor_options', label: 'Poor MCQ Options', description: 'Options are too obvious or confusing', category: 'modify' as RejectionCategory },
  { id: 'needs_improvement', label: 'Needs Improvement', description: 'Use voice/text to explain what to fix', category: 'modify' as RejectionCategory },
  { id: 'completely_new', label: 'Generate New', description: 'Replace with entirely different question', category: 'new' as RejectionCategory },
] as const;

export type RejectionReasonId = typeof REJECTION_REASONS[number]['id'];

// Helper to determine regeneration mode from selected reasons
export function determineRegenerationMode(selectedReasons: string[]): 'modify' | 'new' {
  let modifyCount = 0;
  let newCount = 0;
  
  for (const reasonId of selectedReasons) {
    const reason = REJECTION_REASONS.find(r => r.id === reasonId);
    if (reason) {
      if (reason.category === 'modify') {
        modifyCount++;
      } else {
        newCount++;
      }
    }
  }
  
  // Default to modify unless there's a clear signal for new
  if (newCount > modifyCount || selectedReasons.includes('duplicate') || selectedReasons.includes('off_topic') || selectedReasons.includes('completely_new')) {
    return 'new';
  }
  return 'modify';
}

// Alias for Question with vetting-specific fields
export interface PendingQuestion extends Question {
  course_outcome_mapping?: CourseOutcomeMapping;
}

export type CourseOutcomeMapping = Record<string, number>;

export interface VettingStats {
  total_generated: number;
  total_approved: number;
  total_rejected: number;
  pending_review: number;
  approval_rate: number;
  change_from_last_month: number;
  // Computed aliases for UI
  pending: number;
  approved: number;
  rejected: number;
  total_vetted: number;
}

export interface SubjectAnalytics {
  id: string;
  name: string;
  code: string;
  total_questions: number;
  approved: number;
  rejected: number;
  pending: number;
}

export interface AnalyticsBySubject {
  subjects: SubjectAnalytics[];
}

export interface AnalyticsByLO {
  learning_outcomes: Record<string, number>;
}

export interface AnalyticsByBloom {
  bloom_levels: Record<string, number>;
}

export const vettingService = {
  /**
   * Get questions pending review
   */
  async getPendingQuestions(
    page: number = 1,
    limit: number = 20,
    subjectId?: string,
    topicId?: string,
    questionType?: string
  ): Promise<{ questions: PendingQuestion[] } & PaginatedResponse<PendingQuestion>> {
    const params = new URLSearchParams({
      page: page.toString(),
      limit: limit.toString(),
    });
    if (subjectId) params.append('subject_id', subjectId);
    if (topicId) params.append('topic_id', topicId);
    if (questionType) params.append('question_type', questionType);

    const response = await apiClient.get(`/questions/vetting/pending?${params}`);
    return response.data;
  },

  /**
   * Approve or reject a question
   */
  async vetQuestion(
    questionId: string, 
    status: 'approved' | 'rejected', 
    notes?: string,
    rejectionReasons?: string[],
    customFeedback?: string,
    regenerationMode?: 'modify' | 'new'
  ): Promise<Question> {
    const data: VettingRequest = { 
      status, 
      notes, 
      rejection_reasons: rejectionReasons,
      custom_feedback: customFeedback,
      regeneration_mode: regenerationMode,
    };
    const response = await apiClient.post<Question>(`/questions/${questionId}/vet`, data, { timeout: 120000 });
    return response.data;
  },

  /**
   * Update CO mapping for a question
   */
  async updateCOMapping(questionId: string, mapping: Record<string, number>): Promise<Question> {
    const response = await apiClient.put<Question>(`/questions/${questionId}/co-mapping`, mapping);
    return response.data;
  },

  /**
   * Alias for updateCOMapping
   */
  async updateCourseOutcomeMapping(questionId: string, mapping: CourseOutcomeMapping): Promise<Question> {
    return this.updateCOMapping(questionId, mapping);
  },

  /**
   * Get vetting statistics
   */
  async getVettingStats(subjectId?: string): Promise<VettingStats> {
    const params = subjectId ? `?subject_id=${subjectId}` : '';
    const response = await apiClient.get<VettingStats>(`/questions/vetting/stats${params}`);
    const data = response.data;
    // Add computed aliases
    return {
      ...data,
      pending: data.pending_review,
      approved: data.total_approved,
      rejected: data.total_rejected,
      total_vetted: data.total_approved + data.total_rejected,
    };
  },

  /**
   * Get analytics by subject
   */
  async getAnalyticsBySubject(): Promise<AnalyticsBySubject> {
    const response = await apiClient.get<AnalyticsBySubject>('/questions/analytics/by-subject');
    return response.data;
  },

  /**
   * Get analytics by learning outcome
   */
  async getAnalyticsByLO(subjectId?: string): Promise<AnalyticsByLO> {
    const params = subjectId ? `?subject_id=${subjectId}` : '';
    const response = await apiClient.get<AnalyticsByLO>(`/questions/analytics/by-learning-outcome${params}`);
    return response.data;
  },

  /**
   * Get analytics by Bloom's taxonomy
   */
  async getAnalyticsByBloom(subjectId?: string): Promise<AnalyticsByBloom> {
    const params = subjectId ? `?subject_id=${subjectId}` : '';
    const response = await apiClient.get<AnalyticsByBloom>(`/questions/analytics/by-bloom${params}`);
    return response.data;
  },
};

export default vettingService;
