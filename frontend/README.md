# MatchMind Frontend

A React + TypeScript performance analytics dashboard for Premier League football analysis. Deployed on GitHub Pages, connected to a FastAPI backend.

## Tech Stack

- **React 19** + **TypeScript 6** — Type-safe UI
- **Vite 8** — Fast builds with code splitting
- **Tailwind CSS 4** — Utility-first styling with dark/light theming
- **TanStack Query** — Server state management with caching
- **Recharts** — Standard chart components (line, bar, pie)
- **D3.js** — Custom pitch visualisations (shot maps, passing networks, heatmaps)
- **Lucide React** — Icon system
- **React Router v7** — Client-side routing

## Architecture

```
src/
├── api/           # API client, endpoints, TypeScript types
├── components/
│   ├── charts/    # Data visualisation components
│   ├── layout/    # App shell (Sidebar, Header, Layout)
│   ├── pitch/     # Football pitch SVG component (D3)
│   └── shared/    # Reusable UI components (Card, Table, etc.)
├── hooks/         # Custom React hooks (theme)
├── pages/         # Route-level page components
├── styles/        # Global CSS with theme variables
└── utils/         # Formatting helpers
```

## Pages

| Page | Description |
|------|-------------|
| **Overview** | Platform status and navigation |
| **Opponent Profile** | Pre-match scouting: attack patterns, defensive shape, key players |
| **Player Performance** | Season summary, rolling form, radar chart, squad comparison |
| **Team Scorecard** | KPIs, possession profile, pressing intensity, transitions, set-pieces |
| **Match Analysis** | Shot map, passing network, xG timeline, pressure heatmap |
| **Player Comparison** | Cosine similarity search across normalised per-90 vectors |
| **Simulation** | Monte Carlo match outcome simulation (10,000 iterations) |

## Development

```bash
# Install dependencies
npm install

# Start dev server (connects to local FastAPI at localhost:8080)
npm run dev

# Type check
npm run type-check

# Production build
npm run build

# Preview production build
npm run preview
```

## Environment Variables

Copy `.env.example` to `.env`:

```
VITE_API_URL=http://localhost:8080/api/v1
```

For production, set this to your deployed FastAPI URL.

## Deployment

Deployed automatically via GitHub Actions on push to `main` (when `frontend/` changes). The workflow:

1. Installs dependencies
2. Runs TypeScript type check
3. Builds production bundle
4. Deploys to GitHub Pages

## Theme System

The dashboard supports dark (default) and light themes:

- **Dark mode** — Default for analyst workstation usage
- **Light mode** — Switchable for presentations and report exports

Theme preference is persisted in localStorage and respects system preference on first visit.

## API Integration

All data fetches use TanStack Query with:
- 5-minute stale time for efficient caching
- Automatic retry (2 attempts)
- No refetch on window focus (analyst usage pattern)

The API client is configured in `src/api/client.ts` and expects the FastAPI backend to be running at the URL specified in `VITE_API_URL`.
