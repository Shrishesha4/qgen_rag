/**
 * Vetter Portal API Service
 */

import apiClient from './api';
import { QuestionSourceInfo } from './questions';

// Types
export interface TeacherSummary {
  id: string;
  username: string;
  full_name: string | null;
  email: string;
  pending_count: number;
  approved_count: number;
  rejected_count: number;
  subjects: string[];
}

export interface SubjectSummary {
  id: string;
  name: string;
  code: string;
  teacher_id: string;
  teacher_name: string;
  pending_count: number;
  approved_count: number;
  rejected_count: number;
  topics: TopicInfo[];
}

export interface TopicInfo {
  id: string;
  name: string;
  pending_count: number;
}

export interface TopicQuestionStats {
  id: string;
  name: string;
  pending_count: number;
  approved_count: number;
  rejected_count: number;
}

export interface VetterDashboard {
  total_pending: number;
  total_approved: number;
  total_rejected: number;
  teachers_with_pending: number;
  subjects_with_pending: number;
  recent_submissions: number;
}

export interface QuestionForVetting {
  id: string;
  question_text: string;
  question_type: string;
  options: string[] | null;
  correct_answer: string | null;
  explanation: string | null;
  expected_answer: string | null;
  key_points: string[] | null;
  marks: number | null;
  difficulty_level: string | null;
  bloom_taxonomy_level: string | null;
  vetting_status: string;
  vetting_notes: string | null;
  learning_outcome_id: string | null;
  course_outcome_mapping: Record<string, number> | null;
  created_at: string;
  teacher_id: string | null;
  teacher_name: string | null;
  subject_id: string | null;
  subject_name: string | null;
  subject_code: string | null;
  topic_id: string | null;
  topic_name: string | null;
  source_info: QuestionSourceInfo | null;
  // Version control
  version_number: number;
  replaces_id: string | null;
  replaced_by_id: string | null;
}

export interface QuestionsResponse {
  questions: QuestionForVetting[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export interface VetQuestionRequest {
  status: 'approved' | 'rejected';
  notes?: string;
  course_outcome_mapping?: Record<string, number>;
  rejection_reasons?: string[];
  custom_feedback?: string;
}

export interface BulkVetRequest {
  question_ids: string[];
  status: 'approved' | 'rejected';
  notes?: string;
}

export interface VetterUpdateQuestionRequest {
  marks?: number;
  difficulty_level?: string;
  bloom_taxonomy_level?: string;
  correct_answer?: string;
  options?: string[];
  question_text?: string;
  course_outcome_mapping?: Record<string, number>;
  learning_outcome_id?: string;
}

export interface RejectAndRegenerateRequest {
  notes?: string;
  rejection_reasons?: string[];
  custom_feedback?: string;
}

export interface RejectAndRegenerateResponse {
  message: string;
  question_id: string;
  status: string;
  regenerated: boolean;
  new_question?: {
    id: string;
    question_text: string;
    question_type: string;
    options: string[] | null;
    correct_answer: string | null;
    marks: number | null;
    difficulty_level: string | null;
    bloom_taxonomy_level: string | null;
    vetting_status: string;
    version_number: number;
    session_id: string;
  } | null;
}

export interface QuestionFilters {
  page?: number;
  limit?: number;
  teacher_id?: string;
  subject_id?: string;
  topic_id?: string;
  question_type?: string;
  status?: 'pending' | 'approved' | 'rejected' | 'all';
}

export interface QuestionVersionEntry {
  id: string;
  version_number: number;
  question_text: string;
  question_type: string;
  options: string[] | null;
  correct_answer: string | null;
  marks: number | null;
  difficulty_level: string | null;
  vetting_status: string;
  vetting_notes: string | null;
  is_latest: boolean;
  generated_at: string | null;
}

export interface VersionHistoryResponse {
  question_id: string;
  versions: QuestionVersionEntry[];
}

// API Service
export const vetterService = {
  /**
   * Get vetter dashboard stats
   */
  async getDashboard(): Promise<VetterDashboard> {
    const response = await apiClient.get<VetterDashboard>('/vetter/dashboard');
    return response.data;
  },

  /**
   * Get list of teachers with questions
   */
  async getTeachers(): Promise<TeacherSummary[]> {
    const response = await apiClient.get<TeacherSummary[]>('/vetter/teachers');
    return response.data;
  },

  /**
   * Get list of subjects with question stats
   */
  async getSubjects(teacherId?: string): Promise<SubjectSummary[]> {
    const params = teacherId ? { teacher_id: teacherId } : {};
    const response = await apiClient.get<SubjectSummary[]>('/vetter/subjects', { params });
    return response.data;
  },

  /**
   * Get topic stats for a subject
   */
  async getTopicStats(subjectId: string): Promise<TopicQuestionStats[]> {
    const response = await apiClient.get<TopicQuestionStats[]>(`/vetter/subjects/${subjectId}/topics`);
    return response.data;
  },

  /**
   * Get questions for vetting with filters
   */
  async getQuestions(filters: QuestionFilters = {}): Promise<QuestionsResponse> {
    const params: Record<string, string | number> = {};
    if (filters.page) params.page = filters.page;
    if (filters.limit) params.limit = filters.limit;
    if (filters.teacher_id) params.teacher_id = filters.teacher_id;
    if (filters.subject_id) params.subject_id = filters.subject_id;
    if (filters.topic_id) params.topic_id = filters.topic_id;
    if (filters.question_type) params.question_type = filters.question_type;
    if (filters.status) params.status = filters.status;

    const response = await apiClient.get<QuestionsResponse>('/vetter/questions', { params });
    return response.data;
  },

  /**
   * Vet a single question (approve/reject)
   */
  async vetQuestion(questionId: string, data: VetQuestionRequest): Promise<{ message: string; question_id: string; status: string }> {
    const response = await apiClient.post(`/vetter/questions/${questionId}/vet`, data);
    return response.data;
  },

  /**
   * Bulk vet multiple questions
   */
  async bulkVet(data: BulkVetRequest): Promise<{ message: string; count: number; status: string }> {
    const response = await apiClient.post('/vetter/questions/bulk-vet', data);
    return response.data;
  },

  /**
   * Update a question as a vetter
   */
  async updateQuestion(questionId: string, data: VetterUpdateQuestionRequest): Promise<{ message: string; question_id: string; question: QuestionForVetting }> {
    const response = await apiClient.put(`/vetter/questions/${questionId}`, data);
    return response.data;
  },

  /**
   * Reject a question and trigger automatic regeneration of a replacement.
   * The new question is linked to the teacher's history as a 'vetter_regen' session.
   */
  async rejectAndRegenerate(questionId: string, data: RejectAndRegenerateRequest): Promise<RejectAndRegenerateResponse> {
    const response = await apiClient.post<RejectAndRegenerateResponse>(
      `/vetter/questions/${questionId}/reject-and-regenerate`,
      data,
    );
    return response.data;
  },

  /**
   * Get the full version history chain for a question.
   */
  async getVersionHistory(questionId: string): Promise<VersionHistoryResponse> {
    const response = await apiClient.get<VersionHistoryResponse>(
      `/vetter/questions/${questionId}/version-history`,
    );
    return response.data;
  },

  /**
   * Restore a previous version of a question as the latest active version.
   */
  async restoreVersion(versionId: string): Promise<{ message: string; restored_question_id: string; version_number: number }> {
    const response = await apiClient.post(`/vetter/questions/${versionId}/restore`);
    return response.data;
  },
};

export default vetterService;
