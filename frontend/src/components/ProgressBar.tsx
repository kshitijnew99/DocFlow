import { cn } from "@/utils";
import type { JobStatus } from "@/types";

interface Props {
  progress: number; // 0–1
  status: JobStatus;
  showLabel?: boolean;
  className?: string;
}

export default function ProgressBar({ progress, status, showLabel = true, className }: Props) {
  const pct = Math.round(progress * 100);
  const isActive = status === "processing";
  const isFailed = status === "failed";

  return (
    <div className={cn("space-y-1", className)}>
      {showLabel && (
        <div className="flex justify-between text-xs" style={{ color: "var(--muted)" }}>
          <span>Progress</span>
          <span>{pct}%</span>
        </div>
      )}
      <div
        className="relative h-1.5 rounded-full overflow-hidden"
        style={{ background: "var(--surface-3)" }}
      >
        <div
          className={cn(
            "absolute inset-y-0 left-0 rounded-full transition-all duration-700 ease-out",
            isActive && "progress-shimmer",
            isFailed && "bg-red-500"
          )}
          style={{
            width: `${pct}%`,
            background: isActive
              ? undefined
              : isFailed
              ? undefined
              : status === "completed" || status === "finalized"
              ? "var(--success)"
              : "var(--accent)",
          }}
        />
      </div>
    </div>
  );
}
