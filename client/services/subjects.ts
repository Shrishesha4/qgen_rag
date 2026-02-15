/**
 * Subjects API Service
 */

import apiClient from './api';

export interface LearningOutcome {
  id: string;
  name: string;
  description?: string;
}

export interface CourseOutcome {
  id: string;
  name: string;
  description?: string;
}

export interface Topic {
  id: string;
  subject_id: string;
  name: string;
  description?: string;
  order_index: number;
  has_syllabus: boolean;
  syllabus_content?: string;
  learning_outcome_mappings?: Record<string, number>;
  total_questions: number;
  created_at: string;
  updated_at: string;
}

export interface Subject {
  id: string;
  user_id: string;
  name: string;
  code: string;
  description?: string;
  learning_outcomes?: { outcomes: LearningOutcome[] };
  course_outcomes?: { outcomes: CourseOutcome[] };
  total_questions: number;
  total_topics: number;
  syllabus_coverage: number;
  created_at: string;
  updated_at: string;
}

export interface SubjectDetail extends Subject {
  topics: Topic[];
}

export interface PaginatedResponse<T> {
  pagination: {
    page: number;
    limit: number;
    total: number;
    total_pages: number;
  };
}

export interface SubjectCreateData {
  name: string;
  code: string;
  description?: string;
  learning_outcomes?: LearningOutcome[];
  course_outcomes?: CourseOutcome[];
}

export interface TopicCreateData {
  subject_id: string;
  name: string;
  description?: string;
  order_index?: number;
}

export interface TopicUpdateData {
  name?: string;
  description?: string;
  order_index?: number;
  has_syllabus?: boolean;
  syllabus_content?: string;
  learning_outcome_mappings?: Record<string, number>;
}

export const subjectsService = {
  /**
   * List all subjects
   */
  async listSubjects(
    page: number = 1,
    limit: number = 20,
    search?: string
  ): Promise<{ subjects: Subject[] } & PaginatedResponse<Subject>> {
    const params = new URLSearchParams({
      page: page.toString(),
      limit: limit.toString(),
    });
    if (search) params.append('search', search);

    const response = await apiClient.get(`/subjects?${params}`);
    return response.data;
  },

  /**
   * Get a specific subject with topics
   */
  async getSubject(subjectId: string): Promise<SubjectDetail> {
    const response = await apiClient.get<SubjectDetail>(`/subjects/${subjectId}`);
    return response.data;
  },

  /**
   * Create a new subject
   */
  async createSubject(data: SubjectCreateData): Promise<Subject> {
    const response = await apiClient.post<Subject>('/subjects', data);
    return response.data;
  },

  /**
   * Update a subject
   */
  async updateSubject(subjectId: string, data: Partial<SubjectCreateData>): Promise<Subject> {
    const response = await apiClient.put<Subject>(`/subjects/${subjectId}`, data);
    return response.data;
  },

  /**
   * Delete a subject
   */
  async deleteSubject(subjectId: string): Promise<void> {
    await apiClient.delete(`/subjects/${subjectId}`);
  },

  /**
   * List topics for a subject
   */
  async listTopics(
    subjectId: string,
    page: number = 1,
    limit: number = 50
  ): Promise<{ topics: Topic[] } & PaginatedResponse<Topic>> {
    const params = new URLSearchParams({
      page: page.toString(),
      limit: limit.toString(),
    });

    const response = await apiClient.get(`/subjects/${subjectId}/topics?${params}`);
    return response.data;
  },

  /**
   * Create a topic
   */
  async createTopic(subjectId: string, data: TopicCreateData): Promise<Topic> {
    const response = await apiClient.post<Topic>(`/subjects/${subjectId}/topics`, data);
    return response.data;
  },

  /**
   * Update a topic
   */
  async updateTopic(subjectId: string, topicId: string, data: TopicUpdateData): Promise<Topic> {
    const response = await apiClient.put<Topic>(`/subjects/${subjectId}/topics/${topicId}`, data);
    return response.data;
  },

  /**
   * Delete a topic
   */
  async deleteTopic(subjectId: string, topicId: string): Promise<void> {
    await apiClient.delete(`/subjects/${subjectId}/topics/${topicId}`);
  },

  /**
   * Upload syllabus document to a topic (PDF, DOCX, TXT)
   * Extracts text and saves to topic's syllabus_content
   */
  async uploadTopicSyllabus(
    subjectId: string,
    topicId: string,
    uri: string,
    filename: string,
    mimeType: string
  ): Promise<Topic> {
    const formData = new FormData();
    
    // For React Native, we need to create a proper file object
    formData.append('file', {
      uri,
      name: filename,
      type: mimeType,
    } as unknown as Blob);

    const response = await apiClient.post<Topic>(
      `/subjects/${subjectId}/topics/${topicId}/upload-syllabus`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: 120000, // 2 minutes for file upload and text extraction
      }
    );

    return response.data;
  },
};

export default subjectsService;
