/**
 * Rubrics API Service
 */

import apiClient from './api';
import { PaginatedResponse } from './subjects';

export interface QuestionTypeDistribution {
  count: number;
  marks_each: number;
}

export interface Rubric {
  id: string;
  user_id: string;
  subject_id: string;
  name: string;
  exam_type: 'final_exam' | 'mid_term' | 'quiz' | 'assignment';
  duration_minutes: number;
  question_type_distribution: Record<string, QuestionTypeDistribution>;
  learning_outcomes_distribution: Record<string, number>;
  total_questions: number;
  total_marks: number;
  created_at: string;
  updated_at: string;
}

export interface RubricDetail extends Rubric {
  subject_name?: string;
  subject_code?: string;
}

export interface RubricCreateData {
  subject_id: string;
  name: string;
  exam_type: string;
  duration_minutes: number;
  question_type_distribution: Record<string, QuestionTypeDistribution>;
  learning_outcomes_distribution: Record<string, number>;
}

export const rubricsService = {
  /**
   * List all rubrics
   */
  async listRubrics(
    page: number = 1,
    limit: number = 20,
    subjectId?: string,
    examType?: string
  ): Promise<{ rubrics: Rubric[] } & PaginatedResponse<Rubric>> {
    const params = new URLSearchParams({
      page: page.toString(),
      limit: limit.toString(),
    });
    if (subjectId) params.append('subject_id', subjectId);
    if (examType) params.append('exam_type', examType);

    const response = await apiClient.get(`/rubrics?${params}`);
    return response.data;
  },

  /**
   * Get a specific rubric
   */
  async getRubric(rubricId: string): Promise<RubricDetail> {
    const response = await apiClient.get<RubricDetail>(`/rubrics/${rubricId}`);
    return response.data;
  },

  /**
   * Create a new rubric
   */
  async createRubric(data: RubricCreateData): Promise<Rubric> {
    const response = await apiClient.post<Rubric>('/rubrics', data);
    return response.data;
  },

  /**
   * Update a rubric
   */
  async updateRubric(rubricId: string, data: Partial<RubricCreateData>): Promise<Rubric> {
    const response = await apiClient.put<Rubric>(`/rubrics/${rubricId}`, data);
    return response.data;
  },

  /**
   * Delete a rubric
   */
  async deleteRubric(rubricId: string): Promise<void> {
    await apiClient.delete(`/rubrics/${rubricId}`);
  },

  /**
   * Generate questions from a rubric (SSE streaming)
   */
  generateFromRubric(
    rubricId: string,
    onProgress: (progress: GenerationProgress) => void,
    onComplete: () => void,
    onError: (error: Error) => void
  ): () => void {
    const abortController = new AbortController();

    (async () => {
      try {
        const response = await apiClient.post(
          '/questions/generate-from-rubric',
          { rubric_id: rubricId },
          {
            responseType: 'text',
            signal: abortController.signal,
            headers: {
              Accept: 'text/event-stream',
            },
            timeout: 300000, // 5 minutes for generation
          }
        );

        // Parse SSE events
        const data = response.data as string;
        const events = data.split('\n\n').filter(Boolean);
        
        for (const event of events) {
          if (event.startsWith('data: ')) {
            const json = event.slice(6);
            try {
              const progress = JSON.parse(json) as GenerationProgress;
              onProgress(progress);
            } catch {
              // Skip invalid JSON
            }
          }
        }
        
        onComplete();
      } catch (error) {
        if (!abortController.signal.aborted) {
          onError(error as Error);
        }
      }
    })();

    return () => abortController.abort();
  },
};

export interface GenerationProgress {
  status: 'processing' | 'generating' | 'complete' | 'error';
  progress: number;
  current_question?: number;
  total_questions?: number;
  message?: string;
  question?: {
    id: string;
    question_text: string;
    question_type: string;
    marks: number;
  };
}

export default rubricsService;