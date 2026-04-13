# 08 — Deployment

This file explains how to deploy EduRag to Vercel as a unified application.

## 🚀 Unified Vercel Deployment

EduRag is designed to deploy to Vercel as a single project using a React frontend and a FastAPI backend (running as a Python Serverless Function).

### 1. Repository Setup
Ensure your GitHub repository has the following structure at the root:
- `requirements.txt` — **CRITICAL**: Must contain all backend dependencies (like `hindsight-client`, `fastapi`, etc.) for Vercel to install them.
- `api/index.py` — The entry point for the Vercel Python runtime.
- `vercel.json` — Configuration for rewrites and functions.

### 2. Vercel Project Configuration
- **Framework Preset**: Create React App (or Other)
- **Build Command**: `npm run build`
- **Output Directory**: `build`

### 3. Environment Variables
Add these in the Vercel Dashboard (Settings -> Environment Variables):

| Category | Variables |
|----------|-----------|
| **Supabase** | `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_ROLE_KEY` |
| **Gemini AI** | `GEMINI_API_KEY` |
| **JWT Auth** | `JWT_SECRET`, `JWT_ALGORITHM` |
| **Hindsight** | `HINDSIGHT_ENABLED`, `HINDSIGHT_API_KEY`, `HINDSIGHT_BASE_URL` |

### 4. Rewrites (vercel.json)
The `vercel.json` file handles routing between the static frontend and the serverless backend:
```json
{
  "rewrites": [
    { "source": "/api/(.*)", "destination": "/api/index.py" },
    { "source": "/(.*)", "destination": "/index.html" }
  ]
}
```

## 🛠️ Monitoring
- **Build Logs**: Check Vercel build logs for `npm install` or `pip install` failures.
- **Runtime Logs**: View FastAPI logs (stdout/stderr) in the Vercel "Functions" tab to debug integration issues or Hindsight connection errors.
