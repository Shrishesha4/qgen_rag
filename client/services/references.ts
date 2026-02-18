/**
 * Reference Materials API Service
 * Handles reference books and template question papers per subject
 */

import apiClient from './api';

export interface ReferenceDocument {
  id: string;
  filename: string;
  file_size_bytes: number;
  mime_type: string | null;
  index_type: 'reference_book' | 'template_paper';
  subject_id: string;
  processing_status: 'pending' | 'processing' | 'completed' | 'failed';
  total_chunks: number | null;
  upload_timestamp: string;
  processed_at: string | null;
}

export interface ReferenceMaterialsResponse {
  reference_books: ReferenceDocument[];
  template_papers: ReferenceDocument[];
}

export interface NoveltySettings {
  novelty_threshold: number;
  max_regeneration_attempts: number;
}

export const referencesService = {
  /**
   * Get all reference materials for a subject
   */
  async listReferences(subjectId: string): Promise<ReferenceMaterialsResponse> {
    const response = await apiClient.get<ReferenceMaterialsResponse>(
      `/documents/reference/list?subject_id=${subjectId}`
    );
    return response.data;
  },

  /**
   * Upload a reference book PDF
   */
  async uploadReferenceBook(
    subjectId: string,
    uri: string,
    filename: string,
    mimeType: string
  ): Promise<{ document_id: string; status: string }> {
    const formData = new FormData();
    
    formData.append('file', {
      uri,
      name: filename,
      type: mimeType,
    } as unknown as Blob);
    formData.append('index_type', 'reference_book');
    formData.append('subject_id', subjectId);

    const response = await apiClient.post('/documents/reference/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: 120000, // 2 minutes for file upload
    });

    return response.data;
  },

  /**
   * Upload a template question paper PDF
   */
  async uploadTemplatePaper(
    subjectId: string,
    uri: string,
    filename: string,
    mimeType: string
  ): Promise<{ document_id: string; status: string }> {
    const formData = new FormData();
    
    formData.append('file', {
      uri,
      name: filename,
      type: mimeType,
    } as unknown as Blob);
    formData.append('index_type', 'template_paper');
    formData.append('subject_id', subjectId);

    const response = await apiClient.post('/documents/reference/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: 120000, // 2 minutes for file upload
    });

    return response.data;
  },

  /**
   * Delete a reference document
   */
  async deleteReference(documentId: string): Promise<void> {
    await apiClient.delete(`/documents/${documentId}`);
  },

  /**
   * Get user's novelty settings
   */
  async getNoveltySettings(): Promise<NoveltySettings> {
    const response = await apiClient.get<NoveltySettings>('/questions/novelty/settings');
    return response.data;
  },

  /**
   * Update user's novelty settings
   */
  async updateNoveltySettings(settings: Partial<NoveltySettings>): Promise<NoveltySettings> {
    const response = await apiClient.put<NoveltySettings>('/questions/novelty/settings', settings);
    return response.data;
  },
};

export default referencesService;
