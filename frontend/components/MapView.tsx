"use client";

import "leaflet/dist/leaflet.css";

import L from "leaflet";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  CircleMarker,
  MapContainer,
  Polyline,
  Popup,
  TileLayer,
  Tooltip,
  useMap,
} from "react-leaflet";

import { api } from "@/lib/api";
import { entityColor, ENTITY_LABELS } from "@/lib/colors";
import type {
  ColocationPair,
  GeoFeature,
  PatternOfLifeResponse,
} from "@/lib/types";

const DEFAULT_CENTER: [number, number] = [20, 0];

// Imperatively fit the map to the available points whenever they change.
function FitBounds({ points }: { points: [number, number][] }) {
  const map = useMap();
  useEffect(() => {
    if (points.length === 0) return;
    if (points.length === 1) {
      map.setView(points[0], 6);
      return;
    }
    map.fitBounds(L.latLngBounds(points).pad(0.2));
  }, [map, points]);
  return null;
}

export function MapView({ onLogout }: { onLogout?: () => void }) {
  const [features, setFeatures] = useState<GeoFeature[]>([]);
  const [pol, setPol] = useState<PatternOfLifeResponse | null>(null);
  const [pairs, setPairs] = useState<ColocationPair[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [map, colo] = await Promise.all([api.geoMap(), api.colocation()]);
        setFeatures(map.features);
        setPairs(colo.pairs);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load map data");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const points = useMemo<[number, number][]>(
    () => features.map((f) => [f.lat, f.lon]),
    [features],
  );

  const track = useMemo<[number, number][]>(
    () => (pol?.visits ?? []).map((v) => [v.lat, v.lon]),
    [pol],
  );

  async function showPattern(entityId: string) {
    try {
      setPol(await api.patternOfLife(entityId));
    } catch {
      setPol(null);
    }
  }

  return (
    <main className="flex h-screen flex-col bg-slate-900 text-slate-100">
      <header className="flex items-center justify-between border-b border-slate-800 px-4 py-2">
        <div className="flex items-center gap-4">
          <h1 className="text-sm font-semibold">Atlas · Geospatial</h1>
          <Link href="/explore" className="text-xs text-sky-400 hover:underline">
            ← Graph explorer
          </Link>
        </div>
        <div className="flex items-center gap-3 text-xs text-slate-400">
          <span>{features.length} placed</span>
          {onLogout && (
            <button onClick={onLogout} className="text-slate-400 hover:text-slate-200">
              Log out
            </button>
          )}
        </div>
      </header>

      <div className="relative flex-1">
        {error && (
          <div className="absolute left-1/2 top-4 z-[1000] -translate-x-1/2 rounded bg-red-900/80 px-3 py-1 text-xs">
            {error}
          </div>
        )}
        {loading && (
          <div className="absolute left-1/2 top-4 z-[1000] -translate-x-1/2 text-xs text-slate-400">
            Loading map…
          </div>
        )}

        <MapContainer center={DEFAULT_CENTER} zoom={2} className="h-full w-full">
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <FitBounds points={points} />

          {features.map((f) => (
            <CircleMarker
              key={f.id}
              center={[f.lat, f.lon]}
              radius={6}
              pathOptions={{
                color: entityColor(f.type),
                fillColor: entityColor(f.type),
                fillOpacity: f.placed_via === "self" ? 0.9 : 0.5,
                weight: f.placed_via === "self" ? 2 : 1,
              }}
              eventHandlers={{ click: () => showPattern(f.id) }}
            >
              <Tooltip>{f.name}</Tooltip>
              <Popup>
                <div className="text-xs">
                  <div className="font-semibold">{f.name}</div>
                  <div className="text-slate-500">{ENTITY_LABELS[f.type]}</div>
                  {f.location_name && <div>via {f.location_name}</div>}
                  <button
                    className="mt-1 text-sky-600 underline"
                    onClick={() => showPattern(f.id)}
                  >
                    Pattern of life
                  </button>
                </div>
              </Popup>
            </CircleMarker>
          ))}

          {/* Movement track for the selected entity (#8). */}
          {track.length > 1 && (
            <Polyline positions={track} pathOptions={{ color: "#fbbf24", weight: 3, dashArray: "6 6" }} />
          )}
          {(pol?.visits ?? []).map((v, i) => (
            <CircleMarker
              key={`${pol?.entity_id}-${i}`}
              center={[v.lat, v.lon]}
              radius={9}
              pathOptions={{ color: "#fbbf24", fillColor: "#fbbf24", fillOpacity: 0.8 }}
            >
              <Tooltip permanent>{i + 1}</Tooltip>
              <Popup>
                <div className="text-xs">
                  <div className="font-semibold">{v.label}</div>
                  <div className="text-slate-500">{v.date ?? "undated"}</div>
                </div>
              </Popup>
            </CircleMarker>
          ))}
        </MapContainer>

        {/* Side panels */}
        <div className="absolute right-3 top-3 z-[1000] flex w-72 flex-col gap-3">
          {pol && (
            <div className="rounded-lg border border-slate-700 bg-slate-800/95 p-3 text-xs">
              <div className="mb-1 flex items-center justify-between">
                <span className="font-semibold text-amber-300">Pattern of life</span>
                <button className="text-slate-400 hover:text-slate-200" onClick={() => setPol(null)}>
                  ✕
                </button>
              </div>
              <div className="text-slate-300">{pol.entity_name}</div>
              <div className="text-slate-400">
                {pol.place_count} places · {pol.total_distance_km.toLocaleString()} km tracked
              </div>
              <ol className="mt-2 list-decimal space-y-1 pl-4 text-slate-300">
                {pol.visits.map((v, i) => (
                  <li key={i}>
                    {v.date ?? "—"}: {v.location_name}
                  </li>
                ))}
              </ol>
            </div>
          )}

          {pairs.length > 0 && (
            <div className="max-h-72 overflow-auto rounded-lg border border-slate-700 bg-slate-800/95 p-3 text-xs">
              <div className="mb-1 font-semibold text-teal-300">Co-location leads (#9)</div>
              <ul className="space-y-2">
                {pairs.slice(0, 12).map((p, i) => (
                  <li key={i} className="border-b border-slate-700/60 pb-1">
                    <div className="text-slate-200">
                      {p.a_name} ↔ {p.b_name}
                    </div>
                    <div className="text-slate-400">
                      @ {p.location_name} · {p.shared_visits}×
                      {p.temporally_overlapping ? " · same time" : ""}
                      {p.already_connected ? " · linked" : " · suggest edge"}
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
