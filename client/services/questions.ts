/**
 * Questions API Service
 */

import apiClient, { tokenStorage } from './api';
import EventSource from 'react-native-sse';

// Source reference information showing where content came from
export interface SourceReference {
  document_name: string | null;
  page_number: number | null;
  page_range: [number, number] | null;
  position_in_page: 'top' | 'middle' | 'bottom' | null;
  position_percentage: number | null;
  section_heading: string | null;
  content_snippet: string | null;
  highlighted_phrase: string | null;
  relevance_reason: string | null;
}

// Complete source information for a question
export interface QuestionSourceInfo {
  sources: SourceReference[];
  generation_reasoning: string | null;
  content_coverage: string | null;
}

export interface Question {
  id: string;
  document_id: string;
  session_id: string | null;
  subject_id: string | null;
  topic_id: string | null;
  question_text: string;
  question_type: 'mcq' | 'short_answer' | 'long_answer';
  marks: number | null;
  difficulty_level: 'easy' | 'medium' | 'hard' | null;
  bloom_taxonomy_level: string | null;
  options: string[] | null;
  correct_answer: string | null;
  explanation: string | null;
  topic_tags: string[] | null;
  source_chunk_ids: string[] | null;
  
  // Source Attribution
  source_info: QuestionSourceInfo | null;
  
  answerability_score: number | null;
  specificity_score: number | null;
  generation_confidence: number | null;
  generated_at: string;
  times_shown: number;
  user_rating: number | null;
  is_archived: boolean;

  // Vetting
  vetting_status: 'pending' | 'approved' | 'rejected';
  vetted_at?: string | null;
  vetting_notes?: string | null;

  // Assessment mappings assigned by backend
  learning_outcome_id?: string | null;
  course_outcome_mapping?: Record<string, number> | null;
}

export interface GenerationRequest {
  document_id: string;
  count: number;
  types?: ('mcq' | 'short_answer' | 'long_answer')[];
  difficulty?: 'easy' | 'medium' | 'hard';
  marks?: number;
  focus_topics?: string[];
  bloom_levels?: ('remember' | 'understand' | 'apply' | 'analyze' | 'evaluate' | 'create')[];
  exclude_question_ids?: string[];
}

export interface GenerationProgress {
  status: 'processing' | 'generating' | 'validating' | 'complete' | 'error';
  progress: number;
  current_question: number | null;
  total_questions: number | null;
  question: Question | null;
  message: string | null;
}

export interface QuickGenerateProgress {
  status: 'uploading' | 'processing' | 'generating' | 'complete' | 'error';
  progress: number;
  current_question: number | null;
  total_questions: number | null;
  question: Question | null;
  message: string | null;
  document_id: string | null;
}

export interface QuickGenerateRequest {
  file: {
    uri: string;
    name: string;
    type: string;
  };
  context: string;
  count?: number;
  types?: ('mcq' | 'short_answer' | 'long_answer')[];
  difficulty?: 'easy' | 'medium' | 'hard';
  bloom_levels?: ('remember' | 'understand' | 'apply' | 'analyze' | 'evaluate' | 'create')[];
  marks_mcq?: number;
  marks_short?: number;
  marks_long?: number;
  subject_id?: string;
  topic_id?: string;
}

export interface QuickGenerateFromSubjectRequest {
  subject_id: string;
  topic_id?: string;
  context: string;
  count?: number;
  types?: ('mcq' | 'short_answer' | 'long_answer')[];
  difficulty?: 'easy' | 'medium' | 'hard';
  marks_mcq?: number;
  marks_short?: number;
  marks_long?: number;
}

export interface QuestionUpdateRequest {
  marks?: number;
  difficulty_level?: 'easy' | 'medium' | 'hard';
  bloom_taxonomy_level?: 'remember' | 'understand' | 'apply' | 'analyze' | 'evaluate' | 'create';
  subject_id?: string;
  topic_id?: string;
  learning_outcome_id?: string;
  course_outcome_mapping?: Record<string, number>;
  question_text?: string;
  correct_answer?: string;
  options?: string[];
}

export interface GenerationSession {
  id: string;
  document_id: string | null;
  user_id: string;
  subject_id: string | null;
  subject_name: string | null;
  subject_code: string | null;
  topic_id: string | null;
  topic_name: string | null;
  generation_method: string | null;
  requested_count: number;
  requested_types: string[] | null;
  requested_marks: number | null;
  requested_difficulty: string | null;
  focus_topics: string[] | null;
  status: string;
  started_at: string;
  completed_at: string | null;
  questions_generated: number;
  questions_failed: number;
  questions_duplicate: number;
  total_duration_seconds: number | null;
  llm_calls: number | null;
  tokens_used: number | null;
  blacklist_size: number | null;
  chunks_used: number | null;
  error_message: string | null;
  generation_config: Record<string, unknown> | null;
}

export interface SessionQuestion {
  id: string;
  question_text: string;
  question_type: string;
  options: string[] | null;
  correct_answer: string | null;
  marks: number | null;
  difficulty_level: string | null;
  bloom_taxonomy_level: string | null;
  course_outcome_mapping: Record<string, number> | null;
  learning_outcome_id: string | null;
  topic_tags: string[] | null;
  vetting_status: string;
  generated_at: string | null;
  version_number?: number;
  replaces_id?: string | null;
  is_latest?: boolean;
  regenerated_by_vetter?: boolean;
  // Source Attribution
  source_info?: QuestionSourceInfo | null;
}

export interface QuestionStats {
  total_questions_generated: number;
  total_sessions: number;
  average_questions_per_session: number;
  questions_by_type: Record<string, number>;
  questions_by_difficulty: Record<string, number>;
  average_generation_time_seconds: number;
}

export interface TeacherDashboard {
  subjects_count: number;
  documents_count: number;
  sessions_count: number;
  total_questions: number;
  pending_questions: number;
  approved_questions: number;
  rejected_questions: number;
  approval_rate: number;
  questions_by_type: Record<string, number>;
}

export const questionsService = {
  /**
   * Generate questions with true SSE streaming
   */
  generateQuestions(
    request: GenerationRequest,
    onProgress: (progress: GenerationProgress) => void,
    onComplete: () => void,
    onError: (error: Error) => void
  ): () => void {
    let eventSource: EventSource | null = null;
    let isClosed = false;

    (async () => {
      try {
        const accessToken = await tokenStorage.getAccessToken();
        const baseUrl = apiClient.defaults.baseURL || '';

        // Build URL with query params for SSE GET request
        // Or use POST body - depends on backend implementation
        const url = `${baseUrl}/questions/generate-stream`;

        console.log('[GenerateQuestions] Starting SSE connection to:', url);

        eventSource = new EventSource(url, {
          headers: {
            'Authorization': accessToken ? `Bearer ${accessToken}` : '',
            'Content-Type': 'application/json',
          },
          method: 'POST',
          body: JSON.stringify(request),
          pollingInterval: 0, // Disable polling, use true streaming
          withCredentials: false,
        });

        eventSource.addEventListener('message', (event) => {
          if (isClosed) return;

          try {
            const data = event.data;
            if (data) {
              const progress = JSON.parse(data) as GenerationProgress;
              console.log('[GenerateQuestions] SSE Event:', progress.status);
              onProgress(progress);

              if (progress.status === 'complete' || progress.status === 'error') {
                eventSource?.close();
                onComplete();
              }
            }
          } catch (parseError) {
            console.warn('[GenerateQuestions] Failed to parse SSE event:', parseError);
          }
        });

        eventSource.addEventListener('error', (event) => {
          if (isClosed) return;
          console.error('[GenerateQuestions] SSE Error:', event);
          eventSource?.close();
          onError(new Error('SSE connection error'));
        });

        eventSource.addEventListener('open', () => {
          console.log('[GenerateQuestions] SSE connection opened');
        });

      } catch (error) {
        console.error('[GenerateQuestions] Error:', error);
        onError(error as Error);
      }
    })();

    return () => {
      isClosed = true;
      if (eventSource) {
        console.log('[GenerateQuestions] Closing SSE connection');
        eventSource.close();
      }
    };
  },

  /**
   * List questions for a document
   */
  async listQuestions(
    page: number = 1,
    limit: number = 20,
    questionType?: string,
    difficulty?: string,
    documentId?: string,
    subjectId?: string,
    showArchived: boolean = false,
    vettingStatus?: string,
  ): Promise<{ questions: Question[]; pagination: { page: number; limit: number; total: number; total_pages: number } }> {
    const params = new URLSearchParams({
      page: page.toString(),
      limit: limit.toString(),
    });
    if (documentId) params.append('document_id', documentId);
    if (subjectId) params.append('subject_id', subjectId);
    if (questionType) params.append('question_type', questionType);
    if (difficulty) params.append('difficulty', difficulty);
    if (showArchived) params.append('show_archived', 'true');
    if (vettingStatus) params.append('vetting_status', vettingStatus);

    const response = await apiClient.get(`/questions?${params}`);
    return response.data;
  },

  /**
   * Get a specific question
   */
  async getQuestion(questionId: string): Promise<Question> {
    const response = await apiClient.get<Question>(`/questions/${questionId}`);
    return response.data;
  },

  /**
   * Rate a question
   */
  async rateQuestion(
    questionId: string,
    rating: number,
    difficultyRating?: 'too_easy' | 'just_right' | 'too_hard'
  ): Promise<Question> {
    const response = await apiClient.post<Question>(`/questions/${questionId}/rate`, {
      rating,
      difficulty_rating: difficultyRating,
    });
    return response.data;
  },

  /**
   * Archive a question
   */
  async archiveQuestion(questionId: string): Promise<void> {
    await apiClient.delete(`/questions/${questionId}`);
  },

  /**
   * Unarchive a question (restore it)
   */
  async unarchiveQuestion(questionId: string): Promise<void> {
    await apiClient.post(`/questions/${questionId}/unarchive`);
  },

  /**
   * Update a question's editable fields
   */
  async updateQuestion(questionId: string, data: QuestionUpdateRequest): Promise<Question> {
    const response = await apiClient.put<Question>(`/questions/${questionId}`, data);
    return response.data;
  },

  /**
   * Promote an older version to be the current version
   */
  async promoteVersion(questionId: string): Promise<Question> {
    const response = await apiClient.post<Question>(`/questions/${questionId}/promote-version`);
    return response.data;
  },

  /**
   * List generation sessions
   */
  async listSessions(
    documentId?: string,
    subjectId?: string,
    page: number = 1,
    limit: number = 20
  ): Promise<{ sessions: GenerationSession[]; pagination: { page: number; limit: number; total: number; pages: number } }> {
    const params = new URLSearchParams({
      page: page.toString(),
      limit: limit.toString(),
    });
    if (documentId) params.append('document_id', documentId);
    if (subjectId) params.append('subject_id', subjectId);

    const response = await apiClient.get(`/questions/sessions/list?${params}`);
    return response.data;
  },

  /**
   * Get questions for a specific session
   */
  async getSessionQuestions(sessionId: string): Promise<{
    session_id: string;
    generation_method: string | null;
    started_at: string | null;
    questions: SessionQuestion[];
  }> {
    const response = await apiClient.get(`/questions/sessions/${sessionId}/questions`);
    return response.data;
  },

  /**
   * Import questions from Excel/CSV file
   */
  async importQuestions(
    file: { uri: string; name: string; type: string },
    subjectId: string,
    topicId?: string,
  ): Promise<{ message: string; imported: number; skipped: number; session_id: string }> {
    const formData = new FormData();
    formData.append('file', {
      uri: file.uri,
      name: file.name,
      type: file.type,
    } as unknown as Blob);
    formData.append('subject_id', subjectId);
    if (topicId) formData.append('topic_id', topicId);

    const response = await apiClient.post('/questions/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000,
    });
    return response.data;
  },

  /**
   * Get session details
   */
  async getSession(sessionId: string): Promise<GenerationSession> {
    const response = await apiClient.get<GenerationSession>(`/questions/sessions/${sessionId}`);
    return response.data;
  },

  /**
   * Delete a generation session and its questions
   */
  async deleteSession(sessionId: string): Promise<void> {
    await apiClient.delete(`/questions/sessions/${sessionId}`);
  },

  /**
   * Get question stats
   */
  async getStats(documentId?: string): Promise<QuestionStats> {
    const params = documentId ? `?document_id=${documentId}` : '';
    const response = await apiClient.get<QuestionStats>(`/questions/stats/summary${params}`);
    return response.data;
  },

  async getTeacherDashboard(): Promise<TeacherDashboard> {
    const response = await apiClient.get<TeacherDashboard>('/questions/teacher/dashboard');
    return response.data;
  },

  /**
   * Quick generate questions from PDF with just context
   * Uses two-step approach: upload file first, then SSE for generation
   */
  quickGenerate(
    request: QuickGenerateRequest,
    onProgress: (progress: QuickGenerateProgress) => void,
    onComplete: (documentId: string | null) => void,
    onError: (error: Error) => void
  ): () => void {
    let xhr: XMLHttpRequest | null = null;
    let isCancelled = false;
    let lastDocumentId: string | null = null;

    (async () => {
      try {
        // Step 1: Upload file and get document ID
        onProgress({
          status: 'uploading',
          progress: 0,
          current_question: null,
          total_questions: null,
          question: null,
          message: 'Uploading document...',
          document_id: null,
        });

        const formData = new FormData();
        formData.append('file', {
          uri: request.file.uri,
          name: request.file.name,
          type: request.file.type,
        } as any);
        formData.append('context', request.context);
        if (request.count) formData.append('count', request.count.toString());
        if (request.types) formData.append('types', request.types.join(','));
        if (request.difficulty) formData.append('difficulty', request.difficulty);
        if (request.bloom_levels) formData.append('bloom_levels', request.bloom_levels.join(','));
        if (request.marks_mcq) formData.append('marks_mcq', request.marks_mcq.toString());
        if (request.marks_short) formData.append('marks_short', request.marks_short.toString());
        if (request.marks_long) formData.append('marks_long', request.marks_long.toString());
        if (request.subject_id) formData.append('subject_id', request.subject_id);
        if (request.topic_id) formData.append('topic_id', request.topic_id);

        const accessToken = await tokenStorage.getAccessToken();
        const baseUrl = apiClient.defaults.baseURL || '';

        // Use XMLHttpRequest for file upload with true SSE streaming via onprogress
        await new Promise<void>((resolve, reject) => {
          xhr = new XMLHttpRequest();
          let buffer = '';
          let processedLength = 0;

          // Handle incremental SSE data via onprogress
          xhr.onprogress = () => {
            if (isCancelled || !xhr) return;

            // Get new data since last read
            const responseText = xhr.responseText || '';
            const newData = responseText.slice(processedLength);
            processedLength = responseText.length;

            if (!newData) return;

            // Add to buffer and process complete events
            buffer += newData;
            const events = buffer.split('\n\n');

            // Keep incomplete event in buffer
            buffer = events.pop() || '';

            for (const event of events) {
              if (event.startsWith('data: ')) {
                try {
                  const json = event.slice(6).trim();
                  if (json) {
                    const progress = JSON.parse(json) as QuickGenerateProgress;
                    console.log('[QuickGenerate] SSE Event:', progress.status, progress.message);
                    if (progress.document_id) {
                      lastDocumentId = progress.document_id;
                    }
                    onProgress(progress);
                  }
                } catch (parseError) {
                  console.warn('[QuickGenerate] Failed to parse event:', event.substring(0, 100));
                }
              }
            }
          };

          xhr.onload = () => {
            if (isCancelled || !xhr) return;

            console.log('[QuickGenerate] Request completed, status:', xhr.status);

            if (xhr.status === 200) {
              // Process any remaining data in buffer
              if (buffer && buffer.startsWith('data: ')) {
                try {
                  const json = buffer.slice(6).trim();
                  if (json) {
                    const progress = JSON.parse(json) as QuickGenerateProgress;
                    if (progress.document_id) {
                      lastDocumentId = progress.document_id;
                    }
                    onProgress(progress);
                  }
                } catch (e) {
                  // Ignore incomplete final event
                }
              }

              onComplete(lastDocumentId);
              resolve();
            } else {
              reject(new Error(`Request failed: ${xhr.status} - ${xhr.responseText?.substring(0, 200)}`));
            }
          };

          xhr.onerror = () => {
            console.error('[QuickGenerate] Network error');
            reject(new Error('Network error'));
          };

          xhr.ontimeout = () => {
            console.error('[QuickGenerate] Request timeout');
            reject(new Error('Request timeout'));
          };

          xhr.open('POST', `${baseUrl}/questions/quick-generate`);
          xhr.timeout = 300000; // 5 minute timeout
          xhr.setRequestHeader('Accept', 'text/event-stream');
          if (accessToken) {
            xhr.setRequestHeader('Authorization', `Bearer ${accessToken}`);
          }

          console.log('[QuickGenerate] Starting request to:', `${baseUrl}/questions/quick-generate`);
          xhr.send(formData);
        });

      } catch (error) {
        if (!isCancelled) {
          console.error('[QuickGenerate] Error:', error);
          onError(error as Error);
        }
      }
    })();

    return () => {
      isCancelled = true;
      if (xhr) {
        console.log('[QuickGenerate] Aborting XHR request');
        xhr.abort();
      }
    };
  },
  /**
   * Quick generate questions from a subject (no file needed) with SSE streaming
   */
  quickGenerateFromSubject(
    request: QuickGenerateFromSubjectRequest,
    onProgress: (progress: QuickGenerateProgress) => void,
    onComplete: (documentId: string | null) => void,
    onError: (error: Error) => void
  ): () => void {
    let xhr: XMLHttpRequest | null = null;
    let isCancelled = false;
    let lastDocumentId: string | null = null;

    (async () => {
      try {
        onProgress({
          status: 'processing',
          progress: 0,
          current_question: null,
          total_questions: null,
          question: null,
          message: 'Preparing subject content...',
          document_id: null,
        });

        const formData = new FormData();
        formData.append('subject_id', request.subject_id);
        if (request.topic_id) formData.append('topic_id', request.topic_id);
        formData.append('context', request.context);
        if (request.count) formData.append('count', request.count.toString());
        if (request.types) formData.append('types', request.types.join(','));
        if (request.difficulty) formData.append('difficulty', request.difficulty);
        if (request.marks_mcq) formData.append('marks_mcq', request.marks_mcq.toString());
        if (request.marks_short) formData.append('marks_short', request.marks_short.toString());
        if (request.marks_long) formData.append('marks_long', request.marks_long.toString());

        const accessToken = await tokenStorage.getAccessToken();
        const baseUrl = apiClient.defaults.baseURL || '';

        await new Promise<void>((resolve, reject) => {
          xhr = new XMLHttpRequest();
          let buffer = '';
          let processedLength = 0;

          xhr.onprogress = () => {
            if (isCancelled || !xhr) return;
            const responseText = xhr.responseText || '';
            const newData = responseText.slice(processedLength);
            processedLength = responseText.length;
            if (!newData) return;
            buffer += newData;
            const events = buffer.split('\n\n');
            buffer = events.pop() || '';
            for (const event of events) {
              if (event.startsWith('data: ')) {
                try {
                  const json = event.slice(6).trim();
                  if (json) {
                    const progress = JSON.parse(json) as QuickGenerateProgress;
                    console.log('[QuickGenerateFromSubject] SSE Event:', progress.status, progress.message);
                    if (progress.document_id) lastDocumentId = progress.document_id;
                    onProgress(progress);
                  }
                } catch (parseError) {
                  console.warn('[QuickGenerateFromSubject] Failed to parse event:', event.substring(0, 100));
                }
              }
            }
          };

          xhr.onload = () => {
            if (isCancelled || !xhr) return;
            console.log('[QuickGenerateFromSubject] Request completed, status:', xhr.status);
            if (xhr.status === 200) {
              if (buffer && buffer.startsWith('data: ')) {
                try {
                  const json = buffer.slice(6).trim();
                  if (json) {
                    const progress = JSON.parse(json) as QuickGenerateProgress;
                    if (progress.document_id) lastDocumentId = progress.document_id;
                    onProgress(progress);
                  }
                } catch (e) { /* ignore incomplete final event */ }
              }
              onComplete(lastDocumentId);
              resolve();
            } else {
              reject(new Error(`Request failed: ${xhr.status} - ${xhr.responseText?.substring(0, 200)}`));
            }
          };

          xhr.onerror = () => {
            console.error('[QuickGenerateFromSubject] Network error');
            reject(new Error('Network error'));
          };

          xhr.ontimeout = () => {
            console.error('[QuickGenerateFromSubject] Request timeout');
            reject(new Error('Request timeout'));
          };

          xhr.open('POST', `${baseUrl}/questions/quick-generate-from-subject`);
          xhr.timeout = 300000;
          xhr.setRequestHeader('Accept', 'text/event-stream');
          if (accessToken) xhr.setRequestHeader('Authorization', `Bearer ${accessToken}`);

          console.log('[QuickGenerateFromSubject] Starting request to:', `${baseUrl}/questions/quick-generate-from-subject`);
          xhr.send(formData);
        });

      } catch (error) {
        if (!isCancelled) {
          console.error('[QuickGenerateFromSubject] Error:', error);
          onError(error as Error);
        }
      }
    })();

    return () => {
      isCancelled = true;
      if (xhr) {
        console.log('[QuickGenerateFromSubject] Aborting XHR request');
        xhr.abort();
      }
    };
  },
};

export default questionsService;
