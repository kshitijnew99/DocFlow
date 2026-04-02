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

// ── Upload ────────────────────────────────────────────────────────────────────

export async function uploadDocuments(files: File[]): Promise<UploadResponse> {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  const { data } = await api.post<UploadResponse>("/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
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
