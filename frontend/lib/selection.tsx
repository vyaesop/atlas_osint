"use client";

// Shared selection / brushing store for linked views (Task 9).
//
// One source of truth for "what is the analyst looking at", shared across the
// graph explorer, the linked entity table, the map, and the timeline. Selecting
// or brushing in any view updates the others. Living in the root layout, it also
// persists the selection across client-side route changes (graph → map →
// timeline), so a lead you brush in one view is still highlighted in the next.

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

interface SelectionState {
  /** The single focused entity (drives detail panels). */
  selected: string | null;
  /** The brushed set — highlighted across every linked view. */
  brushed: Set<string>;
  /** Transient hover, for cross-view "preview" highlighting. */
  hovered: string | null;
  select: (id: string | null) => void;
  toggleBrush: (id: string) => void;
  setBrushed: (ids: Iterable<string>) => void;
  clearBrush: () => void;
  setHovered: (id: string | null) => void;
  isActive: (id: string) => boolean;
}

const SelectionContext = createContext<SelectionState | null>(null);

export function SelectionProvider({ children }: { children: ReactNode }) {
  const [selected, setSelected] = useState<string | null>(null);
  const [brushed, setBrushedState] = useState<Set<string>>(new Set());
  const [hovered, setHovered] = useState<string | null>(null);

  const select = useCallback((id: string | null) => setSelected(id), []);

  const toggleBrush = useCallback((id: string) => {
    setBrushedState((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const setBrushed = useCallback((ids: Iterable<string>) => {
    setBrushedState(new Set(ids));
  }, []);

  const clearBrush = useCallback(() => setBrushedState(new Set()), []);

  // An id is "active" (should be emphasised) when it's selected, brushed, or
  // hovered — the union every linked view highlights on.
  const isActive = useCallback(
    (id: string) => id === selected || id === hovered || brushed.has(id),
    [selected, hovered, brushed],
  );

  const value = useMemo<SelectionState>(
    () => ({
      selected, brushed, hovered,
      select, toggleBrush, setBrushed, clearBrush, setHovered, isActive,
    }),
    [selected, brushed, hovered, select, toggleBrush, setBrushed, clearBrush, isActive],
  );

  return <SelectionContext.Provider value={value}>{children}</SelectionContext.Provider>;
}

export function useSelection(): SelectionState {
  const ctx = useContext(SelectionContext);
  if (!ctx) {
    throw new Error("useSelection must be used within a <SelectionProvider>.");
  }
  return ctx;
}
