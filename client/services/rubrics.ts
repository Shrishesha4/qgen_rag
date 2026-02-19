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
   * Generate questions from a rubric (SSE streaming via fetch for real-time updates)
   */
  generateFromRubric(
    rubricId: string,
    onProgress: (progress: GenerationProgress) => void,
    onComplete: () => void,
    onError: (error: Error) => void,
    topicId?: string,
  ): () => void {
    const abortController = new AbortController();

    (async () => {
      try {
        // Build request body
        const body: Record<string, string> = { rubric_id: rubricId };
        if (topicId) body.topic_id = topicId;

        // Get auth token and base URL from the axios client config
        const { tokenStorage } = await import('./api');
        const token = await tokenStorage.getAccessToken();
        const baseURL = apiClient.defaults.baseURL || '';

        const response = await fetch(`${baseURL}/questions/generate-from-rubric`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'text/event-stream',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify(body),
          signal: abortController.signal,
        });

        if (!response.ok) {
          throw new Error(`Generation failed: ${response.status} ${response.statusText}`);
        }

        const reader = response.body?.getReader();
        if (!reader) {
          throw new Error('ReadableStream not supported');
        }

        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // Parse complete SSE events from the buffer
          const parts = buffer.split('\n\n');
          // Keep the last potentially incomplete part in the buffer
          buffer = parts.pop() || '';

          for (const part of parts) {
            const trimmed = part.trim();
            if (trimmed.startsWith('data: ')) {
              const json = trimmed.slice(6);
              try {
                const progress = JSON.parse(json) as GenerationProgress;
                onProgress(progress);
              } catch {
                // Skip invalid JSON
              }
            }
          }
        }

        // Process any remaining data in the buffer
        if (buffer.trim().startsWith('data: ')) {
          try {
            const progress = JSON.parse(buffer.trim().slice(6)) as GenerationProgress;
            onProgress(progress);
          } catch {
            // Skip invalid JSON
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
  // Question payload may include assigned LO/CO and topic/subject ids
  question?: {
    id: string;
    question_text: string;
    question_type: string;
    marks: number;
    subject_id?: string | null;
    topic_id?: string | null;
    learning_outcome_id?: string | null;
    course_outcome_mapping?: Record<string, number> | null;
  };
}

export default rubricsService;