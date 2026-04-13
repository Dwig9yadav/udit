# 04 — Technology Stack

Core technologies used in EduRag:

- Frontend
  - React (Create React App)
  - CSS Modules / plain CSS
  - Fetch / Axios for API calls

- Backend
  - Python 3.8+ with FastAPI (or similar lightweight framework)
  - Uvicorn / Gunicorn for serving

- Data & Services
  - Supabase / Postgres for relational data and metadata
  - Vector store (Supabase vector extension) for embeddings
  - Google Gemini AI (Multimodal) for generation and embeddings
  - **Hindsight Memory Bank** for persistent user context and AI reflection

- Dev & Deployment
  - Vercel for frontend hosting
  - GitHub Actions (optional) for CI/CD

Libraries of interest
- `python-dotenv` for local env management
- `psycopg2` or `asyncpg` for DB connections
- `transformers` or embedding clients for local embedding generation (optional)
