"use client";

// The golden workflow (Task 7): one guided path from raw text to a defensible,
// sourced report — ingest → resolve duplicates → confidence/provenance → report.
// This is the spine the solo researcher lives in; every step links back into the
// explorer so the graph and this flow stay in sync.

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";
import { useSelection } from "@/lib/selection";
import type {
  ConfidenceProvenance,
  DuplicateCandidate,
  Entity,
  EntityReport,
} from "@/lib/types";

type Step = 1 | 2 | 3 | 4;

const STEPS: { n: Step; label: string }[] = [
  { n: 1, label: "Ingest" },
  { n: 2, label: "Resolve" },
  { n: 3, label: "Confidence" },
  { n: 4, label: "Report" },
];

export default function InvestigatePage() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [step, setStep] = useState<Step>(1);
  const { select } = useSelection();

  // Step 1 — ingest
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [extracted, setExtracted] = useState<Entity[]>([]);

  // Step 2 — resolve
  const [dupes, setDupes] = useState<DuplicateCandidate[] | null>(null);

  // Step 3 — confidence/provenance
  const [subject, setSubject] = useState<Entity | null>(null);
  const [provenance, setProvenance] = useState<ConfidenceProvenance | null>(null);

  // Step 4 — report
  const [report, setReport] = useState<EntityReport | null>(null);

  useEffect(() => {
    if (!isAuthenticated()) router.replace("/login");
    else setReady(true);
  }, [router]);

  if (!ready) return null;

  async function run<T>(fn: () => Promise<T>, after: (v: T) => void) {
    setBusy(true);
    setError(null);
    try {
      after(await fn());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  async function doIngest() {
    await run(
      () => api.ingestText(title || "Untitled source", text),
      (res) => {
        setExtracted(res.entities);
        if (res.entities[0]) setSubject(res.entities[0]);
        setStep(2);
      },
    );
  }

  async function doResolve() {
    await run(() => api.duplicates(), (res) => setDupes(res.candidates));
  }

  async function doConfidence(entity: Entity) {
    setSubject(entity);
    await run(() => api.confidenceProvenance(entity.id), setProvenance);
  }

  async function doReport() {
    if (!subject) return;
    await run(() => api.report(subject.id), (r) => {
      setReport(r);
      setStep(4);
    });
  }

  return (
    <main className="mx-auto min-h-screen max-w-3xl px-6 py-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-100">Guided investigation</h1>
        <Link href="/explore" className="text-sm text-sky-400 hover:text-sky-300">
          ← Back to graph
        </Link>
      </div>

      {/* Stepper */}
      <ol className="mb-8 flex items-center gap-2">
        {STEPS.map((s, i) => (
          <li key={s.n} className="flex items-center gap-2">
            <button
              onClick={() => setStep(s.n)}
              className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold ${
                step === s.n ? "bg-sky-600 text-white" : step > s.n ? "bg-emerald-700 text-white" : "bg-panel text-slate-400"
              }`}
            >
              {step > s.n ? "✓" : s.n}
            </button>
            <span className={`text-sm ${step === s.n ? "text-slate-100" : "text-slate-400"}`}>{s.label}</span>
            {i < STEPS.length - 1 && <span className="mx-1 text-slate-600">→</span>}
          </li>
        ))}
      </ol>

      {error && <p className="mb-4 rounded bg-red-900/40 px-3 py-2 text-sm text-red-300">{error}</p>}

      {/* Step 1 — Ingest */}
      {step === 1 && (
        <section className="space-y-3">
          <p className="text-sm text-slate-400">
            Paste source text. Atlas extracts entities/relationships as
            <span className="text-amber-300"> unverified</span> until you review them.
          </p>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Source title"
            className="w-full rounded bg-ink px-3 py-2 text-sm ring-1 ring-edge outline-none focus:ring-sky-500"
          />
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Paste document text here…"
            rows={10}
            className="w-full rounded bg-ink px-3 py-2 text-sm ring-1 ring-edge outline-none focus:ring-sky-500"
          />
          <button
            onClick={doIngest}
            disabled={busy || !text.trim()}
            className="rounded bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-50"
          >
            {busy ? "Extracting…" : "Extract & continue"}
          </button>
        </section>
      )}

      {/* Step 2 — Resolve */}
      {step === 2 && (
        <section className="space-y-3">
          <p className="text-sm text-slate-400">
            {extracted.length} entit{extracted.length === 1 ? "y" : "ies"} extracted. Resolve likely
            duplicates before you reason over the graph.
          </p>
          <ul className="divide-y divide-slate-800 rounded border border-slate-800">
            {extracted.map((e) => (
              <li key={e.id} className="flex items-center justify-between px-3 py-2 text-sm">
                <span className="text-slate-200">{e.name}</span>
                <button onClick={() => doConfidence(e).then(() => setStep(3))} className="text-sky-400 hover:text-sky-300">
                  inspect →
                </button>
              </li>
            ))}
          </ul>
          <button
            onClick={doResolve}
            disabled={busy}
            className="rounded bg-panel px-4 py-2 text-sm text-slate-200 ring-1 ring-edge hover:bg-slate-800 disabled:opacity-50"
          >
            {busy ? "Scanning…" : "Scan for duplicates"}
          </button>
          {dupes && (
            <div className="rounded border border-slate-800 p-3 text-sm">
              {dupes.length === 0 ? (
                <span className="text-emerald-400">No likely duplicates found.</span>
              ) : (
                <ul className="space-y-1">
                  {dupes.map((d, i) => (
                    <li key={i} className="text-slate-300">
                      <span className="text-amber-300">{(d.score * 100).toFixed(0)}%</span>{" "}
                      {d.a_name} ↔ {d.b_name} — {d.reason}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </section>
      )}

      {/* Step 3 — Confidence / provenance */}
      {step === 3 && subject && (
        <section className="space-y-3">
          <p className="text-sm text-slate-400">
            Why we believe <span className="text-slate-100">{subject.name}</span> — every number
            traces to its source.
          </p>
          {provenance ? (
            <div className="space-y-3">
              <div className="flex items-center gap-4 rounded border border-slate-800 p-3">
                <div className="text-3xl font-semibold text-sky-300">
                  {(provenance.score * 100).toFixed(0)}%
                </div>
                <div className="text-sm text-slate-300">
                  <div className="font-medium text-slate-100">{provenance.estimative_label}</div>
                  <div className="text-xs text-slate-400">
                    analytic confidence: {provenance.analytic_confidence}
                    {provenance.is_contradicted && (
                      <span className="ml-2 rounded bg-red-900/50 px-1 text-red-300">contradicted</span>
                    )}
                  </div>
                </div>
              </div>
              <table className="w-full text-left text-xs">
                <thead className="text-slate-400">
                  <tr>
                    <th className="py-1">Source</th>
                    <th>Stance</th>
                    <th>Grade</th>
                    <th>Counted?</th>
                  </tr>
                </thead>
                <tbody>
                  {provenance.contributions.map((c) => (
                    <tr key={c.evidence_id} className="border-t border-slate-800">
                      <td className="py-1 text-slate-200">{c.source ?? c.title}</td>
                      <td className="text-slate-300">{c.stance}</td>
                      <td className="font-mono text-slate-400">{c.admiralty_code ?? "—"}</td>
                      <td className={c.counted ? "text-emerald-400" : "text-slate-500"} title={c.reason}>
                        {c.counted ? "yes" : "no"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="flex gap-2">
                <button onClick={doReport} disabled={busy} className="rounded bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-50">
                  {busy ? "Generating…" : "Generate report →"}
                </button>
                <button
                  onClick={() => { select(subject.id); router.push("/explore"); }}
                  className="rounded bg-panel px-4 py-2 text-sm text-slate-200 ring-1 ring-edge hover:bg-slate-800"
                >
                  Open in graph
                </button>
              </div>
            </div>
          ) : (
            <p className="text-sm text-slate-500">Loading provenance…</p>
          )}
        </section>
      )}

      {/* Step 4 — Report */}
      {step === 4 && report && (
        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-slate-100">{report.subject.name} — target package</h2>
          <p className="text-xs text-slate-500">
            Generated by {report.provider} · confidence {report.confidence.estimative_label}
          </p>
          <p className="whitespace-pre-wrap rounded border border-slate-800 p-3 text-sm text-slate-200">
            {report.narrative}
          </p>
          {report.key_findings.length > 0 && (
            <ul className="list-disc space-y-1 pl-5 text-sm text-slate-300">
              {report.key_findings.map((f, i) => <li key={i}>{f}</li>)}
            </ul>
          )}
          <button
            onClick={() => { select(report.subject.id); router.push("/explore"); }}
            className="rounded bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500"
          >
            Open in graph
          </button>
        </section>
      )}
    </main>
  );
}
