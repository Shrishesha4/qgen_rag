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
   * Generate questions from a rubric (SSE streaming via XMLHttpRequest for React Native)
   */
  generateFromRubric(
    rubricId: string,
    onProgress: (progress: GenerationProgress) => void,
    onComplete: () => void,
    onError: (error: Error) => void,
    topicId?: string,
  ): () => void {
    let cancelled = false;
    let cancelFn = () => { cancelled = true; };

    console.log('[RubricsService] generateFromRubric called, rubricId:', rubricId);

    (async () => {
      try {
        const body: Record<string, string> = { rubric_id: rubricId };
        if (topicId) body.topic_id = topicId;

        const { tokenStorage } = await import('./api');
        const token = await tokenStorage.getAccessToken();
        const baseURL = apiClient.defaults.baseURL || '';

        console.log('[RubricsService] Making SSE request to:', `${baseURL}/questions/generate-from-rubric`);
        console.log('[RubricsService] Request body:', JSON.stringify(body));
        console.log('[RubricsService] Has token:', !!token);

        const xhr = new XMLHttpRequest();
        xhr.open('POST', `${baseURL}/questions/generate-from-rubric`);
        xhr.setRequestHeader('Content-Type', 'application/json');
        xhr.setRequestHeader('Accept', 'text/event-stream');
        if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);

        let lastIndex = 0;

        xhr.onprogress = () => {
          if (cancelled) return;
          const text = xhr.responseText.substring(lastIndex);
          lastIndex = xhr.responseText.length;
          console.log('[RubricsService] XHR onprogress, new text length:', text.length);

          const parts = text.split('\n\n');
          for (const part of parts) {
            const trimmed = part.trim();
            if (trimmed.startsWith('data: ')) {
              try {
                const parsed = JSON.parse(trimmed.slice(6)) as GenerationProgress;
                console.log('[RubricsService] Parsed SSE event:', parsed.status);
                onProgress(parsed);
              } catch (e) {
                console.warn('[RubricsService] Failed to parse SSE:', e);
              }
            }
          }
        };

        xhr.onload = () => {
          console.log('[RubricsService] XHR onload, status:', xhr.status);
          if (cancelled) return;
          const text = xhr.responseText.substring(lastIndex);
          if (text) {
            const parts = text.split('\n\n');
            for (const part of parts) {
              const trimmed = part.trim();
              if (trimmed.startsWith('data: ')) {
                try {
                  onProgress(JSON.parse(trimmed.slice(6)) as GenerationProgress);
                } catch { /* skip */ }
              }
            }
          }
          console.log('[RubricsService] Generation complete');
          onComplete();
        };

        xhr.onerror = (e) => {
          console.error('[RubricsService] XHR onerror:', e);
          if (!cancelled) onError(new Error('Generation request failed'));
        };

        cancelFn = () => {
          cancelled = true;
          xhr.abort();
        };

        console.log('[RubricsService] Sending XHR request...');
        xhr.send(JSON.stringify(body));
      } catch (error) {
        if (!cancelled) onError(error as Error);
      }
    })();

    return () => cancelFn();
  },

  /**
   * Generate questions from a single chapter (SSE streaming via XMLHttpRequest for React Native)
   */
  generateChapter(
    topicId: string,
    questionTypes: Record<string, { count: number; marks_each: number }>,
    onProgress: (progress: GenerationProgress) => void,
    onComplete: () => void,
    onError: (error: Error) => void,
    difficulty: string = 'medium',
    loFilter?: string[],
  ): () => void {
    let cancelled = false;
    let cancelFn = () => { cancelled = true; };

    console.log('[RubricsService] generateChapter called, topicId:', topicId);
    console.log('[RubricsService] questionTypes:', JSON.stringify(questionTypes));

    (async () => {
      try {
        const { tokenStorage } = await import('./api');
        const token = await tokenStorage.getAccessToken();
        const baseURL = apiClient.defaults.baseURL || '';

        console.log('[RubricsService] Making chapter SSE request to:', `${baseURL}/questions/generate-chapter`);
        console.log('[RubricsService] Has token:', !!token);

        const xhr = new XMLHttpRequest();
        xhr.open('POST', `${baseURL}/questions/generate-chapter`);
        xhr.setRequestHeader('Content-Type', 'application/json');
        xhr.setRequestHeader('Accept', 'text/event-stream');
        if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);

        let lastIndex = 0;

        xhr.onprogress = () => {
          if (cancelled) return;
          const text = xhr.responseText.substring(lastIndex);
          lastIndex = xhr.responseText.length;

          const parts = text.split('\n\n');
          for (const part of parts) {
            const trimmed = part.trim();
            if (trimmed.startsWith('data: ')) {
              try {
                onProgress(JSON.parse(trimmed.slice(6)) as GenerationProgress);
              } catch { /* skip invalid JSON */ }
            }
          }
        };

        xhr.onload = () => {
          if (cancelled) return;
          const text = xhr.responseText.substring(lastIndex);
          if (text) {
            const parts = text.split('\n\n');
            for (const part of parts) {
              const trimmed = part.trim();
              if (trimmed.startsWith('data: ')) {
                try {
                  onProgress(JSON.parse(trimmed.slice(6)) as GenerationProgress);
                } catch { /* skip */ }
              }
            }
          }
          onComplete();
        };

        xhr.onerror = () => {
          if (!cancelled) onError(new Error('Generation request failed'));
        };

        cancelFn = () => {
          cancelled = true;
          xhr.abort();
        };

        xhr.send(JSON.stringify({
          topic_id: topicId,
          question_types: questionTypes,
          difficulty,
          lo_filter: loFilter && loFilter.length > 0 ? loFilter : undefined,
        }));
      } catch (error) {
        if (!cancelled) onError(error as Error);
      }
    })();

    return () => cancelFn();
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