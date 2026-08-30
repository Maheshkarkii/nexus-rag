/**
 * Centralized HTTP API Client for AI Research Assistant.
 * Provides unified request configuration, structured error handling, and typed responses.
 */

import { config } from "@/lib/config";
import { ApiError, NetworkError } from "./errors";
import {
  HealthResponse,
  ReadinessResponse,
  ServiceInfoResponse,
  ProjectResponse,
  ProjectCreatePayload,
  ProjectUpdatePayload,
  DocumentResponse,
  DocumentContentResponse,
  RequestOptions,
  ApiResult,
} from "./types";

export interface ApiClientConfig {
  baseUrl?: string;
  defaultTimeoutMs?: number;
  defaultHeaders?: Record<string, string>;
}

export class ApiClient {
  private readonly baseUrl: string;
  private readonly defaultTimeoutMs: number;
  private readonly defaultHeaders: Record<string, string>;

  constructor(clientConfig: ApiClientConfig = {}) {
    this.baseUrl = (clientConfig.baseUrl || config.apiUrl).replace(/\/+$/, "");
    this.defaultTimeoutMs = clientConfig.defaultTimeoutMs || 180000; // 3 minutes to accommodate Render cold starts
    this.defaultHeaders = {
      Accept: "application/json",
      ...(clientConfig.defaultHeaders || {}),
    };
  }

  /**
   * Execute an HTTP request with timeout, JSON formatting, and typed error handling.
   */
  public async request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
    const { timeoutMs = this.defaultTimeoutMs, params, headers, body, ...fetchOptions } = options;

    // 1. Build destination URL
    const url = this.buildUrl(endpoint, params);

    // 2. Prepare headers
    const requestHeaders: Record<string, string> = {
      ...this.defaultHeaders,
      ...((headers as Record<string, string>) || {}),
    };

    let serializedBody: BodyInit | null = null;
    if (body !== undefined && body !== null) {
      if (
        typeof body === "object" &&
        !(body instanceof FormData) &&
        !(body instanceof Blob) &&
        !(body instanceof URLSearchParams)
      ) {
        serializedBody = JSON.stringify(body);
        requestHeaders["Content-Type"] = "application/json";
      } else {
        serializedBody = body as BodyInit;
        if (body instanceof FormData) {
          delete requestHeaders["Content-Type"];
        }
      }
    }

    // 3. Set up AbortController timeout
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const response = await fetch(url, {
        ...fetchOptions,
        headers: requestHeaders,
        body: serializedBody,
        signal: controller.signal,
      });

      clearTimeout(timer);

      // 4. Handle non-2xx HTTP responses
      if (!response.ok) {
        let errorData: unknown = null;
        try {
          errorData = await response.json();
        } catch {
          try {
            errorData = await response.text();
          } catch {
            errorData = null;
          }
        }

        throw ApiError.fromResponse(response.status, errorData, response.statusText);
      }

      // 5. Handle empty responses (e.g. HTTP 204)
      if (response.status === 204) {
        return null as T;
      }

      // 6. Parse JSON payload
      return (await response.json()) as T;
    } catch (err: unknown) {
      clearTimeout(timer);

      if (err instanceof ApiError) {
        throw err;
      }

      // Handle fetch network failures and timeout aborts
      if (err instanceof DOMException && err.name === "AbortError") {
        throw new NetworkError("Request timed out. The backend server may be waking up from cold sleep (Render free tier). Please retry in a few seconds.");
      }

      const rawMessage = err instanceof Error ? err.message : String(err);
      if (
        rawMessage.toLowerCase().includes("failed to fetch") ||
        rawMessage.toLowerCase().includes("networkerror")
      ) {
        throw new NetworkError(
          "Unable to connect to the research assistant backend. The server may still be spinning up from cold sleep."
        );
      }

      throw new NetworkError(`Network communication error: ${rawMessage}`);

    }
  }

  /**
   * Execute request and return a safe result envelope without throwing.
   */
  public async safeRequest<T>(
    endpoint: string,
    options: RequestOptions = {}
  ): Promise<ApiResult<T>> {
    const start = performance.now();
    try {
      const data = await this.request<T>(endpoint, options);
      const latencyMs = Math.round(performance.now() - start);
      return { data, error: null, latencyMs, isSuccess: true };
    } catch (err: unknown) {
      const latencyMs = Math.round(performance.now() - start);
      const errorInstance = err instanceof Error ? err : new Error(String(err));
      return { data: null, error: errorInstance, latencyMs, isSuccess: false };
    }
  }

  // ---------------------------------------------------------------------------
  // Convenience HTTP Methods
  // ---------------------------------------------------------------------------
  public async get<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: "GET" });
  }

  public async post<T>(endpoint: string, data?: unknown, options: RequestOptions = {}): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: "POST", body: data as BodyInit });
  }

  public async put<T>(endpoint: string, data?: unknown, options: RequestOptions = {}): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: "PUT", body: data as BodyInit });
  }

  public async patch<T>(
    endpoint: string,
    data?: unknown,
    options: RequestOptions = {}
  ): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: "PATCH", body: data as BodyInit });
  }

  public async delete<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: "DELETE" });
  }

  // ---------------------------------------------------------------------------
  // Research Project Management Methods
  // ---------------------------------------------------------------------------
  public async listProjects(options: RequestOptions = {}): Promise<ProjectResponse[]> {
    return this.get<ProjectResponse[]>("/api/v1/projects", options);
  }

  public async getProject(
    projectId: string,
    options: RequestOptions = {}
  ): Promise<ProjectResponse> {
    return this.get<ProjectResponse>(`/api/v1/projects/${projectId}`, options);
  }

  public async createProject(
    payload: ProjectCreatePayload,
    options: RequestOptions = {}
  ): Promise<ProjectResponse> {
    return this.post<ProjectResponse>("/api/v1/projects", payload, options);
  }

  public async updateProject(
    projectId: string,
    payload: ProjectUpdatePayload,
    options: RequestOptions = {}
  ): Promise<ProjectResponse> {
    return this.patch<ProjectResponse>(`/api/v1/projects/${projectId}`, payload, options);
  }

  public async deleteProject(projectId: string, options: RequestOptions = {}): Promise<void> {
    return this.delete<void>(`/api/v1/projects/${projectId}`, options);
  }

  // ---------------------------------------------------------------------------
  // Research Document Management Methods (Stage 8 & 9)
  // ---------------------------------------------------------------------------
  public async uploadDocument(
    projectId: string,
    file: File,
    options: RequestOptions = {}
  ): Promise<DocumentResponse> {
    const formData = new FormData();
    formData.append("file", file);
    return this.post<DocumentResponse>(`/api/v1/projects/${projectId}/documents`, formData, options);
  }

  public async listDocuments(
    projectId: string,
    options: RequestOptions = {}
  ): Promise<DocumentResponse[]> {
    return this.get<DocumentResponse[]>(`/api/v1/projects/${projectId}/documents`, options);
  }

  public async getDocument(
    projectId: string,
    documentId: string,
    options: RequestOptions = {}
  ): Promise<DocumentResponse> {
    return this.get<DocumentResponse>(`/api/v1/projects/${projectId}/documents/${documentId}`, options);
  }

  public async processDocument(
    projectId: string,
    documentId: string,
    options: RequestOptions = {}
  ): Promise<DocumentResponse> {
    return this.post<DocumentResponse>(
      `/api/v1/projects/${projectId}/documents/${documentId}/process`,
      undefined,
      options
    );
  }

  public async runDocumentPipeline(
    projectId: string,
    documentId: string,
    params?: { chunkSize?: number; chunkOverlap?: number },
    options: RequestOptions = {}
  ): Promise<DocumentResponse> {
    const searchParams = new URLSearchParams();
    if (params?.chunkSize) searchParams.set("chunk_size", String(params.chunkSize));
    if (params?.chunkOverlap) searchParams.set("chunk_overlap", String(params.chunkOverlap));
    const qs = searchParams.toString() ? `?${searchParams.toString()}` : "";
    return this.post<DocumentResponse>(
      `/api/v1/projects/${projectId}/documents/${documentId}/pipeline${qs}`,
      undefined,
      options
    );
  }

  public async chunkDocument(
    projectId: string,
    documentId: string,
    params?: { chunkSize?: number; chunkOverlap?: number },
    options: RequestOptions = {}
  ): Promise<unknown> {
    const searchParams = new URLSearchParams();
    if (params?.chunkSize) searchParams.set("chunk_size", String(params.chunkSize));
    if (params?.chunkOverlap) searchParams.set("chunk_overlap", String(params.chunkOverlap));
    const qs = searchParams.toString() ? `?${searchParams.toString()}` : "";
    return this.post<unknown>(
      `/api/v1/projects/${projectId}/documents/${documentId}/chunk${qs}`,
      undefined,
      options
    );
  }


  public async embedDocument(
    projectId: string,
    documentId: string,
    options: RequestOptions = {}
  ): Promise<unknown> {
    return this.post<unknown>(
      `/api/v1/projects/${projectId}/documents/${documentId}/embed`,
      undefined,
      options
    );
  }

  public async indexDocument(
    projectId: string,
    documentId: string,
    options: RequestOptions = {}
  ): Promise<unknown> {
    return this.post<unknown>(
      `/api/v1/projects/${projectId}/documents/${documentId}/index`,
      undefined,
      options
    );
  }

  public async getDocumentContent(
    projectId: string,
    documentId: string,
    options: RequestOptions = {}
  ): Promise<DocumentContentResponse> {
    return this.get<DocumentContentResponse>(
      `/api/v1/projects/${projectId}/documents/${documentId}/content`,
      options
    );
  }

  public async deleteDocument(
    projectId: string,
    documentId: string,
    options: RequestOptions = {}
  ): Promise<void> {
    return this.delete<void>(`/api/v1/projects/${projectId}/documents/${documentId}`, options);
  }

  // ---------------------------------------------------------------------------
  // Domain Probing Methods
  // ---------------------------------------------------------------------------
  public async checkHealth(options: RequestOptions = {}): Promise<HealthResponse> {
    return this.get<HealthResponse>("/api/v1/health", { cache: "no-store", ...options });
  }

  public async checkReadiness(options: RequestOptions = {}): Promise<ReadinessResponse> {
    return this.get<ReadinessResponse>("/api/v1/health/ready", { cache: "no-store", ...options });
  }

  public async getServiceInfo(options: RequestOptions = {}): Promise<ServiceInfoResponse> {
    return this.get<ServiceInfoResponse>("/", { cache: "no-store", ...options });
  }

  // ---------------------------------------------------------------------------
  // Conversation & RAG Query Methods
  // ---------------------------------------------------------------------------
  public async createConversation(
    projectId: string,
    title?: string,
    options: RequestOptions = {}
  ): Promise<unknown> {
    return this.post<unknown>(`/api/v1/projects/${projectId}/conversations`, { title }, options);
  }

  public async listConversations(
    projectId: string,
    options: RequestOptions = {}
  ): Promise<unknown[]> {
    return this.get<unknown[]>(`/api/v1/projects/${projectId}/conversations`, options);
  }

  public async getConversationMessages(
    conversationId: string,
    options: RequestOptions = {}
  ): Promise<unknown[]> {
    return this.get<unknown[]>(`/api/v1/conversations/${conversationId}/messages`, options);
  }

  public async deleteConversation(
    conversationId: string,
    options: RequestOptions = {}
  ): Promise<void> {
    return this.delete<void>(`/api/v1/conversations/${conversationId}`, options);
  }

  public async askQuestion(
    projectId: string,
    payload: {
      query: string;
      top_k?: number;
      document_ids?: string[] | null;
      file_types?: string[] | null;
      conversation_id?: string | null;
    },
    options: RequestOptions = {}
  ): Promise<unknown> {
    return this.post<unknown>(`/api/v1/projects/${projectId}/ask`, payload, {
      timeoutMs: 120000,
      ...options,
    });
  }

  // ---------------------------------------------------------------------------
  // Stage 21 Report Generation & Export Methods
  // ---------------------------------------------------------------------------
  public async generateReport(
    projectId: string,
    payload: {
      report_type?: string;
      query?: string;
      conversation_id?: string | null;
      document_ids?: string[] | null;
    },
    options: RequestOptions = {}
  ): Promise<unknown> {
    return this.post<unknown>(`/api/v1/projects/${projectId}/reports`, payload, {
      timeoutMs: 180000,
      ...options,
    });
  }

  public async listReports(
    projectId: string,
    options: RequestOptions = {}
  ): Promise<unknown[]> {
    return this.get<unknown[]>(`/api/v1/projects/${projectId}/reports`, options);
  }

  public async getReport(
    projectId: string,
    report_id: string,
    options: RequestOptions = {}
  ): Promise<unknown> {
    return this.get<unknown>(`/api/v1/projects/${projectId}/reports/${report_id}`, options);
  }

  public async deleteReport(
    projectId: string,
    report_id: string,
    options: RequestOptions = {}
  ): Promise<void> {
    return this.delete<void>(`/api/v1/projects/${projectId}/reports/${report_id}`, options);
  }

  public getExportUrl(projectId: string, report_id: string, format: string): string {
    return `${this.baseUrl}/api/v1/projects/${projectId}/reports/${report_id}/export/${format}`;
  }

  private buildUrl(
    endpoint: string,
    params?: Record<string, string | number | boolean | undefined | null>
  ): string {
    const cleanPath = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
    const fullUrl = `${this.baseUrl}${cleanPath}`;

    if (!params) {
      return fullUrl;
    }

    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, val]) => {
      if (val !== undefined && val !== null) {
        searchParams.append(key, String(val));
      }
    });

    const queryString = searchParams.toString();
    return queryString ? `${fullUrl}?${queryString}` : fullUrl;
  }
}

/**
 * Singleton API client instance configured with the environment-driven base URL.
 */
export const apiClient = new ApiClient();
