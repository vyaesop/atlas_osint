# Atlas Frontend (Phase 2)

Next.js (App Router) + TypeScript + TailwindCSS + React Flow. Provides the
interactive graph explorer and search experience over the Atlas backend.

## Develop

```bash
cp .env.local.example .env.local   # set BACKEND_URL if not localhost:8000
npm install
npm run dev                        # http://localhost:3000
```

`next.config.mjs` proxies `/api/*` to the backend, so the browser only talks to
the same origin (no CORS in dev). Sign in at `/login` (seed an admin on the
backend first), then you land on `/explore`.

## Scripts

| Command            | Purpose                          |
|--------------------|----------------------------------|
| `npm run dev`      | Dev server with HMR              |
| `npm run build`    | Production build                 |
| `npm run start`    | Serve the production build       |
| `npm run typecheck`| `tsc --noEmit`                   |
| `npm run lint`     | `next lint`                      |

## Graph Explorer

- **Search & focus** — type-ahead search (full-text + fuzzy + semantic) brings
  any entity onto the canvas.
- **Expand / collapse** — double-click a node (or use the detail panel) to load
  its 1-hop neighborhood from `/graph/entities/{id}/neighbors`; double-click an
  expanded node to collapse orphaned neighbors.
- **Color-coded types** + legend, **relationship labels** on edges, and a
  per-node confidence bar.
- **Layouts** — Force-directed (d3-force), Hierarchical (dagre), and Timeline
  (positioned by entity/relationship dates). Switch live from the toolbar.
- **Detail panel** — entity properties, aliases, and the live confidence
  breakdown (supporting/contradicting counts, contradiction warning).

## Structure

```
frontend/
├── app/                # routes: /, /login, /explore
├── components/         # GraphExplorer, EntityNode, SearchBar, DetailPanel, Toolbar
└── lib/                # api client, auth, types, colors, layout engine
```
