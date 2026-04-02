export type JobStatus = "queued" | "processing" | "completed" | "failed" | "finalized";

export interface JobSummary {
  id: string;
  status: JobStatus;
  progress: number;
  current_stage: string | null;
  retry_count: number;
  created_at: string;
  completed_at: string | null;
}

export interface Document {
  id: string;
  filename: string;
  original_filename: string;
  file_size: number;
  file_type: string;
  mime_type: string | null;
  uploaded_at: string;
  job?: JobSummary;
}

export interface DocumentListItem {
  id: string;
  original_filename: string;
  file_size: number;
  file_type: string;
  uploaded_at: string;
  job?: JobSummary;
}

export interface PaginatedDocuments {
  items: DocumentListItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface JobEvent {
  id: string;
  event_type: string;
  stage: string | null;
  progress: number;
  message: string | null;
  metadata: Record<string, unknown> | null;
  occurred_at: string;
}

export interface ExtractedResult {
  id: string;
  title: string | null;
  category: string | null;
  summary: string | null;
  keywords: string[] | null;
  word_count: number | null;
  char_count: number | null;
  language: string | null;
  structured_data: Record<string, unknown> | null;
  is_finalized: boolean;
  finalized_at: string | null;
  reviewed_data: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface JobDetail extends JobSummary {
  document_id: string;
  celery_task_id: string | null;
  error_message: string | null;
  max_retries: number;
  started_at: string | null;
  document?: Document;
  result?: ExtractedResult;
  events: JobEvent[];
}

export interface ProgressEvent {
  job_id: string;
  event_type: string;
  stage: string | null;
  progress: number;
  message: string | null;
  status: string | null;
  metadata: Record<string, unknown> | null;
  timestamp: string;
}

export interface UploadResponse {
  documents: Document[];
  jobs: JobSummary[];
  message: string;
}

export interface UpdateResultRequest {
  title?: string;
  category?: string;
  summary?: string;
  keywords?: string[];
  reviewed_data?: Record<string, unknown>;
}

export interface ExportRequest {
  job_ids: string[];
  format: "json" | "csv";
}
