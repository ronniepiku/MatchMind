# MatchMind — Railway + PostgreSQL Deployment Guide

Complete step-by-step guide to deploy MatchMind on [Railway](https://railway.app) with a managed PostgreSQL database.

---

## Prerequisites

- A [Railway account](https://railway.app) (free tier available, Pro recommended for production)
- Git repository pushed to GitHub (Railway deploys from GitHub)
- Local development environment working (`uv run pytest` passes)

---

## Step 1: Create a Railway Project

1. Log in to [railway.app](https://railway.app)
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Authorize Railway to access your GitHub account
5. Select the **MatchMind** repository
6. Railway will detect the `Dockerfile` and `railway.toml` automatically

---

## Step 2: Provision PostgreSQL

1. In your Railway project dashboard, click **"+ New"** → **"Database"** → **"PostgreSQL"**
2. Railway provisions a PostgreSQL 16 instance with:
   - Automatic backups
   - Connection pooling via PgBouncer
   - Private networking between services
3. Click on the PostgreSQL service to see credentials
4. Note: Railway automatically exposes `DATABASE_URL` to linked services

---

## Step 3: Link Database to App Service

1. Click on your **MatchMind app service** (the deployed container)
2. Go to **"Variables"** tab
3. Click **"Add Reference Variable"**
4. Select `DATABASE_URL` from the PostgreSQL service
5. Railway will inject this at runtime — no manual URL copying needed

---

## Step 4: Configure Environment Variables

In the app service **Variables** tab, add:

| Variable | Value | Required |
|----------|-------|----------|
| `DATABASE_URL` | *(auto-linked from PostgreSQL)* | Yes |
| `CORS_ORIGINS` | `https://your-frontend-domain.com,http://localhost:5173` | Yes |
| `API_HOST` | `0.0.0.0` | Yes |
| `LOG_LEVEL` | `INFO` | Recommended |
| `DATA_QUALITY_STRICT` | `false` | Optional |
| `CACHE_TTL_SECONDS` | `3600` | Optional |

> **Note**: Railway automatically sets `PORT`. The app reads `$PORT` from the environment.

> **Security**: Never set `POSTGRES_PASSWORD` directly — use the linked `DATABASE_URL` instead.

---

## Step 5: Deploy

Railway deploys automatically on every push to your default branch.

### First Deployment

1. Push your code to GitHub:
   ```bash
   git add -A
   git commit -m "feat: v0.5.0 — production deployment"
   git push origin main
   ```
2. Railway detects the push and builds the Docker image
3. On startup, the container:
   - Runs `alembic upgrade head` (creates all tables)
   - Starts `uvicorn` on `$PORT`
4. Monitor the build logs in Railway dashboard → **Deployments** tab

### Verify Deployment

```bash
# Replace with your Railway-generated URL
curl https://matchmind-production.up.railway.app/api/v1/health
# → {"status":"healthy","version":"0.5.0"}

# Readiness check (verifies DB connectivity)
curl https://matchmind-production.up.railway.app/api/v1/ready
# → {"status":"ready","database":"connected"}

# OpenAPI docs
open https://matchmind-production.up.railway.app/docs
```

---

## Step 6: Initialize the Database

After the first successful deployment, ingest your initial dataset:

### Option A: Railway Shell (recommended for small datasets)

1. In Railway dashboard, click your app service
2. Click **"Shell"** tab (or use `railway shell` CLI)
3. Run:
   ```bash
   # Ingest a small dataset for verification
   uv run fb-ingest --competition-id 43 --season-id 106 --max-matches 10
   
   # Or use the orchestrator for multiple competitions
   uv run python -m football_analytics.ingest_orchestrator --register \
       --competition 43 --season 106 --name "World Cup 2022"
   uv run python -m football_analytics.ingest_orchestrator --sync-all
   ```

### Option B: Local Machine Pointing to Railway DB

1. Get your `DATABASE_URL` from Railway PostgreSQL service settings
2. Set it locally:
   ```bash
   export DATABASE_URL="postgresql://..."
   uv run fb-ingest --competition-id 43 --season-id 106
   ```

### Option C: Scheduled Cron Job (production)

Add a Railway **Cron Service** for automatic daily sync:
1. Click **"+ New"** → **"Cron Job"**
2. Set schedule: `0 4 * * *` (daily at 4 AM UTC)
3. Command: `uv run python -m football_analytics.ingest_orchestrator --sync-all`
4. Link the same `DATABASE_URL` variable

---

## Step 7: Deploy the Frontend

The React frontend can be deployed to:

### Option A: Railway Static Site

1. In the same Railway project, click **"+ New"** → **"GitHub Repo"**
2. Set the **Root Directory** to `frontend/`
3. Set **Build Command**: `npm run build`
4. Set **Output Directory**: `dist`
5. Add variable: `VITE_API_URL=https://matchmind-production.up.railway.app/api/v1`

### Option B: Vercel/Netlify (recommended for frontend)

```bash
cd frontend
npm run build
# Deploy dist/ to Vercel, Netlify, or Cloudflare Pages
```

Set the environment variable during build:
```
VITE_API_URL=https://matchmind-production.up.railway.app/api/v1
```

### Option C: GitHub Pages

Already configured via `.github/workflows/deploy-frontend.yml`. Update the `VITE_API_URL` in the workflow file.

---

## Step 8: Custom Domain (Optional)

1. In Railway, click your app service → **Settings** → **Networking**
2. Click **"Generate Domain"** for a `*.up.railway.app` URL
3. Or add a **Custom Domain**:
   - Add `api.matchmind.io` (or your domain)
   - Railway provides a CNAME target
   - Add the CNAME record in your DNS provider
   - Railway auto-provisions SSL via Let's Encrypt

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      Railway Project                         │
├─────────────────────┬───────────────────────────────────────┤
│                     │                                       │
│  ┌───────────────┐  │  ┌─────────────────────────────────┐  │
│  │  PostgreSQL   │  │  │      MatchMind API              │  │
│  │  (Managed)    │◄─┼──│  Docker + uvicorn               │  │
│  │               │  │  │  Auto-migrations on startup     │  │
│  │  • Backups    │  │  │  Health checks: /api/v1/health  │  │
│  │  • Pooling    │  │  │  OpenAPI: /docs                 │  │
│  └───────────────┘  │  └──────────────┬──────────────────┘  │
│                     │                 │                      │
├─────────────────────┴─────────────────┼─────────────────────┤
│                                       │                      │
│  ┌─────────────────────────────────┐  │  (Optional)         │
│  │  Cron Service                   │  │  ┌───────────────┐  │
│  │  Daily ingestion sync           │  │  │  Frontend     │  │
│  │  0 4 * * * → --sync-all        │  │  │  (Static)     │  │
│  └─────────────────────────────────┘  │  └───────────────┘  │
└───────────────────────────────────────┴─────────────────────┘
                                        │
                                        ▼
                              ┌─────────────────┐
                              │  React Frontend │
                              │  (Vercel/GH     │
                              │   Pages/Railway)│
                              └─────────────────┘
```

---

## Monitoring & Observability

### Railway Built-in

- **Metrics**: CPU, memory, network (Railway dashboard → Metrics tab)
- **Logs**: Real-time log streaming (Railway dashboard → Logs tab)
- **Alerts**: Set up Railway notifications for deploy failures

### Application-Level

```bash
# Check cache performance
curl https://your-app.up.railway.app/api/v1/cache/stats

# Validate data quality for a match
curl https://your-app.up.railway.app/api/v1/system/validation/3869685

# Database health
curl https://your-app.up.railway.app/api/v1/system/health/db
```

---

## Scaling

### Vertical (Railway Pro)

- Increase RAM/CPU via Railway service settings
- PostgreSQL can be scaled independently

### Horizontal

- Railway supports **replicas** on Pro plan
- API is stateless — safe to run multiple instances
- PostgreSQL handles concurrent connections via pooling (pool_size=5, max_overflow=10)

### Performance Tuning

| Setting | Default | Production |
|---------|---------|-----------|
| `pool_size` | 5 | 10-20 |
| `max_overflow` | 10 | 20-30 |
| `CACHE_TTL_SECONDS` | 3600 | 1800 |
| Workers (uvicorn) | 1 | 2-4 (`--workers`) |

To use multiple workers, update the start command in `railway.toml`:
```toml
startCommand = "uv run alembic upgrade head 2>/dev/null; uv run uvicorn football_analytics.api:app --host 0.0.0.0 --port $PORT --workers 4"
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Build fails | Check Railway build logs; ensure `pyproject.toml` is valid |
| DB connection refused | Verify `DATABASE_URL` is linked, not manually set |
| Migrations fail | Run `railway shell` then `uv run alembic upgrade head` manually |
| CORS errors | Add frontend origin to `CORS_ORIGINS` env var |
| Health check fails | Ensure `PORT` env var is not manually overridden |
| Slow cold starts | First request after deploy may take 5-10s (container boot) |
| Out of memory | Increase service limits or reduce `pool_size` |

---

## Cost Estimate (Railway Pro)

| Component | Usage | ~Monthly Cost |
|-----------|-------|---------------|
| API Service | 512MB RAM, always-on | $5-10 |
| PostgreSQL | 1GB storage, shared | $5-7 |
| Cron Service | Runs 5 min/day | $1-2 |
| **Total** | | **~$11-19/month** |

Free tier: 500 hours/month execution + 1GB DB (sufficient for development/demos).

---

## Production Checklist

- [ ] PostgreSQL provisioned and linked via `DATABASE_URL`
- [ ] `CORS_ORIGINS` set to your frontend domain(s)
- [ ] First deployment successful (check `/api/v1/health`)
- [ ] Initial data ingested (at least one competition)
- [ ] Frontend deployed and pointing to Railway API URL
- [ ] Custom domain configured (optional)
- [ ] Cron job set up for daily data sync (optional)
- [ ] Railway notifications enabled for deploy failures
- [ ] Backup schedule verified on PostgreSQL service
