import { cn, STATUS_COLORS, STATUS_LABELS } from "@/utils";
import type { JobStatus } from "@/types";

interface Props {
  status: JobStatus;
  className?: string;
}

export default function StatusBadge({ status, className }: Props) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border",
        STATUS_COLORS[status],
        className
      )}
    >
      {/* Dot */}
      <span
        className={cn(
          "w-1.5 h-1.5 rounded-full",
          status === "processing" && "animate-pulse"
        )}
        style={{
          background: "currentColor",
        }}
      />
      {STATUS_LABELS[status]}
    </span>
  );
}
