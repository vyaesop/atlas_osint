"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";
import { entityColor, ENTITY_LABELS } from "@/lib/colors";
import type {
  DashboardResponse,
  NeighborRef,
  TimelineResponse,
} from "@/lib/types";
import { Timeline } from "@/components/Timeline";
import { SearchBar } from "@/components/SearchBar";

export default function DashboardPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const search = useSearchParams();
  const id = params.id;
  const compareId = search.get("compare");

  const [dash, setDash] = useState<DashboardResponse | null>(null);
  const [timeline, setTimeline] = useState<TimelineResponse | null>(null);
  const [compareTl, setCompareTl] = useState<TimelineResponse | null>(null);
  const [dateFrom, setDateFrom] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isAuthenticated()) router.replace("/login");
  }, [router]);

  useEffect(() => {
    setError(null);
    Promise.all([api.dashboard(id), api.timeline(id, { dateFrom: dateFrom || undefined })])
      .then(([d, t]) => {
        setDash(d);
        setTimeline(t);
      })
      .catch(() => setError("Could not load dashboard."));
  }, [id, dateFrom]);

  useEffect(() => {
    if (compareId) {
      api.timeline(compareId, { dateFrom: dateFrom || undefined })
        .then(setCompareTl)
        .catch(() => setCompareTl(null));
    } else {
      setCompareTl(null);
    }
  }, [compareId, dateFrom]);

  if (error) {
    return <main className="p-8 text-red-400">{error}</main>;
  }
  if (!dash || !timeline) {
    return <main className="p-8 text-slate-400">Loading dashboard…</main>;
  }

  const color = entityColor(dash.entity.type);
  const inf = dash.influence;

  return (
    <main className="mx-auto max-w-5xl p-6">
      <Link href="/explore" className="text-xs text-slate-400 hover:text-slate-200">
        ← Back to explorer
      </Link>

      <header className="mt-2 flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span
              className="rounded px-2 py-0.5 text-[11px] font-semibold uppercase"
              style={{ background: `${color}22`, color }}
            >
              {ENTITY_LABELS[dash.entity.type]}
            </span>
            {dash.entity.is_ai_generated && (
              <span className="rounded bg-amber-500/20 px-2 py-0.5 text-[11px] font-semibold text-amber-300">
                AI · unverified
              </span>
            )}
          </div>
          <h1 className="mt-1 text-2xl font-semibold">{dash.entity.name}</h1>
          {dash.entity.description && (
            <p className="mt-1 max-w-2xl text-sm text-slate-400">{dash.entity.description}</p>
          )}
        </div>
      </header>

      {/* Stat cards */}
      <section className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Connections" value={dash.stats.total_connections} />
        <Stat label="Evidence" value={dash.stats.total_evidence} />
        <Stat label="Documents" value={dash.stats.total_documents} />
        <Stat label="Confidence" value={`${(dash.stats.confidence_score * 100).toFixed(0)}%`} />
      </section>

      {/* Influence */}
      <section className="mt-4 rounded-lg bg-panel p-4 ring-1 ring-edge">
        <h2 className="mb-2 text-sm font-semibold text-slate-300">Influence (2-hop neighborhood)</h2>
        <div className="flex flex-wrap gap-6 text-sm">
          <Metric label="Degree centrality" value={inf.degree_centrality.toFixed(3)} />
          <Metric label="PageRank" value={inf.pagerank.toFixed(3)} />
          <Metric label="Total connections" value={String(inf.total_connections)} />
        </div>
        {Object.keys(inf.connections_by_type).length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {Object.entries(inf.connections_by_type).map(([t, n]) => (
              <span key={t} className="rounded bg-ink px-2 py-0.5 text-[11px] text-slate-400">
                {t.replace(/_/g, " ").toLowerCase()} · {n}
              </span>
            ))}
          </div>
        )}
      </section>

      {/* Sections (only the non-empty ones relevant to this entity) */}
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <Section title="Organizations" items={dash.sections.organizations} />
        <Section title="Members" items={dash.sections.members} />
        <Section title="Partners" items={dash.sections.partners} />
        <Section title="Events" items={dash.sections.events} />
        <Section title="Locations" items={dash.sections.locations} />
        {dash.kind === "event" && (
          <Section title="Participants & related" items={dash.sections.related_entities} />
        )}
        <DocumentSection titles={dash.sections.documents} />
      </div>

      {/* Timeline + comparison */}
      <section className="mt-6 rounded-lg bg-panel p-4 ring-1 ring-edge">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-slate-300">Timeline</h2>
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <label>From</label>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="rounded bg-ink px-2 py-1 ring-1 ring-edge outline-none"
            />
            {dateFrom && (
              <button onClick={() => setDateFrom("")} className="text-slate-500 hover:text-slate-300">
                clear
              </button>
            )}
          </div>
        </div>

        <div className="grid gap-6 md:grid-cols-2">
          <div>
            <h3 className="mb-2 text-xs font-medium text-slate-400">{timeline.entity_name}</h3>
            <Timeline items={timeline.items} />
          </div>
          <div>
            {compareTl ? (
              <>
                <h3 className="mb-2 flex items-center justify-between text-xs font-medium text-slate-400">
                  {compareTl.entity_name}
                  <button
                    onClick={() => router.replace(`/dashboard/${id}`)}
                    className="text-slate-500 hover:text-slate-300"
                  >
                    remove
                  </button>
                </h3>
                <Timeline items={compareTl.items} />
              </>
            ) : (
              <div>
                <h3 className="mb-2 text-xs font-medium text-slate-400">Compare with…</h3>
                <SearchBar
                  onSelect={(cid) => router.replace(`/dashboard/${id}?compare=${cid}`)}
                />
              </div>
            )}
          </div>
        </div>
      </section>
    </main>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg bg-panel p-3 ring-1 ring-edge">
      <div className="text-2xl font-semibold text-slate-100">{value}</div>
      <div className="text-xs text-slate-400">{label}</div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="font-mono text-slate-200">{value}</div>
      <div className="text-xs text-slate-500">{label}</div>
    </div>
  );
}

function Section({ title, items }: { title: string; items: NeighborRef[] }) {
  if (items.length === 0) return null;
  return (
    <div className="rounded-lg bg-panel p-4 ring-1 ring-edge">
      <h2 className="mb-2 text-sm font-semibold text-slate-300">
        {title} <span className="text-slate-500">({items.length})</span>
      </h2>
      <ul className="space-y-1">
        {items.map((n) => (
          <li key={n.relationship_id} className="flex items-center justify-between text-sm">
            <Link
              href={`/dashboard/${n.id}`}
              className="truncate text-slate-200 hover:text-blue-400"
              style={{ borderLeft: `3px solid ${entityColor(n.type)}`, paddingLeft: 6 }}
            >
              {n.name}
            </Link>
            <span className="ml-2 shrink-0 text-[10px] text-slate-500">
              {n.relationship_type.replace(/_/g, " ").toLowerCase()}
              {n.is_ai_generated ? " · AI" : ""}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function DocumentSection({ titles }: { titles: { id: string | null; title: string }[] }) {
  if (titles.length === 0) return null;
  return (
    <div className="rounded-lg bg-panel p-4 ring-1 ring-edge">
      <h2 className="mb-2 text-sm font-semibold text-slate-300">
        Documents <span className="text-slate-500">({titles.length})</span>
      </h2>
      <ul className="space-y-1 text-sm text-slate-300">
        {titles.map((d, i) => (
          <li key={i} className="truncate">📄 {d.title}</li>
        ))}
      </ul>
    </div>
  );
}
