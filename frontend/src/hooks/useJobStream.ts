import { useEffect, useRef, useState, useCallback } from "react";
import { getStreamUrl } from "@/services/api";
import type { ProgressEvent } from "@/types";

interface UseJobStreamOptions {
  onEvent?: (event: ProgressEvent) => void;
  onComplete?: (event: ProgressEvent) => void;
  onError?: (event: ProgressEvent) => void;
  enabled?: boolean;
}

export function useJobStream(
  jobId: string | null,
  options: UseJobStreamOptions = {}
) {
  const { onEvent, onComplete, onError, enabled = true } = options;
  const [latest, setLatest] = useState<ProgressEvent | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  const close = useCallback(() => {
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
      setIsStreaming(false);
    }
  }, []);

  useEffect(() => {
    if (!jobId || !enabled) return;

    const url = getStreamUrl(jobId);
    const es = new EventSource(url);
    esRef.current = es;
    setIsStreaming(true);

    es.onmessage = (e) => {
      try {
        const payload: ProgressEvent = JSON.parse(e.data);
        setLatest(payload);
        onEvent?.(payload);
        if (payload.status === "completed") {
          onComplete?.(payload);
          close();
        } else if (payload.status === "failed") {
          onError?.(payload);
          close();
        }
      } catch {}
    };

    es.onerror = () => {
      close();
    };

    return close;
  }, [jobId, enabled]);

  return { latest, isStreaming, close };
}
