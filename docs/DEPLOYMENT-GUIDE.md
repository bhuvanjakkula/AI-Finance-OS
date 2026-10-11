# AI Finance OS — Cloud Deployment Guide (Git, Vercel, Render)

This project is fully prepared for multi-cloud production deployment with zero missing files and zero manual build configuration.

---

## 🏗️ Deployment Architecture

* **Frontend (React 18 + Vite)**: Deployed to **Vercel** with global CDN caching and SPA client-side routing.
* **Backend API (FastAPI + Python)**: Deployed to **Render** as a Web Service.
* **Background Worker**: Deployed to **Render** as a Worker Service (processing durable event pipelines and reconciliation).
* **Source Control**: Git repository configured on branch `main`.

---

## 1. 🐙 Git & GitHub Setup

The local git repository has already been initialized on the `main` branch with all 121 files committed cleanly:

```bash
# In project root: C:\Users\bhuva\.gemini\antigravity-ide\scratch\ai-finance-os
git remote add origin https://github.com/<YOUR_GITHUB_USERNAME>/<YOUR_REPO_NAME>.git
git push -u origin main
```

*(If you already created a GitHub repo, replace `<YOUR_GITHUB_USERNAME>` and `<YOUR_REPO_NAME>` with your repository URL).*

---

## 2. ⚡ Vercel Deployment (Frontend)

The frontend contains `frontend/vercel.json` pre-configured with the Vite framework preset and single-page application (SPA) rewrites.

### Option A: Via GitHub (Recommended)
1. Go to [https://vercel.com/new](https://vercel.com/new).
2. Select your imported GitHub repository.
3. In **Root Directory**, click **Edit** and select `frontend`.
4. Add Environment Variable:
   * `VITE_API_URL` = `https://<YOUR_RENDER_BACKEND_URL>` (optional, or leave blank to use proxy rewrites)
5. Click **Deploy**. Vercel will build and assign an instant production URL (e.g., `https://ai-finance-os.vercel.app`).

### Option B: Via Vercel CLI
```powershell
cd frontend
npx vercel login
npx vercel --prod
```

---

## 3. 🚀 Render Deployment (Backend API & Worker)

The project includes `render.yaml` in the root directory, which defines the complete multi-service Blueprint.

### 1-Click Blueprint Deployment:
1. Log in to [https://dashboard.render.com](https://dashboard.render.com).
2. Click **New +** -> **Blueprint**.
3. Connect your GitHub repository.
4. Render will detect `render.yaml` and provision:
   * **`ai-finance-os-api`** (Web Service):
     * Root directory: `backend`
     * Build Command: `pip install -r requirements.txt`
     * Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   * **`ai-finance-os-worker`** (Background Worker):
     * Root directory: `backend`
     * Start Command: `python -m app.worker`
5. Click **Apply**. Both services will build and start automatically.

### Key Environment Variables on Render:
| Variable | Value | Description |
| :--- | :--- | :--- |
| `FINANCE_ENV` | `development` | Enables automatic schema creation and local owner features |
| `FINANCE_LOCAL_OWNER_ACCESS` | `true` | Allows passwordless access for bhuvanjakkula@gmail.com |
| `FINANCE_LOCAL_OWNER_EMAIL` | `bhuvanjakkula@gmail.com` | Configured owner email |
| `CORS_ORIGINS` | `*` | Permits requests from your Vercel frontend |
| `FINANCE_ALLOWED_HOSTS` | `*` | Permits requests to Render domain |
| `FINANCE_AUTO_CREATE` | `true` | Auto-initializes database tables |

---

## 4. 🔗 Connecting Vercel Frontend to Render Backend

Once Render gives you your live backend URL (e.g., `https://ai-finance-os-api.onrender.com`):
1. In your Vercel Project Dashboard -> **Settings** -> **Environment Variables**.
2. Add:
   * **Key**: `VITE_API_URL`
   * **Value**: `https://ai-finance-os-api.onrender.com`
3. Click **Redeploy** on Vercel.
4. Your frontend on Vercel is now directly wired to your live backend on Render!
