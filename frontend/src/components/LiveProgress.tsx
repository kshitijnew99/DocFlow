import { useEffect, useState } from "react";
import { useJobStream } from "@/hooks/useJobStream";
import ProgressBar from "./ProgressBar";
import { STAGE_LABELS } from "@/utils";
import type { JobStatus, ProgressEvent } from "@/types";

interface Props {
  jobId: string;
  initialStatus: JobStatus;
  initialProgress: number;
  onStatusChange?: (status: JobStatus, progress: number) => void;
}

export default function LiveProgress({
  jobId,
  initialStatus,
  initialProgress,
  onStatusChange,
}: Props) {
  const [status, setStatus] = useState<JobStatus>(initialStatus);
  const [progress, setProgress] = useState(initialProgress);
  const [stage, setStage] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [events, setEvents] = useState<ProgressEvent[]>([]);

  const isTerminal = status === "completed" || status === "failed" || status === "finalized";

  useJobStream(jobId, {
    enabled: !isTerminal,
    onEvent: (ev) => {
      setProgress(ev.progress);
      if (ev.stage) setStage(ev.stage);
      if (ev.message) setMessage(ev.message);
      if (ev.status) setStatus(ev.status as JobStatus);
      setEvents((prev) => [ev, ...prev].slice(0, 12));
      onStatusChange?.(ev.status as JobStatus, ev.progress);
    },
  });

  // Sync from props if already terminal
  useEffect(() => {
    setStatus(initialStatus);
    setProgress(initialProgress);
  }, [initialStatus, initialProgress]);

  return (
    <div className="space-y-4">
      {/* Progress bar */}
      <ProgressBar progress={progress} status={status} showLabel />

      {/* Current stage */}
      {(stage || message) && (
        <div
          className="rounded-xl px-4 py-3 text-sm"
          style={{ background: "var(--surface-2)", border: "1px solid var(--border)" }}
        >
          {stage && (
            <p className="font-medium text-xs mb-1" style={{ color: "var(--accent)" }}>
              {STAGE_LABELS[stage] ?? stage}
            </p>
          )}
          {message && <p style={{ color: "var(--text-dim)" }}>{message}</p>}
        </div>
      )}

      {/* Live event feed */}
      {events.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs font-medium" style={{ color: "var(--muted)" }}>
            Live Events
          </p>
          <div className="space-y-1 max-h-48 overflow-y-auto">
            {events.map((ev, i) => (
              <div
                key={i}
                className="flex items-start gap-2 text-xs py-1.5 px-2 rounded-lg animate-slide-in"
                style={{
                  background: i === 0 ? "var(--surface-2)" : "transparent",
                  color: i === 0 ? "var(--text)" : "var(--muted)",
                }}
              >
                <span
                  className="shrink-0 mt-0.5 w-1.5 h-1.5 rounded-full"
                  style={{
                    background:
                      ev.status === "completed"
                        ? "var(--success)"
                        : ev.status === "failed"
                        ? "var(--danger)"
                        : "var(--accent)",
                  }}
                />
                <span>{ev.message ?? ev.event_type}</span>
                <span className="ml-auto shrink-0 tabular-nums">
                  {Math.round(ev.progress * 100)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
