// ============================================================
// Axios API client — wraps all backend endpoints
// Base URL: http://localhost:8000/api/v1
// ============================================================

import axios from "axios";
import type {
  ChatAssessRequest,
  ChatAssessResponse,
  FundsResponse,
  OptimizeRequest,
  OptimizationResponse,
} from "@/types";

// Default to same-origin `/api/v1` so Next.js rewrites proxy to FastAPI (see next.config.mjs).
// Set NEXT_PUBLIC_API_URL to a full URL only when you intentionally bypass the proxy.
const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "/api/v1";

const apiClient = axios.create({
  baseURL: BASE_URL,
  headers: { "Content-Type": "application/json" },
  timeout: 30_000,
});

// ---- GET /api/v1/funds ----
export async function fetchFunds(): Promise<FundsResponse> {
  const { data } = await apiClient.get<FundsResponse>("/funds");
  return data;
}

// ---- POST /api/v1/optimize ----
export async function runOptimization(
  payload: OptimizeRequest
): Promise<OptimizationResponse> {
  const { data } = await apiClient.post<OptimizationResponse>(
    "/optimize",
    payload,
    {
      // Avoid any intermediary caching of POST (browser / dev proxy quirks).
      headers: { "Cache-Control": "no-store", Pragma: "no-cache" },
    }
  );
  return data;
}

// ---- POST /api/v1/chat/assess ----
export async function sendChatMessage(
  payload: ChatAssessRequest
): Promise<ChatAssessResponse> {
  const { data } = await apiClient.post<ChatAssessResponse>("/chat/assess", payload);
  return data;
}
