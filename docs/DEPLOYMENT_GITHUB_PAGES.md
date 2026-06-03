# Deploying MatchMind Frontend to GitHub Pages

This guide covers deploying the React/Vite frontend as a static site on GitHub Pages.

> **Note:** GitHub Pages only hosts static files. The Python/FastAPI backend must be deployed separately (e.g., Railway — see `docs/DEPLOYMENT_RAILWAY.md`).

---

## Prerequisites

- GitHub repository with the MatchMind code pushed
- Node.js 18+ installed locally (for testing the build)
- Backend API deployed and accessible at a public URL

---

## Step 1: Configure the Base Path

GitHub Pages serves from `https://<username>.github.io/<repo-name>/`, so Vite needs a base path.

Edit `frontend/vite.config.ts`:

```ts
export default defineConfig({
  base: "/MatchMind/",  // Replace with your repo name
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
});
```

---

## Step 2: Set the API URL for Production

Create `frontend/.env.production`:

```env
VITE_API_URL=https://your-backend-url.up.railway.app/api/v1
```

Replace with your actual backend URL.

---

## Step 3: Handle Client-Side Routing (SPA)

GitHub Pages doesn't support SPA routing natively. The `public/404.html` file already handles this by redirecting to `index.html`.

Ensure `frontend/public/404.html` exists with a redirect script:

```html
<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>MatchMind</title>
    <script>
      // Redirect all 404s to index.html for SPA routing
      var pathSegmentsToKeep = 1; // keep /MatchMind prefix
      var l = window.location;
      l.replace(
        l.protocol + "//" + l.hostname + (l.port ? ":" + l.port : "") +
        l.pathname.split("/").slice(0, 1 + pathSegmentsToKeep).join("/") + "/?/" +
        l.pathname.slice(1).split("/").slice(pathSegmentsToKeep).join("/").replace(/&/g, "~and~") +
        (l.search ? "&" + l.search.slice(1).replace(/&/g, "~and~") : "") +
        l.hash
      );
    </script>
  </head>
  <body></body>
</html>
```

---

## Step 4: Add the GitHub Actions Workflow

Create `.github/workflows/deploy-pages.yml`:

```yaml
name: Deploy Frontend to GitHub Pages

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: "pages"
  cancel-in-progress: true

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: npm
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        working-directory: frontend
        run: npm ci

      - name: Build
        working-directory: frontend
        run: npm run build

      - name: Upload artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: frontend/dist

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
```

---

## Step 5: Enable GitHub Pages in Repository Settings

1. Go to **Settings → Pages** in your GitHub repository
2. Under **Source**, select **GitHub Actions**
3. Save

---

## Step 6: Push and Deploy

```bash
git add .
git commit -m "feat: add GitHub Pages deployment"
git push origin main
```

The workflow triggers automatically on push to `main`. Monitor progress in the **Actions** tab.

---

## Step 7: Verify

Visit `https://<username>.github.io/MatchMind/` after the workflow completes (~2 minutes).

---

## Updating the Deployment

Every push to `main` automatically rebuilds and redeploys the frontend. No manual steps needed.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Blank page | Check `base` in `vite.config.ts` matches your repo name |
| API calls fail | Verify `VITE_API_URL` in `.env.production` points to your backend |
| Routes return 404 | Ensure `public/404.html` exists with the redirect script |
| Build fails | Run `npm run build` locally in `frontend/` to debug |
| CORS errors | Add your GitHub Pages URL to `CORS_ORIGINS` env var on the backend |
