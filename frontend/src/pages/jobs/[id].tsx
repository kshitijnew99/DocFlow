import { useState, useEffect } from "react";
import Head from "next/head";
import Link from "next/link";
import { useRouter } from "next/router";
import {
  ArrowLeft, RefreshCw, Download, AlertTriangle,
  Clock, FileText, ChevronDown, ChevronUp,
} from "lucide-react";
import Layout from "@/components/Layout";
import StatusBadge from "@/components/StatusBadge";
import LiveProgress from "@/components/LiveProgress";
import ResultEditor from "@/components/ResultEditor";
import { getJob, retryJob, exportResults } from "@/services/api";
import { formatBytes, formatDate, timeAgo, STAGE_LABELS, FILE_TYPE_ICONS } from "@/utils";
import type { JobDetail, ExtractedResult, JobStatus } from "@/types";

export default function JobDetailPage() {
  const router = useRouter();
  const { id } = router.query as { id: string };

  const [job, setJob] = useState<JobDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [retrying, setRetrying] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [showEvents, setShowEvents] = useState(false);
  const [currentStatus, setCurrentStatus] = useState<JobStatus | null>(null);
  const [currentProgress, setCurrentProgress] = useState(0);

  useEffect(() => {
    if (!id) return;
    (async () => {
      try {
        const data = await getJob(id);
        setJob(data);
        setCurrentStatus(data.status);
        setCurrentProgress(data.progress);
      } finally {
        setLoading(false);
      }
    })();
  }, [id]);

  const handleStatusChange = async (status: JobStatus, progress: number) => {
    setCurrentStatus(status);
    setCurrentProgress(progress);
    if (status === "completed") {
      // Reload to get the result
      const data = await getJob(id);
      setJob(data);
    }
  };

  const handleRetry = async () => {
    if (!job) return;
    setRetrying(true);
    try {
      const updated = await retryJob(job.id);
      setJob((prev) => prev ? { ...prev, ...updated } : prev);
      setCurrentStatus("queued");
      setCurrentProgress(0);
    } finally {
      setRetrying(false);
    }
  };

  const handleResultUpdated = (result: ExtractedResult) => {
    setJob((prev) => prev ? { ...prev, result } : prev);
    if (result.is_finalized) setCurrentStatus("finalized");
  };

  const handleExport = async (fmt: "json" | "csv") => {
    if (!job) return;
    setExporting(true);
    try {
      await exportResults({ job_ids: [job.id], format: fmt });
    } finally {
      setExporting(false);
    }
  };

  if (loading) {
    return (
      <Layout>
        <div className="flex items-center justify-center py-32">
          <div
            className="w-8 h-8 border-2 border-t-transparent rounded-full animate-spin"
            style={{ borderColor: "var(--border)", borderTopColor: "var(--accent)" }}
          />
        </div>
      </Layout>
    );
  }

  if (!job) {
    return (
      <Layout>
        <div className="flex flex-col items-center justify-center py-32 gap-4">
          <AlertTriangle size={40} style={{ color: "var(--warning)" }} />
          <p style={{ color: "var(--text)" }}>Job not found.</p>
          <Link href="/" className="text-sm" style={{ color: "var(--accent)" }}>
            ← Back to Dashboard
          </Link>
        </div>
      </Layout>
    );
  }

  const doc = job.document;
  const ext = doc?.file_type?.toLowerCase() ?? ".txt";
  const icon = FILE_TYPE_ICONS[ext] ?? "📄";
  const effectiveStatus = currentStatus ?? job.status;

  return (
    <>
      <Head>
        <title>{doc?.original_filename ?? "Job Detail"} — DocFlow</title>
      </Head>
      <Layout>
        <div className="max-w-4xl mx-auto">
          {/* Back + actions */}
          <div className="flex items-center justify-between mb-6 gap-4 flex-wrap">
            <Link
              href="/"
              className="inline-flex items-center gap-1.5 text-sm transition-colors hover:text-white"
              style={{ color: "var(--muted)" }}
            >
              <ArrowLeft size={14} />
              Dashboard
            </Link>

            <div className="flex items-center gap-2">
              {(effectiveStatus === "completed" || effectiveStatus === "finalized") && (
                <>
                  <button
                    onClick={() => handleExport("json")}
                    disabled={exporting}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
                    style={{
                      background: "var(--surface-2)",
                      border: "1px solid var(--border)",
                      color: "var(--text)",
                    }}
                  >
                    <Download size={12} /> JSON
                  </button>
                  <button
                    onClick={() => handleExport("csv")}
                    disabled={exporting}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-white transition-all"
                    style={{ background: "var(--accent)" }}
                  >
                    <Download size={12} /> CSV
                  </button>
                </>
              )}

              {effectiveStatus === "failed" && (
                <button
                  onClick={handleRetry}
                  disabled={retrying || job.retry_count >= job.max_retries}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all disabled:opacity-50"
                  style={{
                    background: "var(--warning)",
                    color: "#000",
                  }}
                >
                  <RefreshCw size={12} className={retrying ? "animate-spin" : ""} />
                  {retrying ? "Retrying…" : `Retry (${job.retry_count}/${job.max_retries})`}
                </button>
              )}
            </div>
          </div>

          {/* Document header card */}
          <div
            className="rounded-2xl p-6 mb-6 glow-card"
            style={{ background: "var(--surface-1)", border: "1px solid var(--border)" }}
          >
            <div className="flex items-start gap-4">
              <span className="text-4xl shrink-0">{icon}</span>
              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-3 flex-wrap">
                  <div>
                    <h1
                      className="text-xl font-bold truncate"
                      style={{ fontFamily: "'Space Grotesk', sans-serif", color: "var(--text)" }}
                    >
                      {doc?.original_filename}
                    </h1>
                    <p className="text-sm mt-1" style={{ color: "var(--muted)" }}>
                      {doc && formatBytes(doc.file_size)} · {doc?.file_type} · uploaded{" "}
                      {doc && timeAgo(doc.uploaded_at)}
                    </p>
                  </div>
                  <StatusBadge status={effectiveStatus} />
                </div>

                {/* Job meta */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4">
                  {[
                    { label: "Job ID", value: job.id.slice(0, 8) + "…" },
                    { label: "Retries", value: `${job.retry_count} / ${job.max_retries}` },
                    { label: "Started", value: job.started_at ? timeAgo(job.started_at) : "—" },
                    { label: "Completed", value: job.completed_at ? timeAgo(job.completed_at) : "—" },
                  ].map(({ label, value }) => (
                    <div key={label}>
                      <p className="text-xs" style={{ color: "var(--muted)" }}>{label}</p>
                      <p className="text-sm font-medium font-mono mt-0.5" style={{ color: "var(--text)" }}>
                        {value}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <div className="grid lg:grid-cols-5 gap-6">
            {/* Left column: progress + events */}
            <div className="lg:col-span-2 space-y-5">
              {/* Progress */}
              <div
                className="rounded-xl p-5"
                style={{ background: "var(--surface-1)", border: "1px solid var(--border)" }}
              >
                <h2 className="text-sm font-semibold mb-4" style={{ color: "var(--text)" }}>
                  Progress
                </h2>
                <LiveProgress
                  jobId={job.id}
                  initialStatus={effectiveStatus}
                  initialProgress={currentProgress}
                  onStatusChange={handleStatusChange}
                />
              </div>

              {/* Error */}
              {job.error_message && (
                <div
                  className="rounded-xl p-4"
                  style={{
                    background: "rgba(239,68,68,0.08)",
                    border: "1px solid rgba(239,68,68,0.3)",
                  }}
                >
                  <p className="text-xs font-semibold mb-1" style={{ color: "var(--danger)" }}>
                    Error
                  </p>
                  <p className="text-sm font-mono break-all" style={{ color: "#fca5a5" }}>
                    {job.error_message}
                  </p>
                </div>
              )}

              {/* Event log toggle */}
              {job.events?.length > 0 && (
                <div
                  className="rounded-xl overflow-hidden"
                  style={{ border: "1px solid var(--border)" }}
                >
                  <button
                    onClick={() => setShowEvents((v) => !v)}
                    className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium transition-colors hover:bg-surface-2"
                    style={{ background: "var(--surface-1)", color: "var(--text)" }}
                  >
                    <span className="flex items-center gap-2">
                      <Clock size={14} style={{ color: "var(--muted)" }} />
                      Event Log ({job.events.length})
                    </span>
                    {showEvents ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                  </button>

                  {showEvents && (
                    <div
                      className="divide-y max-h-72 overflow-y-auto"
                      style={{ borderTop: "1px solid var(--border)" }}
                    >
                      {[...job.events].reverse().map((ev) => (
                        <div
                          key={ev.id}
                          className="px-4 py-2.5 flex items-start gap-2"
                          style={{ background: "var(--surface-2)" }}
                        >
                          <span
                            className="w-1.5 h-1.5 rounded-full mt-1.5 shrink-0"
                            style={{
                              background:
                                ev.event_type === "job_completed"
                                  ? "var(--success)"
                                  : ev.event_type === "job_failed"
                                  ? "var(--danger)"
                                  : "var(--accent)",
                            }}
                          />
                          <div className="flex-1 min-w-0">
                            <p className="text-xs font-medium" style={{ color: "var(--text)" }}>
                              {STAGE_LABELS[ev.stage ?? ""] ?? ev.event_type}
                            </p>
                            {ev.message && (
                              <p className="text-xs mt-0.5 truncate" style={{ color: "var(--muted)" }}>
                                {ev.message}
                              </p>
                            )}
                          </div>
                          <span className="text-xs shrink-0 tabular-nums" style={{ color: "var(--muted)" }}>
                            {Math.round(ev.progress * 100)}%
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Right column: result editor */}
            <div className="lg:col-span-3">
              {job.result ? (
                <div
                  className="rounded-xl p-5"
                  style={{ background: "var(--surface-1)", border: "1px solid var(--border)" }}
                >
                  <h2 className="text-sm font-semibold mb-4" style={{ color: "var(--text)" }}>
                    Extracted Result
                    {job.result.is_finalized && (
                      <span
                        className="ml-2 text-xs px-2 py-0.5 rounded-full"
                        style={{
                          background: "rgba(167,139,250,0.15)",
                          color: "#a78bfa",
                          border: "1px solid rgba(167,139,250,0.3)",
                        }}
                      >
                        Finalized {job.result.finalized_at ? formatDate(job.result.finalized_at) : ""}
                      </span>
                    )}
                  </h2>
                  <ResultEditor
                    jobId={job.id}
                    result={job.result}
                    jobStatus={effectiveStatus}
                    onUpdated={handleResultUpdated}
                  />
                </div>
              ) : (
                <div
                  className="rounded-xl p-8 flex flex-col items-center justify-center text-center h-full"
                  style={{
                    background: "var(--surface-1)",
                    border: "1px solid var(--border)",
                    minHeight: 280,
                  }}
                >
                  <FileText size={36} style={{ color: "var(--muted)", opacity: 0.4 }} />
                  <p className="mt-3 font-medium" style={{ color: "var(--text)" }}>
                    {effectiveStatus === "failed"
                      ? "Processing failed — no result available"
                      : "Result will appear here once processing completes"}
                  </p>
                  <p className="text-sm mt-1" style={{ color: "var(--muted)" }}>
                    {effectiveStatus === "processing" && "Sit tight, this usually takes a few seconds…"}
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      </Layout>
    </>
  );
}
