# 07 — API Reference

### Authentication
- `POST /api/auth/register` — Register a new user
- `POST /api/auth/login` — Login and receive JWT token
- `GET /api/auth/me` — Get current user profile (requires Bearer token)

### RAG Search
- `POST /api/rag/search` — Perform semantic search over indexed PDFs
- `POST /api/rag/upload-pdf` — Upload a new PDF (Teacher/Admin)
- `GET /api/rag/pdfs` — List all uploaded PDFs
- `GET /api/rag/summary` — Generate an AI summary for a specific PDF

### Hindsight (Memory Bank)
- `GET /api/memory/status` — Check Hindsight connection and get bank ID
- `POST /api/memory/retain` — Store a fact in the user's memory bank
- `POST /api/memory/recall` — Retrieve relevant memories for a query
- `POST /api/memory/reflect` — Generate an AI reflection/summary over the user's memory bank

### Example Request (Reflect)
```bash
curl -X POST http://localhost:8000/api/memory/reflect \
  -H "Authorization: Bearer <YOUR_JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"query":"What have I been studying today?","mission":"You are a helpful assistant."}'
```

### Authentication Architecture
EduRag uses **JWT Bearer Tokens**. All protected routes require the `Authorization: Bearer <token>` header. Tokens are issued upon successful login at `/api/auth/login`.
