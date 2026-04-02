import { useState } from "react";
import { Save, CheckCircle2, AlertCircle, Lock } from "lucide-react";
import { updateResult, finalizeResult } from "@/services/api";
import type { ExtractedResult, JobStatus } from "@/types";

interface Props {
  jobId: string;
  result: ExtractedResult;
  jobStatus: JobStatus;
  onUpdated: (result: ExtractedResult) => void;
}

export default function ResultEditor({ jobId, result, jobStatus, onUpdated }: Props) {
  const [form, setForm] = useState({
    title: result.title ?? "",
    category: result.category ?? "",
    summary: result.summary ?? "",
    keywords: (result.keywords ?? []).join(", "),
  });
  const [saving, setSaving] = useState(false);
  const [finalizing, setFinalizing] = useState(false);
  const [msg, setMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  const locked = result.is_finalized || jobStatus === "finalized";
  const canFinalize = jobStatus === "completed" && !result.is_finalized;

  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const handleSave = async () => {
    setSaving(true);
    setMsg(null);
    try {
      const updated = await updateResult(jobId, {
        title: form.title,
        category: form.category,
        summary: form.summary,
        keywords: form.keywords.split(",").map((k) => k.trim()).filter(Boolean),
      });
      onUpdated(updated);
      setMsg({ type: "ok", text: "Changes saved." });
    } catch (e: any) {
      setMsg({ type: "err", text: e?.response?.data?.detail ?? "Save failed." });
    } finally {
      setSaving(false);
    }
  };

  const handleFinalize = async () => {
    setFinalizing(true);
    setMsg(null);
    try {
      const updated = await finalizeResult(jobId);
      onUpdated(updated);
      setMsg({ type: "ok", text: "Result finalized. No further edits allowed." });
    } catch (e: any) {
      setMsg({ type: "err", text: e?.response?.data?.detail ?? "Finalize failed." });
    } finally {
      setFinalizing(false);
    }
  };

  const inputCls =
    "w-full rounded-xl px-3 py-2 text-sm transition-colors focus:outline-none focus:ring-1";
  const inputStyle = {
    background: "var(--surface-2)",
    border: "1px solid var(--border)",
    color: "var(--text)",
  };
  const focusStyle = { "--tw-ring-color": "var(--accent)" } as React.CSSProperties;

  return (
    <div className="space-y-5">
      {/* Finalized banner */}
      {locked && (
        <div
          className="flex items-center gap-2 rounded-xl px-4 py-3 text-sm"
          style={{
            background: "rgba(167,139,250,0.1)",
            border: "1px solid rgba(167,139,250,0.3)",
            color: "#a78bfa",
          }}
        >
          <Lock size={14} />
          This result is finalized and locked.
        </div>
      )}

      {/* Fields */}
      <div className="grid gap-4">
        {/* Title */}
        <div>
          <label className="block text-xs font-medium mb-1.5" style={{ color: "var(--muted)" }}>
            Title
          </label>
          <input
            className={inputCls}
            style={{ ...inputStyle, ...focusStyle }}
            value={form.title}
            onChange={set("title")}
            disabled={locked}
          />
        </div>

        {/* Category */}
        <div>
          <label className="block text-xs font-medium mb-1.5" style={{ color: "var(--muted)" }}>
            Category
          </label>
          <input
            className={inputCls}
            style={{ ...inputStyle, ...focusStyle }}
            value={form.category}
            onChange={set("category")}
            disabled={locked}
          />
        </div>

        {/* Keywords */}
        <div>
          <label className="block text-xs font-medium mb-1.5" style={{ color: "var(--muted)" }}>
            Keywords{" "}
            <span style={{ color: "var(--muted)", fontWeight: 400 }}>
              (comma-separated)
            </span>
          </label>
          <input
            className={inputCls}
            style={{ ...inputStyle, ...focusStyle }}
            value={form.keywords}
            onChange={set("keywords")}
            disabled={locked}
          />
        </div>

        {/* Summary */}
        <div>
          <label className="block text-xs font-medium mb-1.5" style={{ color: "var(--muted)" }}>
            Summary
          </label>
          <textarea
            className={inputCls}
            style={{ ...inputStyle, ...focusStyle }}
            value={form.summary}
            onChange={set("summary")}
            rows={5}
            disabled={locked}
          />
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: "Words", value: result.word_count?.toLocaleString() ?? "—" },
          { label: "Characters", value: result.char_count?.toLocaleString() ?? "—" },
          { label: "Language", value: result.language ?? "—" },
        ].map(({ label, value }) => (
          <div
            key={label}
            className="rounded-xl px-3 py-2.5 text-center"
            style={{ background: "var(--surface-2)", border: "1px solid var(--border)" }}
          >
            <p className="text-lg font-bold" style={{ color: "var(--text)", fontFamily: "'Space Grotesk', sans-serif" }}>
              {value}
            </p>
            <p className="text-xs mt-0.5" style={{ color: "var(--muted)" }}>
              {label}
            </p>
          </div>
        ))}
      </div>

      {/* Feedback */}
      {msg && (
        <div
          className="flex items-center gap-2 rounded-xl px-4 py-3 text-sm animate-slide-in"
          style={{
            background: msg.type === "ok" ? "rgba(34,211,160,0.1)" : "rgba(239,68,68,0.1)",
            border: `1px solid ${msg.type === "ok" ? "rgba(34,211,160,0.3)" : "rgba(239,68,68,0.3)"}`,
            color: msg.type === "ok" ? "var(--success)" : "var(--danger)",
          }}
        >
          {msg.type === "ok" ? <CheckCircle2 size={14} /> : <AlertCircle size={14} />}
          {msg.text}
        </div>
      )}

      {/* Action buttons */}
      {!locked && (
        <div className="flex gap-3">
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-medium transition-all disabled:opacity-50"
            style={{
              background: "var(--surface-3)",
              border: "1px solid var(--border)",
              color: "var(--text)",
            }}
          >
            <Save size={14} />
            {saving ? "Saving…" : "Save Changes"}
          </button>

          {canFinalize && (
            <button
              onClick={handleFinalize}
              disabled={finalizing}
              className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-semibold text-white transition-all disabled:opacity-50"
              style={{
                background: "var(--accent)",
                boxShadow: "0 0 20px var(--accent-glow)",
              }}
            >
              <CheckCircle2 size={14} />
              {finalizing ? "Finalizing…" : "Finalize Result"}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
