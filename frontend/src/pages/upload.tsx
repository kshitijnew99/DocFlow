import { useState } from "react";
import Head from "next/head";
import Link from "next/link";
import { ArrowLeft, ArrowRight, CheckCircle2 } from "lucide-react";
import Layout from "@/components/Layout";
import DropZone from "@/components/DropZone";
import StatusBadge from "@/components/StatusBadge";
import LiveProgress from "@/components/LiveProgress";
import { uploadDocuments } from "@/services/api";
import type { UploadResponse, JobStatus } from "@/types";

export default function UploadPage() {
  const [isUploading, setIsUploading] = useState(false);
  const [response, setResponse] = useState<UploadResponse | null>(null);
  const [jobStatuses, setJobStatuses] = useState<Record<string, { status: JobStatus; progress: number }>>({});

  const handleUpload = async (files: File[]) => {
    setIsUploading(true);
    try {
      const res = await uploadDocuments(files);
      setResponse(res);
      // Seed initial statuses
      const initial: Record<string, { status: JobStatus; progress: number }> = {};
      res.jobs.forEach((j) => {
        initial[j.id] = { status: j.status, progress: j.progress };
      });
      setJobStatuses(initial);
    } finally {
      setIsUploading(false);
    }
  };

  const handleStatusChange = (jobId: string, status: JobStatus, progress: number) => {
    setJobStatuses((prev) => ({ ...prev, [jobId]: { status, progress } }));
  };

  return (
    <>
      <Head>
        <title>Upload — DocFlow</title>
      </Head>
      <Layout>
        <div className="max-w-2xl mx-auto">
          {/* Back link */}
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-sm mb-6 transition-colors hover:text-white"
            style={{ color: "var(--muted)" }}
          >
            <ArrowLeft size={14} />
            Back to Dashboard
          </Link>

          <h1
            className="text-3xl font-bold tracking-tight mb-2"
            style={{ fontFamily: "'Space Grotesk', sans-serif", color: "var(--text)" }}
          >
            Upload Documents
          </h1>
          <p className="text-sm mb-8" style={{ color: "var(--muted)" }}>
            Upload one or more files. Each file is processed asynchronously by a background worker.
          </p>

          {/* Drop zone */}
          <div
            className="rounded-2xl p-6 mb-6"
            style={{ background: "var(--surface-1)", border: "1px solid var(--border)" }}
          >
            <DropZone onUpload={handleUpload} isUploading={isUploading} />
          </div>

          {/* Post-upload job cards */}
          {response && (
            <div className="space-y-4 animate-slide-in">
              <div className="flex items-center justify-between">
                <h2 className="font-semibold text-sm" style={{ color: "var(--text)" }}>
                  Processing Jobs
                </h2>
                <Link
                  href="/"
                  className="flex items-center gap-1 text-xs transition-colors"
                  style={{ color: "var(--accent)" }}
                >
                  View Dashboard <ArrowRight size={12} />
                </Link>
              </div>

              {response.jobs.map((job, idx) => {
                const doc = response.documents[idx];
                const current = jobStatuses[job.id] ?? { status: job.status, progress: job.progress };
                const isDone =
                  current.status === "completed" || current.status === "finalized";

                return (
                  <div
                    key={job.id}
                    className="rounded-xl p-4 space-y-3"
                    style={{ background: "var(--surface-2)", border: "1px solid var(--border)" }}
                  >
                    {/* File info + status */}
                    <div className="flex items-center justify-between gap-2">
                      <div className="min-w-0">
                        <p className="font-medium text-sm truncate" style={{ color: "var(--text)" }}>
                          {doc?.original_filename}
                        </p>
                        <p className="text-xs font-mono mt-0.5" style={{ color: "var(--muted)" }}>
                          job:{job.id.slice(0, 8)}…
                        </p>
                      </div>
                      <StatusBadge status={current.status} />
                    </div>

                    {/* Live progress stream */}
                    <LiveProgress
                      jobId={job.id}
                      initialStatus={current.status}
                      initialProgress={current.progress}
                      onStatusChange={(s, p) => handleStatusChange(job.id, s, p)}
                    />

                    {/* Link to detail page when done */}
                    {isDone && (
                      <Link
                        href={`/jobs/${job.id}`}
                        className="flex items-center justify-center gap-2 w-full py-2.5 rounded-xl text-sm font-medium text-white transition-all animate-slide-in"
                        style={{ background: "var(--accent)", boxShadow: "0 0 15px var(--accent-glow)" }}
                      >
                        <CheckCircle2 size={14} />
                        Review & Edit Result
                      </Link>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </Layout>
    </>
  );
}
