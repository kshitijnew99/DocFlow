import Link from "next/link";
import { ChevronRight, RefreshCw } from "lucide-react";
import StatusBadge from "./StatusBadge";
import ProgressBar from "./ProgressBar";
import { cn, formatBytes, timeAgo, STAGE_LABELS, FILE_TYPE_ICONS } from "@/utils";
import type { DocumentListItem } from "@/types";

interface Props {
  doc: DocumentListItem;
  onRetry?: (jobId: string) => void;
  selected?: boolean;
  onSelect?: (jobId: string, checked: boolean) => void;
}

export default function JobCard({ doc, onRetry, selected, onSelect }: Props) {
  const job = doc.job;
  const ext = doc.file_type?.toLowerCase() ?? ".txt";
  const icon = FILE_TYPE_ICONS[ext] ?? "📄";

  return (
    <div
      className={cn(
        "group rounded-xl border transition-all duration-200 hover:border-accent/50 animate-slide-in",
        selected && "border-accent/70 bg-accent/5"
      )}
      style={{
        background: "var(--surface-1)",
        borderColor: selected ? "var(--accent)" : "var(--border)",
      }}
    >
      <div className="flex items-center gap-4 px-4 py-3">
        {/* Checkbox */}
        {job && (job.status === "completed" || job.status === "finalized") && onSelect && (
          <input
            type="checkbox"
            checked={selected}
            onChange={(e) => onSelect(job.id, e.target.checked)}
            className="w-4 h-4 rounded accent-violet-500 cursor-pointer"
            onClick={(e) => e.stopPropagation()}
          />
        )}

        {/* File icon */}
        <span className="text-2xl shrink-0">{icon}</span>

        {/* Main info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <p
                className="font-medium text-sm truncate"
                style={{ color: "var(--text)" }}
              >
                {doc.original_filename}
              </p>
              <p className="text-xs mt-0.5" style={{ color: "var(--muted)" }}>
                {formatBytes(doc.file_size)} · {timeAgo(doc.uploaded_at)}
                {job?.current_stage && job.status === "processing" && (
                  <span style={{ color: "var(--accent)" }}>
                    {" "}· {STAGE_LABELS[job.current_stage] ?? job.current_stage}
                  </span>
                )}
              </p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {job && <StatusBadge status={job.status} />}
            </div>
          </div>

          {/* Progress bar (only when processing) */}
          {job && job.status === "processing" && (
            <ProgressBar
              progress={job.progress}
              status={job.status}
              showLabel={false}
              className="mt-2"
            />
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1 shrink-0">
          {job?.status === "failed" && onRetry && (
            <button
              onClick={(e) => {
                e.preventDefault();
                onRetry(job.id);
              }}
              className="p-1.5 rounded-lg text-xs transition-colors hover:bg-yellow-500/20"
              style={{ color: "var(--warning)" }}
              title="Retry"
            >
              <RefreshCw size={14} />
            </button>
          )}
          {job && (
            <Link
              href={`/jobs/${job.id}`}
              className="p-1.5 rounded-lg transition-colors hover:bg-surface-3"
              style={{ color: "var(--muted)" }}
              title="View details"
            >
              <ChevronRight size={16} />
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
