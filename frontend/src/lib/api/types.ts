/**
 * Centralized API response and request type definitions.
 * Separates backend contract interfaces from UI presentation components.
 */

export interface HealthResponse {
  status: string;
}

export interface DependencyCheckInfo {
  name: string;
  status: string;
  details?: string;
}

export interface ReadinessResponse {
  status: string;
  environment: string;
  version: string;
  timestamp: string;
  checks: {
    configuration: DependencyCheckInfo;
    database: DependencyCheckInfo;
    vector_store: DependencyCheckInfo;
    [key: string]: DependencyCheckInfo;
  };
}

export interface ServiceInfoResponse {
  name: string;
  version: string;
  environment: string;
  status: string;
  health: string;
  ready: string;
  docs: string;
}

export interface ProjectResponse {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreatePayload {
  name: string;
  description?: string | null;
}

export interface ProjectUpdatePayload {
  name?: string;
  description?: string | null;
}

export type DocumentStatus = "uploaded" | "processing" | "ready" | "failed";

export interface DocumentResponse {
  id: string;
  project_id: string;
  original_filename: string;
  mime_type: string;
  file_extension: string;
  file_size: number;
  status: DocumentStatus | string;
  extracted_character_count?: number | null;
  extracted_word_count?: number | null;
  processing_error?: string | null;
  processed_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentContentResponse {
  id: string;
  project_id: string;
  original_filename: string;
  mime_type: string;
  file_extension: string;
  file_size: number;
  status: DocumentStatus | string;
  extracted_text?: string | null;
  extracted_character_count?: number | null;
  extracted_word_count?: number | null;
  extracted_metadata?: Record<string, unknown> | null;
  processing_error?: string | null;
  processed_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ApiErrorEnvelope {
  error?: {
    code?: string;
    message?: string;
    details?: unknown;
  };
  detail?: string | { msg?: string; type?: string; loc?: string[] }[];
}

export interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: BodyInit | Record<string, unknown> | unknown[] | null;
  timeoutMs?: number;
  params?: Record<string, string | number | boolean | undefined | null>;
}

export interface ApiResult<T> {
  data: T | null;
  error: Error | null;
  latencyMs: number;
  isSuccess: boolean;
}
