/**
 * Reference Materials API Service
 * Handles reference books, template question papers, and reference questions per subject
 */

import apiClient from './api';

export interface ReferenceDocument {
  id: string;
  filename: string;
  file_size_bytes: number;
  mime_type: string | null;
  index_type: 'reference_book' | 'template_paper' | 'reference_questions';
  subject_id: string;
  processing_status: 'pending' | 'processing' | 'completed' | 'failed';
  total_chunks: number | null;
  upload_timestamp: string;
  processed_at: string | null;
  parsed_question_count?: number | null;
}

export interface ReferenceMaterialsResponse {
  reference_books: ReferenceDocument[];
  template_papers: ReferenceDocument[];
  reference_questions: ReferenceDocument[];
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
      timeout: 600000, // 10 minutes for large file upload
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
      timeout: 600000, // 10 minutes for large file upload
    });

    return response.data;
  },

  /**
   * Upload reference questions from Excel/CSV
   */
  async uploadReferenceQuestions(
    subjectId: string,
    uri: string,
    filename: string,
    mimeType: string
  ): Promise<{ document_id: string; status: string; message: string }> {
    const formData = new FormData();

    formData.append('file', {
      uri,
      name: filename,
      type: mimeType,
    } as unknown as Blob);
    formData.append('index_type', 'reference_questions');
    formData.append('subject_id', subjectId);

    const response = await apiClient.post('/documents/reference/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: 600000, // 10 minutes for large file upload
    });

    return response.data;
  },

  /**
   * Delete a reference document
   */
  async deleteReference(documentId: string): Promise<void> {
    await apiClient.delete(`/documents/${documentId}`);
  },
};

export default referencesService;
