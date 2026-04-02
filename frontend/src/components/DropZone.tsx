import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, File, X, AlertCircle, CheckCircle2 } from "lucide-react";
import { cn, formatBytes, FILE_TYPE_ICONS } from "@/utils";

const ACCEPTED = {
  "text/plain": [".txt"],
  "application/pdf": [".pdf"],
  "text/csv": [".csv"],
  "application/json": [".json"],
  "text/markdown": [".md"],
  "application/xml": [".xml"],
  "text/xml": [".xml"],
};

interface Props {
  onUpload: (files: File[]) => Promise<void>;
  isUploading: boolean;
}

export default function DropZone({ onUpload, isUploading }: Props) {
  const [queued, setQueued] = useState<File[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const onDrop = useCallback((accepted: File[], rejected: any[]) => {
    setError(null);
    setSuccess(false);
    if (rejected.length) {
      setError(
        `${rejected.length} file(s) rejected. Allowed: .txt .pdf .csv .json .md .xml (max 50 MB)`
      );
    }
    setQueued((prev) => {
      const existing = new Set(prev.map((f) => f.name));
      return [...prev, ...accepted.filter((f) => !existing.has(f.name))];
    });
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED,
    maxSize: 50 * 1024 * 1024,
    disabled: isUploading,
  });

  const remove = (name: string) =>
    setQueued((prev) => prev.filter((f) => f.name !== name));

  const handleSubmit = async () => {
    if (!queued.length) return;
    setError(null);
    try {
      await onUpload(queued);
      setQueued([]);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 4000);
    } catch (e: any) {
      setError(
        e?.response?.data?.detail ||
          e?.message ||
          "Upload failed. Please try again."
      );
    }
  };

  return (
    <div className="space-y-4">
      {/* Drop area */}
      <div
        {...getRootProps()}
        className={cn(
          "relative border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer transition-all duration-200 group",
          isDragActive
            ? "border-accent bg-accent/5 scale-[1.01]"
            : "border-border hover:border-accent/50 hover:bg-surface-1"
        )}
        style={{
          borderColor: isDragActive ? "var(--accent)" : "var(--border)",
          background: isDragActive ? "var(--accent-glow)" : "var(--surface-1)",
        }}
      >
        <input {...getInputProps()} />
        <div className="flex flex-col items-center gap-3 pointer-events-none">
          <div
            className={cn(
              "w-16 h-16 rounded-2xl flex items-center justify-center transition-transform duration-200",
              isDragActive ? "scale-110" : "group-hover:scale-105"
            )}
            style={{ background: "var(--surface-3)" }}
          >
            <Upload
              size={28}
              style={{ color: isDragActive ? "var(--accent)" : "var(--muted)" }}
            />
          </div>
          <div>
            <p className="font-semibold text-base" style={{ color: "var(--text)" }}>
              {isDragActive ? "Drop files here" : "Drag & drop files here"}
            </p>
            <p className="text-sm mt-1" style={{ color: "var(--muted)" }}>
              or{" "}
              <span style={{ color: "var(--accent)" }} className="font-medium">
                browse files
              </span>
            </p>
          </div>
          <p className="text-xs" style={{ color: "var(--muted)" }}>
            .txt · .pdf · .csv · .json · .md · .xml — up to 50 MB each
          </p>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div
          className="flex items-start gap-2 rounded-xl px-4 py-3 text-sm animate-slide-in"
          style={{ background: "rgba(239,68,68,0.1)", color: "#ef4444", border: "1px solid rgba(239,68,68,0.3)" }}
        >
          <AlertCircle size={16} className="shrink-0 mt-0.5" />
          {error}
        </div>
      )}

      {/* Success */}
      {success && (
        <div
          className="flex items-center gap-2 rounded-xl px-4 py-3 text-sm animate-slide-in"
          style={{ background: "rgba(34,211,160,0.1)", color: "var(--success)", border: "1px solid rgba(34,211,160,0.3)" }}
        >
          <CheckCircle2 size={16} />
          Files uploaded successfully and queued for processing!
        </div>
      )}

      {/* File queue */}
      {queued.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-medium" style={{ color: "var(--muted)" }}>
            {queued.length} file{queued.length !== 1 ? "s" : ""} ready
          </p>
          {queued.map((file) => {
            const ext = "." + file.name.split(".").pop()!.toLowerCase();
            const icon = FILE_TYPE_ICONS[ext] ?? "📄";
            return (
              <div
                key={file.name}
                className="flex items-center gap-3 rounded-xl px-4 py-3 animate-slide-in"
                style={{ background: "var(--surface-2)", border: "1px solid var(--border)" }}
              >
                <span className="text-xl">{icon}</span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate" style={{ color: "var(--text)" }}>
                    {file.name}
                  </p>
                  <p className="text-xs" style={{ color: "var(--muted)" }}>
                    {formatBytes(file.size)}
                  </p>
                </div>
                <button
                  onClick={() => remove(file.name)}
                  className="p-1 rounded-lg transition-colors hover:bg-red-500/20"
                  style={{ color: "var(--muted)" }}
                  disabled={isUploading}
                >
                  <X size={14} />
                </button>
              </div>
            );
          })}

          <button
            onClick={handleSubmit}
            disabled={isUploading || queued.length === 0}
            className="w-full mt-2 py-3 px-4 rounded-xl font-semibold text-sm text-white transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
            style={{
              background: isUploading
                ? "var(--accent-dim)"
                : "var(--accent)",
              boxShadow: isUploading ? "none" : "0 0 20px var(--accent-glow)",
            }}
          >
            {isUploading ? (
              <span className="flex items-center justify-center gap-2">
                <span
                  className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"
                />
                Uploading…
              </span>
            ) : (
              `Upload ${queued.length} file${queued.length !== 1 ? "s" : ""}`
            )}
          </button>
        </div>
      )}
    </div>
  );
}
