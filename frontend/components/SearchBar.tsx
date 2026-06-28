"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { entityColor, ENTITY_LABELS } from "@/lib/colors";
import type { Suggestion } from "@/lib/types";

interface Props {
  onSelect: (entityId: string) => void;
}

export function SearchBar({ onSelect }: Props) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Suggestion[]>([]);
  const [open, setOpen] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    if (q.trim().length < 2) {
      setResults([]);
      return;
    }
    // Debounced suggest; falls back to full search for richer matches.
    timer.current = setTimeout(async () => {
      try {
        const hits = await api.search(q, { semantic: true });
        setResults(hits.map((h) => ({ id: h.id, type: h.type, name: h.name, score: h.score })));
        setOpen(true);
      } catch {
        setResults([]);
      }
    }, 200);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [q]);

  function choose(id: string) {
    onSelect(id);
    setOpen(false);
    setQ("");
    setResults([]);
  }

  return (
    <div className="relative w-96">
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onFocus={() => results.length && setOpen(true)}
        placeholder="Search people, orgs, companies… (fuzzy + semantic)"
        className="w-full rounded-md bg-panel px-3 py-2 text-sm ring-1 ring-edge outline-none focus:ring-blue-500"
      />
      {open && results.length > 0 && (
        <ul className="absolute z-20 mt-1 max-h-80 w-full overflow-auto rounded-md bg-panel py-1 text-sm shadow-2xl ring-1 ring-edge">
          {results.map((r) => (
            <li key={r.id}>
              <button
                onClick={() => choose(r.id)}
                className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-ink"
              >
                <span
                  className="rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase"
                  style={{ background: `${entityColor(r.type)}22`, color: entityColor(r.type) }}
                >
                  {ENTITY_LABELS[r.type]}
                </span>
                <span className="truncate">{r.name}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
