/**
 * Documents API Service
 */

import apiClient from './api';
import * as FileSystem from 'expo-file-system';
import * as DocumentPicker from 'expo-document-picker';

export interface Document {
  id: string;
  filename: string;
  file_size_bytes: number;
  mime_type: string | null;
  processing_status: 'pending' | 'processing' | 'completed' | 'failed';
  total_chunks: number | null;
  total_tokens: number | null;
  upload_timestamp: string;
  processed_at: string | null;
  document_metadata: Record<string, unknown> | null;
  questions_generated: number;
}

export interface DocumentListItem {
  id: string;
  filename: string;
  processing_status: string;
  upload_timestamp: string;
  total_chunks: number | null;
  questions_generated: number;
}

export interface Pagination {
  page: number;
  limit: number;
  total: number;
  total_pages: number;
}

export interface DocumentListResponse {
  documents: DocumentListItem[];
  pagination: Pagination;
}

export interface DocumentChunk {
  index: number;
  text: string;
  token_count: number | null;
  page_number: number | null;
}

export const documentsService = {
  /**
   * Upload a document
   */
  async uploadDocument(uri: string, filename: string, mimeType: string): Promise<{ document_id: string; status: string }> {
    const formData = new FormData();
    
    // For React Native, we need to create a proper file object
    formData.append('file', {
      uri,
      name: filename,
      type: mimeType,
    } as unknown as Blob);

    const response = await apiClient.post('/documents/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });

    return response.data;
  },

  /**
   * Pick and upload a document
   */
  async pickAndUploadDocument(): Promise<{ document_id: string; status: string } | null> {
    const result = await DocumentPicker.getDocumentAsync({
      type: ['application/pdf', 'text/plain', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
      copyToCacheDirectory: true,
    });

    if (result.canceled || !result.assets || result.assets.length === 0) {
      return null;
    }

    const file = result.assets[0];
    return this.uploadDocument(file.uri, file.name, file.mimeType || 'application/pdf');
  },

  /**
   * List documents with pagination
   */
  async listDocuments(
    page: number = 1,
    limit: number = 20,
    status?: string
  ): Promise<DocumentListResponse> {
    const params = new URLSearchParams({
      page: page.toString(),
      limit: limit.toString(),
    });
    if (status) {
      params.append('status', status);
    }

    const response = await apiClient.get<DocumentListResponse>(`/documents?${params}`);
    return response.data;
  },

  /**
   * Get document details
   */
  async getDocument(documentId: string): Promise<Document> {
    const response = await apiClient.get<Document>(`/documents/${documentId}`);
    return response.data;
  },

  /**
   * Delete a document
   */
  async deleteDocument(documentId: string): Promise<void> {
    await apiClient.delete(`/documents/${documentId}`);
  },

  /**
   * Get document chunks (for preview)
   */
  async getDocumentChunks(documentId: string): Promise<{
    document_id: string;
    total_chunks: number;
    chunks: DocumentChunk[];
  }> {
    const response = await apiClient.get(`/documents/${documentId}/chunks`);
    return response.data;
  },

  /**
   * Get document processing status
   */
  async getDocumentStatus(documentId: string): Promise<{
    document_id: string;
    filename: string;
    status: string;
    total_chunks: number | null;
    total_tokens: number | null;
    processed_at: string | null;
  }> {
    const response = await apiClient.get(`/documents/${documentId}/status`);
    return response.data;
  },
};

export default documentsService;
