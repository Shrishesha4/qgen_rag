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
  async vetQuestion(questionId: string, status: 'approved' | 'rejected', notes?: string): Promise<Question> {
    const data: VettingRequest = { status, notes };
    const response = await apiClient.post<Question>(`/questions/${questionId}/vet`, data);
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
