import { useState, useEffect, useCallback, useRef } from "react";
import Head from "next/head";
import Link from "next/link";
import {
  Search, Filter, SortDesc, SortAsc, RefreshCw,
  Download, Upload, FileText, CheckCircle2, AlertCircle,
  Clock, Zap, ChevronLeft, ChevronRight,
} from "lucide-react";
import Layout from "@/components/Layout";
import JobCard from "@/components/JobCard";
import { listDocuments, retryJob, exportResults } from "@/services/api";
import type { DocumentListItem, JobStatus } from "@/types";
import { cn } from "@/utils";

const STATUSES: { value: string; label: string }[] = [
  { value: "", label: "All" },
  { value: "queued", label: "Queued" },
  { value: "processing", label: "Processing" },
  { value: "completed", label: "Completed" },
  { value: "finalized", label: "Finalized" },
  { value: "failed", label: "Failed" },
];

const SORT_OPTIONS = [
  { value: "uploaded_at", label: "Date" },
  { value: "filename", label: "Name" },
  { value: "file_size", label: "Size" },
];

export default function Dashboard() {
  const [docs, setDocs] = useState<DocumentListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [sortBy, setSortBy] = useState("uploaded_at");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [exporting, setExporting] = useState(false);

  const searchTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listDocuments({
        page,
        page_size: 15,
        search: search || undefined,
        status: statusFilter || undefined,
        sort_by: sortBy,
        sort_dir: sortDir,
      });
      setDocs(res.items);
      setTotal(res.total);
      setTotalPages(res.total_pages);
    } finally {
      setLoading(false);
    }
  }, [page, search, statusFilter, sortBy, sortDir]);

  useEffect(() => {
    load();
  }, [load]);

  // Auto-refresh when any job is processing
  useEffect(() => {
    const hasActive = docs.some(
      (d) => d.job?.status === "queued" || d.job?.status === "processing"
    );
    if (!hasActive) return;
    const id = setInterval(load, 3000);
    return () => clearInterval(id);
  }, [docs, load]);

  const handleSearch = (val: string) => {
    if (searchTimeout.current) {
      clearTimeout(searchTimeout.current);
    }
    searchTimeout.current = setTimeout(() => {
      setSearch(val);
      setPage(1);
    }, 350);
  };

  const handleRetry = async (jobId: string) => {
    await retryJob(jobId);
    load();
  };

  const toggleSelect = (jobId: string, checked: boolean) => {
    setSelected((prev) => {
      const next = new Set(prev);
      checked ? next.add(jobId) : next.delete(jobId);
      return next;
    });
  };

  const handleExport = async (fmt: "json" | "csv") => {
    if (!selected.size) return;
    setExporting(true);
    try {
      await exportResults({ job_ids: Array.from(selected), format: fmt });
    } finally {
      setExporting(false);
    }
  };

  // Stats
  const counts = docs.reduce(
    (acc, d) => {
      const s = d.job?.status;
      if (s) acc[s] = (acc[s] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  );

  return (
    <>
      <Head>
        <title>Dashboard — DocFlow</title>
      </Head>
      <Layout>
        {/* Header */}
        <div className="flex items-start justify-between mb-8 gap-4">
          <div>
            <h1
              className="text-3xl font-bold tracking-tight"
              style={{ fontFamily: "'Space Grotesk', sans-serif", color: "var(--text)" }}
            >
              Documents
            </h1>
            <p className="text-sm mt-1" style={{ color: "var(--muted)" }}>
              {total} document{total !== 1 ? "s" : ""} in system
            </p>
          </div>
          <Link
            href="/upload"
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl font-medium text-sm text-white transition-all"
            style={{ background: "var(--accent)", boxShadow: "0 0 20px var(--accent-glow)" }}
          >
            <Upload size={15} />
            Upload
          </Link>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
          {[
            { label: "Processing", count: counts.processing ?? 0, icon: Zap, color: "#60a5fa" },
            { label: "Completed", count: counts.completed ?? 0, icon: CheckCircle2, color: "var(--success)" },
            { label: "Finalized", count: counts.finalized ?? 0, icon: FileText, color: "#a78bfa" },
            { label: "Failed", count: counts.failed ?? 0, icon: AlertCircle, color: "var(--danger)" },
          ].map(({ label, count, icon: Icon, color }) => (
            <div
              key={label}
              className="rounded-xl px-4 py-3 flex items-center gap-3"
              style={{ background: "var(--surface-1)", border: "1px solid var(--border)" }}
            >
              <Icon size={18} style={{ color }} />
              <div>
                <p className="text-xl font-bold" style={{ fontFamily: "'Space Grotesk', sans-serif", color: "var(--text)" }}>
                  {count}
                </p>
                <p className="text-xs" style={{ color: "var(--muted)" }}>{label}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Controls */}
        <div className="flex flex-wrap gap-3 mb-5">
          {/* Search */}
          <div
            className="flex items-center gap-2 flex-1 min-w-[200px] rounded-xl px-3 py-2"
            style={{ background: "var(--surface-1)", border: "1px solid var(--border)" }}
          >
            <Search size={15} style={{ color: "var(--muted)" }} />
            <input
              type="text"
              placeholder="Search filenames…"
              className="flex-1 bg-transparent text-sm focus:outline-none"
              style={{ color: "var(--text)" }}
              onChange={(e) => handleSearch(e.target.value)}
            />
          </div>

          {/* Status filter */}
          <div className="flex rounded-xl overflow-hidden border" style={{ borderColor: "var(--border)" }}>
            {STATUSES.map(({ value, label }) => (
              <button
                key={value}
                onClick={() => { setStatusFilter(value); setPage(1); }}
                className="px-3 py-2 text-xs font-medium transition-colors"
                style={{
                  background: statusFilter === value ? "var(--surface-3)" : "var(--surface-1)",
                  color: statusFilter === value ? "var(--text)" : "var(--muted)",
                  borderRight: "1px solid var(--border)",
                }}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Sort */}
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="rounded-xl px-3 py-2 text-xs focus:outline-none"
            style={{
              background: "var(--surface-1)",
              border: "1px solid var(--border)",
              color: "var(--text)",
            }}
          >
            {SORT_OPTIONS.map(({ value, label }) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>

          <button
            onClick={() => setSortDir((d) => (d === "asc" ? "desc" : "asc"))}
            className="p-2 rounded-xl transition-colors"
            style={{ background: "var(--surface-1)", border: "1px solid var(--border)", color: "var(--muted)" }}
          >
            {sortDir === "desc" ? <SortDesc size={15} /> : <SortAsc size={15} />}
          </button>

          <button
            onClick={load}
            className="p-2 rounded-xl transition-colors"
            style={{ background: "var(--surface-1)", border: "1px solid var(--border)", color: "var(--muted)" }}
          >
            <RefreshCw size={15} className={loading ? "animate-spin" : ""} />
          </button>
        </div>

        {/* Export bar */}
        {selected.size > 0 && (
          <div
            className="flex items-center gap-3 rounded-xl px-4 py-3 mb-4 animate-slide-in"
            style={{ background: "var(--surface-2)", border: "1px solid var(--accent)" }}
          >
            <span className="text-sm font-medium" style={{ color: "var(--text)" }}>
              {selected.size} selected
            </span>
            <button
              onClick={() => setSelected(new Set())}
              className="text-xs ml-auto"
              style={{ color: "var(--muted)" }}
            >
              Clear
            </button>
            <button
              onClick={() => handleExport("json")}
              disabled={exporting}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
              style={{ background: "var(--surface-3)", border: "1px solid var(--border)", color: "var(--text)" }}
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
          </div>
        )}

        {/* Document list */}
        {loading && docs.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 gap-3">
            <div
              className="w-8 h-8 border-2 border-t-transparent rounded-full animate-spin"
              style={{ borderColor: "var(--border)", borderTopColor: "var(--accent)" }}
            />
            <p style={{ color: "var(--muted)" }}>Loading documents…</p>
          </div>
        ) : docs.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 gap-4">
            <FileText size={48} style={{ color: "var(--muted)", opacity: 0.4 }} />
            <p className="font-medium" style={{ color: "var(--text)" }}>No documents found</p>
            <p className="text-sm" style={{ color: "var(--muted)" }}>
              {search || statusFilter ? "Try adjusting your filters" : "Upload your first document to get started"}
            </p>
            <Link
              href="/upload"
              className="mt-2 px-4 py-2 rounded-xl text-sm font-medium text-white"
              style={{ background: "var(--accent)" }}
            >
              Upload Document
            </Link>
          </div>
        ) : (
          <div className="space-y-2">
            {docs.map((doc) => (
              <JobCard
                key={doc.id}
                doc={doc}
                onRetry={handleRetry}
                selected={doc.job ? selected.has(doc.job.id) : false}
                onSelect={toggleSelect}
              />
            ))}
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-2 mt-6">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="p-2 rounded-lg disabled:opacity-40 transition-colors"
              style={{ background: "var(--surface-1)", border: "1px solid var(--border)", color: "var(--text)" }}
            >
              <ChevronLeft size={15} />
            </button>
            <span className="text-sm px-3" style={{ color: "var(--muted)" }}>
              Page {page} of {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="p-2 rounded-lg disabled:opacity-40 transition-colors"
              style={{ background: "var(--surface-1)", border: "1px solid var(--border)", color: "var(--text)" }}
            >
              <ChevronRight size={15} />
            </button>
          </div>
        )}
      </Layout>
    </>
  );
}
