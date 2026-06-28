"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { IngestionResponse } from "@/lib/types";

interface Props {
  onIngested: (result: IngestionResponse) => void;
  onClose: () => void;
}

export function IngestPanel({ onIngested, onClose }: Props) {
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [provider, setProvider] = useState<string | null>(null);
  const [result, setResult] = useState<IngestionResponse | null>(null);

  useEffect(() => {
    api.aiProvider().then((p) => setProvider(p.provider)).catch(() => {});
  }, []);

  async function submit() {
    if (!title.trim() || !text.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.ingestText(title.trim(), text);
      setResult(res);
      onIngested(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Ingestion failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="absolute left-4 top-20 z-10 w-96 rounded-xl bg-panel/95 p-4 shadow-2xl ring-1 ring-edge backdrop-blur">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-200">Ingest document</h2>
        <button onClick={onClose} className="text-slate-500 hover:text-slate-300">✕</button>
      </div>
      <p className="mb-3 text-[11px] text-slate-500">
        Paste text; the {provider ?? "AI"} extractor proposes entities &amp; relationships,
        labeled <span className="text-amber-300">AI</span> and unverified until reviewed.
      </p>

      <input
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Document title"
        className="mb-2 w-full rounded-md bg-ink px-3 py-2 text-sm ring-1 ring-edge outline-none focus:ring-blue-500"
      />
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Paste document text here…"
        rows={7}
        className="mb-2 w-full resize-y rounded-md bg-ink px-3 py-2 text-sm ring-1 ring-edge outline-none focus:ring-blue-500"
      />

      {error && <p className="mb-2 text-xs text-red-400">{error}</p>}
      {result && (
        <p className="mb-2 text-xs text-emerald-400">
          Extracted {result.summary.entities_created} entities,{" "}
          {result.summary.relationships_created} relationships — added to the graph.
        </p>
      )}

      <button
        onClick={submit}
        disabled={busy || !title.trim() || !text.trim()}
        className="w-full rounded-md bg-blue-600 py-2 text-sm font-medium hover:bg-blue-500 disabled:opacity-50"
      >
        {busy ? "Extracting…" : "Extract & add to graph"}
      </button>
    </div>
  );
}
