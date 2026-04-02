import axios from "axios";
import type {
  PaginatedDocuments,
  JobDetail,
  ExtractedResult,
  UploadResponse,
  UpdateResultRequest,
  ExportRequest,
  JobSummary,
} from "@/types";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: `${BASE}/api/v1`,
  timeout: 30_000,
});

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

async function waitForBackendReady(maxWaitMs = 90_000): Promise<void> {
  const started = Date.now();
  let lastError: unknown = null;

  while (Date.now() - started < maxWaitMs) {
    try {
      await api.get("/health", { timeout: 8_000 });
      return;
    } catch (err) {
      lastError = err;
      await delay(2_000);
    }
  }

  if (axios.isAxiosError(lastError) && lastError.message) {
    throw new Error(`Backend is waking up. ${lastError.message}`);
  }
  throw new Error("Backend is waking up. Please try again in a few seconds.");
}

function isTransientUploadError(error: unknown): boolean {
  if (!axios.isAxiosError(error)) return false;
  if (error.code === "ECONNABORTED") return true;
  if (!error.response) return true;
  return [429, 502, 503, 504].includes(error.response.status);
}

// ── Upload ────────────────────────────────────────────────────────────────────

export async function uploadDocuments(files: File[]): Promise<UploadResponse> {
  await waitForBackendReady();

  const form = new FormData();
  files.forEach((f) => form.append("files", f));

  let lastError: unknown = null;
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      const { data } = await api.post<UploadResponse>("/upload", form, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 120_000,
      });
      return data;
    } catch (error) {
      lastError = error;
      if (!isTransientUploadError(error) || attempt === 1) {
        throw error;
      }
      await delay(1_500);
    }
  }

  throw lastError;
}

// ── Documents list ────────────────────────────────────────────────────────────

export async function listDocuments(params: {
  page?: number;
  page_size?: number;
  search?: string;
  status?: string;
  sort_by?: string;
  sort_dir?: string;
}): Promise<PaginatedDocuments> {
  const { data } = await api.get<PaginatedDocuments>("/documents", { params });
  return data;
}

// ── Job detail ────────────────────────────────────────────────────────────────

export async function getJob(jobId: string): Promise<JobDetail> {
  const { data } = await api.get<JobDetail>(`/jobs/${jobId}`);
  return data;
}

// ── SSE stream URL (used directly in EventSource) ────────────────────────────

export function getStreamUrl(jobId: string): string {
  return `${BASE}/api/v1/jobs/${jobId}/stream`;
}

// ── Retry ─────────────────────────────────────────────────────────────────────

export async function retryJob(jobId: string): Promise<JobSummary> {
  const { data } = await api.post<JobSummary>(`/jobs/${jobId}/retry`);
  return data;
}

// ── Edit result ───────────────────────────────────────────────────────────────

export async function updateResult(
  jobId: string,
  payload: UpdateResultRequest
): Promise<ExtractedResult> {
  const { data } = await api.patch<ExtractedResult>(
    `/jobs/${jobId}/result`,
    payload
  );
  return data;
}

// ── Finalize ──────────────────────────────────────────────────────────────────

export async function finalizeResult(
  jobId: string,
  reviewedData?: Record<string, unknown>
): Promise<ExtractedResult> {
  const { data } = await api.post<ExtractedResult>(`/jobs/${jobId}/finalize`, {
    reviewed_data: reviewedData,
  });
  return data;
}

// ── Export ────────────────────────────────────────────────────────────────────

export async function exportResults(payload: ExportRequest): Promise<void> {
  const response = await api.post("/export", payload, {
    responseType: "blob",
  });
  const ext = payload.format === "csv" ? "csv" : "json";
  const url = URL.createObjectURL(response.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = `docflow_export.${ext}`;
  a.click();
  URL.revokeObjectURL(url);
}

export default api;
