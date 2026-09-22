# ShockProof Dashboard

React + Vite frontend for the ShockProof supply-chain resilience platform. See the
[project README](../README.md) for the full architecture, the benchmark results, and how to run
the backend this app talks to.

## Development

```bash
npm install
npm run dev      # dev server on http://localhost:5173, expects the API on http://localhost:8000
npm run build    # production build to dist/
```

## Stack

- React 19 + React Router 7, Vite 8
- Recharts for charts, `react-force-graph-2d` for the network graph
- Hand-written CSS design system in `src/index.css` (dark/light theme via CSS custom properties,
  no UI framework) — no other UI/chart libraries are installed, by design
