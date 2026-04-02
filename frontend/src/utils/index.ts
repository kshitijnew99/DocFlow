import { clsx, type ClassValue } from "clsx";
import type { JobStatus } from "@/types";

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const secs = Math.floor(diff / 1000);
  if (secs < 60) return `${secs}s ago`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export const STATUS_COLORS: Record<JobStatus, string> = {
  queued: "text-yellow-400 bg-yellow-400/10 border-yellow-400/30",
  processing: "text-blue-400 bg-blue-400/10 border-blue-400/30",
  completed: "text-emerald-400 bg-emerald-400/10 border-emerald-400/30",
  failed: "text-red-400 bg-red-400/10 border-red-400/30",
  finalized: "text-purple-400 bg-purple-400/10 border-purple-400/30",
};

export const STATUS_LABELS: Record<JobStatus, string> = {
  queued: "Queued",
  processing: "Processing",
  completed: "Completed",
  failed: "Failed",
  finalized: "Finalized",
};

export const STAGE_LABELS: Record<string, string> = {
  document_received: "Document Received",
  parsing_started: "Parsing Started",
  parsing_completed: "Parsing Complete",
  extraction_started: "Extraction Started",
  extraction_completed: "Extraction Complete",
  final_result_stored: "Storing Result",
  job_completed: "Job Complete",
  job_failed: "Job Failed",
};

export const FILE_TYPE_ICONS: Record<string, string> = {
  ".txt": "📄",
  ".pdf": "📕",
  ".csv": "📊",
  ".json": "📋",
  ".md": "📝",
  ".xml": "🗂️",
};
