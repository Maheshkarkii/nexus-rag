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

const getBaseApiUrl = (): string => {
  const envUrl = process.env.NEXT_PUBLIC_API_URL?.trim();
  
  // 1. If explicit valid environment variable provided and not default localhost in browser production
  if (typeof window !== "undefined") {
    // Check for user-configured custom backend URL override in localStorage
    const stored = localStorage.getItem("nexus_custom_api_url")?.trim();
    if (stored) return stored;

    const hostname = window.location.hostname;
    const isVercel = hostname.includes("vercel.app") || hostname.includes("nexus-rag");

    // If running on Vercel and env is empty or accidentally points to localhost, route to Render
    if (isVercel && (!envUrl || envUrl.includes("localhost") || envUrl.includes("127.0.0.1"))) {
      return "https://nexus-rag-backend.onrender.com";
    }
  }

  return envUrl || "http://127.0.0.1:8000";
};

export const config: AppConfig = {
  appName: process.env.NEXT_PUBLIC_APP_NAME || "AI Research Assistant",
  get apiUrl(): string {
    return getBaseApiUrl();
  },
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
