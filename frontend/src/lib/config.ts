/**
 * Client and Server environment configuration abstraction.
 * Ensures the API base URL is centrally configured and never hardcoded.
 */

export interface AppConfig {
  appName: string;
  apiUrl: string;
  isProduction: boolean;
  version: string;
}

export const config: AppConfig = {
  appName: process.env.NEXT_PUBLIC_APP_NAME || "AI Research Assistant",
  apiUrl: process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000",
  isProduction: process.env.NODE_ENV === "production",
  version: "0.1.0",
};

/**
 * Returns the fully qualified API endpoint URL for a given relative path.
 *
 * @param path - Relative API route (e.g. "/api/v1/health")
 * @returns Fully qualified URL string
 */
export function getApiUrl(path: string): string {
  const cleanBase = config.apiUrl.replace(/\/+$/, "");
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  return `${cleanBase}${cleanPath}`;
}
